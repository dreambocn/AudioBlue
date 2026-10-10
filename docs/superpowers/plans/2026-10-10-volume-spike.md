# 音量控制可行性 Spike 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证能否把一个已连接的 A2DP Sink 蓝牙设备关联到它的 Core Audio 渲染端点，从而用 `IAudioEndpointVolume` 读写音量；产出书面结论供后续实现决策。

**Architecture:** 一个独立的控制台程序 `tools/volume-spike/`，不依赖 AudioBule 主工程，不打包。它枚举 A2DP 设备 → 读取 `System_DeviceEndpointId` → 用 `IMMDeviceEnumerator` 取端点 → 读/写音量 → 注册回调观察变化。每一步打印结构化输出。

**Tech Stack:** C++17 / C++WinRT（`Windows.Media.Audio`、`Windows.Devices.Enumeration`）/ Core Audio COM（`mmdeviceapi.h`、`endpointvolume.h`）/ WIL / MSVC **v145**（Visual Studio 2026，编译器 14.51.36231）。

**Spec:** `docs/superpowers/specs/2026-10-10-audiobule-design.md`（§5 音量控制 Spike）

## Global Constraints

- 这些约束适用于本计划的每一个任务：
  - **前置环境**（已实测通过）：Visual Studio Community 2026（18.10.12224.181），安装于 `D:\Applications\Microsoft Visual Studio\18\Community`。
  - **PlatformToolset 为 `v145`**，不是 `v180`。`v180` 是 MSBuild 目录名与工程版本号，写进 `<PlatformToolset>` 会报 `MSB8020 找不到 v180 的生成工具`。实际可用工具集需以 `MSBuild\Microsoft\VC\v180\PlatformToolsets\x64\PlatformToolsets\` 下的目录名为准。
  - Windows SDK 为 **10.0.26100.0**，安装于**非默认路径** `D:\Windows Kits\10`。在 `<WindowsTargetPlatformVersion>` 中显式写 `10.0.26100.0`，不要留 `10.0`。
  - NuGet 缓存已有以下版本，可离线还原：`Microsoft.WindowsAppSDK` 2.2.0、`Microsoft.WindowsAppSDK.WinUI` 2.2.1、`Microsoft.Windows.CppWinRT` 3.0.260520.1、`Microsoft.Windows.ImplementationLibrary` 1.0.260126.7。
  - **WIL 等头文件一律走 NuGet `PackageReference`，不要手写 `/I` 路径**。本机 MSVC 与 Windows SDK 路径含空格，手写 `/I` 在 PowerShell 下无法正确传给 cl.exe；且 NuGet 还原是唯一可靠的路径来源。
  - 构建命令：`msbuild <proj> -t:Restore` 后再 `-p:Configuration=Release -p:Platform=x64`。C++/WinRT 项目必须先还原，否则头文件路径不生效。
  - 默认输出目录是 `$(SolutionDir)\x64\Release\`。Spike 有独立 sln 且位于 `tools\volume-spike\`，故产物在 `tools\volume-spike\bin\volume-spike.exe`。在 `<Import Microsoft.Cpp.targets>` 之前显式设置 `<IntDir>` 与 `<OutDir>` 可避免多 sln 场景下的产物路径歧义。
  - 最低系统版本：Windows 10 2004（build 19041）。A2DP Sink 能力由 `AudioPlaybackConnection` 提供，更低版本必须优雅退出。
  - 本 Spike 只做验证，代码不进入 `AudioBule.Core`。 Spike 全部代码保留在 `tools/volume-spike/` 作为技术决策证据。
  - C++ 标准：C++17 或更高（`/std:c++latest`）。
  - 编译警告级别 W4，`/WX` 视为错误。
  - 目标架构 x64。Core Audio COM 接口与架构无关，但设备关联逻辑需要在真实硬件上验证。
  - 不引入除 `wil`、`cppwinrt` 之外的第三方依赖。
  - 每个 COM 接口指针必须释放；`wil::com_ptr` 优于裸 `Release()`。
  - 所有 HRESULT 必须检查，不得忽略。

## Review Focus

以下输入/条件最可能咬到实际使用的人，但没有任何任务的测试会覆盖它们。每一条都已在对应任务中补上验证步骤：

1. **用户在未连接任何设备时运行 Spike** —— 应打印「无设备」并正常退出码返回，而非崩溃或挂起。Task 4。
2. **Windows 版本低于 2004** —— `AudioPlaybackConnection` 类型不存在，`winrt::Windows::Media::Audio` 命名空间的头文件仍能编译但运行期调用失败。必须用 `ApiInformation::IsTypePresent` 先检测再调用。Task 2。
3. **设备的 `System_DeviceEndpointId` 属性不存在**（部分旧驱动或非蓝牙设备） —— `Properties.Lookup` 返回空值，必须跳过而非解引用空 `IInspectable`。Task 3。
4. **A2DP 已连接但端点尚未就绪** —— 端点可能延迟数秒才出现在枚举结果中，立即查询会得到 `E_NOTFOUND`。Task 3 需要重试逻辑。
5. **`IAudioEndpointVolumeCallback::OnNotify` 在非 STA 线程被调用** —— COM 回调线程模型不匹配会导致 UI 冻结或跨 apartment 违规。Task 5 必须验证回调线程。

---

## File Structure

```
tools/volume-spike/
├─ volume-spike.vcxproj      # 控制台应用工程
├─ pch.h                     # 预编译头：Win32 + WIL + C++/WinRT 音频/枚举头
├─ pch.cpp                   # 预编译头实现
├─ main.cpp                  # 入口：串联下面五个步骤
├─ Step1_Enumerate.h/.cpp    # 枚举 A2DP 设备
├─ Step2_EndpointId.h/.cpp   # 读取 System_DeviceEndpointId
├─ Step3_FindEndpoint.h/.cpp # IMMDeviceEnumerator 取端点（含重试）
├─ Step4_Volume.h/.cpp       # 读/写音量
└─ Step5_Notify.h           # 音量变化回调（方法内联，无 cpp）
```

每个 Step 一个头/源对，职责单一，输出清晰，便于单独删除不需要的步骤。`main.cpp` 只做串联与报告，不含具体逻辑。

---

### Task 1: Spike 工程骨架

**Files:**
- Create: `tools/volume-spike/volume-spike.vcxproj`
- Create: `tools/volume-spike/pch.h`
- Create: `tools/volume-spike/pch.cpp`
- Create: `tools/volume-spike/main.cpp`
- Create: `tools/volume-spike/targetver.h`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces: 可编译运行的 x64 控制台工程。`main.cpp` 的 `wmain()` 骨架，后续任务往里插入步骤调用。

- [ ] **Step 1: 创建 targetver.h**

```cpp
#pragma once

// AudioBule 项目统一目标版本：Windows 10 2004 (build 19041)
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define NTDDI_VERSION NTDDI_WIN10_RS3
```

- [ ] **Step 2: 创建 pch.h**

```cpp
#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>
#include <mmdeviceapi.h>
#include <endpointvolume.h>
#include <functiondiscoverykeysapi.h>

#include <cstdio>
#include <string>
#include <vector>
#include <wil/common.h>
#include <wil/result.h>

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Metadata.h>
#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Media.Audio.h>
```

注意：`#undef GetCurrentTime` 必须在包含 C++/WinRT 头之前，因为 `Windows.Foundation` 会定义它，与 `windows.h` 的宏冲突。

- [ ] **Step 3: 修正 pch.h 的宏冲突**

在 `#include <winrt/base.h>` 之前插入：

```cpp
// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，
// 与 windows.h 中的声明冲突，导致 C4002 错误
#undef GetCurrentTime
```

- [ ] **Step 4: 创建 pch.cpp**

```cpp
#include "pch.h"
```

- [ ] **Step 5: 创建 main.cpp 骨架**

```cpp
#include "pch.h"

int wmain()
{
    // 后续任务填充具体流程
    return 0;
}
```

Task 1 不预先声明尚不存在的函数 —— 各任务的真实函数签名见各自的头文件，`main.cpp` 在那些任务中相应 include。

- [ ] **Step 6: 创建 volume-spike.vcxproj**

这是一个最小的 vcxproj，只需要 x64|Debug 和 x64|Release 两个配置：

```xml
<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Debug|x64">
      <Configuration>Debug</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <VCProjectVersion>18.0</VCProjectVersion>
    <Keyword>Win32Proj</Keyword>
    <ProjectGuid>{7A1E4C2B-9D3F-4E58-8B71-2C6A0D4F3E19}</ProjectGuid>
    <RootNamespace>volume_spike</RootNamespace>
    <WindowsTargetPlatformVersion>10.0.26100.0</WindowsTargetPlatformVersion>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <PlatformToolset>v145</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <PlatformToolset>v145</PlatformToolset>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings">
  </ImportGroup>
  <ImportGroup Label="Shared">
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <TargetName>volume-spike</TargetName>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <TargetName>volume-spike</TargetName>
  </PropertyGroup>
  <PropertyGroup>
    <IntDir>$(ProjectDir)obj\</IntDir>
    <OutDir>$(ProjectDir)bin\</OutDir>
  </PropertyGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <ClCompile>
      <WarningLevel>Level4</WarningLevel>
      <SDLCheck>true</SDLCheck>
      <ConformanceMode>true</ConformanceMode>
      <PrecompiledHeader>Use</PrecompiledHeader>
      <PrecompiledHeaderFile>pch.h</PrecompiledHeaderFile>
      <TreatWarningAsError>true</TreatWarningAsError>
      <LanguageStandard>stdcpplatest</LanguageStandard>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
    </Link>
  </ItemDefinitionGroup>
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <WarningLevel>Level4</WarningLevel>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <SDLCheck>true</SDLCheck>
      <ConformanceMode>true</ConformanceMode>
      <PrecompiledHeader>Use</PrecompiledHeader>
      <PrecompiledHeaderFile>pch.h</PrecompiledHeaderFile>
      <TreatWarningAsError>true</TreatWarningAsError>
      <LanguageStandard>stdcpplatest</LanguageStandard>
      <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <EnableCOMDATFolding>true</EnableCOMDATFolding>
      <OptimizeReferences>true</OptimizeReferences>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClInclude Include="pch.h" />
    <ClInclude Include="targetver.h" />
  </ItemGroup>
  <ItemGroup>
    <ClCompile Include="main.cpp" />
    <ClCompile Include="pch.cpp">
      <PrecompiledHeader>Create</PrecompiledHeader>
    </ClCompile>
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Windows.ImplementationLibrary" Version="1.0.260126.7" />
    <PackageReference Include="Microsoft.Windows.CppWinRT" Version="3.0.260520.1" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
</Project>
```

- [ ] **Step 7: 还原 NuGet 包**

C++/WinRT 项目必须先还原，否则 NuGet 提供的头文件路径不生效，编译会以 `无法打开包括文件: "wil/common.h"` 失败。

Run:
```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    tools\volume-spike\volume-spike.vcxproj -t:Restore `
    -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: `已还原 ...volume-spike.vcxproj`。本机 NuGet 缓存已有 WIL 1.0.260126.7 与 C++/WinRT 3.0.260520.1，无需联网。

**msbuild 不在 PATH 上**，必须用完整路径调用。也可先执行一次：

```powershell
$env:Path += ";D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin"
```

- [ ] **Step 8: 验证编译通过**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64 /t:ClCompile -v:minimal -nologo
```

Expected: 编译 `pch.cpp` 与 `main.cpp` 成功，无警告无错误。

**只编译不链接**：此时工程文件里还没有 Step 各源文件，链接阶段会因缺少 `main` 之外的符号而失败。`/t:ClCompile` 只跑编译阶段。完整的链接验证在 Task 2 Step 5 进行。

- [ ] **Step 9: 把工程加进解决方案**

Spike 工程刻意**不**加入 `AudioBule.sln`，避免污染主构建。它需要独立 sln（`AudioBule.sln` 属于计划一的 Task 1，届时尚不存在）：

```powershell
cd tools\volume-spike
dotnet new sln --name volume-spike
dotnet sln volume-spike.sln add volume-spike.vcxproj
```

Expected: 生成 `tools/volume-spike/volume-spike.sln`。

- [ ] **Step 10: 提交**

```bash
git add tools/volume-spike
git commit -m "build: add volume control feasibility spike project"
```

---

### Task 2: 系统能力检测与设备枚举

**Files:**
- Create: `tools/volume-spike/Step1_Enumerate.h`
- Create: `tools/volume-spike/Step1_Enumerate.cpp`
- Modify: `tools/volume-spike/main.cpp`
- Modify: `tools/volume-spike/pch.h`（补 `winrt/Windows.Foundation.Collections.h`）

**Interfaces:**
- Consumes: Task 1 的 `pch.h`
- Produces:
  - `struct A2dpDeviceInfo { std::wstring id; std::wstring name; };`
  - `std::vector<A2dpDeviceInfo> EnumerateA2dpDevices();` —— 返回枚举到的设备；系统不支持时返回空并打印原因
  - `bool IsA2dpSinkSupported();` —— 供 `main` 与未来主工程复用的检测逻辑

- [ ] **Step 1: 先写检测逻辑的头文件**

`Step1_Enumerate.h`：

```cpp
#pragma once

#include <string>
#include <vector>

struct A2dpDeviceInfo
{
    std::wstring id;
    std::wstring name;
};

// 检测系统是否支持 A2DP Sink（Windows 10 2004+）
bool IsA2dpSinkSupported();

// 枚举已配对的 A2DP Sink 设备。系统不支持或无设备时返回空向量。
std::vector<A2dpDeviceInfo> EnumerateA2dpDevices();
```

- [ ] **Step 2: 运行验证 —— 先确认缺少实现**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64 /t:ClCompile
```
Expected: 编译成功（只有声明还未被调用，不报错）。这一步只是确认头文件本身语法正确。

- [ ] **Step 3: 实现检测与枚举**

`Step1_Enumerate.cpp`：

```cpp
#include "pch.h"
#include "Step1_Enumerate.h"

using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation::Metadata;
using namespace winrt::Windows::Media::Audio;

bool IsA2dpSinkSupported()
{
    try
    {
        return ApiInformation::IsTypePresent(winrt::name_of<AudioPlaybackConnection>());
    }
    catch (winrt::hresult_error const&)
    {
        return false;
    }
}

std::vector<A2dpDeviceInfo> EnumerateA2dpDevices()
{
    std::vector<A2dpDeviceInfo> result;

    if (!IsA2dpSinkSupported())
    {
        wprintf(L"[SKIP] 系统不支持 A2DP Sink（需要 Windows 10 2004 / build 19041 及以上）\n");
        return result;
    }

    auto selector = AudioPlaybackConnection::GetDeviceSelector();

    DeviceInformationCollection devices = nullptr;
    try
    {
        // 同步阻塞等待 —— Spike 是控制台程序，阻塞可接受且避免协程复杂度
        devices = DeviceInformation::FindAllAsync(selector).get();
    }
    catch (winrt::hresult_error const& e)
    {
        wprintf(L"[FAIL] 枚举设备失败: %s (0x%08X)\n", e.message().c_str(), static_cast<uint32_t>(e.code()));
        return result;
    }

    if (devices.Size() == 0)
    {
        wprintf(L"[INFO] 未找到已配对的 A2DP 设备。请先在系统设置中配对蓝牙设备。\n");
        return result;
    }

    for (const auto& device : devices)
    {
        A2dpDeviceInfo info;
        info.id = std::wstring(device.Id());
        info.name = device.Name().empty() ? L"(未命名)" : std::wstring(device.Name());
        wprintf(L"[OK]   设备: %s\n       Id : %s\n", info.name.c_str(), info.id.c_str());
        result.push_back(std::move(info));
    }

    wprintf(L"[OK] 共枚举到 %zu 台设备\n", result.size());
    return result;
}
```

- [ ] **Step 4: 在 main 中调用**

`main.cpp`：

```cpp
#include "pch.h"
#include "Step1_Enumerate.h"

int wmain()
{
    wprintf(L"=== A2DP 音量控制可行性 Spike ===\n\n");

    if (!IsA2dpSinkSupported())
    {
        wprintf(L"[结论] 系统不支持 A2DP Sink，无法继续验证。\n");
        return 1;
    }

    wprintf(L"[1/5] 枚举 A2DP 设备...\n");
    auto devices = EnumerateA2dpDevices();
    if (devices.empty())
    {
        wprintf(L"[结论] 没有可用设备，无法验证。请配对设备后重试。\n");
        return 2;
    }

    // 后续步骤在此插入

    return 0;
}
```

- [ ] **Step 5: 编译并链接**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64
```
Expected: 编译链接成功，生成 `volume-spike.exe`。

- [ ] **Step 6: 运行验证 —— 未连接设备的边界情况**

Run:
```powershell
tools\volume-spike\bin\volume-spike.exe
```

Expected（未配对设备时）:
```
=== A2DP 音量控制可行性 Spike ===

[1/5] 枚举 A2DP 设备...
[INFO] 未找到已配对的 A2DP 设备。请先在系统设置中配对蓝牙设备。
[结论] 没有可用设备，无法验证。请配对设备后重试。
```
退出码 `2`。这验证了 Review Focus 第 1 条 —— 不崩溃、不挂起。

- [ ] **Step 7: 提交**

```bash
git add tools/volume-spike
git commit -m "feat: add A2DP device enumeration with OS support detection"
```

---

### Task 3: 设备到音频端点的关联（核心验证）

这是整个 Spike 的关键 —— 它验证 Review Focus 第 3、4 条。

**Files:**
- Create: `tools/volume-spike/Step2_EndpointId.h`
- Create: `tools/volume-spike/Step2_EndpointId.cpp`
- Modify: `tools/volume-spike/main.cpp`

**Interfaces:**
- Consumes: Task 2 的 `A2dpDeviceInfo`、`EnumerateA2dpDevices()`
- Produces:
  - `std::vector<std::wstring> GetEndpointIdsForDevices(const std::vector<A2dpDeviceInfo>&);` —— 返回每台设备对应的音频端点 ID；无法获取的设备被跳过并记录

- [ ] **Step 1: 写头文件**

`Step2_EndpointId.h`：

```cpp
#pragma once

#include "Step1_Enumerate.h"
#include <string>
#include <vector>

// 读取每台设备的 System_DeviceEndpointId 属性。
// 属性缺失或非字符串的设备会被跳过（Review Focus 第 3 条）。
std::vector<std::wstring> GetEndpointIdsForDevices(const std::vector<A2dpDeviceInfo>& devices);
```

- [ ] **Step 2: 实现属性读取**

`Step2_EndpointId.cpp`：

```cpp
#include "pch.h"
#include "Step2_EndpointId.h"

using namespace winrt::Windows::Devices::Enumeration;

std::vector<std::wstring> GetEndpointIdsForDevices(const std::vector<A2dpDeviceInfo>& devices)
{
    std::vector<std::wstring> endpointIds;

    for (const auto& device : devices)
    {
        // 用 device.Id 重新取一次，拿到完整的 Properties 集合
        DeviceInformation info = nullptr;
        try
        {
            info = DeviceInformation::CreateFromIdAsync(device.id).get();
        }
        catch (winrt::hresult_error const& e)
        {
            wprintf(L"[SKIP] 无法重新获取设备 %s: %s (0x%08X)\n",
                device.name.c_str(), e.message().c_str(), static_cast<uint32_t>(e.code()));
            continue;
        }

        auto properties = info.Properties();

        // Lookup 返回可能为 nullptr —— 属性不存在时必须跳过而非解引用
        if (!properties.HasKey(L"System_DeviceEndpointId"))
        {
            wprintf(L"[SKIP] 设备 %s 没有 System_DeviceEndpointId 属性\n", device.name.c_str());
            continue;
        }

        auto value = properties.Lookup(L"System_DeviceEndpointId");
        if (!value || value.ValueType() != PropertyType::String)
        {
            wprintf(L"[SKIP] 设备 %s 的 System_DeviceEndpointId 不是字符串\n", device.name.c_str());
            continue;
        }

        auto endpointId = std::wstring(value.GetString());
        wprintf(L"[OK]   %s -> 端点 %s\n", device.name.c_str(), endpointId.c_str());
        endpointIds.push_back(endpointId);
    }

    return endpointIds;
}
```

- [ ] **Step 3: 在 main 中调用**

在 `main.cpp` 的 `if (devices.empty())` 之后插入：

```cpp
    wprintf(L"\n[2/5] 读取设备音频端点 ID...\n");
    auto endpointIds = GetEndpointIdsForDevices(devices);
    if (endpointIds.empty())
    {
        wprintf(L"[结论] 无法从任何设备获取音频端点 ID。\n");
        wprintf(L"        音量控制方案不可行 —— AudioPlaybackConnection 与 Core Audio 端点无可用关联。\n");
        return 3;
    }
    wprintf(L"[OK]   %zu 台设备成功关联到音频端点\n", endpointIds.size());
```

- [ ] **Step 4: 编译并运行**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64
tools\volume-spike\bin\volume-spike.exe
```

Expected（已配对设备且属性存在）:
```
[2/5] 读取设备音频端点 ID...
[OK]   我的蓝牙音箱 -> {0.0.0.00000000}.{8f4b2c1d-...}.{...}
[OK]   1 台设备成功关联到音频端点
```

这是**假设成立**的第一个证据。若输出 `[SKIP] 设备 X 没有 System_DeviceEndpointId 属性` 且全部设备都被跳过，说明该假设不成立。

- [ ] **Step 5: 提交**

```bash
git add tools/volume-spike
git commit -m "feat: map A2DP devices to Core Audio endpoint IDs"
```

---

### Task 4: 端点获取与音量读写

**Files:**
- Create: `tools/volume-spike/Step3_FindEndpoint.h`
- Create: `tools/volume-spike/Step3_FindEndpoint.cpp`
- Create: `tools/volume-spike/Step4_Volume.h`
- Create: `tools/volume-spike/Step4_Volume.cpp`
- Modify: `tools/volume-spike/main.cpp`

**Interfaces:**
- Consumes: Task 3 的 `GetEndpointIdsForDevices()` 输出的 `endpointIds`
- Produces:
  - `wil::com_ptr<IMMDevice> FindDevice(const wil::com_ptr<IMMDeviceEnumerator>& enumerator, const std::wstring& endpointId);` —— 含 5 次重试，间隔 500ms（Review Focus 第 4 条）
  - `bool ReadMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float& out);`
  - `bool WriteMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float value);`
  - `bool ReadMute(const wil::com_ptr<IAudioEndpointVolume>& volume, bool& out);`

注意 `IMMDeviceEnumerator` 的创建与 `IAudioEndpointVolume` 的激活直接写在 `main.cpp` 里，因为 Spike 只需验证一次，单独包一层没有复用价值。主工程实现时再抽成 `VolumeController`。

- [ ] **Step 1: 写端点查找头文件**

`Step3_FindEndpoint.h`：

```cpp
#pragma once

#include <string>

// 端点在 A2DP 连接建立后可能延迟出现，重试 5 次每次间隔 500ms。
// 全部失败返回 nullptr。
wil::com_ptr<IMMDevice> FindDevice(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::wstring& endpointId);
```

- [ ] **Step 2: 实现端点查找**

`Step3_FindEndpoint.cpp`：

```cpp
#include "pch.h"
#include "Step3_FindEndpoint.h"

wil::com_ptr<IMMDevice> FindDevice(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::wstring& endpointId)
{
    constexpr int kMaxAttempts = 5;
    constexpr int kRetryDelayMs = 500;

    for (int attempt = 1; attempt <= kMaxAttempts; ++attempt)
    {
        wil::com_ptr<IMMDevice> device;
        HRESULT hr = enumerator->GetDevice(endpointId.c_str(), device.put());
        if (SUCCEEDED(hr))
        {
            wprintf(L"[OK]   找到端点（第 %d 次尝试）\n", attempt);
            return device;
        }

        wprintf(L"[WAIT] 端点尚不可用（尝试 %d/%d，hr=0x%08X），%dms 后重试\n",
            attempt, kMaxAttempts, static_cast<uint32_t>(hr), kRetryDelayMs);
        Sleep(kRetryDelayMs);
    }

    wprintf(L"[FAIL] 端点在 %d 次尝试后仍不可用\n", kMaxAttempts);
    return nullptr;
}
```

- [ ] **Step 3: 写音量读写头文件**

`Step4_Volume.h`：

```cpp
#pragma once

// 以下函数均假定参数非空；调用方负责检查。
// com_ptr 按 const 引用传递 —— 避免每次调用都做引用计数增减。
bool ReadMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float& out);
bool WriteMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float value);
bool ReadMute(const wil::com_ptr<IAudioEndpointVolume>& volume, bool& out);
```

- [ ] **Step 4: 实现音量读写**

`Step4_Volume.cpp`：

```cpp
#include "pch.h"
#include "Step4_Volume.h"

bool ReadMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float& out)
{
    float value = 0.0f;
    HRESULT hr = volume->GetMasterVolumeLevelScalar(&value);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 读取音量失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    out = value;
    wprintf(L"[OK]   当前音量: %.1f%%\n", value * 100.0f);
    return true;
}

bool WriteMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float value)
{
    // value 必须在 [0,1]，防止越界导致未定义行为
    if (value < 0.0f || value > 1.0f)
    {
        wprintf(L"[FAIL] 音量值 %.2f 超出 [0,1] 范围\n", value);
        return false;
    }

    HRESULT hr = volume->SetMasterVolumeLevelScalar(value, nullptr);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 设置音量失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    wprintf(L"[OK]   已设置音量为 %.1f%%\n", value * 100.0f);
    return true;
}

bool ReadMute(const wil::com_ptr<IAudioEndpointVolume>& volume, bool& out)
{
    BOOL muted = FALSE;
    HRESULT hr = volume->GetMute(&muted);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 读取静音状态失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    out = (muted != FALSE);
    wprintf(L"[OK]   静音状态: %s\n", out ? L"是" : L"否");
    return true;
}
```

- [ ] **Step 5: 在 main 中串联**

在 Task 3 的代码之后插入：

```cpp
    wprintf(L"\n[3/5] 获取音频端点...\n");
    wil::com_ptr<IMMDeviceEnumerator> enumerator;
    HRESULT hr = CoCreateInstance(
        __uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
        __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(enumerator.put()));
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 创建 MMDeviceEnumerator 失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return 4;
    }

    wil::com_ptr<IMMDevice> device = FindDevice(enumerator, endpointIds.front());
    if (!device)
    {
        wprintf(L"[结论] 无法获取音频端点，音量控制方案不可行。\n");
        return 4;
    }

    wprintf(L"\n[4/5] 读写音量...\n");
    wil::com_ptr<IAudioEndpointVolume> volume;
    hr = device->Activate(__uuidof(IAudioEndpointVolume), CLSCTX_ALL, nullptr,
        reinterpret_cast<void**>(volume.put()));
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 激活 IAudioEndpointVolume 失败: 0x%08X\n", static_cast<uint32_t>(hr));
        wprintf(L"[结论] 该端点不支持音量控制。\n");
        return 5;
    }

    float originalVolume = 0.0f;
    bool volumeRead = ReadMasterVolume(volume, originalVolume);

    bool muted = false;
    bool muteRead = ReadMute(volume, muted);

    bool writeOk = false;
    if (volumeRead)
    {
        // 写到 50%，验证可写
        writeOk = WriteMasterVolume(volume, 0.5f);
    }

    // 恢复原音量，避免留下副作用
    if (writeOk && volumeRead)
    {
        WriteMasterVolume(volume, originalVolume);
    }
```

- [ ] **Step 6: 编译并运行**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64
tools\volume-spike\bin\volume-spike.exe
```

Expected:
```
[3/5] 获取音频端点...
[OK]   找到端点（第 1 次尝试）

[4/5] 读写音量...
[OK]   当前音量: 65.0%
[OK]   静音状态: 否
[OK]   已设置音量为 50.0%
[OK]   已设置音量为 65.0%   <- 恢复原值
```

系统音量滑块应可见地跟随变化，然后恢复。

- [ ] **Step 7: 提交**

```bash
git add tools/volume-spike
git commit -m "feat: read and write endpoint volume via IAudioEndpointVolume"
```

---

### Task 5: 音量变化回调验证

验证 Review Focus 第 5 条 —— 回调的线程模型。

**Files:**
- Create: `tools/volume-spike/Step5_Notify.h`（`VolumeCallback` 全部方法内联定义在头文件里，无 .cpp）
- Modify: `tools/volume-spike/main.cpp`

**Interfaces:**
- Consumes: Task 4 的 `wil::com_ptr<IAudioEndpointVolume>`
- Produces: `class VolumeCallback : public IAudioEndpointVolumeCallback`，带 `DWORD CallbackThreadId()` 便于诊断

- [ ] **Step 1: 写回调类**

`Step5_Notify.h`：

```cpp
#pragma once

#include <atomic>

// 实现 IAudioEndpointVolumeCallback，用于观察音量变化通知。
// 记录回调发生的线程 ID，以便诊断 COM 线程模型问题。
class VolumeCallback : public IAudioEndpointVolumeCallback
{
public:
    VolumeCallback() = default;

    // IUnknown
    ULONG STDMETHODCALLTYPE AddRef() override
    {
        return static_cast<ULONG>(InterlockedIncrement(&m_refCount));
    }

    ULONG STDMETHODCALLTYPE Release() override
    {
        auto count = InterlockedDecrement(&m_refCount);
        if (count == 0) { delete this; }
        return static_cast<ULONG>(count);
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppv) override
    {
        if (!ppv) { return E_POINTER; }
        if (riid == __uuidof(IUnknown) || riid == __uuidof(IAudioEndpointVolumeCallback))
        {
            *ppv = static_cast<IAudioEndpointVolumeCallback*>(this);
            AddRef();
            return S_OK;
        }
        *ppv = nullptr;
        return E_NOINTERFACE;
    }

    // IAudioEndpointVolumeCallback
    HRESULT STDMETHODCALLTYPE OnNotify(PAUDIO_VOLUME_NOTIFICATION_DATA data) override
    {
        if (!data) { return S_OK; }

        m_callbackCount.fetch_add(1);
        m_callbackThreadId = GetCurrentThreadId();

        wprintf(L"[NOTIFY] 音量变化: %.1f%% 静音=%s (线程 %lu, 第 %d 次)\n",
            data->fMasterVolume * 100.0f,
            data->bMuted ? L"是" : L"否",
            m_callbackThreadId,
            m_callbackCount.load());
        return S_OK;
    }

    DWORD CallbackThreadId() const { return m_callbackThreadId; }
    int  CallbackCount() const { return m_callbackCount.load(); }

private:
    LONG m_refCount = 1;
    std::atomic<int> m_callbackCount{ 0 };
    DWORD m_callbackThreadId = 0;
};
```

- [ ] **Step 2: 在 main 中注册回调**

在 Task 4 的代码之后插入：

```cpp
    wprintf(L"\n[5/5] 验证音量变化回调...\n");
    auto* callback = new VolumeCallback();

    hr = volume->RegisterControlChangeNotify(callback);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 注册回调失败: 0x%08X\n", static_cast<uint32_t>(hr));
        callback->Release();
    }
    else
    {
        wprintf(L"[OK]   回调已注册。主线程 ID = %lu\n", GetCurrentThreadId());
        wprintf(L"       请在 10 秒内用系统音量界面改变音量...\n");

        // 主动改一次音量，确保至少触发一次回调
        Sleep(1000);
        if (volumeRead)
        {
            WriteMasterVolume(volume, 0.3f);
            Sleep(1000);
            WriteMasterVolume(volume, 0.7f);
            Sleep(1000);
            WriteMasterVolume(volume, originalVolume);
        }

        Sleep(3000);

        wprintf(L"[INFO] 回调次数: %d，回调线程 ID: %lu\n",
            callback->CallbackCount(), callback->CallbackThreadId());

        if (callback->CallbackCount() > 0)
        {
            if (callback->CallbackThreadId() == GetCurrentThreadId())
            {
                wprintf(L"[结论] 回调在主线程触发 —— 线程模型为 STA，主工程可直接处理。\n");
            }
            else
            {
                wprintf(L"[结论] 回调在独立线程触发 —— 主工程需 marshalling 到 UI 线程。\n");
            }
        }
        else
        {
            wprintf(L"[FAIL] 未收到任何回调，音量变化的实时同步不可行。\n");
        }

        volume->UnregisterControlChangeNotify(callback);
        callback->Release();
    }
```

- [ ] **Step 3: 编译并运行**

Run:
```powershell
msbuild tools\volume-spike\volume-spike.vcxproj /p:Configuration=Release /p:Platform=x64
tools\volume-spike\bin\volume-spike.exe
```

Expected:
```
[5/5] 验证音量变化回调...
[OK]   回调已注册。主线程 ID = 12345
       请在 10 秒内用系统音量界面改变音量...
[NOTIFY] 音量变化: 30.0% 静音=否 (线程 12345, 第 1 次)
[NOTIFY] 音量变化: 70.0% 静音=否 (线程 12345, 第 2 次)
[NOTIFY] 音量变化: 65.0% 静音=否 (线程 12345, 第 3 次)
[INFO] 回调次数: 3，回调线程 ID: 12345
[结论] 回调在主线程触发 —— 线程模型为 STA，主工程可直接处理。
```

- [ ] **Step 4: 提交**

```bash
git add tools/volume-spike
git commit -m "feat: verify volume change callback threading model"
```

---

### Task 6: Spike 结论报告

把实测结果固化成文档，作为后续实现的决策依据。

**Files:**
- Create: `docs/superpowers/spikes/2026-10-10-volume-spike-results.md`
- Create: `docs/superpowers/spikes/volume-spike-output.txt`

- [ ] **Step 1: 运行完整 Spike 并保存输出**

Run:
```powershell
tools\volume-spike\bin\volume-spike.exe 2>&1 |
    Tee-Object -FilePath docs\superpowers\spikes\volume-spike-output.txt
```

（先创建目录：`New-Item -ItemType Directory -Force docs\superpowers\spikes`）

- [ ] **Step 2: 写结论报告**

`docs/superpowers/spikes/2026-10-10-volume-spike-results.md`：

```markdown
# 音量控制 Spike 结论

- 日期：2026-10-10
- 环境：Windows <实际版本>，x64
- 设备：<实际设备名>
- 完整输出：[volume-spike-output.txt](volume-spike-output.txt)

## 验证结果

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| 系统支持 A2DP Sink | <是/否> | Step 1 |
| 设备有 System_DeviceEndpointId 属性 | <是/否> | Step 2 |
| 端点可通过 IMMDeviceEnumerator 取得 | <是/否> | Step 3 |
| 可读 MasterVolumeLevelScalar | <是/否> | Step 4 |
| 可写 SetMasterVolumeLevelScalar | <是/否> | Step 4 |
| 可读 GetMute | <是/否> | Step 4 |
| 音量变化回调触发 | <是/否> | Step 5 |
| 回调线程模型 | <STA主线程/独立线程> | Step 5 |

## 结论

**<采用 / 不采用 / 有条件采用> 音量控制方案。**

理由：<基于上表的具体说明>

## 对主工程的影响

- 若采用：`VolumeController` 按 <具体 API 路径> 实现；回调在 <线程> 触发，因此 <是否需要 marshalling>。
- 若不采用：设备列表窗口隐藏音量滑块；`ConnectionEntry` 不含音量字段。
- 关联稳定性：<属性关联是否可靠，是否需要名称匹配兜底>
```

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/spikes
git commit -m "docs: add volume control spike results"
```

---

## 完成标准

本计划完成时应当具备：

- [ ] `tools/volume-spike/` 可独立编译运行
- [ ] 五个验证步骤全部有实测输出
- [ ] `docs/superpowers/spikes/2026-10-10-volume-spike-results.md` 给出明确的采用/不采用结论
- [ ] 后续计划（音量实现或移除）有据可依，不再是猜测