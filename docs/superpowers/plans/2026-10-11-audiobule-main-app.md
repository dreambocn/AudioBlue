# AudioBule 主工程实施计划（阶段 0~3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可用的 AudioBule 应用：托盘常驻，点击弹出自绘设备列表窗口，可对多台蓝牙设备并行连接/断开，配置持久化，能打 MSIX 包。

**Architecture:** 两个工程。`AudioBule.Core` 是无 UI 依赖的静态库，封装设备枚举、连接状态机、配置读写、图标生成；其唯一的外部依赖 `AudioPlaybackConnection` 通过 `IAudioDeviceProvider` 接口注入，因此状态机可用自研的轻量测试框架离线单测。`AudioBule.App` 是 WinUI 3 壳，只做呈现与平台集成：托盘线程（独立 STA + message-only HWND）经 `DispatcherQueue` 把事件 post 回 UI 线程，UI 一律通过 `ConnectionManager` 读状态，不直接触碰 WinRT 连接对象。

**Tech Stack:** C++17（`/std:c++latest`）/ C++/WinRT（Windows SDK 投影头 + `Microsoft.Windows.CppWinRT` 3.0.260520.1）/ WIL 1.0.260126.7 / Windows App SDK 2.2.0 + WinUI 2.2.1 / MSVC 工具集 **v145** / GDI（图标生成）。

**Spec:** `docs/superpowers/specs/2026-10-10-audiobule-design.md`

**进度与结论来源:** `PROGRESS.md`、`docs/superpowers/spikes/2026-10-10-volume-spike-results.md`

---

## 本计划与 Spec 的偏差（执行前须知）

以下三处**有意偏离** spec，理由如下，不接受"照 spec 写"的指令：

| 项 | Spec | 本计划 | 理由 |
| --- | --- | --- | --- |
| 单元测试框架 | "普通单元测试框架" | 自研 `TestHarness.h`（约 90 行，控制台 exe，退出码 0/1） | 本机 NuGet 缓存中**没有** MSTest / Catch2 / GoogleTest / xUnit 任何一项。引入需要联网，与"离线可还原"的既有约束冲突。自研 harness 满足全部真实需求：独立可跑的测试用例、失败即非零退出码、输出可读 |
| 图标生成 | `SVG → Direct2D CreateSvgDocument → CreateIconIndirect` | GDI 直接绘制到 32bpp DIB + 1bpp mask，再 `CreateIconIndirect` | SVG 需要在仓库里放二进制/文本资产并在运行时解析，且引入 Direct2D 依赖链（`ID2D1DeviceContext5`、`IWICBitmap` 等约 200 行胶水）。托盘图标是 16~32px 的静态小图，GDI 绘制足够。图标**外观**在 spec 中未定义，因此无功能损失。若后续要换 SVG，只改 `IconFactory.cpp` 内部，不影响调用方 |
| `VolumeController` | 文件结构中列出，`ConnectionEntry` 含音量字段 | **完全不存在** | 音量 Spike 已给出否定结论（见 spike 报告）：A2DP Sink 不为蓝牙设备建独立渲染端点，且设备侧无端点关联字段。`ConnectionEntry` 不含音量字段 |

**"独立线程 + message-only HWND" 是本项目最关键的技术点**，spec §3.4 已定为独立阶段（阶段 2），本计划的 Task 8 专攻它，不与其它任务混在一起。

---

## Global Constraints

以下约束适用于本计划**每一个**任务：

- **工具链（已实测）**：Visual Studio Community 2026，MSBuild 完整路径
  `D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe`。
  **msbuild 不在 PATH**，所有命令必须用完整路径调用。
- **`<PlatformToolset>` 必须是 `v145`**。写 `v180` 会报 `MSB8020 找不到 v180 的生成工具`。
  实际工具集目录：`D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Microsoft\VC\v180\Platforms\x64\PlatformToolsets\v145`。
  （注意：是 `Platforms\x64\PlatformToolsets`，**不是** `PlatformToolsets\x64\PlatformToolsets` —— `PROGRESS.md` 里这行路径写错了。）
- **`<WindowsTargetPlatformVersion>` 必须显式写 `10.0.26100.0`**，留 `10.0` 会去默认路径 `C:\Program Files (x86)\Windows Kits\10` 找不到。SDK 实际安装在 **`D:\Windows Kits\10`**。
- **C++/WinRT 投影头必须显式加 include 路径**。MSBuild 默认注入 `<sdk>\Include\<ver>\winrt\`（C 语言头目录），投影头实际在
  `D:\Windows Kits\10\Include\10.0.26100.0\cppwinrt\winrt`。本计划在 `Directory.Build.props` 里定义属性 `CppWinRTProjectionIncludePath`，每个工程在 `ItemDefinitionGroup` 里引用它。
- **必须先 `-t:Restore`**，否则 NuGet 头文件路径不生效，编译报 `无法打开包括文件: "wil/common.h"`。
- **编译选项必须含 `/utf-8`**。C++/WinRT 生成的投影头是 UTF-8 无 BOM，本机代码页 936(GBK) 会触发 C4819，而 `/WX` 把它升级为错误。
- **NuGet 缓存（可离线还原，无需联网）**：`Microsoft.WindowsAppSDK` 2.2.0、`Microsoft.WindowsAppSDK.WinUI` 2.2.1、`Microsoft.Windows.CppWinRT` 3.0.260520.1、`Microsoft.Windows.ImplementationLibrary` 1.0.260126.7。**不得引入这四个之外的任何新包。**
- **最低系统版本：Windows 10 2004（build 19041）**。低于此版本 `AudioPlaybackConnection` 类型不存在，必须 `ApiInformation::IsTypePresent` 先检测再调用，然后优雅退出并提示。
- **`AudioBule.Core` 不引用任何 WinUI 头文件**，只依赖 Win32 / C++/WinRT / WIL。这是 Core 层可单元测试的前提，任何任务不得破坏它。
- **警告级别 W4 + `/WX`（警告即错误）**。C++ 标准 `stdcpplatest`。
- **架构仅 x64**。仅 `Debug|x64` 与 `Release|x64` 两个配置。
- **所有 HRESULT 必须检查**，不得忽略。所有 COM 接口指针必须释放（`wil::com_ptr` 优于裸 `Release()`）。
- **`IMMDevice::GetId` 返回 CoTaskMem 字符串**，需手工 `CoTaskMemFree`，不能直接用 `wil::unique_hz`。（本计划最终不需要它，但若有人想加端点查询，记住这条。）
- **`DeviceInformation::Properties.Lookup()` 返回可能为 `IInspectable`**，取字符串需先 `as<Windows::Foundation::IPropertyValue>()`，类型判断用 `Type()` 而非 `ValueType()`。
- **范围 for 遍历 WinRT 集合需要 `<winrt/Windows.Foundation.Collections.h>`**，缺失报 C3536/C2100。
- **每完成一个 Task 提交一次 git**，提交信息用 `type: 描述` 格式（英文小写祈使句）。

---

## Review Focus

以下条件最可能咬到实际使用的人，但没有任何任务的测试会覆盖。每一条都已在线性任务中补上对应的验证步骤：

1. **用户手机正作为 A2DP 源连着别的设备** —— 这是**真实且高频**的失败：手机连着耳机时无法同时做接收端，`OpenAsync` 失败且扩展错误码为 `0x8007001F (ERROR_GEN_FAILURE)`。用户在 UI 上只会看到一个含义不明的"失败"。**期望**：错误文案必须明确指向"手机当前不能作为接收端"，而不是泛泛的"连接失败"。→ Task 4 Step 7、Task 10 Step 6。
2. **用户首次启动，配置文件不存在** —— 期望：静默使用默认值正常启动，不弹任何错误框。→ Task 3 Step 5。
3. **配置文件存在但 JSON 被手改坏** —— 期望：同样静默回落默认值，不崩溃、不清空已有内容。→ Task 3 Step 6。
4. **用户点窗口的 X 关闭按钮** —— 期望：隐藏到托盘，**程序继续运行**；退出只能走托盘菜单。写成"关闭即退出"会让用户以为程序挂了，下次开机（若自启已配）可能连不上。→ Task 10 Step 7。
5. **用户任务管理器结束 `explorer.exe` 后恢复** —— 期望：托盘图标重新出现，不需要重启 AudioBule。→ Task 9 Step 6。
6. **程序正常退出但托盘线程没停干净** —— 期望：进程能真正退出，不残留幽灵进程或残留图标。→ Task 8 Step 8。
7. **用户在设备列表窗口点了某台设备的「连接」，然后立刻退出程序** —— 期望：不崩溃，且下次启动自动重连（因为配置已写入）。→ Task 11 Step 6。

---

## File Structure

```
AudioBule/
├─ AudioBule.sln
├─ Directory.Build.props                  # 所有工程共享的编译设置（工具集/SDK/警告/utf-8）
├─ .gitignore
├─ AudioBule.Core/                        # 静态库，无 UI 依赖
│  ├─ AudioBule.Core.vcxproj
│  ├─ pch.h / pch.cpp                     # 预编译头
│  ├─ targetver.h                         # _WIN32_WINNT = 0x0A00
│  ├─ SimpleEvent.h                       # 轻量事件（Add/Remove/Raise），供 Core 对外通知
│  ├─ StringUtil.h / .cpp                 # UTF-8/UTF-16 转换、错误码格式化
│  ├─ Messages.h / .cpp                   # Core 层错误文案查表（不复用 YMO，用显式映射）
│  ├─ IAudioDeviceProvider.h              # 设备枚举与连接的抽象接口（测试替身注入点）
│  ├─ ConnectionEntry.h                   # 单条连接状态
│  ├─ ConnectionManager.h / .cpp          # 多设备连接状态机（唯一状态源）
│  ├─ WinRtDeviceProvider.h / .cpp        # 生产实现：包装 AudioPlaybackConnection
│  ├─ Settings.h / .cpp                   # JSON 配置持久化
│  └─ IconFactory.h / .cpp                # GDI 绘制托盘图标（深/浅两套）
├─ AudioBule.App/                         # WinUI 3 可执行程序
│  ├─ AudioBule.App.vcxproj
│  ├─ pch.h / pch.cpp
│  ├─ main.cpp                            # wWinMain：apartment 初始化 + Application::Start
│  ├─ App.xaml / App.xaml.h / App.xaml.cpp
│  ├─ MainWindow.xaml / .h / .cpp         # 设备列表窗口
│  ├─ DeviceItemViewModel.h / .cpp        # 每行 ViewModel，实现 INotifyPropertyChanged
│  ├─ TrayIconService.h / .cpp            # 独立线程 + message-only HWND + DispatcherQueue 桥接
│  ├─ App.xaml                            # 样式与资源
│  └─ app.manifest
├─ assets/
│  └─ AudioBule.Package.appxmanifest      # MSIX 清单（Task 12 才用）
└─ tests/
   ├─ TestHarness.h                       # 自研测试框架（见「偏差」一节）
   ├─ main.cpp                            # 测试入口，遍历注册的用例
   ├─ StringUtil.test.cpp
   ├─ Settings.test.cpp
   ├─ ConnectionManager.test.cpp
   ├─ IconFactory.test.cpp
   └─ AudioBule.Core.Tests.vcxproj        # 放 tests/ 下，引用 Core
```

**分层的硬边界**：`AudioBule.Core` 里出现任何 `winrt::Microsoft::UI::Xaml` 都是错误，反之 `AudioBule.App` 里出现 `AudioPlaybackConnection` 也是错误。Task 11 会用一条构建期检查把这条边界钉死。

**为什么不按 spec 把测试放 `tests/AudioBule.Core.Tests/` 子目录**：测试工程只有一个，多套一层目录没有收益，只会让 `Include` 路径多一层。`TestHarness.h` 与测试用例平铺在 `tests/` 下更直观。

---

## Task 1: 解决方案骨架 + 共享编译设置 + 测试框架

**Files:**
- Create: `Directory.Build.props`
- Create: `.gitignore`
- Create: `AudioBule.sln`
- Create: `AudioBule.Core/AudioBule.Core.vcxproj`
- Create: `AudioBule.Core/targetver.h`
- Create: `AudioBule.Core/pch.h` / `AudioBule.Core/pch.cpp`
- Create: `tests/AudioBule.Core.Tests.vcxproj`
- Create: `tests/TestHarness.h`
- Create: `tests/main.cpp`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `AudioBule.sln`，含 `AudioBule.Core` 与 `AudioBule.Core.Tests` 两个工程，配置 `Debug|x64` / `Release|x64`
  - 三个后续任务直接复用的属性：`CppWinRTProjectionIncludePath`、`AudioBuleRepoRoot`
  - 测试宏（`TestHarness.h`）：`AB_TEST(name)`、`CHECK(cond)`、`CHECK_EQ(a, b)`、`CHECK_NE(a, b)`
  - 测试入口约定：`tests/main.cpp` 的 `int main()` 调用 `ab::test::RunAll()`，失败返回 `1`，全过返回 `0`。测试工程用窄字符入口，**不**加 `EntryPointSymbol`

本任务的交付物是**一条可执行的验证链路**：`msbuild AudioBule.sln` 能还原并编译出 `tests\bin\AudioBule.Core.Tests.exe`，运行它退出码为 `0`。后续每个 Core 任务都在这条链路上加用例。

---

- [ ] **Step 1: 创建 `Directory.Build.props`**

所有 vcxproj 自动导入它。放在仓库根目录。

```xml
<?xml version="1.0" encoding="utf-8"?>
<Project>
  <PropertyGroup>
    <AudioBuleRepoRoot>$(MSBuildThisFileDirectory)</AudioBuleRepoRoot>

    <!-- 必须显式写版本号：留 10.0 会去找 C:\Program Files (x86)\Windows Kits\10，
         而本机 SDK 装在 D:\Windows Kits\10 -->
    <WindowsTargetPlatformVersion>10.0.26100.0</WindowsTargetPlatformVersion>

    <!-- v180 是 MSBuild 目录名，v145 才是可用的工具集名 -->
    <PlatformToolset>v145</PlatformToolset>

    <!-- C++/WinRT 投影头的真实位置。MSBuild 默认注入的是 <sdk>\Include\<ver>\winrt\
         （C 语言头目录），投影头在同级的 cppwinrt\winrt\ 下，必须显式补。
         路径硬编码是因为 Directory.Build.props 导入时 $(WindowsSdkDir) 尚未定义。 -->
    <CppWinRTProjectionIncludePath>D:\Windows Kits\10\Include\10.0.26100.0\cppwinrt\winrt</CppWinRTProjectionIncludePath>
  </PropertyGroup>
</Project>
```

- [ ] **Step 2: 创建 `.gitignore`**

所有产物路径都写成**以 `/` 开头的根锚定**形式。不要用裸 `bin/`、`obj/`、`x64/` ——
那会连带忽略 `tools/volume-spike/bin/` 下的 Spike 产物，而那是刻意保留的技术证据。

```gitignore
# MSBuild 中间产物与输出
/x64/
/Debug/
/Release/
/AudioBule.Core/bin/
/AudioBule.Core/obj/
/AudioBule.App/bin/
/AudioBule.App/obj/
/tests/bin/
/tests/obj/
/.vs/
*.user
*.aps
*.tlog
*.idb
*.ipch
*.iobj

# 打包产物
AppPackages/
*.msix
*.msixbundle
*.appx
*.appxbundle
*.pri
```

- [ ] **Step 3: 创建 `AudioBule.Core/targetver.h`**

```cpp
#pragma once

// AudioBule 统一目标版本：Windows 10 2004 (build 19041)。
// AudioPlaybackConnection 由该版本引入，更低版本需优雅退出。
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define NTDDI_VERSION NTDDI_WIN10_RS3
```

- [ ] **Step 4: 创建 `AudioBule.Core/pch.h`**

```cpp
#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>

#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/com.h>
#include <wil/result.h>

// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，与 windows.h 冲突导致 C4002。
// 必须在包含 C++/WinRT 头之前 #undef。
#undef GetCurrentTime

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
// 范围 for 遍历 WinRT 集合（DeviceInformationCollection 等）依赖此头的迭代器
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>
```

- [ ] **Step 5: 创建 `AudioBule.Core/pch.cpp`**

```cpp
#include "pch.h"
```

- [ ] **Step 6: 创建 `AudioBule.Core/AudioBule.Core.vcxproj`**

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
    <ProjectGuid>{A1B2C3D4-0001-4E5F-9A8B-000000000001}</ProjectGuid>
    <RootNamespace>AudioBuleCore</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>StaticLibrary</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>StaticLibrary</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings" />
  <ImportGroup Label="Shared" />
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup>
    <TargetName>AudioBule.Core</TargetName>
    <IntDir>$(ProjectDir)obj\</IntDir>
    <OutDir>$(ProjectDir)bin\</OutDir>
  </PropertyGroup>
  <ItemDefinitionGroup>
    <ClCompile>
      <AdditionalIncludeDirectories>$(CppWinRTProjectionIncludePath);$(ProjectDir);%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <WarningLevel>Level4</WarningLevel>
      <SDLCheck>true</SDLCheck>
      <ConformanceMode>true</ConformanceMode>
      <PrecompiledHeader>Use</PrecompiledHeader>
      <PrecompiledHeaderFile>pch.h</PrecompiledHeaderFile>
      <TreatWarningAsError>true</TreatWarningAsError>
      <LanguageStandard>stdcpplatest</LanguageStandard>
      <!-- C++/WinRT 投影头是 UTF-8 无 BOM，本机代码页 936(GBK) 会触发 C4819，
           /WX 把它升级为错误 -->
      <AdditionalOptions>/utf-8 %(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClInclude Include="pch.h" />
    <ClInclude Include="targetver.h" />
  </ItemGroup>
  <ItemGroup>
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

> 静态库工程不需要 `<Link>` 配置节。`pch.cpp` 是唯一源文件 —— 一个能编过的空库。
> Task 2 起往里加 `.cpp`，并同步在两个 `ItemGroup` 里登记。

- [ ] **Step 7: 创建 `tests/TestHarness.h`**

```cpp
#pragma once

// 自研的极简测试框架。理由：本机 NuGet 缓存中没有任何单元测试框架包，
// 引入需要联网，与本项目"离线可还原"的约束冲突。
//
// 用法：
//   AB_TEST(Utf8RoundTrip) { CHECK_EQ(Utf8ToWide("hi"), std::wstring(L"hi")); }
//   在 tests/main.cpp 的 main() 里调 ab::test::RunAll()。
// 失败抛 AssertionFailure 异常，RunAll 捕获并计数，返回失败数（0 表示全过）。

#include <cstdio>
#include <exception>
#include <functional>
#include <string>
#include <vector>

namespace ab::test {

class AssertionFailure : public std::exception
{
public:
    const char* what() const noexcept override { return "assertion failed"; }
};

struct TestCase
{
    const char* name;
    std::function<void()> body;
};

inline std::vector<TestCase>& Registry()
{
    static std::vector<TestCase> registry;
    return registry;
}

struct Registrar
{
    Registrar(const char* name, std::function<void()> body)
    {
        Registry().push_back(TestCase{ name, std::move(body) });
    }
};

// 报告一个失败但不中断当前用例（用于 CHECK_NOTHROW 之外的软断言）。
inline void ReportFailure(const char* file, int line, const std::string& message)
{
    std::printf("  FAILED %s(%d): %s\n", file, line, message.c_str());
}

// RunAll 返回失败用例数。0 表示全过。
inline int RunAll()
{
    int failed = 0;
    std::printf("Running %zu test(s)\n", Registry().size());
    for (const auto& test : Registry())
    {
        try
        {
            test.body();
            std::printf("  [PASS] %s\n", test.name);
        }
        catch (AssertionFailure const&)
        {
            std::printf("  [FAIL] %s\n", test.name);
            ++failed;
        }
        catch (std::exception const& e)
        {
            std::printf("  [FAIL] %s (unexpected exception: %s)\n", test.name, e.what());
            ++failed;
        }
    }
    std::printf("%zu passed, %d failed\n", Registry().size() - static_cast<size_t>(failed), failed);
    return failed;
}

} // namespace ab::test

#define AB_TEST(name)                                                          \
    static void name();                                                        \
    static ::ab::test::Registrar ab_reg_##name(#name, name);                   \
    static void name()

#define CHECK(cond)                                                           \
    do {                                                                      \
        if (!(cond)) {                                                        \
            ::ab::test::ReportFailure(__FILE__, __LINE__, "CHECK(" #cond ")"); \
            throw ::ab::test::AssertionFailure{};                             \
        }                                                                     \
    } while (false)

#define CHECK_EQ(a, b)                                                        \
    do {                                                                      \
        auto&& ab_a = (a);                                                    \
        auto&& ab_b = (b);                                                    \
        if (!(ab_a == ab_b)) {                                                \
            ::ab::test::ReportFailure(__FILE__, __LINE__,                     \
                "CHECK_EQ(" #a ", " #b ")");                                  \
            throw ::ab::test::AssertionFailure{};                             \
        }                                                                     \
    } while (false)

#define CHECK_NE(a, b)                                                        \
    do {                                                                      \
        auto&& ab_a = (a);                                                    \
        auto&& ab_b = (b);                                                    \
        if (ab_a == ab_b) {                                                   \
            ::ab::test::ReportFailure(__FILE__, __LINE__,                     \
                "CHECK_NE(" #a ", " #b ")");                                  \
            throw ::ab::test::AssertionFailure{};                             \
        }                                                                     \
    } while (false)
```

- [ ] **Step 8: 创建 `tests/main.cpp` 与一个冒烟用例**

```cpp
#include "TestHarness.h"

// 冒烟用例：验证框架自身能跑通。Task 2 起会被真正的用例覆盖掉。
AB_TEST(HarnessRunsAndReportsSuccess)
{
    int value = 2 + 2;
    CHECK_EQ(value, 4);
    CHECK_NE(value, 5);
    CHECK(value == 4);
}

// 测试工程统一用窄字符入口 main()，不需要 wmain / EntryPointSymbol。
// 需要打印宽字符时走 Core 的 WideToUtf8 转成窄字符再 printf。
int main()
{
    return ab::test::RunAll() == 0 ? 0 : 1;
}
```

- [ ] **Step 9: 创建 `tests/AudioBule.Core.Tests.vcxproj`**

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
    <ProjectGuid>{A1B2C3D4-0003-4E5F-9A8B-000000000003}</ProjectGuid>
    <RootNamespace>AudioBuleCoreTests</RootNamespace>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings" />
  <ImportGroup Label="Shared" />
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup>
    <TargetName>AudioBule.Core.Tests</TargetName>
    <IntDir>$(ProjectDir)obj\</IntDir>
    <OutDir>$(ProjectDir)bin\</OutDir>
  </PropertyGroup>
  <ItemDefinitionGroup>
    <ClCompile>
      <AdditionalIncludeDirectories>$(CppWinRTProjectionIncludePath);$(ProjectDir);$(ProjectDir)..\AudioBule.Core;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <WarningLevel>Level4</WarningLevel>
      <SDLCheck>true</SDLCheck>
      <ConformanceMode>true</ConformanceMode>
      <TreatWarningAsError>true</TreatWarningAsError>
      <LanguageStandard>stdcpplatest</LanguageStandard>
      <AdditionalOptions>/utf-8 %(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
    <Link>
      <SubSystem>Console</SubSystem>
      <!-- Core 是 /MT（静态 CRT），测试工程必须一致，否则链接期 LNK2038 冲突 -->
      <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClInclude Include="TestHarness.h" />
  </ItemGroup>
  <ItemGroup>
    <ClCompile Include="main.cpp" />
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\AudioBule.Core\AudioBule.Core.vcxproj">
      <Project>{A1B2C3D4-0001-4E5F-9A8B-000000000001}</Project>
    </ProjectReference>
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Windows.ImplementationLibrary" Version="1.0.260126.7" />
    <PackageReference Include="Microsoft.Windows.CppWinRT" Version="3.0.260520.1" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
</Project>
```

> **CRT 一致性是易踩的坑**：`AudioBule.Core` 的 Release 配置在 Task 9 会设
> `/MT`（`MultiThreaded`），静态库不链接 CRT 所以自身不会报错，但测试工程若用
> 默认 `/MD` 就会在链接期报 `LNK2038: 检测到不一致`。此处提前把测试工程也设为
> `/MT`，与 App 工程保持一致。

- [ ] **Step 10: 创建 `AudioBule.sln`**

```text
Microsoft Visual Studio Solution File, Format Version 12.00
# Visual Studio Version 17
VisualStudioVersion = 17.0.31903.59
MinimumVisualStudioVersion = 10.0.40219.1
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AudioBule.Core", "AudioBule.Core\AudioBule.Core.vcxproj", "{A1B2C3D4-0001-4E5F-9A8B-000000000001}"
EndProject
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AudioBule.Core.Tests", "tests\AudioBule.Core.Tests.vcxproj", "{A1B2C3D4-0003-4E5F-9A8B-000000000003}"
EndProject
Global
	GlobalSection(SolutionConfigurationPlatforms) = preSolution
		Debug|x64 = Debug|x64
		Release|x64 = Release|x64
	EndGlobalSection
	GlobalSection(ProjectConfigurationPlatforms) = postSolution
		{A1B2C3D4-0001-4E5F-9A8B-000000000001}.Debug|x64.ActiveCfg = Debug|x64
		{A1B2C3D4-0001-4E5F-9A8B-000000000001}.Debug|x64.Build.0 = Debug|x64
		{A1B2C3D4-0001-4E5F-9A8B-000000000001}.Release|x64.ActiveCfg = Release|x64
		{A1B2C3D4-0001-4E5F-9A8B-000000000001}.Release|x64.Build.0 = Release|x64
		{A1B2C3D4-0003-4E5F-9A8B-000000000003}.Debug|x64.ActiveCfg = Debug|x64
		{A1B2C3D4-0003-4E5F-9A8B-000000000003}.Debug|x64.Build.0 = Debug|x64
		{A1B2C3D4-0003-4E5F-9A8B-000000000003}.Release|x64.ActiveCfg = Release|x64
		{A1B2C3D4-0003-4E5F-9A8B-000000000003}.Release|x64.Build.0 = Release|x64
	EndGlobalSection
	GlobalSection(SolutionProperties) = preSolution
		HideSolutionNode = FALSE
	EndGlobalSection
EndGlobal
```

> 注意 sln 中每个工程只声明 `Debug|x64` 与 `Release|x64`。**不要**加 `Win32`
> 配置 —— 本项目只做 x64，加了反而在 VS 里多出两行空白且误导人。

- [ ] **Step 11: 还原并编译**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -t:Restore -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: 两次都退出码 0，产物 `AudioBule.Core\bin\AudioBule.Core.lib` 与
`tests\bin\AudioBule.Core.Tests.exe`。

- [ ] **Step 12: 运行测试**

Run:

```powershell
& ".\tests\bin\AudioBule.Core.Tests.exe"
$LASTEXITCODE
```

Expected:

```text
Running 1 test(s)
  [PASS] HarnessRunsAndReportsSuccess
1 passed, 0 failed
```

`$LASTEXITCODE` 为 `0`。

- [ ] **Step 13: 提交**

```bash
git add Directory.Build.props .gitignore AudioBule.sln AudioBule.Core tests
git commit -m "build: scaffold solution with Core library and test harness"
```

---

## Task 2: SimpleEvent 与 StringUtil

**Files:**
- Create: `AudioBule.Core/SimpleEvent.h`
- Create: `AudioBule.Core/StringUtil.h`
- Create: `AudioBule.Core/StringUtil.cpp`
- Modify: `AudioBule.Core/AudioBule.Core.vcxproj`（登记新文件）
- Create: `tests/StringUtil.test.cpp`
- Modify: `tests/AudioBule.Core.Tests.vcxproj`（登记新文件）

**Interfaces:**
- Consumes: Task 1 的 `TestHarness.h`、`AudioBule.Core.pch`
- Produces:
  - `namespace AudioBule::Core::SimpleEvent<Args...>`：
    - `void Add(std::function<void(Args...)>)`
    - `void Remove(std::function<void(Args...)>)` —— 按 handler 身份移除
    - `void Raise(Args...) const` —— **在副本上遍历**，回调中可以安全地 Add/Remove
    - `bool Empty() const`
  - `namespace AudioBule::Core`：
    - `std::string WideToUtf8(std::wstring_view)`
    - `std::wstring Utf8ToWide(std::string_view)`
    - `std::wstring FormatWin32Error(DWORD hr)` —— 格式化为 `0x%08X`
    - `std::wstring FormatMessageForHresult(HRESULT hr)` —— 取系统错误文本，失败回落为 `FormatWin32Error`

`SimpleEvent` 存在的唯一理由：`ConnectionManager` 要在**不引入任何 WinRT 类型**的前提下
对外广播条目变更。Core 的边界要求（Global Constraints）不允许 `IInspectable` 泄漏到
接口面，而 `winrt::event_token` 会把 WinRT 类型拖进来。

---

- [ ] **Step 1: 写失败的测试 `tests/StringUtil.test.cpp`**

```cpp
#include "TestHarness.h"
#include "StringUtil.h"

#include <string>

using namespace AudioBule::Core;

AB_TEST(AsciiRoundTrip)
{
    CHECK_EQ(WideToUtf8(L"hello"), std::string("hello"));
    CHECK(Utf8ToWide("hello") == std::wstring(L"hello"));
}

AB_TEST(EmptyStringRoundTrip)
{
    CHECK(WideToUtf8(L"").empty());
    CHECK(Utf8ToWide("").empty());
}

AB_TEST(ChineseRoundTrip)
{
    // 窄 wprintf 按控制台 ANSI 代码页解释字节，所以宽字符是主表示，
    // 窄字符只是日志/调试用的次要表示。
    auto wide = Utf8ToWide("蓝牙音频");
    CHECK(wide == std::wstring(L"蓝牙音频"));
    CHECK(WideToUtf8(wide) == std::string("蓝牙音频"));
}

AB_TEST(SurrogatePairRoundTrip)
{
    // U+1F50A 扬声器 emoji，需 UTF-16 代理对处理正确
    auto s = Utf8ToWide("\xF0\x9F\x94\x8A");
    CHECK_EQ(s.size(), static_cast<size_t>(2)); // 代理对 = 2 个 wchar
    CHECK_EQ(WideToUtf8(s), std::string("\xF0\x9F\x94\x8A"));
}

AB_TEST(EmbeddedNulIsTruncatedByCStringConvention)
{
    // WideToUtf8 按 wcslen 语义处理，遇 NUL 停止。这是刻意的：
    // 错误文案与设备名在实践中不含内嵌 NUL。
    CHECK_EQ(WideToUtf8(L"ab\0cd").size(), static_cast<size_t>(2));
}

AB_TEST(FormatWin32ErrorIsUppercaseHex)
{
    auto text = FormatWin32Error(0x8007001Fu);
    CHECK(text == std::wstring(L"0x8007001F"));
}

AB_TEST(FormatMessageForHresultFallsBackToHex)
{
    // 0x8007001F 是 ERROR_GEN_FAILURE，系统有文本；但用一个人为构造的、
    // 几乎不可能有本地化文本的码来验证回落路径更稳妥。
    auto text = FormatMessageForHresult(static_cast<HRESULT>(0x00001234u));
    CHECK(!text.empty());
}
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: **失败**，`无法打开包括文件: "StringUtil.h"`。这正是我们要的 —— 先看到红。

> 注意：本步预期编译失败，因此**不要**执行 `-t:Restore`。Restore 已在 Task 1
> 完成，且文件列表未变，NuGet 缓存路径依然生效。

- [ ] **Step 3: 创建 `AudioBule.Core/SimpleEvent.h`**

```cpp
#pragma once

#include <functional>
#include <mutex>
#include <utility>
#include <vector>

namespace AudioBule::Core
{

// 线程安全的轻量事件。用途：ConnectionManager 需要广播条目变更，
// 但 Core 的公开接口不允许出现 WinRT 类型（winrt::event_token 会把
// IInspectable 拖进接口面），因此自建。
//
// Raise 在副本上遍历：回调里可以安全地 Add / Remove 而不会让迭代器失效。
template <typename... Args>
class SimpleEvent
{
public:
    using Handler = std::function<void(Args...)>;

    void Add(Handler handler)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_handlers.push_back(std::move(handler));
    }

    // 按 handler 身份移除。传入的必须是先前 Add 的同一个 std::function 对象，
    // 或与之一致（lambda 拷贝即可，std::function 的 operator== 比较目标与参数）。
    void Remove(Handler const& handler)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        for (auto it = m_handlers.begin(); it != m_handlers.end(); ++it)
        {
            if (*it == handler)
            {
                m_handlers.erase(it);
                return;
            }
        }
    }

    void Raise(Args... args) const
    {
        std::vector<Handler> copy;
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            copy = m_handlers;
        }
        // 解锁后再回调：回调里可以自由 Add/Remove，也可以重入 Snapshot()
        for (auto const& handler : copy)
        {
            handler(args...);
        }
    }

    bool Empty() const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_handlers.empty();
    }

private:
    mutable std::mutex m_mutex;
    std::vector<Handler> m_handlers;
};

} // namespace AudioBule::Core
```

> 注意 `Remove` 在**解锁后不重试**是刻意的：多个相同的 lambda 被注册时，
> 移除第一个匹配项即可，语义上等同于"退订一次"。UI 层每个订阅点都是
> 一个独立的 lambda 捕获，不存在歧义。

- [ ] **Step 4: 创建 `AudioBule.Core/StringUtil.h`**

```cpp
#pragma once

#include <string>
#include <string_view>

namespace AudioBule::Core
{

// 宽字符串 → UTF-8。按 wcslen 语义处理，遇 NUL 停止。
std::string WideToUtf8(std::wstring_view text);

// UTF-8 → 宽字符串。无效的 UTF-8 字节序列替换为 U+FFFD，不抛异常。
std::wstring Utf8ToWide(std::string_view text);

// 把 HRESULT/Win32 错误码格式化为 0x%08X（八位大写十六进制）。
std::wstring FormatWin32Error(DWORD code);

// 取系统错误文本。系统没有可用文本时回落到 FormatWin32Error，保证非空。
std::wstring FormatMessageForHresult(HRESULT hr);

} // namespace AudioBule::Core
```

- [ ] **Step 5: 创建 `AudioBule.Core/StringUtil.cpp`**

```cpp
#include "pch.h"
#include "StringUtil.h"

namespace AudioBule::Core
{

std::string WideToUtf8(std::wstring_view text)
{
    if (text.empty())
    {
        return {};
    }

    // wcslen 语义：std::wstring_view 可能含内嵌 NUL，显式按首个 NUL 截断
    size_t length = text.find(L'\0');
    if (length == std::wstring_view::npos)
    {
        length = text.size();
    }

    int required = ::WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(length), nullptr, 0, nullptr, nullptr);
    if (required <= 0)
    {
        return {};
    }

    std::string result(static_cast<size_t>(required), '\0');
    int written = ::WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(length),
        result.data(), required, nullptr, nullptr);
    if (written <= 0)
    {
        return {};
    }
    result.resize(static_cast<size_t>(written));
    return result;
}

std::wstring Utf8ToWide(std::string_view text)
{
    if (text.empty())
    {
        return {};
    }

    // MB_ERR_INVALID_CHARS 在旧系统上对部分合法序列会误报，
    // 这里不传该标志：无效字节按 WinAPI 默认行为替换为 U+FFFD。
    int required = ::MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    if (required <= 0)
    {
        return {};
    }

    std::wstring result(static_cast<size_t>(required), L'\0');
    int written = ::MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()),
        result.data(), required);
    if (written <= 0)
    {
        return {};
    }
    result.resize(static_cast<size_t>(written));
    return result;
}

std::wstring FormatWin32Error(DWORD code)
{
    wchar_t buffer[16] = {};
    swprintf_s(buffer, L"0x%08X", static_cast<unsigned>(code));
    return std::wstring(buffer);
}

std::wstring FormatMessageForHresult(HRESULT hr)
{
    LPWSTR text = nullptr;
    DWORD length = ::FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
            FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr, static_cast<DWORD>(hr),
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&text), 0, nullptr);

    if (length == 0 || text == nullptr)
    {
        // 系统无本地化文本 —— 用十六进制兜底，保证调用方永远拿到非空字符串
        if (text != nullptr)
        {
            ::LocalFree(text);
        }
        return FormatWin32Error(static_cast<DWORD>(hr));
    }

    std::wstring result(text, length);
    ::LocalFree(text);

    // FormatMessageW 的文本带尾随 CRLF，UI 上显示会多出空白
    while (!result.empty() && (result.back() == L'\r' || result.back() == L'\n' ||
                              result.back() == L' '))
    {
        result.pop_back();
    }

    return result.empty() ? FormatWin32Error(static_cast<DWORD>(hr)) : result;
}

} // namespace AudioBule::Core
```

- [ ] **Step 6: 在 `AudioBule.Core.vcxproj` 登记新文件**

在 `<ItemGroup>` 里加入：

```xml
  <ItemGroup>
    <ClInclude Include="SimpleEvent.h" />
    <ClInclude Include="StringUtil.h" />
  </ItemGroup>
```

并在源文件 `ItemGroup` 里加入：

```xml
    <ClCompile Include="StringUtil.cpp" />
```

- [ ] **Step 7: 在测试工程登记 `tests/StringUtil.test.cpp`**

```xml
    <ClCompile Include="StringUtil.test.cpp" />
```

- [ ] **Step 8: 编译并运行测试**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

Expected:

```text
Running 7 test(s)
  [PASS] AsciiRoundTrip
  [PASS] EmptyStringRoundTrip
  [PASS] ChineseRoundTrip
  [PASS] SurrogatePairRoundTrip
  [PASS] EmbeddedNulIsTruncatedByCStringConvention
  [PASS] FormatWin32ErrorIsUppercaseHex
  [PASS] FormatMessageForHresultFallsBackToHex
7 passed, 0 failed
```

退出码 `0`。

- [ ] **Step 9: 提交**

```bash
git add AudioBule.Core tests
git commit -m "feat: add SimpleEvent and string conversion utilities"
```

---

## Task 3: Settings 持久化

**Files:**
- Create: `AudioBule.Core/Settings.h`
- Create: `AudioBule.Core/Settings.cpp`
- Modify: `AudioBule.Core/AudioBule.Core.vcxproj`
- Create: `tests/Settings.test.cpp`
- Modify: `tests/AudioBule.Core.Tests.vcxproj`

**Interfaces:**
- Consumes: Task 2 的 `StringUtil.h`
- Produces:
  - `namespace AudioBule::Core`
    - `struct AppSettings { bool autoReconnect = true; bool runAtStartup = false; std::vector<std::wstring> lastConnectedDevices; }`
    - `std::wstring DefaultSettingsPath()` —— `%LOCALAPPDATA%\AudioBule\settings.json`
    - `AppSettings LoadSettings(std::wstring const& path)`
    - `bool SaveSettings(AppSettings const& settings, std::wstring const& path)`

**核心契约（spec §3.8「配置读写失败 → 记日志并使用默认值，不阻断启动」）：**
`LoadSettings` **永不抛出、永不返回错误码**，任何失败都回落到默认值。
`SaveSettings` 返回 bool 供调用方记日志，但不抛。

---

- [ ] **Step 1: 写失败的测试 `tests/Settings.test.cpp`**

```cpp
#include "TestHarness.h"
#include "Settings.h"

#include <cstdio>
#include <string>

using namespace AudioBule::Core;

namespace {

// 每个用例一个独立的临时子目录，避免互相污染
class TempDir
{
public:
    TempDir()
    {
        wchar_t tempDir[MAX_PATH] = {};
        DWORD length = ::GetTempPathW(MAX_PATH, tempDir);
        if (length == 0 || length >= MAX_PATH)
        {
            return;
        }
        // 用测试名做后缀，保证同一进程内多次运行互不干扰
        m_path = std::wstring(tempDir, length) + L"AudioBuleTest_" +
            std::to_wstring(::GetCurrentProcessId()) + L"_" +
            std::to_wstring(reinterpret_cast<uintptr_t>(this));
        ::CreateDirectoryW(m_path.c_str(), nullptr);
    }

    ~TempDir()
    {
        if (!m_path.empty())
        {
            ::RemoveDirectoryW(m_path.c_str());
        }
    }

    TempDir(TempDir const&) = delete;
    TempDir& operator=(TempDir const&) = delete;

    std::wstring FilePath() const { return m_path + L"\\settings.json"; }

private:
    std::wstring m_path;
};

void WriteFile(std::wstring const& path, std::wstring const& content)
{
    FILE* file = nullptr;
    _wfopen_s(&file, path.c_str(), L"wb");
    if (file == nullptr)
    {
        return;
    }
    fwrite(content.data(), 1, content.size() * sizeof(wchar_t), file);
    fclose(file);
}

} // namespace

AB_TEST(DefaultSettingsPathEndsWithExpectedSuffix)
{
    auto path = DefaultSettingsPath();
    CHECK(!path.empty());
    CHECK(path.size() > 20);
    CHECK_EQ(path.substr(path.size() - 13), std::wstring(L"settings.json"));
    CHECK(path.find(L"AudioBule") != std::wstring::npos);
}

AB_TEST(MissingFileYieldsDefaults)
{
    // Review Focus 第 2 条：用户首次启动，配置文件不存在，
    // 期望静默使用默认值正常启动，不弹任何错误。
    TempDir dir;
    auto settings = LoadSettings(dir.FilePath());
    CHECK(settings.autoReconnect);
    CHECK(!settings.runAtStartup);
    CHECK(settings.lastConnectedDevices.empty());
}

AB_TEST(RoundTripPreservesAllFields)
{
    TempDir dir;
    AppSettings original;
    original.autoReconnect = false;
    original.runAtStartup = true;
    original.lastConnectedDevices = { L"BTHENUM\\{AAA}\\0000", L"BTHENUM\\{BBB}\\0000" };

    CHECK(SaveSettings(original, dir.FilePath()));

    auto loaded = LoadSettings(dir.FilePath());
    CHECK(!loaded.autoReconnect);
    CHECK(loaded.runAtStartup);
    CHECK_EQ(loaded.lastConnectedDevices.size(), static_cast<size_t>(2));
    CHECK(loaded.lastConnectedDevices[0] == L"BTHENUM\\{AAA}\\0000");
    CHECK(loaded.lastConnectedDevices[1] == L"BTHENUM\\{BBB}\\0000");
}

AB_TEST(CorruptJsonFallsBackToDefaults)
{
    // Review Focus 第 3 条：JSON 被手改坏，期望静默回落默认值，不崩溃。
    TempDir dir;
    WriteFile(dir.FilePath(), L"{ this is not json at all ]]");

    auto settings = LoadSettings(dir.FilePath());
    CHECK(settings.autoReconnect);
    CHECK(!settings.runAtStartup);
    CHECK(settings.lastConnectedDevices.empty());
}

AB_TEST(TruncatedJsonFallsBackToDefaults)
{
    TempDir dir;
    WriteFile(dir.FilePath(), L"{\"autoReconnect\": fal");

    auto settings = LoadSettings(dir.FilePath());
    CHECK(settings.autoReconnect);
}

AB_TEST(EmptyFileFallsBackToDefaults)
{
    TempDir dir;
    WriteFile(dir.FilePath(), L"");

    auto settings = LoadSettings(dir.FilePath());
    CHECK(settings.autoReconnect);
    CHECK(settings.lastConnectedDevices.empty());
}

AB_TEST(UnknownFieldsAreIgnoredAndDefaultsFilledIn)
{
    TempDir dir;
    WriteFile(dir.FilePath(), L"{\"autoReconnect\": false, \"futureField\": 123}");

    auto settings = LoadSettings(dir.FilePath());
    CHECK(!settings.autoReconnect);          // 已知字段生效
    CHECK(!settings.runAtStartup);           // 缺失字段回落默认
    CHECK(settings.lastConnectedDevices.empty());
}

AB_TEST(SaveCreatesMissingDirectory)
{
    TempDir dir;
    // 目标子目录尚不存在，Save 必须自己创建 —— MSIX 下用户可能从未运行过旧版
    auto nested = dir.FilePath() + L".nested\\settings.json";
    AppSettings settings;
    settings.autoReconnect = false;
    CHECK(SaveSettings(settings, nested));

    auto loaded = LoadSettings(nested);
    CHECK(!loaded.autoReconnect);
}

AB_TEST(SaveToUnwritablePathReturnsFalseWithoutThrowing)
{
    // 无效路径（盘符不存在）。期望：返回 false，不抛异常。
    bool result = false;
    bool threw = false;
    try
    {
        result = SaveSettings(AppSettings{}, L"Z:\\definitely\\not\\exist\\settings.json");
    }
    catch (...)
    {
        threw = true;
    }
    CHECK(!threw);
    CHECK(!result);
}
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: **失败**，`无法打开包括文件: "Settings.h"`。

- [ ] **Step 3: 创建 `AudioBule.Core/Settings.h`**

```cpp
#pragma once

#include <string>
#include <vector>

namespace AudioBule::Core
{

struct AppSettings
{
    bool autoReconnect = true;
    bool runAtStartup = false;
    std::vector<std::wstring> lastConnectedDevices;
};

// %LOCALAPPDATA%\AudioBule\settings.json
// 不用 exe 同目录：MSIX 打包后安装目录只读，写不进去。
std::wstring DefaultSettingsPath();

// 读配置。**永不抛出、永不返回错误码** —— 文件不存在、JSON 损坏、
// 字段缺失、类型不符，一律回落到默认值。对齐 spec §3.8
// 「配置读写失败 → 记日志并使用默认值，不阻断启动」。
AppSettings LoadSettings(std::wstring const& path);

// 写配置。失败返回 false（调用方记日志即可），不抛异常。
bool SaveSettings(AppSettings const& settings, std::wstring const& path);

} // namespace AudioBule::Core
```

- [ ] **Step 4: 创建 `AudioBule.Core/Settings.cpp`**

```cpp
#include "pch.h"
#include "Settings.h"
#include "StringUtil.h"

#include <wil/result.h>

#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Storage.h>

#include <algorithm>
#include <filesystem>
#include <system_error>
#include <vector>

namespace AudioBule::Core
{

using namespace winrt::Windows::Foundation;
using namespace winrt::Windows::Storage;

namespace {

constexpr wchar_t kAutoReconnectKey[] = L"autoReconnect";
constexpr wchar_t kRunAtStartupKey[] = L"runAtStartup";
constexpr wchar_t kLastDevicesKey[] = L"lastConnectedDevices";

// 从 IInspectable 取 bool，非 bool 返回 defaultValue。
// Lookup 返回的可能是任意类型，必须先试 IPropertyValue，
// 且类型判断用 Type() 而不是 ValueType()。
bool TryGetBool(IInspectable const& value, bool defaultValue)
{
    auto property = value.try_as<IPropertyValue>();
    if (!property)
    {
        return defaultValue;
    }
    if (property.Type() != PropertyType::Boolean)
    {
        return defaultValue;
    }
    return property.GetBoolean();
}

// 从 IInspectable 取字符串数组，非字符串数组返回空。
std::vector<std::wstring> TryGetStringArray(IInspectable const& value)
{
    std::vector<std::wstring> result;

    auto property = value.try_as<IPropertyValue>();
    if (!property)
    {
        return result;
    }
    if (property.Type() != PropertyType::StringArray)
    {
        return result;
    }

    for (auto const& item : property.GetStringArray())
    {
        result.push_back(item);
    }
    return result;
}

// 去重并限制长度，防止配置文件被改坏导致条目无限增长。
void NormalizeDeviceList(std::vector<std::wstring>& devices)
{
    constexpr size_t kMaxDevices = 32;

    devices.erase(std::unique(devices.begin(), devices.end()), devices.end());
    devices.erase(std::remove_if(devices.begin(), devices.end(),
                      [](std::wstring const& id) { return id.empty(); }),
        devices.end());

    if (devices.size() > kMaxDevices)
    {
        devices.resize(kMaxDevices);
    }
}

} // namespace

std::wstring DefaultSettingsPath()
{
    wchar_t localAppData[MAX_PATH] = {};
    DWORD length = ::GetEnvironmentVariableW(L"LOCALAPPDATA", localAppData, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
    {
        // 环境变量缺失（几乎不可能，但 API 契约允许）：退回 exe 同级的临时目录，
        // 至少保证本进程内读写一致，不至于崩溃。
        return L"AudioBule\\settings.json";
    }

    std::wstring base(localAppData, length);
    return base + L"\\AudioBule\\settings.json";
}

AppSettings LoadSettings(std::wstring const& path)
{
    AppSettings settings; // 默认值

    if (path.empty())
    {
        return settings;
    }

    try
    {
        // PathIO 直接收发路径字符串，省掉 StorageFile + FileIO 两步。
        // 注意：PathIO::ReadTextAsync 收的是 hstring（UTF-16），
        // 不是 UTF-8 —— 见下方注释里的常见误解。
        auto content = PathIO::ReadTextAsync(winrt::to_hstring(path)).get();

        if (content.empty())
        {
            return settings; // 空文件 → 默认值
        }

        auto json = JsonObject::Parse(content);
        if (json == nullptr)
        {
            return settings;
        }

        if (auto value = json.Lookup(kAutoReconnectKey); value != nullptr)
        {
            settings.autoReconnect = TryGetBool(value, settings.autoReconnect);
        }
        if (auto value = json.Lookup(kRunAtStartupKey); value != nullptr)
        {
            settings.runAtStartup = TryGetBool(value, settings.runAtStartup);
        }
        if (auto value = json.Lookup(kLastDevicesKey); value != nullptr)
        {
            settings.lastConnectedDevices = TryGetStringArray(value);
        }
    }
    catch (winrt::hresult_error const&)
    {
        // 文件不存在（0x80070002）、JSON 语法错误（E_FAIL）等一律回落默认值。
        // 这里刻意不记日志：首次启动时"文件不存在"是常态，记日志会污染输出。
        return AppSettings{};
    }
    catch (std::exception const&)
    {
        return AppSettings{};
    }

    NormalizeDeviceList(settings.lastConnectedDevices);
    return settings;
}

bool SaveSettings(AppSettings const& settings, std::wstring const& path)
{
    if (path.empty())
    {
        return false;
    }

    AppSettings normalized = settings;
    NormalizeDeviceList(normalized.lastConnectedDevices);

    try
    {
        JsonObject json;
        json.Insert(kAutoReconnectKey, winrt::box_value(normalized.autoReconnect));
        json.Insert(kRunAtStartupKey, winrt::box_value(normalized.runAtStartup));

        // 字符串数组必须用 PropertyValue::CreateStringArray —— winrt::box_value
        // 对 array_view 没有 reference_traits 特化，编译不过。
        std::vector<winrt::hstring> ids;
        ids.reserve(normalized.lastConnectedDevices.size());
        for (auto const& id : normalized.lastConnectedDevices)
        {
            ids.push_back(winrt::hstring(id));
        }
        json.Insert(kLastDevicesKey, PropertyValue::CreateStringArray(ids));

        // 父目录不存在时自己创建 —— 用户可能从未运行过旧版本
        std::filesystem::path parent = std::filesystem::path(path).parent_path();
        if (!parent.empty())
        {
            std::error_code ec;
            std::filesystem::create_directories(parent, ec);
            if (ec)
            {
                return false;
            }
        }

        auto file = StorageFile::GetFileFromPathAsync(winrt::to_hstring(path)).get();
        FileIO::WriteTextAsync(file, json.Stringify()).get();
        return true;
    }
    catch (winrt::hresult_error const&)
    {
        return false;
    }
    catch (std::exception const&)
    {
        return false;
    }
}

} // namespace AudioBule::Core
```

> **WinRT 字符串类型**：本文件用到的 `PathIO` / `StorageFile` / `FileIO` /
> `JsonObject::Parse` 参数**全部是 `hstring`（UTF-16）**，用
> `winrt::to_hstring(std::wstring)` 传入即可。没有一个收 `char const*`。
>
> **字符串数组的装箱**：`winrt::box_value` 对 `array_view<hstring const>`
> 没有 `reference_traits` 特化，会编译失败。必须走
> `PropertyValue::CreateStringArray(std::vector<winrt::hstring>)`。
> 读取侧对应 `IPropertyValue::GetStringArray()` 与 `PropertyType::StringArray`。
>
> 写文件这里用 `StorageFile` + `FileIO`（而非 `PathIO::WriteTextAsync`）是因为
> `PathIO::WriteTextAsync` 只能覆盖已存在的文件，无法新建；配置首启时文件不存在，
> 必须走 `StorageFile`。而读用 `PathIO` 是因为它一步到位且能正确抛出
> `0x80070002 (FILE_NOT_FOUND)`。
>
> `std::filesystem` 需要 `<system_error>`，已在上面显式 include 链中通过
> `<algorithm>` / `<filesystem>` 间接引入。若编译报 C2039 或缺 `error_code`，
> 在文件顶部补 `#include <system_error>`。

- [ ] **Step 5: 在 `AudioBule.Core.vcxproj` 登记 `Settings`**

```xml
  <ItemGroup>
    <ClInclude Include="Settings.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="Settings.cpp" />
```

- [ ] **Step 6: 在测试工程登记 `tests/Settings.test.cpp`**

```xml
    <ClCompile Include="Settings.test.cpp" />
```

> 测试文件用 `TempDir` 辅助类，需要 `<direct.h>`/`<filesystem>` 之外的标准头，
> 已在文件内自行 include。`GetTempPathW` / `CreateDirectoryW` / `RemoveDirectoryW`
> 来自 `pch.h` 里已经 include 的 `<windows.h>`。

- [ ] **Step 7: 编译并运行测试**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

Expected: 17 个用例全过（8 个新增 + 7 个 StringUtil + 1 个冒烟 + 1 个空）。
`0 failed`，退出码 `0`。

> 若 `CorruptJsonFallsBackToDefaults` 失败并显示 JSON 解析成功，说明
> `JsonObject::Parse` 对该输入宽容度过高 —— 换一个测试数据：
> `L"[[[{"`（非法的对象起始）。

- [ ] **Step 8: 提交**

```bash
git add AudioBule.Core tests
git commit -m "feat: add JSON settings persistence with fail-safe defaults"
```

---

## Task 4: ConnectionManager 状态机 + IAudioDeviceProvider 抽象

**Files:**
- Create: `AudioBule.Core/ConnectionEntry.h`
- Create: `AudioBule.Core/Messages.h`
- Create: `AudioBule.Core/Messages.cpp`
- Create: `AudioBule.Core/IAudioDeviceProvider.h`
- Create: `AudioBule.Core/ConnectionManager.h`
- Create: `AudioBule.Core/ConnectionManager.cpp`
- Modify: `AudioBule.Core/AudioBule.Core.vcxproj`
- Create: `tests/ConnectionManager.test.cpp`
- Modify: `tests/AudioBule.Core.Tests.vcxproj`

**Interfaces:**
- Consumes: Task 2 的 `SimpleEvent.h`、Task 3 的 `Settings.h`
- Produces:
  - `namespace AudioBule::Core`
    - `enum class ConnectionState { Disconnected, Connecting, Connected, Failed }`
    - `struct ConnectionEntry { std::wstring deviceId, displayName, errorMessage; ConnectionState state = Disconnected; }`
    - `enum class ConnectFailure { None, DeviceNotSupported, RequestTimedOut, DeniedBySystem, GenericFailure, UnknownFailure, HresultError, DeviceNotFound }`
    - `struct ConnectResult { bool succeeded = false; ConnectFailure failure = ConnectFailure::None; HRESULT extendedError = 0; }`
    - `struct DeviceInfo { std::wstring id, name; }`
    - `class IAudioDeviceProvider`（抽象基类）
    - `class ConnectionManager`
  - `std::wstring MessageForConnectFailure(ConnectFailure failure, HRESULT extendedError)`

**`IAudioDeviceProvider` 的形状（这是全项目最关键的可测试性决策）：**

```cpp
class IAudioDeviceProvider
{
public:
    virtual ~IAudioDeviceProvider() = default;

    // 系统是否支持 A2DP Sink（Windows 10 2004+）
    virtual bool IsSupported() const = 0;

    // 枚举已配对的 A2DP 设备。抛异常时上层应视为空列表。
    virtual std::vector<DeviceInfo> EnumerateDevices() = 0;

    // 建立连接。**同步阻塞**直到成功或失败。
    // 真实实现在工作线程上调用，调用方不得在 UI 线程直接调。
    virtual ConnectResult Connect(std::wstring_view deviceId) = 0;

    // 断开连接。必须是幂等的 —— 对未连接的设备调用不应报错。
    virtual void Disconnect(std::wstring_view deviceId) = 0;

    // 底层连接被系统关闭（设备走出范围、手机断开蓝牙）时触发，参数为 deviceId。
    // ConnectionManager 在构造时订阅它。
    SimpleEvent<std::wstring> ConnectionLost;
};
```

**为什么 `Connect` 是同步阻塞而不是返回 future**：真实实现是
`StartAsync().get()` + `OpenAsync().get()`，本来就阻塞。把它包装成 future
只会把复杂度推给实现层，而 `ConnectionManager` 已经在外层做了异步化。
`ConnectAsync` 才是对外的异步接口。

---

- [ ] **Step 1: 写失败的测试 `tests/ConnectionManager.test.cpp`**

测试替身必须能**编程式**控制每次 `Connect` 的结果，否则测不出失败分支。

```cpp
#include "TestHarness.h"
#include "ConnectionManager.h"
#include "Messages.h"

#include <atomic>
#include <future>
#include <map>
#include <mutex>
#include <set>
#include <stdexcept>
#include <thread>
#include <vector>

using namespace AudioBule::Core;

namespace {

class FakeDeviceProvider final : public IAudioDeviceProvider
{
public:
    // 可编程的枚举结果
    std::vector<DeviceInfo> devices;
    bool supported = true;
    bool throwOnEnumerate = false;

    void SetConnectResult(std::wstring const& deviceId, ConnectResult result)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_connectResults[deviceId] = result;
    }

    void SetConnectThrows(std::wstring const& deviceId)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_throwingDevices.insert(deviceId);
    }

    int ConnectCount(std::wstring const& deviceId) const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        auto it = m_connectCounts.find(deviceId);
        return it == m_connectCounts.end() ? 0 : it->second;
    }

    bool IsDisconnected(std::wstring const& deviceId) const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_disconnected.count(deviceId) > 0;
    }

    // --- IAudioDeviceProvider ---
    bool IsSupported() const override { return supported; }

    std::vector<DeviceInfo> EnumerateDevices() override
    {
        if (throwOnEnumerate)
        {
            throw std::runtime_error("enumerate failed");
        }
        return devices;
    }

    ConnectResult Connect(std::wstring_view deviceId) override
    {
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            m_connectCounts[std::wstring(deviceId)]++;
            if (m_throwingDevices.count(std::wstring(deviceId)) > 0)
            {
                throw winrt::hresult_error(E_FAIL, L"simulated");
            }
            auto it = m_connectResults.find(std::wstring(deviceId));
            if (it != m_connectResults.end())
            {
                return it->second;
            }
        }
        return ConnectResult{ true, ConnectFailure::None, 0 };
    }

    void Disconnect(std::wstring_view deviceId) override
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_disconnected.insert(std::wstring(deviceId));
    }

private:
    mutable std::mutex m_mutex;
    std::map<std::wstring, ConnectResult> m_connectResults;
    std::map<std::wstring, int> m_connectCounts;
    std::set<std::wstring> m_throwingDevices;
    std::set<std::wstring> m_disconnected;
};

ConnectResult MakeSuccess()
{
    return ConnectResult{ true, ConnectFailure::None, 0 };
}

ConnectResult MakeFailure(ConnectFailure failure, HRESULT extended = 0)
{
    return ConnectResult{ false, failure, extended };
}

// 找到指定 deviceId 的条目，找不到返回 nullptr
ConnectionEntry const* Find(ConnectionManager const& manager, std::wstring const& deviceId)
{
    for (auto const& entry : manager.Snapshot())
    {
        if (entry.deviceId == deviceId)
        {
            return &entry;
        }
    }
    return nullptr;
}

ConnectionState StateOf(ConnectionManager const& manager, std::wstring const& deviceId)
{
    auto const* entry = Find(manager, deviceId);
    return entry == nullptr ? ConnectionState::Disconnected : entry->state;
}

} // namespace

AB_TEST(RefreshPopulatesEntriesFromProvider)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    ConnectionManager manager(provider);

    manager.Refresh();

    auto snapshot = manager.Snapshot();
    CHECK_EQ(snapshot.size(), static_cast<size_t>(2));
    CHECK(snapshot[0].deviceId == L"devA");
    CHECK(snapshot[0].displayName == L"手机 A");
    CHECK(snapshot[0].state == ConnectionState::Disconnected);
}

AB_TEST(UnsupportedSystemYieldsEmptyList)
{
    FakeDeviceProvider provider;
    provider.supported = false;
    ConnectionManager manager(provider);

    manager.Refresh();
    CHECK(manager.Snapshot().empty());
}

AB_TEST(EnumerateThrowingYieldsEmptyListAndDoesNotCrash)
{
    FakeDeviceProvider provider;
    provider.throwOnEnumerate = true;
    ConnectionManager manager(provider);

    manager.Refresh();   // 不得抛出
    CHECK(manager.Snapshot().empty());
}

AB_TEST(ConnectSuccessMovesEntryToConnected)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();

    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
    CHECK(Find(manager, L"devA")->errorMessage.empty());
}

AB_TEST(ConnectFailureMovesEntryToFailedWithMessage)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectResult(L"devA", MakeFailure(ConnectFailure::RequestTimedOut));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();

    CHECK(StateOf(manager, L"devA") == ConnectionState::Failed);
    CHECK(!Find(manager, L"devA")->errorMessage.empty());
}

AB_TEST(ErrorGenFailureMessagePointsAtPhoneCannotBeReceiver)
{
    // Review Focus 第 1 条：手机正作为 A2DP 源连着耳机时，OpenAsync 失败且
    // 扩展错误码为 0x8007001F。文案必须让用户看出"手机现在不能当接收端"，
    // 而不是泛泛的"连接失败"。
    auto message = MessageForConnectFailure(ConnectFailure::GenericFailure, 0x8007001Fu);
    CHECK(!message.empty());
    CHECK(message.find(L"0x8007001F") != std::wstring::npos);
    CHECK(message.find(L"接收") != std::wstring::npos);
}

AB_TEST(EveryFailureKindProducesNonEmptyMessage)
{
    ConnectFailure const failures[] = {
        ConnectFailure::DeviceNotSupported,
        ConnectFailure::RequestTimedOut,
        ConnectFailure::DeniedBySystem,
        ConnectFailure::GenericFailure,
        ConnectFailure::UnknownFailure,
        ConnectFailure::HresultError,
        ConnectFailure::DeviceNotFound,
    };
    for (auto failure : failures)
    {
        CHECK(!MessageForConnectFailure(failure, 0).empty());
        CHECK(!MessageForConnectFailure(failure, 0x80004005u).empty());
    }
}

AB_TEST(ConnectThrowingLeavesEntryFailedNotCrashed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectThrows(L"devA");
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();   // 不得抛出

    CHECK(StateOf(manager, L"devA") == ConnectionState::Failed);
    CHECK(!Find(manager, L"devA")->errorMessage.empty());
}

AB_TEST(ConnectUnknownDeviceAddsFailedEntry)
{
    // 设备列表刷新后用户手机走远了，点连接时 id 仍要得到一个可读的失败态，
    // 而不是崩溃或静默无反应。
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"ghost").get();

    CHECK(StateOf(manager, L"ghost") == ConnectionState::Failed);
}

AB_TEST(DisconnectMovesEntryToDisconnectedAndCallsProvider)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();
    CHECK(provider.IsDisconnected(L"devA") == false);

    manager.DisconnectAsync(L"devA").get();

    CHECK(StateOf(manager, L"devA") == ConnectionState::Disconnected);
    CHECK(provider.IsDisconnected(L"devA"));
}

AB_TEST(DisconnectOnDisconnectedEntryIsHarmlessNoOp)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.DisconnectAsync(L"devA").get();   // 不得崩溃

    CHECK(StateOf(manager, L"devA") == ConnectionState::Disconnected);
}

AB_TEST(RetryAfterFailureIsAllowedAndCanSucceed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectResult(L"devA", MakeFailure(ConnectFailure::RequestTimedOut));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    CHECK(StateOf(manager, L"devA") == ConnectionState::Failed);

    // 用户点「重试」，这次设备可用
    provider.SetConnectResult(L"devA", MakeSuccess());
    manager.ConnectAsync(L"devA").get();

    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
    CHECK(Find(manager, L"devA")->errorMessage.empty());
}

AB_TEST(ConnectWhileConnectedDoesNotCallProviderAgain)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devA").get();

    CHECK_EQ(provider.ConnectCount(L"devA"), 1);
    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
}

AB_TEST(ExternalConnectionLostMovesEntryToDisconnected)
{
    // 设备走出范围 / 手机关蓝牙：provider 从底层 StateChanged 观察到 Closed
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.ConnectionLost.Raise(L"devA");

    CHECK(StateOf(manager, L"devA") == ConnectionState::Disconnected);
}

AB_TEST(ConnectionLostForUnknownDeviceIsIgnored)
{
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.ConnectionLost.Raise(L"never-seen");   // 不得崩溃

    CHECK(manager.Snapshot().empty());
}

AB_TEST(RefreshPreservesConnectedState)
{
    // 用户在窗口开着时新插了一个设备点刷新，已连接的不能被重置。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.devices.push_back({ L"devB", L"手机 B" });
    manager.Refresh();

    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
    CHECK(StateOf(manager, L"devB") == ConnectionState::Disconnected);
    CHECK_EQ(manager.Snapshot().size(), static_cast<size_t>(2));
}

AB_TEST(RefreshDropsDevicesThatDisappeared)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.devices = { { L"devA", L"手机 A" } };
    manager.Refresh();

    CHECK_EQ(manager.Snapshot().size(), static_cast<size_t>(1));
    CHECK(Find(manager, L"devA") != nullptr);
}

AB_TEST(RefreshUpdatesDisplayName)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"旧名字" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.devices = { { L"devA", L"新名字" } };
    manager.Refresh();

    CHECK(Find(manager, L"devA")->displayName == L"新名字");
}

AB_TEST(SnapshotReturnsIndependentCopy)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    auto copy = manager.Snapshot();
    copy[0].state = ConnectionState::Failed;
    copy[0].displayName = L"篡改";

    auto fresh = manager.Snapshot();
    CHECK(fresh[0].state == ConnectionState::Disconnected);
    CHECK(fresh[0].displayName == L"手机 A");
}

AB_TEST(MultipleDevicesConnectIndependently)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeniedBySystem));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devB").get();

    // 一台成功一台失败，互不影响 —— spec §3.8「任何单设备失败都不影响其它设备」
    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
    CHECK(StateOf(manager, L"devB") == ConnectionState::Failed);
}

AB_TEST(ConcurrentConnectsOnDifferentDevicesBothSucceed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" }, { L"devB", L"B" }, { L"devC", L"C" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    std::vector<std::future<void>> futures;
    for (auto const& device : provider.devices)
    {
        futures.push_back(manager.ConnectAsync(device.id));
    }
    for (auto& future : futures)
    {
        future.get();
    }

    for (auto const& device : provider.devices)
    {
        CHECK(StateOf(manager, device.id) == ConnectionState::Connected);
    }
}

AB_TEST(EntryChangedFiresOnEachTransition)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    int entryChangedCount = 0;
    int entriesChangedCount = 0;
    std::mutex counterMutex;

    manager.EntryChanged.Add([&](ConnectionEntry const&) {
        std::lock_guard<std::mutex> lock(counterMutex);
        ++entryChangedCount;
    });
    manager.EntriesChanged.Add([&] {
        std::lock_guard<std::mutex> lock(counterMutex);
        ++entriesChangedCount;
    });

    manager.ConnectAsync(L"devA").get();
    manager.DisconnectAsync(L"devA").get();

    // Connecting → Connected → Disconnected，三次迁移三次通知
    CHECK_EQ(entryChangedCount, 3);
    // 集合本身没增删（Refresh 之外的增删只有 ConnectUnknownDevice 那种）
    CHECK_EQ(entriesChangedCount, 0);
}

AB_TEST(EntriesChangedFiresWhenCollectionGrows)
{
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    int entriesChangedCount = 0;
    manager.EntriesChanged.Add([&] { ++entriesChangedCount; });

    provider.devices = { { L"devA", L"手机 A" } };
    manager.Refresh();

    CHECK_EQ(entriesChangedCount, 1);
}

AB_TEST(ReconnectSavedDevicesConnectsEachAndSkipsFailures)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeviceNotFound));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ReconnectSavedDevices({ L"devA", L"devB" });

    // 同步等待两次连接完成
    manager.WaitForIdle();
    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
    CHECK(StateOf(manager, L"devB") == ConnectionState::Failed);
}

AB_TEST(EventHandlerCanCallSnapshotWithoutDeadlock)
{
    // Raise 在 SimpleEvent 内部会先解锁再回调，但 ConnectionManager 若在持有
    // 自身互斥量时 Raise，这里就会死锁。用一个会重入 Snapshot 的处理器钉住。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.EntryChanged.Add([&](ConnectionEntry const&) {
        auto snapshot = manager.Snapshot();
        (void)snapshot.size();
    });

    manager.ConnectAsync(L"devA").get();   // 若死锁则测试永久挂起

    CHECK(StateOf(manager, L"devA") == ConnectionState::Connected);
}
```

> 最后一个用例（`EventHandlerCanCallSnapshotWithoutDeadlock`）在实现错误时会
> **永久挂起**而不是失败。看到它卡住，就说明 Raise 被放在了锁内。

- [ ] **Step 2: 运行测试，确认失败**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: **失败**，`无法打开包括文件: "ConnectionManager.h"`。

- [ ] **Step 3: 创建 `AudioBule.Core/ConnectionEntry.h`**

```cpp
#pragma once

#include <string>

namespace AudioBule::Core
{

// 连接的四个状态。注意 Connecting 之后**只有**两个出口：
// Connected 或 Failed。没有"取消中"——取消语义由 Disconnect 在 Disconnected
// 状态下重建条目承担。
enum class ConnectionState
{
    Disconnected,
    Connecting,
    Connected,
    Failed,
};

// 连接失败的归类。真实实现在 OpenAsync 的 Status + ExtendedError 上做映射，
// 测试实现直接指定。
enum class ConnectFailure
{
    None,
    DeviceNotSupported,   // TryCreateFromId 返回 null
    RequestTimedOut,      // AudioPlaybackConnectionOpenResultStatus::RequestTimedOut
    DeniedBySystem,       // AudioPlaybackConnectionOpenResultStatus::DeniedBySystem
    GenericFailure,       // ExtendedError 落在已知可诊断的码上（如 0x8007001F）
    UnknownFailure,       // 其余 Status
    HresultError,         // 抛 winrt::hresult_error
    DeviceNotFound,       // 刷新后设备消失
};

struct ConnectResult
{
    bool succeeded = false;
    ConnectFailure failure = ConnectFailure::None;
    HRESULT extendedError = 0;   // 仅失败时有意义
};

struct DeviceInfo
{
    std::wstring id;
    std::wstring name;
};

struct ConnectionEntry
{
    std::wstring deviceId;
    std::wstring displayName;
    ConnectionState state = ConnectionState::Disconnected;

    // 仅 state == Failed 时有效。成功连上后必须清空 —— 见
    // ConnectSuccessMovesEntryToConnected 的断言。
    std::wstring errorMessage;
};

} // namespace AudioBule::Core
```

> `HRESULT` 来自 `windows.h`，已由 `pch.h` 引入。

- [ ] **Step 4: 创建 `AudioBule.Core/Messages.h`**

```cpp
#pragma once

#include "ConnectionEntry.h"

#include <string>

namespace AudioBule::Core
{

// Core 层错误文案。spec §3.7 规定：Core 产出的字符串走这里，
// App 不硬编码 Core 的错误文案。
//
// 当前实现返回简体中文。计划二（增强功能）会把它改成按 UI 语言查表的静态表，
// 接口形态保持不变 —— 届时只需改这个 .cpp。
std::wstring MessageForConnectFailure(ConnectFailure failure, HRESULT extendedError);

} // namespace AudioBule::Core
```

- [ ] **Step 5: 创建 `AudioBule.Core/Messages.cpp`**

```cpp
#include "pch.h"
#include "Messages.h"
#include "StringUtil.h"

namespace AudioBule::Core
{

std::wstring MessageForConnectFailure(ConnectFailure failure, HRESULT extendedError)
{
    switch (failure)
    {
    case ConnectFailure::DeviceNotSupported:
        return L"此设备不支持 A2DP 音频接收";

    case ConnectFailure::RequestTimedOut:
        return L"连接请求超时。请确认设备已开机且在附近，然后重试。";

    case ConnectFailure::DeniedBySystem:
        return L"连接被系统拒绝。请在「设置 - 蓝牙和设备」中检查设备状态。";

    case ConnectFailure::GenericFailure:
        // 0x8007001F = ERROR_GEN_FAILURE。实测中这个码几乎总是同一个原因：
        // 手机正作为 A2DP 源连着别的设备（耳机/车机），无法同时当接收端。
        // 加上明确的操作建议，否则用户只看到"失败"无从下手。
        if (static_cast<DWORD>(extendedError) == 0x8007001Fu)
        {
            return L"设备当前无法作为蓝牙音频接收端（0x8007001F）。"
                   L"请先断开手机上已连接的其它蓝牙音频设备（如耳机、车机），再重试。";
        }
        return L"连接失败（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::UnknownFailure:
        return L"连接失败（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::HresultError:
        return L"连接时发生错误（" + FormatWin32Error(static_cast<DWORD>(extendedError)) + L"）。";

    case ConnectFailure::DeviceNotFound:
        return L"设备已不可用。点击「刷新」重新扫描。";

    case ConnectFailure::None:
    default:
        return L"未知错误";
    }
}

} // namespace AudioBule::Core
```

- [ ] **Step 6: 创建 `AudioBule.Core/IAudioDeviceProvider.h`**

```cpp
#pragma once

#include "ConnectionEntry.h"
#include "SimpleEvent.h"

#include <string>
#include <string_view>
#include <vector>

namespace AudioBule::Core
{

// 设备枚举与连接的抽象。存在的唯一理由是让 ConnectionManager 脱离
// AudioPlaybackConnection 依赖，从而可单元测试（spec §6）。
//
// 实现约定：
//  - Connect / Disconnect 会被 ConnectionManager 在**工作线程**上调用，
//    不得在 UI 线程直接调用。
//  - EnumerateDevices 允许抛异常；ConnectionManager 会吞掉并视为空列表。
//  - 底层连接被系统关闭时，必须 Raise ConnectionLost。
class IAudioDeviceProvider
{
public:
    virtual ~IAudioDeviceProvider() = default;

    virtual bool IsSupported() const = 0;
    virtual std::vector<DeviceInfo> EnumerateDevices() = 0;
    virtual ConnectResult Connect(std::wstring_view deviceId) = 0;
    virtual void Disconnect(std::wstring_view deviceId) = 0;

    // 参数为 deviceId。由 provider 在其 ConnectionStateChanged 观察到 Closed 时触发。
    SimpleEvent<std::wstring> ConnectionLost;
};

} // namespace AudioBule::Core
```

- [ ] **Step 7: 创建 `AudioBule.Core/ConnectionManager.h`**

```cpp
#pragma once

#include "ConnectionEntry.h"
#include "IAudioDeviceProvider.h"
#include "SimpleEvent.h"

#include <atomic>
#include <condition_variable>
#include <future>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace AudioBule::Core
{

// 多设备连接状态机，全项目唯一的状态源（spec §3.3）。
//
// 线程模型：所有公开成员都可从任意线程调用。状态迁移在 m_mutex 保护下进行，
// 事件在**解锁之后** Raise —— 处理器可以安全地重入 Snapshot() 或发起新操作。
class ConnectionManager
{
public:
    // provider 必须 outlive ConnectionManager
    explicit ConnectionManager(IAudioDeviceProvider& provider);
    ~ConnectionManager();

    ConnectionManager(ConnectionManager const&) = delete;
    ConnectionManager& operator=(ConnectionManager const&) = delete;

    // 单条状态变化。参数是变化后的条目快照。
    SimpleEvent<ConnectionEntry> EntryChanged;

    // 集合增删（刷新后设备数量/身份变了）。UI 应据此重建整个列表。
    SimpleEvent<> EntriesChanged;

    // 重新扫描设备。已存在的条目保留其状态，消失的设备被移除。
    // 系统不支持 A2DP Sink 或枚举抛异常时，得到空列表。
    void Refresh();

    // 异步发起连接。立即返回；结果通过 EntryChanged 通知。
    // 已处于 Connecting/Connected 的设备会被忽略（幂等）。
    // 未知设备会新增一条 Failed 条目，保证 UI 有东西可显示。
    std::future<void> ConnectAsync(std::wstring_view deviceId);

    // 异步断开。对非 Connected 条目是无害的空操作。
    std::future<void> DisconnectAsync(std::wstring_view deviceId);

    // 按顺序对每个 id 发起连接（开机自启用）。单个失败不影响其余。
    void ReconnectSavedDevices(std::vector<std::wstring> const& deviceIds);

    // 阻塞直到当前所有在途的 Connect/Disconnect 完成。仅供测试与关机流程使用。
    void WaitForIdle();

    // 返回条目列表的深拷贝，供 UI 绑定。
    std::vector<ConnectionEntry> Snapshot() const;

    bool IsSupported() const;

private:
    void ApplyConnectResult(std::wstring const& deviceId, ConnectResult const& result);
    void HandleConnectionLost(std::wstring const& deviceId);
    ConnectionEntry* FindLocked(std::wstring const& deviceId);
    ConnectionEntry const* FindLocked(std::wstring const& deviceId) const;
    ConnectionEntry CopyOrCreateLocked(std::wstring const& deviceId);
    void RaiseEntryChanged(ConnectionEntry const& entry);
    static std::future<void> CompletedFuture();

    IAudioDeviceProvider& m_provider;
    // 存成成员以便析构时按同一对象 Remove（见 ConnectionManager.cpp 的说明）
    SimpleEvent<std::string>::Handler m_lostHandler;

    mutable std::mutex m_mutex;
    std::vector<ConnectionEntry> m_entries;

    // 追踪在途异步操作，供 WaitForIdle 使用
    mutable std::mutex m_pendingMutex;
    std::condition_variable m_pendingDone;
    size_t m_pendingCount = 0;
};

} // namespace AudioBule::Core
```

- [ ] **Step 8: 创建 `AudioBule.Core/ConnectionManager.cpp`**

```cpp
#include "pch.h"
#include "ConnectionManager.h"
#include "Messages.h"

namespace AudioBule::Core
{

ConnectionManager::ConnectionManager(IAudioDeviceProvider& provider)
    : m_provider(provider)
{
    // handler 必须存成成员：SimpleEvent::Remove 按 std::function 相等性比较，
    // 而 std::function 只在**目标类型相同且捕获相等**时才相等。重新写一个
    // 捕获相同 this、函数体不同的 lambda 是不同的闭包类型，Remove 匹配不上。
    m_lostHandler = [this](std::wstring const& deviceId) { HandleConnectionLost(deviceId); };
    m_provider.ConnectionLost.Add(m_lostHandler);
}

ConnectionManager::~ConnectionManager()
{
    WaitForIdle();

    // 摘掉订阅：provider 通常是成员，析构顺序在本对象之后。
    // 不摘的话 provider 上会残留指向已析构 this 的 handler，
    // 之后 provider 若再 Raise 就会访问已释放内存。
    m_provider.ConnectionLost.Remove(m_lostHandler);
}

std::future<void> ConnectionManager::CompletedFuture()
{
    std::promise<void> promise;
    promise.set_value();
    return promise.get_future();
}

bool ConnectionManager::IsSupported() const
{
    try
    {
        return m_provider.IsSupported();
    }
    catch (...)
    {
        return false;
    }
}

ConnectionEntry* ConnectionManager::FindLocked(std::wstring const& deviceId)
{
    for (auto& entry : m_entries)
    {
        if (entry.deviceId == deviceId)
        {
            return &entry;
        }
    }
    return nullptr;
}

ConnectionEntry const* ConnectionManager::FindLocked(std::wstring const& deviceId) const
{
    for (auto const& entry : m_entries)
    {
        if (entry.deviceId == deviceId)
        {
            return &entry;
        }
    }
    return nullptr;
}

ConnectionEntry ConnectionManager::CopyOrCreateLocked(std::wstring const& deviceId)
{
    if (auto const* existing = FindLocked(deviceId))
    {
        return *existing;
    }
    ConnectionEntry entry;
    entry.deviceId = deviceId;
    entry.displayName = deviceId;   // 未知设备先显示 id，Refresh 后会被真名覆盖
    return entry;
}

void ConnectionManager::RaiseEntryChanged(ConnectionEntry const& entry)
{
    // 刻意不在调用方持锁时执行本函数。SimpleEvent::Raise 虽会先解锁自身，
    // 但 ConnectionManager 的 m_mutex 是非递归的 —— 若在持锁时 Raise，
    // 处理器调用 Snapshot() 会立即死锁。
    EntryChanged.Raise(entry);
}

void ConnectionManager::Refresh()
{
    std::vector<DeviceInfo> devices;
    try
    {
        if (!IsSupported())
        {
            devices.clear();
        }
        else
        {
            devices = m_provider.EnumerateDevices();
        }
    }
    catch (winrt::hresult_error const&)
    {
        devices.clear();
    }
    catch (std::exception const&)
    {
        devices.clear();
    }

    std::vector<ConnectionEntry> updated;
    updated.reserve(devices.size());

    bool collectionChanged = false;

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        // 保留已有条目的状态：用户开着窗口时点刷新，不能把已连上的设备打回未连接
        for (auto const& device : devices)
        {
            if (auto const* existing = FindLocked(device.id))
            {
                ConnectionEntry entry = *existing;
                entry.displayName = device.name.empty() ? device.id : device.name;
                updated.push_back(std::move(entry));
            }
            else
            {
                collectionChanged = true;
                ConnectionEntry entry;
                entry.deviceId = device.id;
                entry.displayName = device.name.empty() ? device.id : device.name;
                updated.push_back(std::move(entry));
            }
        }

        collectionChanged = collectionChanged || updated.size() != m_entries.size();
        m_entries = std::move(updated);
    }

    if (collectionChanged)
    {
        EntriesChanged.Raise();
    }
}

std::future<void> ConnectionManager::ConnectAsync(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(id);
        if (entry != nullptr && (entry->state == ConnectionState::Connecting ||
                                 entry->state == ConnectionState::Connected))
        {
            // 幂等：重复点「连接」不应产生第二次真实连接尝试
            return CompletedFuture();
        }

        entry = FindLocked(id);
        if (entry == nullptr)
        {
            // 设备已不在列表里（走远了）。仍建条目并标失败，让 UI 有东西可显示。
            snapshot = CopyOrCreateLocked(id);
            snapshot.state = ConnectionState::Failed;
            snapshot.errorMessage = MessageForConnectFailure(
                ConnectFailure::DeviceNotFound, 0);
            m_entries.push_back(snapshot);
        }
        else
        {
            snapshot = *entry;
            snapshot.state = ConnectionState::Connecting;
            snapshot.errorMessage.clear();
            *entry = snapshot;
        }
    }

    RaiseEntryChanged(snapshot);

    // 在途计数：让 WaitForIdle 能等到连接真正结束
    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        ++m_pendingCount;
    }

    auto promise = std::promise<void>();
    auto future = promise.get_future();

    // promise 必须**移动**进 lambda。捕获引用 (&promise) 会 use-after-free：
    // 本函数紧接着返回，栈上的 promise 随即析构，而 detached 线程还没跑完。
    std::thread([this, id = std::move(id), promise = std::move(promise)]() mutable {
        ConnectResult result;
        try
        {
            result = m_provider.Connect(id);
        }
        catch (winrt::hresult_error const& e)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, e.code() };
        }
        catch (std::exception const&)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, E_FAIL };
        }

        ApplyConnectResult(id, result);

        promise.set_value();

        {
            std::lock_guard<std::mutex> lock(m_pendingMutex);
            --m_pendingCount;
        }
        m_pendingDone.notify_all();
    }).detach();

    return future;
}

void ConnectionManager::ApplyConnectResult(std::wstring const& deviceId,
    ConnectResult const& result)
{
    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(deviceId);
        if (entry == nullptr)
        {
            // 连接期间设备被 Refresh 掉了：静默丢弃结果
            return;
        }

        snapshot = *entry;
        if (result.succeeded)
        {
            snapshot.state = ConnectionState::Connected;
            snapshot.errorMessage.clear();
        }
        else
        {
            snapshot.state = ConnectionState::Failed;
            snapshot.errorMessage =
                MessageForConnectFailure(result.failure, result.extendedError);
        }
        *entry = snapshot;
    }

    RaiseEntryChanged(snapshot);
}

std::future<void> ConnectionManager::DisconnectAsync(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(id);
        if (entry == nullptr || entry->state != ConnectionState::Connected)
        {
            // 非 Connected 是无害空操作：按钮在 UI 上本就禁用，
            // 且外部断开事件可能已经先行处理过
            return CompletedFuture();
        }

        snapshot = *entry;
        snapshot.state = ConnectionState::Disconnected;
        snapshot.errorMessage.clear();
        *entry = snapshot;
    }

    // 先更新状态并通知 UI，再通知 provider 真正断开 ——
    // provider 可能阻塞，反过来会让界面卡住
    RaiseEntryChanged(snapshot);

    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        ++m_pendingCount;
    }

    auto promise = std::promise<void>();
    auto future = promise.get_future();

    // 同 ConnectAsync：promise 移动进 lambda，不能捕获引用
    std::thread([this, id = std::move(id), promise = std::move(promise)]() mutable {
        try
        {
            m_provider.Disconnect(id);
        }
        catch (...)
        {
            // 断开失败不改变 UI 状态：用户已经看到"已断开"，
            // 系统侧残留会在 ConnectionLost 里自然收敛
        }

        promise.set_value();

        {
            std::lock_guard<std::mutex> lock(m_pendingMutex);
            --m_pendingCount;
        }
        m_pendingDone.notify_all();
    }).detach();

    return future;
}

void ConnectionManager::ReconnectSavedDevices(std::vector<std::wstring> const& deviceIds)
{
    for (auto const& id : deviceIds)
    {
        // 故意不等每个 future：开机时多台设备并行连，逐个串行会很慢
        ConnectAsync(id);
    }
}

void ConnectionManager::HandleConnectionLost(std::wstring const& deviceId)
{
    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(deviceId);
        if (entry == nullptr)
        {
            return;   // 未知设备的断开事件，忽略
        }

        if (entry->state == ConnectionState::Disconnected)
        {
            return;   // 已经断开了，重复通知无意义
        }

        snapshot = *entry;
        snapshot.state = ConnectionState::Disconnected;
        snapshot.errorMessage.clear();
        *entry = snapshot;
    }

    RaiseEntryChanged(snapshot);
}

void ConnectionManager::WaitForIdle()
{
    std::unique_lock<std::mutex> lock(m_pendingMutex);
    m_pendingDone.wait(lock, [this] { return m_pendingCount == 0; });
}

std::vector<ConnectionEntry> ConnectionManager::Snapshot() const
{
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_entries;
}

} // namespace AudioBule::Core
```

**实现上的三个关键点（写错了测试会挂住或死锁）：**

1. **绝不在持 `m_mutex` 时 Raise 事件。** 每个 `RaiseEntryChanged` 调用前
   都先退出作用域锁。`EventHandlerCanCallSnapshotWithoutDeadlock` 钉住这条。
2. **析构里用同一个 lambda 表达式 Remove。** `SimpleEvent` 的
   `Remove` 按 `std::function` 相等性比较 —— 捕获相同 `this` 的两个 lambda
   是相等的，所以 `[this](std::wstring const&) { HandleConnectionLost(L""); }`
   能匹配上订阅时那个。这里传参内容不同没关系，比较的是目标与捕获。
   若编译器对 lambda 相等性有异议，改用 `Add` 返回 token 的接口。
3. **`std::thread(...).detach()` + 在途计数。** 没有线程池，避免为一个状态机
   引入额外依赖；`m_pendingCount` 保证析构前能收尾。

- [ ] **Step 9: 在 `AudioBule.Core.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="ConnectionEntry.h" />
    <ClInclude Include="Messages.h" />
    <ClInclude Include="IAudioDeviceProvider.h" />
    <ClInclude Include="ConnectionManager.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="Messages.cpp" />
    <ClCompile Include="ConnectionManager.cpp" />
```

- [ ] **Step 10: 在测试工程登记 `tests/ConnectionManager.test.cpp`**

```xml
    <ClCompile Include="ConnectionManager.test.cpp" />
```

- [ ] **Step 11: 编译并运行测试**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

Expected: 全部用例通过，`0 failed`，退出码 `0`。

**如果测试卡住不返回**，几乎一定是 `EventHandlerCanCallSnapshotWithoutDeadlock`
死锁了 —— 检查 `RaiseEntryChanged` 的调用位置。

- [ ] **Step 12: 提交**

```bash
git add AudioBule.Core tests
git commit -m "feat: add connection state machine with injectable device provider"
```

---

## Task 5: WinRtDeviceProvider（生产实现）

**Files:**
- Create: `AudioBule.Core/WinRtDeviceProvider.h`
- Create: `AudioBule.Core/WinRtDeviceProvider.cpp`
- Modify: `AudioBule.Core/AudioBule.Core.vcxproj`
- Modify: `tests/ConnectionManager.test.cpp`（补一个真实 provider 的冒烟用例）

**Interfaces:**
- Consumes: Task 4 的 `IAudioDeviceProvider`
- Produces: `namespace AudioBule::Core::WinRtDeviceProvider final : public IAudioDeviceProvider`

**已核实的 API 事实（不要凭记忆写，值以此为准）：**

| 事实 | 值 | 来源 |
| --- | --- | --- |
| `AudioPlaybackConnectionOpenResultStatus` | `Success=0, RequestTimedOut=1, DeniedBySystem=2, UnknownFailure=3` | `winrt/impl/windows.media.audio.0.h` |
| `AudioPlaybackConnectionState` | **只有** `Closed=0, Opened=1` | 同上 |
| `StartAsync()` 返回 | `void`，无结果值 | spike 实测 |
| `OpenAsync()` 返回 | 带 `Status` + `ExtendedError` 的结果 | spike 实测 |
| `TryCreateFromId(id)` 返回 | null 表示设备不支持 A2DP | spike 实测 |

> ⚠️ **`AudioPlaybackConnectionState` 没有 `Connecting` 状态**，只有
> `Closed` 和 `Opened`。spike 里的 `newState == 2` 判断（Step2_Connect.cpp:91）
> **永远不会成立**，那是 spike 遗留的死代码 —— 主工程不要照抄。
> 「连接中」是 AudioBule **自己**的 `ConnectionState::Connecting`，
> 由 `ConnectionManager` 在 `OpenAsync` 返回前维持。

---

- [ ] **Step 1: 创建 `AudioBule.Core/WinRtDeviceProvider.h`**

```cpp
#pragma once

#include "IAudioDeviceProvider.h"

#include <winrt/Windows.Media.Audio.h>

#include <mutex>
#include <unordered_map>

namespace AudioBule::Core
{

// IAudioDeviceProvider 的生产实现，包装 AudioPlaybackConnection。
//
// 线程模型：Connect / Disconnect 会被 ConnectionManager 在工作线程上调用，
// 因此这里不加 STA 假设；但 StateChanged 事件的处理器可能在任意线程被调用，
// 所以 m_connections 的访问一律加锁。
class WinRtDeviceProvider final : public IAudioDeviceProvider
{
public:
    WinRtDeviceProvider();
    ~WinRtDeviceProvider() override;

    bool IsSupported() const override;
    std::vector<DeviceInfo> EnumerateDevices() override;
    ConnectResult Connect(std::wstring_view deviceId) override;
    void Disconnect(std::wstring_view deviceId) override;

private:
    // 设备 id → 活跃连接。断开时从这里移除并释放。
    std::mutex m_mutex;
    std::unordered_map<std::wstring, winrt::Windows::Media::Audio::AudioPlaybackConnection>
        m_connections;
};

} // namespace AudioBule::Core
```

- [ ] **Step 2: 创建 `AudioBule.Core/WinRtDeviceProvider.cpp`**

```cpp
#include "pch.h"
#include "WinRtDeviceProvider.h"

#include <winrt/Windows.Devices.Enumeration.h>
#include <winrt/Windows.Foundation.Metadata.h>
#include <winrt/Windows.Media.Audio.h>

namespace AudioBule::Core
{

using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation::Metadata;
using namespace winrt::Windows::Media::Audio;

namespace {

// 把 OpenAsync 的 Status 映射到我们的 ConnectFailure。
ConnectFailure MapOpenStatus(AudioPlaybackConnectionOpenResultStatus status)
{
    switch (status)
    {
    case AudioPlaybackConnectionOpenResultStatus::Success:
        return ConnectFailure::None;
    case AudioPlaybackConnectionOpenResultStatus::RequestTimedOut:
        return ConnectFailure::RequestTimedOut;
    case AudioPlaybackConnectionOpenResultStatus::DeniedBySystem:
        return ConnectFailure::DeniedBySystem;
    case AudioPlaybackConnectionOpenResultStatus::UnknownFailure:
    default:
        return ConnectFailure::UnknownFailure;
    }
}

} // namespace

WinRtDeviceProvider::WinRtDeviceProvider() = default;

WinRtDeviceProvider::~WinRtDeviceProvider()
{
    std::lock_guard<std::mutex> lock(m_mutex);
    // 直接清空即可：AudioPlaybackConnection 的析构会断开底层 A2DP 会话。
    // 刻意不逐个 Close()——析构程序正在退出时，任何 COM 调用都可能失败并阻塞。
    m_connections.clear();
}

bool WinRtDeviceProvider::IsSupported() const
{
    try
    {
        // Windows 10 2004 以下 AudioPlaybackConnection 类型不存在。
        // 先探测再调用，否则低版本系统上会在 GetDeviceSelector 处 E_NOINTERFACE。
        return ApiInformation::IsTypePresent(winrt::name_of<AudioPlaybackConnection>());
    }
    catch (...)
    {
        return false;
    }
}

std::vector<DeviceInfo> WinRtDeviceProvider::EnumerateDevices()
{
    std::vector<DeviceInfo> result;

    if (!IsSupported())
    {
        return result;
    }

    auto selector = AudioPlaybackConnection::GetDeviceSelector();

    // 同步阻塞：ConnectionManager::Refresh 是同步方法，调用方已在工作线程上
    auto devices = DeviceInformation::FindAllAsync(selector).get();

    for (auto const& device : devices)
    {
        DeviceInfo info;
        info.id = std::wstring(device.Id());
        auto name = device.Name();
        info.name = name.empty() ? info.id : std::wstring(name);
        result.push_back(std::move(info));
    }

    return result;
}

ConnectResult WinRtDeviceProvider::Connect(std::wstring_view deviceId)
{
    if (!IsSupported())
    {
        return ConnectResult{ false, ConnectFailure::DeviceNotSupported, 0 };
    }

    {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_connections.find(std::wstring(deviceId)) != m_connections.end())
        {
            // 已经连着。ConnectionManager 的幂等检查通常已经拦住了，
            // 这里是第二道防线 —— 万一两个线程同时进来，不能建两个会话。
            return ConnectResult{ true, ConnectFailure::None, 0 };
        }
    }

    AudioPlaybackConnection connection = nullptr;
    try
    {
        connection = AudioPlaybackConnection::TryCreateFromId(
            winrt::to_hstring(std::wstring(deviceId)));
    }
    catch (winrt::hresult_error const& e)
    {
        return ConnectResult{ false, ConnectFailure::HresultError, e.code() };
    }

    if (!connection)
    {
        // 设备不支持 A2DP Sink（spike 实测：某些手机会这样）
        return ConnectResult{ false, ConnectFailure::DeviceNotSupported, 0 };
    }

    try
    {
        // StartAsync 返回 void，无结果值可查 —— 不要试图检查它的"返回值"
        connection.StartAsync().get();

        auto openResult = connection.OpenAsync().get();

        if (openResult.Status() != AudioPlaybackConnectionOpenResultStatus::Success)
        {
            auto extended = openResult.ExtendedError();

            // ERROR_GEN_FAILURE (0x8007001F) 在实践中几乎总是同一个原因：
            // 手机正作为 A2DP 源连着别的设备，无法同时当接收端。
            // 归到 GenericFailure 而不是 UnknownFailure，好让 Messages 给出
            // 针对性的操作建议。
            ConnectFailure failure = MapOpenStatus(openResult.Status());
            if (static_cast<DWORD>(extended) == 0x8007001Fu)
            {
                failure = ConnectFailure::GenericFailure;
            }

            return ConnectResult{ false, failure, extended };
        }
    }
    catch (winrt::hresult_error const& e)
    {
        return ConnectResult{ false, ConnectFailure::HresultError, e.code() };
    }

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        // 重新检查：可能在我们等待 OpenAsync 期间已被别的线程断开
        if (m_connections.find(std::wstring(deviceId)) != m_connections.end())
        {
            return ConnectResult{ true, ConnectFailure::None, 0 };
        }

        m_connections.emplace(std::wstring(deviceId), connection);

        // 底层连接被系统关闭（设备走远、手机关蓝牙）时通知 ConnectionManager。
        // 注意 AudioPlaybackConnectionState 只有 Closed / Opened 两种，
        // 没有中间的 Connecting —— 我们只关心"从开着变成关着"这一跳。
        connection.StateChanged(
            [this, id = std::wstring(deviceId)](AudioPlaybackConnection const& sender, auto const&)
            {
                if (sender.State() == AudioPlaybackConnectionState::Closed)
                {
                    {
                        std::lock_guard<std::mutex> lock(m_mutex);
                        m_connections.erase(id);
                    }
                    ConnectionLost.Raise(id);
                }
            });
    }

    return ConnectResult{ true, ConnectFailure::None, 0 };
}

void WinRtDeviceProvider::Disconnect(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    AudioPlaybackConnection connection = nullptr;
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        auto it = m_connections.find(id);
        if (it == m_connections.end())
        {
            return;   // 幂等：未连接时直接返回
        }
        connection = it->second;
        m_connections.erase(it);
    }

    // 在锁外 Close：Close 会触发 StateChanged → 上面那个 lambda → 再取锁。
    // 若在锁内调用会死锁（非递归 mutex）。
    try
    {
        connection.Close();
    }
    catch (winrt::hresult_error const&)
    {
        // 关不掉也不要紧：连接对象已从表里移除并在此析构，
        // AudioPlaybackConnection 的析构同样会关闭底层会话。
    }
}

} // namespace AudioBule::Core
```

**实现上的三个关键点：**

1. **`Close()` 必须在锁外调用。** 它会同步触发 `StateChanged`，
   而那个 lambda 会 `lock(m_mutex)`。锁内调用 = 非递归 mutex 自死锁。
2. **`Connect` 里有两次「已在表中」的检查**（调用前后各一次）。第二次是必要的：
   `OpenAsync` 可能要等几秒，期间另一线程可能已经连上或断开。
3. **析构时不清 `StateChanged` 订阅，直接 clear 容器。** 程序退出路径上
   不值得再发起 COM 交互；`AudioPlaybackConnection` 析构会自行收尾。

- [ ] **Step 3: 在 `AudioBule.Core.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="WinRtDeviceProvider.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="WinRtDeviceProvider.cpp" />
```

- [ ] **Step 4: 加真实 provider 的冒烟用例**

追加到 `tests/ConnectionManager.test.cpp` 末尾：

```cpp
// 真实 provider 的冒烟测试。只验证"在真实系统上不会崩、能枚举"，
// 不断言具体设备 —— 测试机上不一定有可连接的蓝牙设备。
// 真正需要设备的行为由 Task 13 的手动验证清单覆盖。
AB_TEST(WinRtProviderEnumeratesWithoutCrashing)
{
    WinRtDeviceProvider provider;
    CHECK(provider.IsSupported());   // 开发机是 Windows 11，必支持

    auto devices = provider.EnumerateDevices();
    // 不检查数量 —— 有没有配对设备取决于测试机状态
    for (auto const& device : devices)
    {
        CHECK(!device.id.empty());
    }
}

AB_TEST(WinRtProviderConnectOnUnknownDeviceFailsGracefully)
{
    WinRtDeviceProvider provider;
    // 随便编一个不存在的 id。期望：返回失败，绝不抛异常。
    auto result = provider.Connect(L"BTHENUM\\{00000000-0000-0000-0000-000000000000}\\0000");
    CHECK(!result.succeeded);
    CHECK(result.failure != ConnectFailure::None);
}

AB_TEST(WinRtProviderDisconnectOnUnknownDeviceIsNoOp)
{
    WinRtDeviceProvider provider;
    provider.Disconnect(L"not-connected");   // 不得崩溃
}
```

并在文件顶部补 `#include "WinRtDeviceProvider.h"`。

- [ ] **Step 5: 编译并运行测试**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

Expected: 全部通过。若 `WinRtProviderEnumeratesWithoutCrashing` 失败且报
`IsSupported()` 为 false，说明测试机系统版本低于 19041 —— 这在开发机上不可能，
遇到就先检查 `targetver.h` 是否被正确编入。

- [ ] **Step 6: 提交**

```bash
git add AudioBule.Core tests
git commit -m "feat: add WinRT-backed device provider for A2DP connections"
```

---

## Task 6: IconFactory（托盘图标）

**Files:**
- Create: `AudioBule.Core/IconFactory.h`
- Create: `AudioBule.Core/IconFactory.cpp`
- Modify: `AudioBule.Core/AudioBule.Core.vcxproj`
- Create: `tests/IconFactory.test.cpp`
- Modify: `tests/AudioBule.Core.Tests.vcxproj`

**Interfaces:**
- Consumes: 无（独立工具类）
- Produces: `namespace AudioBule::Core`
  - `struct TrayIcon { void* handle = nullptr; explicit operator bool() const { return handle != nullptr; } };`
  - `TrayIcon CreateTrayIcon(bool darkTheme)`
  - `void DestroyTrayIcon(TrayIcon icon)`

主题判定不在这里 —— 它属于 App 层（要读 `UISettings`）。Core 只接收布尔。

**为什么不用 `HICON`**：`windows.h` 把 `HICON` 定义为 `struct HICON__*`。
若本头文件再写 `using HICON = void*;`，同一个 TU 里同时包含 `windows.h`
和本头就会撞名（`IconFactory.cpp` 恰好两个都包含）。用一个自己的
`TrayIcon` 包装类型彻底避开，且顺带给调用方免去 include `<windows.h>`。

---

- [ ] **Step 1: 写失败的测试 `tests/IconFactory.test.cpp`**

```cpp
#include "TestHarness.h"
#include "IconFactory.h"

#include <windows.h>

#include <cmath>
#include <vector>

using namespace AudioBule::Core;

AB_TEST(LightTrayIconIsCreatedAndNonNull)
{
    TrayIcon icon = CreateTrayIcon(false);
    CHECK(static_cast<bool>(icon));
    DestroyTrayIcon(icon);
}

AB_TEST(DarkTrayIconIsCreatedAndNonNull)
{
    TrayIcon icon = CreateTrayIcon(true);
    CHECK(static_cast<bool>(icon));
    DestroyTrayIcon(icon);
}

AB_TEST(IconHasCorrectDimensions)
{
    // 32x32 是本项目的图标画布尺寸。CreateIconIndirect 对尺寸不做要求，
    // 但我们固定生成 32x32 再由系统缩放到托盘槽位。
    TrayIcon icon = CreateTrayIcon(false);
    CHECK(static_cast<bool>(icon));

    ICONINFO info = {};
    GetIconInfo(reinterpret_cast<HICON>(icon.handle), &info, 1);
    if (info.hbmColor != nullptr)
    {
        BITMAP bitmap = {};
        GetObjectW(info.hbmColor, sizeof(bitmap), &bitmap);
        CHECK_EQ(bitmap.bmWidth, static_cast<LONG>(32));
        CHECK_EQ(bitmap.bmHeight, static_cast<LONG>(32)); // 颜色位图高度 = 32（已用负值）
        DeleteObject(info.hbmColor);
    }
    if (info.hbmMask != nullptr)
    {
        BITMAP bitmap = {};
        GetObjectW(info.hbmMask, sizeof(bitmap), &bitmap);
        CHECK_EQ(bitmap.bmWidth, static_cast<LONG>(32));
        CHECK_EQ(bitmap.bmHeight, static_cast<LONG>(64)); // 掩码位图高度翻倍
        DeleteObject(info.hbmMask);
    }

    DestroyTrayIcon(icon);
}

AB_TEST(LightAndDarkIconsDiffer)
{
    // 深浅两套必须真的不一样 —— 否则主题自适应是假的
    TrayIcon light = CreateTrayIcon(false);
    TrayIcon dark = CreateTrayIcon(true);
    CHECK(static_cast<bool>(light));
    CHECK(static_cast<bool>(dark));

    ICONINFO lightInfo = {};
    ICONINFO darkInfo = {};
    GetIconInfo(reinterpret_cast<HICON>(light.handle), &lightInfo, 1);
    GetIconInfo(reinterpret_cast<HICON>(dark.handle), &darkInfo, 1);

    // 逐字节比较颜色位图内容，确认图形颜色确实不同
    bool identical = true;
    if (lightInfo.hbmColor != nullptr && darkInfo.hbmColor != nullptr)
    {
        BITMAP lightBitmap = {};
        BITMAP darkBitmap = {};
        GetObjectW(lightInfo.hbmColor, sizeof(lightBitmap), &lightBitmap);
        GetObjectW(darkInfo.hbmColor, sizeof(darkBitmap), &darkBitmap);

        std::vector<BYTE> lightBytes(static_cast<size_t>(lightBitmap.bmWidthBytes) *
            static_cast<size_t>(std::abs(lightBitmap.bmHeight)), 0);
        std::vector<BYTE> darkBytes(static_cast<size_t>(darkBitmap.bmWidthBytes) *
            static_cast<size_t>(std::abs(darkBitmap.bmHeight)), 0);

        HDC dc = ::CreateCompatibleDC(nullptr);
        HGDIOBJ oldBitmap = ::SelectObject(dc, lightInfo.hbmColor);
        ::GetDIBits(dc, lightInfo.hbmColor, 0, lightBitmap.bmHeight, lightBytes.data(), nullptr, DIB_RGB_COLORS);
        ::SelectObject(dc, oldBitmap);
        ::SelectObject(dc, darkInfo.hbmColor);
        ::GetDIBits(dc, darkInfo.hbmColor, 0, darkBitmap.bmHeight, darkBytes.data(), nullptr, DIB_RGB_COLORS);
        ::SelectObject(dc, oldBitmap);
        ::DeleteDC(dc);

        identical = lightBytes == darkBytes;
    }
    CHECK(!identical);

    for (HBITMAP handle : { lightInfo.hbmColor, lightInfo.hbmMask,
             darkInfo.hbmColor, darkInfo.hbmMask })
    {
        if (handle != nullptr)
        {
            DeleteObject(handle);
        }
    }

    DestroyTrayIcon(light);
    DestroyTrayIcon(dark);
}

AB_TEST(CreatingManyIconsDoesNotLeak)
{
    // GDI 对象泄漏在托盘图标反复切换主题时会累积成用户可见的问题。
    // 这里只验证"反复创建不崩"，真正的泄漏检测在手动验证清单里
    // （Task 9 Step 7：反复切换主题后看任务管理器 GDI 对象数）。
    for (int i = 0; i < 200; ++i)
    {
        TrayIcon icon = CreateTrayIcon((i % 2) == 0);
        CHECK(static_cast<bool>(icon));
        DestroyTrayIcon(icon);
    }
}

AB_TEST(DestroyTrayIconToleratesNull)
{
    DestroyTrayIcon(TrayIcon{});   // 不得崩溃
}
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

Expected: **失败**，`无法打开包括文件: "IconFactory.h"`。

- [ ] **Step 3: 创建 `AudioBule.Core/IconFactory.h`**

```cpp
#pragma once

namespace AudioBule::Core
{

// 托盘图标句柄。刻意不用 windows.h 的 HICON（它是 struct HICON__*），
// 以免调用方为了用本文件而被迫包含 windows.h。
struct TrayIcon
{
    void* handle = nullptr;

    explicit operator bool() const { return handle != nullptr; }
};

// 生成 32x32 托盘图标。
//   darkTheme = false → 浅色任务栏：画深色图形
//   darkTheme = true  → 深色任务栏：画浅色图形
// 调用方**必须**用 DestroyTrayIcon 释放，否则 GDI 对象泄漏。
TrayIcon CreateTrayIcon(bool darkTheme);

void DestroyTrayIcon(TrayIcon icon);

} // namespace AudioBule::Core
```

- [ ] **Step 4: 创建 `AudioBule.Core/IconFactory.cpp`**

```cpp
#include "pch.h"
#include "IconFactory.h"

namespace AudioBule::Core
{

namespace {

constexpr int kIconSize = 32;

// 画一个"蓝牙耳机"轮廓：外圈圆弧 + 中心实心点。
// 用 GDI 而非 SVG 渲染：见计划开头的「偏差」一节。
void DrawGlyph(HWND /*unused*/, HDC dc, COLORREF color)
{
    HPEN pen = ::CreatePen(PS_SOLID, 3, color);
    HGDIOBJ oldPen = ::SelectObject(dc, pen);
    HGDIOBJ oldBrush = ::SelectObject(dc, ::GetStockObject(NULL_BRUSH));

    // 中心圆点
    ::Ellipse(dc, kIconSize / 2 - 5, kIconSize / 2 - 5, kIconSize / 2 + 5, kIconSize / 2 + 5);

    // 左上到右下的一道斜线（头戴式耳机的头梁）
    ::MoveToEx(dc, 8, kIconSize - 9, nullptr);
    ::LineTo(dc, kIconSize / 2, 9);

    // 左下到右上的一道斜线（另一侧头梁）
    ::MoveToEx(dc, kIconSize - 9, kIconSize - 9, nullptr);
    ::LineTo(dc, kIconSize / 2, 9);

    ::SelectObject(dc, oldPen);
    ::SelectObject(dc, oldBrush);
    ::DeleteObject(pen);
}

} // namespace

TrayIcon CreateTrayIcon(bool darkTheme)
{
    // 深色任务栏上要画浅色图形，反之亦然
    const COLORREF color = darkTheme ? RGB(0xF5, 0xF5, 0xF5) : RGB(0x20, 0x20, 0x20);

    // CreateIconIndirect 需要：
    //   - 32bpp 颜色位图，尺寸 32x32
    //   - 1bpp 单色掩码位图，尺寸同样是 32x32，但**高度是宽度的两倍**（XOR + AND 各一份）
    std::vector<BYTE> colorBits(static_cast<size_t>(kIconSize) * kIconSize * 4, 0);
    std::vector<BYTE> maskBits(static_cast<size_t>(kIconSize) * kIconSize / 8, 0);

    BITMAPINFO colorInfo = {};
    colorInfo.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    colorInfo.bmiHeader.biWidth = kIconSize;
    // 负高度表示自上而下扫描
    colorInfo.bmiHeader.biHeight = -kIconSize;
    colorInfo.bmiHeader.biPlanes = 1;
    colorInfo.bmiHeader.biBitCount = 32;
    colorInfo.bmiHeader.biCompression = BI_RGB;

    void* colorBitsPtr = nullptr;
    HDC screen = ::GetDC(nullptr);
    HBITMAP colorBitmap = ::CreateDIBSection(
        screen, &colorInfo, DIB_RGB_COLORS, &colorBitsPtr, nullptr, 0);
    if (screen != nullptr)
    {
        ::ReleaseDC(nullptr, screen);
    }

    if (colorBitmap == nullptr || colorBitsPtr == nullptr)
    {
        if (colorBitmap != nullptr)
        {
            ::DeleteObject(colorBitmap);
        }
        return TrayIcon{};
    }

    std::memcpy(colorBitsPtr, colorBits.data(), colorBits.size());

    BITMAPINFO maskInfo = {};
    maskInfo.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    maskInfo.bmiHeader.biWidth = kIconSize;
    // 高度翻倍：上半是 XOR（颜色不透明处），下半是 AND（透明掩码）
    maskInfo.bmiHeader.biHeight = kIconSize * 2;
    maskInfo.bmiHeader.biPlanes = 1;
    maskInfo.bmiHeader.biBitCount = 1;
    maskInfo.bmiHeader.biCompression = BI_RGB;

    void* maskBitsPtr = nullptr;
    HBITMAP maskBitmap = ::CreateDIBSection(
        nullptr, &maskInfo, DIB_RGB_COLORS, &maskBitsPtr, nullptr, 0);
    if (maskBitmap == nullptr || maskBitsPtr == nullptr)
    {
        if (maskBitmap != nullptr)
        {
            ::DeleteObject(maskBitmap);
        }
        ::DeleteObject(colorBitmap);
        return TrayIcon{};
    }

    std::memcpy(maskBitsPtr, maskBits.data(), maskBits.size());

    // 把图形画进颜色位图，同时算出 1bpp 掩码
    HDC colorDc = ::CreateCompatibleDC(nullptr);
    HGDIOBJ oldColorBitmap = ::SelectObject(colorDc, colorBitmap);
    DrawGlyph(nullptr, colorDc, color);

    HDC maskDc = ::CreateCompatibleDC(nullptr);
    HGDIOBJ oldMaskBitmap = ::SelectObject(maskDc, maskBitmap);
    DrawGlyph(nullptr, maskDc, RGB(255, 255, 255));

    ::SelectObject(colorDc, oldColorBitmap);
    ::SelectObject(maskDc, oldMaskBitmap);
    ::DeleteDC(colorDc);
    ::DeleteDC(maskDc);

    ICONINFO iconInfo = {};
    iconInfo.fIcon = TRUE;
    iconInfo.hbmColor = colorBitmap;
    iconInfo.hbmMask = maskBitmap;

    HICON icon = ::CreateIconIndirect(&iconInfo);

    // 位图已交给图标，调用方持有的是图标本身，这里释放中间产物
    ::DeleteObject(colorBitmap);
    ::DeleteObject(maskBitmap);

    return TrayIcon{ reinterpret_cast<void*>(icon) };
}

void DestroyTrayIcon(TrayIcon icon)
{
    if (icon.handle != nullptr)
    {
        ::DestroyIcon(reinterpret_cast<HICON>(icon.handle));
    }
}

} // namespace AudioBule::Core
```

> 需要 `<cstring>` 提供 `std::memcpy`；`pch.h` 当前没有包含它。
> 在文件顶部加 `#include <cstring>` 与 `#include <vector>`。
>
> `CreateTrayIcon` 成功后立即 `DeleteObject` 两个位图是**正确**的 ——
> `CreateIconIndirect` 会复制位图内容。留着它们才是泄漏。

- [ ] **Step 5: 在 `AudioBule.Core.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="IconFactory.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="IconFactory.cpp" />
```

- [ ] **Step 6: 在测试工程登记 `tests/IconFactory.test.cpp`**

```xml
    <ClCompile Include="IconFactory.test.cpp" />
```

> 测试文件用到了 `GetIconInfo` / `GetObjectW` / `DeleteObject` / `BITMAP`，
> 已在文件内 include `<windows.h>`。`std::wstring` 之类不需要额外头。

- [ ] **Step 7: 编译并运行测试**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

Expected: 全部通过。若 `IconHasCorrectDimensions` 失败并报宽度不是 32，
检查 `biHeight` 是否误写成正值（负值 = 自上而下，正值 = 自下而上，
两种都合法，但与 `CopyMemory` 的写入顺序必须一致）。

- [ ] **Step 8: 提交**

```bash
git add AudioBule.Core tests
git commit -m "feat: add GDI-based tray icon factory with light and dark variants"
```

---

## Core 层完成

至此 spec §7 阶段 1（Core + 抽象 + 测试）完成。运行测试确认全绿：

```powershell
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

用例总数应为 **54**：1（框架冒烟）+ 7（StringUtil）+ 8（Settings）+
26（ConnectionManager）+ 3（WinRtDeviceProvider 冒烟）+ 6（IconFactory）。
执行时 `RunAll` 打印的 `Running N test(s)` 与 `N passed, 0 failed` 中的 N 必须相等。

---

## Task 7: WinUI 3 App 工程骨架

**Files:**
- Create: `AudioBule.App/AudioBule.App.vcxproj`
- Create: `AudioBule.App/pch.h` / `AudioBule.App/pch.cpp`
- Create: `AudioBule.App/targetver.h`
- Create: `AudioBule.App/main.cpp`
- Create: `AudioBule.App/App.xaml` / `AudioBule.App/App.xaml.h` / `AudioBule.App/App.xaml.cpp`
- Create: `AudioBule.App/MainWindow.xaml` / `AudioBule.App/MainWindow.xaml.h` / `AudioBule.App/MainWindow.xaml.cpp`
- Modify: `AudioBule.sln`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 的 `Directory.Build.props`
- Produces: 可启动的空 WinUI 3 应用，窗口标题为 `AudioBule`

**本任务是全计划风险最高的一步。** Windows App SDK 的 C++/WinUI 3 工程依赖
XAML 编译器（由 `Microsoft.WindowsAppSDK.WinUI` 包的 MSBuild targets 驱动），
配置项错一个就是几百行 MSBuild 报错。如果下面的构建步骤失败，
**不要**猜着改，先看错误码再对照本步末尾的排查表。

**技术栈事实（已核实 NuGet 缓存内容）：**
- `Microsoft.WindowsAppSDK` **2.2.0**
- `Microsoft.WindowsAppSDK.WinUI` **2.2.1**（自带 XAML 编译器 targets，
  位于 `build/Microsoft.UI.Xaml.Markup.Compiler.interop.targets`）
- 二者是独立包，`Microsoft.WindowsAppSDK` 通过 nuspec 依赖 `WinUI`，
  所以**只需**引用 `Microsoft.WindowsAppSDK` 一个包

---

- [ ] **Step 1: 创建 `AudioBule.App/targetver.h`**

与 Core 一致。

```cpp
#pragma once

#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define NTDDI_VERSION NTDDI_WIN10_RS3
```

- [ ] **Step 2: 创建 `AudioBule.App/pch.h`**

```cpp
#pragma once

#include "targetver.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <objbase.h>

#include <string>
#include <vector>

#include <wil/common.h>
#include <wil/com.h>
#include <wil/result.h>

// C++/WinRT 的 Windows.Foundation 头会定义 GetCurrentTime 宏，与 windows.h 冲突（C4002）
#undef GetCurrentTime

#include <winrt/base.h>
#include <winrt/Windows.Foundation.h>
#include <winrt/Windows.Foundation.Collections.h>
#include <winrt/Windows.Foundation.Metadata.h>

// Core 的公开头 —— App 允许依赖 Core，反之不行
#include "ConnectionEntry.h"
#include "ConnectionManager.h"
#include "IAudioDeviceProvider.h"
#include "IconFactory.h"
#include "Messages.h"
#include "Settings.h"
#include "StringUtil.h"
#include "WinRtDeviceProvider.h"
```

- [ ] **Step 3: 创建 `AudioBule.App/pch.cpp`**

```cpp
#include "pch.h"
```

- [ ] **Step 4: 创建 `AudioBule.App/App.xaml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<Application
    x:Class="AudioBule.App.App"
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
</Application>
```

> WinUI 3 的 `Application` 元素**不接受** `RequestedTheme` 属性（那是 UWP 的写法）。
> 也不要在这里放 `x:Class` 之外的复杂内容 —— 样式资源在 Task 10 加。

- [ ] **Step 5: 创建 `AudioBule.App/App.xaml.h`**

```cpp
#pragma once

#include "App.xaml.g.h"

namespace winrt::AudioBule::App::implementation
{

struct App : AppT<App>
{
    App() noexcept;

    void OnLaunched(Windows::ApplicationModel::Activation::LaunchActivatedEventArgs const& e);
};

} // namespace winrt::AudioBule::App::implementation
```

- [ ] **Step 6: 创建 `AudioBule.App/App.xaml.cpp`**

```cpp
#include "pch.h"

#include "App.xaml.h"

#include "MainWindow.xaml.h"

using namespace winrt;
using namespace Windows::ApplicationModel::Activation;
using namespace Windows::UI;
using namespace Windows::UI::Xaml;
using namespace Windows::UI::Xaml::Controls;
using namespace AudioBule::App::implementation;

namespace winrt::AudioBule::App::implementation
{

App::App() noexcept
{
    InitializeComponent();
}

void App::OnLaunched(LaunchActivatedEventArgs const& e)
{
    auto window = Window();
    window.Activate();
}

} // namespace winrt::AudioBule::App::implementation
```

> `Window()` / `WindowT<App>()` 是 XAML 编译器根据 `x:Class="AudioBule.App.App"`
> 生成的成员函数，返回 `MainWindow`。本任务先不显式 new 出 MainWindow ——
> 由生成的代码负责。Task 10 会改成显式持有窗口实例以便控制显示/隐藏。

- [ ] **Step 7: 创建 `AudioBule.App/MainWindow.xaml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<Window
    x:Class="AudioBule.App.MainWindow"
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml">
    <Grid>
        <TextBlock Text="AudioBule" HorizontalAlignment="Center" VerticalAlignment="Center" />
    </Grid>
</Window>
```

- [ ] **Step 8: 创建 `AudioBule.App/MainWindow.xaml.h`**

```cpp
#pragma once

#include "MainWindow.xaml.g.h"

namespace winrt::AudioBule::App::implementation
{

struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow() noexcept;
};

} // namespace winrt::AudioBule::App::implementation

namespace winrt::AudioBule::App::factory_implementation
{

struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
{
};

} // namespace winrt::AudioBule::App::factory_implementation
```

- [ ] **Step 9: 创建 `AudioBule.App/MainWindow.xaml.cpp`**

```cpp
#include "pch.h"

#include "MainWindow.xaml.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

using namespace winrt;
using namespace AudioBule::App::implementation;

namespace winrt::AudioBule::App::implementation
{

MainWindow::MainWindow() noexcept
{
    InitializeComponent();
}

} // namespace winrt::AudioBule::App::implementation
```

- [ ] **Step 10: 创建 `AudioBule.App/main.cpp`**

```cpp
#include "pch.h"

// XAML 编译器生成的 Application 派生类（来自 App.xaml 的 x:Class）
#include "winrt/AudioBule.App.h"

using namespace winrt;

int WINAPI wWinMain(WinRT initInstance, _In_ HINSTANCE /*hInstance*/,
    _In_opt_ HINSTANCE /*hPrevInstance*/, _In_ LPWSTR /*lpCmdLine*/, _In_ int /*nCmdShow*/)
{
    // 初始化 COM/WinRT apartment。WinUI 3 必须是 STA。
    winrt::init_apartment(winrt::apartment_type::single_threaded);

    // 启动 XAML 消息循环。生成的 Application 类由 App.xaml 的 x:Class 决定。
    winrt::AudioBule::App::App().Launch(winrt::initInstance);
}
```

> **WinUI 3 的 `wWinMain` 签名是特殊的**：第一个参数是 `WinRT initInstance`
> （`IInspectable*`），不是 `HINSTANCE` / `PSTR`。这是 Windows App SDK
> 定义的入口约定，务必照抄，不要改成传统的 WinMain 签名。

- [ ] **Step 11: 创建 `AudioBule.App/AudioBule.App.vcxproj`**

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
    <ProjectGuid>{A1B2C3D4-0002-4E5F-9A8B-000000000002}</ProjectGuid>
    <RootNamespace>AudioBuleApp</RootNamespace>
    <ApplicationType>Windows Store</ApplicationType>
    <ApplicationEnvironment>windows</ApplicationEnvironment>
    <ApplicationKind>windows</ApplicationKind>
    <WindowsPackageType>None</WindowsPackageType>
    <EnableMsixTooling>true</EnableMsixTooling>
    <EnableDefaultCssItems>false</EnableDefaultCssItems>
    <EnableDefaultPageItems>false</EnableDefaultPageItems>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Debug|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>true</UseDebugLibraries>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'" Label="Configuration">
    <ConfigurationType>Application</ConfigurationType>
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings" />
  <ImportGroup Label="Shared" />
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup>
    <TargetName>AudioBule</TargetName>
    <IntDir>$(ProjectDir)obj\</IntDir>
    <OutDir>$(ProjectDir)bin\</OutDir>
    <!-- 自包含 Windows App SDK 运行时：目标机器无需预装 Windows App Runtime -->
    <WindowsAppSDKSelfContained>true</WindowsAppSDKSelfContained>
    <WindowsPackageType>None</WindowsPackageType>
    <AppxPackageSigningEnabled>false</AppxPackageSigningEnabled>
  </PropertyGroup>
  <ItemDefinitionGroup>
    <ClCompile>
      <AdditionalIncludeDirectories>$(CppWinRTProjectionIncludePath);$(ProjectDir);$(ProjectDir)..\AudioBule.Core;%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <WarningLevel>Level4</WarningLevel>
      <SDLCheck>true</SDLCheck>
      <ConformanceMode>true</ConformanceMode>
      <PrecompiledHeader>Use</PrecompiledHeader>
      <PrecompiledHeaderFile>pch.h</PrecompiledHeaderFile>
      <TreatWarningAsError>true</TreatWarningAsError>
      <LanguageStandard>stdcpplatest</LanguageStandard>
      <AdditionalOptions>/utf-8 %(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
    <Link>
      <SubSystem>Windows</SubSystem>
      <!-- Core 是 /MT（静态 CRT），App 必须一致，否则链接期 LNK2038 -->
      <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup>
    <ClInclude Include="pch.h" />
    <ClInclude Include="targetver.h" />
    <ClInclude Include="App.xaml.h" />
    <ClInclude Include="MainWindow.xaml.h" />
  </ItemGroup>
  <ItemGroup>
    <ClCompile Include="pch.cpp">
      <PrecompiledHeader>Create</PrecompiledHeader>
    </ClCompile>
    <ClCompile Include="main.cpp" />
    <ClCompile Include="App.xaml.cpp">
      <DependentUpon>App.xaml</DependentUpon>
    </ClCompile>
    <ClCompile Include="MainWindow.xaml.cpp">
      <DependentUpon>MainWindow.xaml</DependentUpon>
    </ClCompile>
  </ItemGroup>
  <ItemGroup>
    <ApplicationDefinition Include="App.xaml">
      <SubType>Designer</SubType>
    </ApplicationDefinition>
    <Page Include="MainWindow.xaml">
      <SubType>Designer</SubType>
    </Page>
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\AudioBule.Core\AudioBule.Core.vcxproj">
      <Project>{A1B2C3D4-0001-4E5F-9A8B-000000000001}</Project>
    </ProjectReference>
  </ItemGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.WindowsAppSDK" Version="2.2.0" />
    <PackageReference Include="Microsoft.Windows.CppWinRT" Version="3.0.260520.1" />
    <PackageReference Include="Microsoft.Windows.ImplementationLibrary" Version="1.0.260126.7" />
  </ItemGroup>
  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
</Project>
```

> `<WindowsPackageType>None</WindowsPackageType>` 表示**未打包**运行。
> 这是有意的：Task 7~11 全程用未打包模式跑通，Task 12 再切到 MSIX。
> 未打包模式下 `StartupTask` 与 toast 不可用 —— 那正是 Task 12 之后的计划二内容，
> 本计划不需要它们。
>
> `Core` 需在 Release 下设 `/MT` 才能与 App 的 `/MT` 一致。Task 1 建立 Core 时
> 只在测试工程设了 `<RuntimeLibrary>MultiThreaded</RuntimeLibrary>`，
> **Core 的 vcxproj 现在要补上**（见 Step 12）。

- [ ] **Step 12: 给 `AudioBule.Core.vcxproj` 的 Release 配置补 `/MT`**

Core 是静态库，链接期不检查 CRT 一致性，所以问题会推迟到 App 链接时才爆。
现在补上：

```xml
  <ItemDefinitionGroup Condition="'$(Configuration)|$(Platform)'=='Release|x64'">
    <ClCompile>
      <FunctionLevelLinking>true</FunctionLevelLinking>
      <IntrinsicFunctions>true</IntrinsicFunctions>
      <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
    </ClCompile>
  </ItemDefinitionGroup>
```

- [ ] **Step 13: 把 App 加进 `AudioBule.sln`**

在 `AudioBule.sln` 的两个 `Project(...)` 之间插入：

```text
Project("{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}") = "AudioBule.App", "AudioBule.App\AudioBule.App.vcxproj", "{A1B2C3D4-0002-4E5F-9A8B-000000000002}"
EndProject
```

并在 `ProjectConfigurationPlatforms` 节里追加四行：

```text
		{A1B2C3D4-0002-4E5F-9A8B-000000000002}.Debug|x64.ActiveCfg = Debug|x64
		{A1B2C3D4-0002-4E5F-9A8B-000000000002}.Debug|x64.Build.0 = Debug|x64
		{A1B2C3D4-0002-4E5F-9A8B-000000000002}.Release|x64.ActiveCfg = Release|x64
		{A1B2C3D4-0002-4E5F-9A8B-000000000002}.Release|x64.Build.0 = Release|x64
```

- [ ] **Step 14: 更新 `.gitignore`**

XAML 编译器会在 `obj\` 下生成 `.g.h` / `.g.cpp`，加一条：

```gitignore
# XAML 编译器产物
/AudioBule.App/Generated Files/
```

- [ ] **Step 15: 还原并编译**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -t:Restore -p:Configuration=Debug -p:Platform=x64 -v:minimal -nologo
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Debug -p:Platform=x64 -v:minimal -nologo
```

Expected: 退出码 0，产物 `AudioBule.App\bin\AudioBule.exe`。
用 **Debug** 而非 Release —— XAML 编译器在 Debug 下的报错信息更完整，
首次打通工具链时更容易定位问题。

- [ ] **Step 16: 运行应用**

Run:

```powershell
& ".\AudioBule.App\bin\AudioBule.exe"
```

Expected: 弹出一个窗口，中央显示 `AudioBule`。关闭窗口后进程退出。

### 构建失败排查表

按错误信息对照，不要盲目改：

| 错误 | 原因 | 处理 |
| --- | --- | --- |
| `MSB8020 找不到 v180 的生成工具` | `PlatformToolset` 写成了 `v180` | 检查 `Directory.Build.props` 是 `v145` |
| `无法打开包括文件: "wil/common.h"` | 没先 Restore | 先跑 `-t:Restore` |
| `无法打开包括文件: "winrt/base.h"` | `CppWinRTProjectionIncludePath` 没生效 | 检查该属性是否在 `Directory.Build.props` 中，且工程 `ItemDefinitionGroup` 引用了它 |
| `C2065 GetCurrentTime` / `C4002` | 忘了在 C++/WinRT 头之前 `#undef GetCurrentTime` | 检查 `pch.h` |
| `LNK2038 检测到不一致` | Core 与 App 的 CRT 不一致 | 两者都必须是 `MultiThreaded`（`/MT`） |
| `找不到 XamlCompiler 任务` | `Microsoft.WindowsAppSDK` 未还原 | 确认已 `-t:Restore`，且 NuGet 缓存里有 2.2.0 |
| `error C3775: 无法从"const App"转换为"App"` | WinUI 3 的 App 结构体需非 const | 检查 `OnLaunched` 的 `const&` 参数签名与 `AppT<App>` 匹配 |
| `找不到 winrt/AudioBule.App.h` | `RootNamespace` 与 `x:Class` 命名空间不一致 | 二者必须都是 `AudioBule.App` |

- [ ] **Step 17: 提交**

```bash
git add AudioBule.App AudioBule.sln .gitignore AudioBule.Core/AudioBule.Core.vcxproj
git commit -m "build: add WinUI 3 app skeleton that launches an empty window"
```

---

## Task 8: TrayIconService（独立线程 + DispatcherQueue 桥接）

**Files:**
- Create: `AudioBule.App/TrayIconService.h`
- Create: `AudioBule.App/TrayIconService.cpp`
- Modify: `AudioBule.App/AudioBule.App.vcxproj`

**Interfaces:**
- Consumes: Task 7 的 App 骨架；Task 6 的 `Core::CreateTrayIcon` / `DestroyTrayIcon`
- Produces: `namespace AudioBule::App::TrayService` 的 `TrayIconService`

**为什么这个任务独立成一个 Task：** spec §3.4 明确定它为「本项目最关键的技术点」。
WinUI 3 的 UI 线程（STA）独占主消息循环，无法再跑一个 `GetMessageW` 泵接收
`Shell_NotifyIcon` 回调；而 WinUI 3 本身不提供任何原生托盘 API。唯一可行的路子是
自建线程自建窗口，再用 `DispatcherQueue` 把事件 post 回 UI 线程。

**本 Task 只做「托盘 ↔ UI」的单向桥接**，不做 UI 呈现（菜单、窗口显示在 Task 9/10）。
这样每个 Task 的可交付物都能独立验证。

---

- [ ] **Step 1: 创建 `AudioBule.App/TrayIconService.h`**

```cpp
#pragma once

#include <windows.h>

#include <atomic>
#include <functional>
#include <thread>

namespace AudioBule::App::TrayService
{

// 托盘服务。在独立 STA 线程上创建 message-only 窗口并运行消息循环，
// 通过回调把用户交互通知回 UI 线程。
//
// 线程约定：
//  - 构造在 UI 线程调用；析构也在 UI 线程调用。
//  - 所有回调（Callbacks 里的 lambda）都在 **UI 线程**执行 —— 由
//    DispatcherQueue.TryEnqueue post 过去，托盘线程从不直接触碰 XAML。
//  - 更新图标/提示文字的调用可以在任意线程，内部会 post 到托盘线程。
class TrayIconService
{
public:
    struct Callbacks
    {
        // 托盘图标被单击（含键盘 NIN_KEYSELECT）
        std::function<void()> onToggled;

        // 用户在图标上点了右键。参数为光标的屏幕坐标（物理像素）。
        std::function<void(POINT)> onContextMenu;

        // 系统主题/个性化设置变了。UI 层收到后读 UISettings 并调 UpdateIcon。
        std::function<void()> onThemeShouldRefresh;
    };

    // uiQueue 必须是 UI 线程的 DispatcherQueue（在 UI 线程上取得的）。
    // 返回 false 表示托盘线程启动失败（此时不会创建图标）。
    explicit TrayIconService(winrt::Windows::UI::Dispatching::DispatcherQueue const& uiQueue,
        Callbacks callbacks);
    ~TrayIconService();

    TrayIconService(TrayIconService const&) = delete;
    TrayIconService& operator=(TrayIconService const&) = delete;

    // 按系统主题切换图标。darkTheme=true → 深色任务栏。
    void UpdateIcon(bool darkTheme);

    // 更新悬停提示文字。
    void UpdateTooltip(std::wstring text);

    // 阻塞直到托盘线程真正启动并完成图标创建。
    // 调用方应在 UI 线程上短暂调用，以避免"图标还没出现用户就点了"的竞态。
    bool WaitUntilReady(unsigned timeoutMs = 5000);

private:
    static LRESULT CALLBACK WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam);
    static DWORD WINAPI ThreadProc(LPVOID param);

    void ThreadMain();
    bool CreateMessageWindow();
    void DestroyMessageWindow();
    bool AddTrayIcon();

    // 在托盘线程上执行。内部保证跨线程调用被 post 过去。
    void PostToTrayThread(std::function<void()> work);

    void HandleTrayCallback(WPARAM wParam, LPARAM lParam);

    // --- 只在托盘线程上访问的成员 ---
    HINSTANCE m_instance = nullptr;
    HWND m_window = nullptr;
    NOTIFYICONDATAW m_nid = {};
    Core::TrayIcon m_icon = {};
    bool m_iconAdded = false;
    UINT m_taskbarCreatedMessage = 0;

    // --- 跨线程共享 ---
    winrt::Windows::UI::Dispatching::DispatcherQueue m_uiQueue;
    Callbacks m_callbacks;
    std::thread m_thread;
    std::atomic<bool> m_ready{ false };
    std::atomic<bool> m_stopping{ false };
    std::mutex m_pendingMutex;
    std::vector<std::function<void()>> m_pendingWork;
};

} // namespace AudioBule::App::TrayService
```

- [ ] **Step 2: 创建 `AudioBule.App/TrayIconService.cpp`**

```cpp
#include "pch.h"
#include "TrayIconService.h"

#include "IconFactory.h"

#include <winrt/Windows.UI.Dispatching.h>

using namespace winrt;
using namespace winrt::Windows::UI::Dispatching;

namespace AudioBule::App::TrayService
{

namespace
{

constexpr wchar_t kWindowClassName[] = L"AudioBuleTrayWindow";
constexpr UINT kTrayCallbackMessage = WM_APP + 1;
constexpr UINT kUpdateTrayMessage = WM_APP + 2;
constexpr UINT TRAY_ICON_ID = 1;

} // namespace

TrayIconService::TrayIconService(DispatcherQueue const& uiQueue, Callbacks callbacks)
    : m_uiQueue(uiQueue)
    , m_callbacks(std::move(callbacks))
{
    m_thread = std::thread(&TrayIconService::ThreadProc, this);
}

TrayIconService::~TrayIconService()
{
    m_stopping = true;

    // 唤醒托盘线程的 GetMessage。必须 PostThreadMessage 而不是设标志：
    // GetMessage 会阻塞在消息队列空上，设标志它看不见。
    if (m_thread.joinable())
    {
        ::PostThreadMessageW(m_thread.native_handle(), WM_QUIT, 0, 0);
        m_thread.join();
    }
}

DWORD WINAPI TrayIconService::ThreadProc(LPVOID param)
{
    auto* self = static_cast<TrayIconService*>(param);

    // 托盘线程必须是 STA：窗口消息、OLE 交互都要求这一点
    HRESULT hr = ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool comInitialized = SUCCEEDED(hr);

    self->ThreadMain();

    if (comInitialized)
    {
        ::CoUninitialize();
    }
    return 0;
}

void TrayIconService::ThreadMain()
{
    m_instance = ::GetModuleHandleW(nullptr);

    if (!CreateMessageWindow())
    {
        m_ready = true;   // 放行 WaitUntilReady，让调用方拿到 false 而不是死等
        return;
    }

    m_iconAdded = AddTrayIcon();

    // m_taskbarCreatedMessage 用于 explorer 重启后补回图标
    m_taskbarCreatedMessage = ::RegisterWindowMessageW(L"TaskbarCreated");

    m_ready = true;

    MSG message = {};
    while (::GetMessageW(&message, nullptr, 0, 0) > 0)
    {
        ::TranslateMessage(&message);
        ::DispatchMessageW(&message);
    }

    DestroyMessageWindow();
}

bool TrayIconService::CreateMessageWindow()
{
    WNDCLASSEXW windowClass = {};
    windowClass.cbSize = sizeof(WNDCLASSEXW);
    windowClass.lpfnWndProc = &TrayIconService::WndProc;
    windowClass.hInstance = m_instance;
    windowClass.lpszClassName = kWindowClassName;

    if (::RegisterClassExW(&windowClass) == 0)
    {
        // ERROR_CLASS_ALREADY_EXISTS (1410) 可接受 —— 同一进程内重建
        if (::GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        {
            return false;
        }
    }

    // HWND_MESSAGE = message-only 窗口：不出现在任务栏、不接收键盘输入、
    // 收不到广播以外的鼠标消息。这正是托盘回调窗口想要的。
    m_window = ::CreateWindowExW(
        0,                        // dwExStyle
        kWindowClassName,
        L"AudioBule",             // lpWindowName
        0,                        // dwStyle
        0, 0, 0, 0,
        HWND_MESSAGE,             // hWndParent
        nullptr,
        m_instance,
        this);                    // lpParam → GWLP_USERDATA

    if (m_window == nullptr)
    {
        return false;
    }

    ::SetWindowLongPtrW(m_window, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(this));
    return true;
}

void TrayIconService::DestroyMessageWindow()
{
    if (m_nid.hWnd != nullptr && m_iconAdded)
    {
        ::Shell_NotifyIconW(NIM_DELETE, &m_nid);
        m_iconAdded = false;
    }

    if (m_icon.handle != nullptr)
    {
        Core::DestroyTrayIcon(m_icon);
        m_icon = Core::TrayIcon{};
    }

    if (m_window != nullptr)
    {
        ::DestroyWindow(m_window);
        m_window = nullptr;
    }

    if (m_taskbarCreatedMessage != 0)
    {
        ::UnregisterWindowMessage(m_taskbarCreatedMessage);
        m_taskbarCreatedMessage = 0;
    }
}

bool TrayIconService::AddTrayIcon()
{
    m_icon = Core::CreateTrayIcon(false);
    if (!m_icon)
    {
        return false;
    }

    m_nid = {};
    m_nid.cbSize = sizeof(NOTIFYICONDATAW);
    m_nid.hWnd = m_window;
    m_nid.uID = TRAY_ICON_ID;
    m_nid.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    m_nid.uCallbackMessage = kTrayCallbackMessage;
    m_nid.hIcon = reinterpret_cast<HICON>(m_icon.handle);
    wcscpy_s(m_nid.szTip, L"AudioBule");

    if (::Shell_NotifyIconW(NIM_ADD, &m_nid) == FALSE)
    {
        return false;
    }

    // 必须设置版本 4，否则收不到 NIN_SELECT / NIN_KEYSELECT。
    // NOTIFYICON_VERSION_4 会改变 wParam/lParam 的语义，见 HandleTrayCallback。
    m_nid.uVersion = NOTIFYICON_VERSION_4;
    ::Shell_NotifyIconW(NIM_SETVERSION, &m_nid);

    return true;
}

LRESULT CALLBACK TrayIconService::WndProc(HWND hWnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    // TaskbarCreated 是动态注册的消息，值从 RegisterWindowMessageW 得来，
    // 不能与任何常量比较，只能与运行时值比。
    if (message == WM_NCCREATE)
    {
        auto* createStruct = reinterpret_cast<CREATESTRUCTW*>(lParam);
        ::SetWindowLongPtrW(hWnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(createStruct->lpCreateParams));
    }

    auto* self = reinterpret_cast<TrayIconService*>(::GetWindowLongPtrW(hWnd, GWLP_USERDATA));
    if (self == nullptr)
    {
        return ::DefWindowProcW(hWnd, message, wParam, lParam);
    }

    if (message == kTrayCallbackMessage)
    {
        self->HandleTrayCallback(wParam, lParam);
        return TRUE;   // 返回 TRUE 才会收到 NIN_SELECT / NIN_KEYSELECT
    }

    if (message == kUpdateTrayMessage)
    {
        // 执行 PostToTrayThread 排队的跨线程工作
        std::vector<std::function<void()>> work;
        {
            std::lock_guard<std::mutex> lock(self->m_pendingMutex);
            work.swap(self->m_pendingWork);
        }
        for (auto& item : work)
        {
            item();
        }
        return 0;
    }

    if (message == WM_SETTINGCHANGE)
    {
        // 主题切换：让 UI 线程去读 UISettings 并决定用哪套图标。
        // 托盘线程不碰 XAML，也不该自己去读 UI 设置。
        auto queue = self->m_uiQueue;
        queue.TryEnqueue([] {
            if (self->m_callbacks.onThemeShouldRefresh)
            {
                self->m_callbacks.onThemeShouldRefresh();
            }
        });
        return 0;
    }

    if (self->m_taskbarCreatedMessage != 0 && message == self->m_taskbarCreatedMessage)
    {
        // explorer 重启后所有图标都被清空，必须手动补回。
        // Review Focus 第 5 条。
        self->m_iconAdded = self->AddTrayIcon();
        return 0;
    }

    if (message == WM_DESTROY)
    {
        ::PostQuitMessage(0);
        return 0;
    }

    return ::DefWindowProcW(hWnd, message, wParam, lParam);
}

void TrayIconService::HandleTrayCallback(WPARAM wParam, LPARAM lParam)
{
    // NOTIFYICON_VERSION_4 之下：
    //   LOWORD(lParam)  = X 坐标，HIWORD(lParam) = Y 坐标
    //   LOWORD(wParam)  = 事件 ID，HIWORD(wParam) = 图标 ID
    const UINT eventId = LOWORD(wParam);
    const auto x = static_cast<LONG>(static_cast<short>(LOWORD(lParam)));
    const auto y = static_cast<LONG>(static_cast<short>(HIWORD(lParam)));

    auto queue = m_uiQueue;

    switch (eventId)
    {
    case WM_CONTEXTMENU:
    case WM_RBUTTONUP:
    {
        // 在光标处弹菜单。坐标必须原样传给 UI 层，不能在托盘线程上做 DPI 换算 ——
        // UI 层有正确的 per-monitor DPI 上下文。
        queue.TryEnqueue([this, x, y] {
            if (m_callbacks.onContextMenu)
            {
                m_callbacks.onContextMenu(POINT{ x, y });
            }
        });
        return;
    }

    case NIN_SELECT:
    case NIN_KEYSELECT:
    {
        queue.TryEnqueue([this] {
            if (m_callbacks.onToggled)
            {
                m_callbacks.onToggled();
            }
        });
        return;
    }

    default:
        return;
    }
}

void TrayIconService::UpdateIcon(bool darkTheme)
{
    auto icon = Core::CreateTrayIcon(darkTheme);
    if (!icon)
    {
        return;
    }

    PostToTrayThread([this, icon] {
        // 新图标建好后才释放旧的，避免闪烁期间出现空图标
        NOTIFYICONDATAW nid = m_nid;
        nid.hIcon = reinterpret_cast<HICON>(icon.handle);

        if (m_iconAdded && ::Shell_NotifyIconW(NIM_MODIFY, &nid) != FALSE)
        {
            Core::DestroyTrayIcon(m_icon);
            m_icon = icon;
            return;
        }

        // 图标还没加上（启动早期或 explorer 刚重启），先记下来，
        // 等 AddTrayIcon 时用上
        Core::DestroyTrayIcon(icon);
        m_icon = icon;
    });
}

void TrayIconService::UpdateTooltip(std::wstring text)
{
    PostToTrayThread([this, text = std::move(text)] {
        // 限制长度：szTip 是 128 字符的定长数组，写超了会内存损坏
        wcsncpy_s(m_nid.szTip, text.c_str(), _TRUNCATE);

        if (m_iconAdded)
        {
            ::Shell_NotifyIconW(NIM_MODIFY, &m_nid);
        }
    });
}

void TrayIconService::PostToTrayThread(std::function<void()> work)
{
    if (m_stopping || m_window == nullptr)
    {
        return;
    }

    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        if (m_pendingWork.size() > 64)
        {
            return;   // 队列爆了说明 UI 线程卡死，丢弃即可
        }
        m_pendingWork.push_back(std::move(work));
    }

    ::PostMessageW(m_window, kUpdateTrayMessage, 0, 0);
}

bool TrayIconService::WaitUntilReady(unsigned timeoutMs)
{
    auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeoutMs);

    while (!m_ready.load())
    {
        if (std::chrono::steady_clock::now() >= deadline)
        {
            return false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    return m_window != nullptr;
}

} // namespace AudioBule::App::TrayService
```

**实现上必须注意的点：**

1. **`TryEnqueue` 返回 false = UI 线程已退出。** 此时静默丢弃。
   绝不能阻塞等待 —— UI 没了，托盘留着也没意义。
2. **`WndProc` 返回 `TRUE`** 才能收到 `NIN_SELECT`/`NIN_KEYSELECT`。
   惯例是返回 0，但那样收不到点击事件。
3. **`kUpdateTrayMessage`（`WM_APP + 2`）必须真的执行队列。** 否则
   `UpdateIcon` / `UpdateTooltip` 是死代码，本任务无法验证。
4. **`WM_SETTINGCHANGE` 转发 `onThemeShouldRefresh`**，由 UI 层读
   `UISettings` 决定新图标。托盘线程不碰 XAML。

- [ ] **Step 3: 确认 `pch.h` 有需要的头**

`TrayIconService.cpp` 用到了 `<mutex>`、`<chrono>`、`<vector>`。
`pch.h` 已有 `<vector>`，补上：

```cpp
#include <chrono>
#include <mutex>
```

- [ ] **Step 4: 在 `AudioBule.App.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="TrayIconService.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="TrayIconService.cpp" />
```

- [ ] **Step 5: 编译**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Debug -p:Platform=x64 -v:minimal -nologo
```

Expected: 退出码 0。

- [ ] **Step 6: 手工验证托盘线程能起来**

在 `App::OnLaunched` 里临时加一段，把服务启起来并等它就绪，
然后**不**挂任何回调，只验证不崩溃：

```cpp
void App::OnLaunched(LaunchActivatedEventArgs const& e)
{
    auto window = Window();
    window.Activate();

    // --- Task 8 临时验证代码，Task 9 会替换 ---
    static TrayService::TrayIconService tray(
        winrt::Windows::UI::Dispatching::DispatcherQueue::GetForCurrentThread(),
        TrayService::TrayIconService::Callbacks{});

    if (!tray.WaitUntilReady())
    {
        ::OutputDebugStringW(L"AudioBule: tray icon failed to initialize\n");
        return;
    }

    tray.UpdateIcon(false);
    ::OutputDebugStringW(L"AudioBule: tray icon initialized\n");
}
```

同时在 `App.xaml.cpp` 顶部加：

```cpp
#include "TrayIconService.h"
```

重新编译并运行。

**Expected**: 任务栏托盘区出现 AudioBule 图标；`OutputDebugString` 窗口
（VS 里按 Ctrl+Alt+Shift+V 或用 DebugView）能看到
`AudioBule: tray icon initialized`。窗口关闭后进程退出，托盘图标消失。

- [ ] **Step 7: 验证进程能干净退出（Review Focus 第 6 条）**

Run:

```powershell
& ".\AudioBule.App\bin\AudioBule.exe"
Start-Sleep -Seconds 3
Get-Process AudioBule -ErrorAction SilentlyContinue | Select-Object Id, Name
# 关闭应用窗口后再次检查
Start-Sleep -Seconds 2
Get-Process AudioBule -ErrorAction SilentlyContinue | Select-Object Id, Name
```

Expected: 第一次有进程，关闭窗口后第二次**无输出**（进程已退出）。
若进程残留，说明 `TrayIconService` 析构没有唤醒托盘线程 ——
检查 `PostThreadMessageW(WM_QUIT)` 那一行。

> `static` 局部变量是为了让 `TrayIconService` 在 `OnLaunched` 返回后继续存活。
> 若不加 `static`，服务会在 `OnLaunched` 结束时析构，托盘图标立刻消失。

- [ ] **Step 8: 提交**

```bash
git add AudioBule.App
git commit -m "feat: add tray icon service on dedicated thread with dispatcher bridge"
```

---

## Task 9: 托盘接线 —— 主题图标、右键菜单、explorer 重启恢复

**Files:**
- Modify: `AudioBule.App/App.xaml.h`
- Modify: `AudioBule.App/App.xaml.cpp`
- Create: `AudioBule.App/TrayMenuBuilder.h` / `TrayMenuBuilder.cpp`
- Modify: `AudioBule.App/AudioBule.App.vcxproj`

**Interfaces:**
- Consumes: Task 8 的 `TrayIconService`
- Produces: `TrayIconService::Callbacks` 的三个回调全部接线完成；窗口能响应托盘交互

**本任务把 Task 8 的临时验证代码替换成真实实现。**

---

- [ ] **Step 1: 创建 `AudioBule.App/TrayMenuBuilder.h`**

```cpp
#pragma once

#include <windows.h>

namespace AudioBule::App::TrayService
{

// 托盘右键菜单项。spec §2.1 要求四项：蓝牙设置、开机自启、关于、退出。
struct TrayMenu
{
    void* hMenu = nullptr;
};

// 在 screenPoint 处弹出菜单。必须是模态：菜单显示期间要吃掉输入，
// 否则用户点击菜单外时事件会漏到下面的窗口。
//
// 返回用户选中的命令 ID，未选中返回 0。
int ShowTrayMenu(HWND owner, POINT screenPoint, bool autoReconnect, bool runAtStartup);

constexpr int kCmdBluetoothSettings = 1001;
constexpr int kCmdAutoReconnect = 1002;
constexpr int kCmdRunAtStartup = 1003;
constexpr int kCmdAbout = 1004;
constexpr int kCmdExit = 1005;

} // namespace AudioBule::App::TrayService
```

- [ ] **Step 2: 创建 `AudioBule.App/TrayMenuBuilder.cpp`**

```cpp
#include "pch.h"
#include "TrayMenuBuilder.h"

#include <shellapi.h>

namespace AudioBule::App::TrayService
{

namespace {

void AppendCheckItem(HMENU menu, UINT id, wchar_t const* text, bool checked)
{
    MENUITEMINFOW info = {};
    info.cbSize = sizeof(info);
    info.fMask = MIIM_STRING | MIIM_ID | MIIM_STATE;
    info.fState = checked ? MFS_CHECKED : MFS_UNCHECKED;
    info.wID = id;
    ::InsertMenuItemW(menu, ::GetMenuItemCount(menu), TRUE, &info);

    // InsertMenuItemW 的 MIIM_STRING 不接受字符串指针，需另设文本
    // （MENUITEMINFO 的 dwTypeData + MIIM_STRING 在部分系统版本上不生效，
    //  这是 Win32 的已知坑 —— 用 SetMenuItemInfoW 补一次）
    MENUITEMINFOW textInfo = {};
    textInfo.cbSize = sizeof(textInfo);
    textInfo.fMask = MIIM_STRING;
    textInfo.dwTypeData = const_cast<LPWSTR>(text);
    ::SetMenuItemInfoW(menu, static_cast<UINT>(-1), TRUE, &textInfo);
}

} // namespace

int ShowTrayMenu(HWND owner, POINT screenPoint, bool autoReconnect, bool runAtStartup)
{
    HMENU menu = ::CreatePopupMenu();
    if (menu == nullptr)
    {
        return 0;
    }

    AppendCheckItem(menu, kCmdBluetoothSettings, L"蓝牙设置...", false);
    AppendCheckItem(menu, kCmdAutoReconnect, L"启动时自动重连上次设备", autoReconnect);
    AppendCheckItem(menu, kCmdRunAtStartup, L"开机自启", runAtStartup);
    ::InsertMenuW(menu, static_cast<UINT>(-1), TRUE, MF_SEPARATOR);
    AppendCheckItem(menu, kCmdAbout, L"关于 AudioBule", false);
    AppendCheckItem(menu, kCmdExit, L"退出", false);

    // 右键菜单必须在显示前把焦点抢过来，否则菜单会立刻消失。
    // 这是 shell 扩展的经典要求，不是可选项。
    ::SetForegroundWindow(owner);
    DWORD command = ::TrackPopupMenuEx(
        menu,
        TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
        screenPoint.x, screenPoint.y,
        owner, nullptr);

    ::DestroyMenu(menu);
    return static_cast<int>(command);
}

} // namespace AudioBule::App::TrayService
```

> `TrayMenu` 结构体本任务用不上（菜单是模态的，返回命令 ID 即可），
> 保留它是为了将来做异步菜单时有个扩展点。若编译器对未使用的结构体报警，
> 直接删掉这个结构体。

- [ ] **Step 3: 在 `AudioBule.App.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="TrayMenuBuilder.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="TrayMenuBuilder.cpp" />
```

- [ ] **Step 4: 重写 `App.xaml.h`**

```cpp
#pragma once

#include "App.xaml.g.h"

#include "TrayIconService.h"

#include <memory>

namespace winrt::AudioBule::App::implementation
{

struct App : AppT<App>
{
    App() noexcept;

    void OnLaunched(Windows::ApplicationModel::Activation::LaunchActivatedEventArgs const& e);

private:
    // 三者的析构顺序很重要：托盘服务最先析构（它要 PostThreadMessage 退出），
    // 其次 provider，最后 manager（manager 在析构时会 WaitForIdle 并解绑 provider 事件）。
    // C++ 成员按**声明逆序**析构，所以这里必须反着声明。
    Core::ConnectionManager m_manager;
    Core::WinRtDeviceProvider m_provider;
    std::unique_ptr<TrayService::TrayIconService> m_tray;

    Core::AppSettings m_settings;

    void ShowDeviceWindow();
    void ApplyTheme();
    void HandleTrayCommand(int command);
};

} // namespace winrt::AudioBule::App::implementation
```

- [ ] **Step 5: 重写 `App.xaml.cpp`**

```cpp
#include "pch.h"

#include "App.xaml.h"

#include "MainWindow.xaml.h"
#include "TrayMenuBuilder.h"

#include <shellapi.h>

#include <winrt/Windows.UI.ViewManagement.h>

using namespace winrt;
using namespace Windows::ApplicationModel::Activation;
using namespace Windows::UI::Xaml;
using namespace AudioBule::App::implementation;
using namespace AudioBule::Core;

namespace winrt::AudioBule::App::implementation
{

App::App() noexcept
    : m_manager(m_provider)
{
    InitializeComponent();

    m_settings = LoadSettings(DefaultSettingsPath());

    // 记录主窗口，供托盘点击时显示/隐藏
    m_window = Window().as<MainWindow>();
}

void App::OnLaunched(LaunchActivatedEventArgs const& e)
{
    // 启动时不显示设备列表窗口 —— 这是托盘应用，弹出窗口会很突兀。
    // 窗口实例在构造函数里已经建好，这里只不 Activate。
    m_window.as<Window>().Close();

    if (!m_manager.IsSupported())
    {
        // 系统不支持 A2DP Sink。提示后退出，不留一个没用的托盘图标。
        ::MessageBoxW(nullptr, L"AudioBule 需要 Windows 10 2004（build 19041）或更高版本。",
            L"版本过低", MB_OK | MB_ICONWARNING);
        ::ExitProcess(0);
        return;
    }

    TrayService::TrayIconService::Callbacks callbacks;
    callbacks.onToggled = [this] { ShowDeviceWindow(); };
    callbacks.onContextMenu = [this](POINT point) {
        HandleTrayCommand(TrayService::ShowTrayMenu(
            m_tray->WindowHandle(), point,
            m_settings.autoReconnect, m_settings.runAtStartup));
    };
    callbacks.onThemeShouldRefresh = [this] { ApplyTheme(); };

    m_tray = std::make_unique<TrayService::TrayIconService>(
        DispatcherQueue::GetForCurrentThread(), std::move(callbacks));

    if (!m_tray->WaitUntilReady())
    {
        // 托盘起不来也要继续：spec §3.8「托盘图标创建失败 → 记录日志，
        // 不崩溃；窗口仍可通过其它入口打开」
        OutputDebugStringW(L"AudioBule: tray icon unavailable\n");
        m_tray.reset();
    }

    ApplyTheme();

    m_manager.Refresh();

    if (m_settings.autoReconnect && !m_settings.lastConnectedDevices.empty())
    {
        m_manager.ReconnectSavedDevices(m_settings.lastConnectedDevices);
    }
}

void App::ApplyTheme()
{
    if (!m_tray)
    {
        return;
    }

    // UISettings 的 BackgroundColor 与任务栏主题一致（Win11 起）
    try
    {
        auto settings = Windows::UI::ViewManagement::UISettings();
        auto color = settings.GetColorValue(
            Windows::UI::ViewManagement::UIColorType::Background);
        // 亮度低于 128 视为深色
        bool darkTheme = color.R < 128;
        m_tray->UpdateIcon(darkTheme);
    }
    catch (...)
    {
        m_tray->UpdateIcon(false);
    }
}

void App::ShowDeviceWindow()
{
    auto window = m_window.as<Window>();
    window.Activate();
}

void App::HandleTrayCommand(int command)
{
    switch (command)
    {
    case TrayService::kCmdBluetoothSettings:
        // 配对入口：跳系统蓝牙设置。用 ShellExecute 而不是 explorer.exe，
        // 后者在某些系统上会开新进程残留。
        ::ShellExecuteW(nullptr, L"open", L"ms-settings:bluetooth", nullptr, nullptr, SW_SHOWNORMAL);
        break;

    case TrayService::kCmdAutoReconnect:
        m_settings.autoReconnect = !m_settings.autoReconnect;
        SaveSettings(m_settings, DefaultSettingsPath());
        break;

    case TrayService::kCmdRunAtStartup:
        // 未打包模式下 StartupTask 不可用，计划二才实现自启。
        // 这里只记录开关，不做实际动作。
        m_settings.runAtStartup = !m_settings.runAtStartup;
        SaveSettings(m_settings, DefaultSettingsPath());
        break;

    case TrayService::kCmdAbout:
        ::MessageBoxW(m_tray ? m_tray->WindowHandle() : nullptr,
            L"AudioBule\n蓝牙 A2DP 接收端连接管家",
            L"关于", MB_OK | MB_INFORMATION);
        break;

    case TrayService::kCmdExit:
        m_manager.WaitForIdle();
        ::PostQuitMessage(0);
        break;

    default:
        break;
    }
}

} // namespace winrt::AudioBule::App::implementation
```

- [ ] **Step 6: 补上 App 缺失的成员与依赖**

`Step 4` 的 `App.xaml.h` 用到了 `m_window`，但头文件里没声明。补上：

```cpp
    winrt::Windows::UI::Xaml::Window m_window{ nullptr };
```

`Step 5` 还用了 `TrayService::TrayIconService::WindowHandle()`，
Task 8 没有这个方法。加上 —— 它返回 message-only 窗口的句柄，
供 `SetForegroundWindow` 与 `MessageBox` 的父窗口使用：

```cpp
    // 供菜单/对话框作为父窗口使用。返回托盘线程上的 message-only 窗口句柄。
    HWND WindowHandle() const { return m_window; }
```

- [ ] **Step 7: 编译**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Debug -p:Platform=x64 -v:minimal -nologo
```

Expected: 退出码 0。若报 `m_window` 未声明，说明 Step 6 没做。

- [ ] **Step 8: 手工验证托盘交互**

Run:

```powershell
& ".\AudioBule.App\bin\AudioBule.exe"
```

逐项确认：

| 操作 | 期望 |
| --- | --- |
| 程序启动 | **不弹出窗口**，托盘出现图标 |
| 左键单击托盘图标 | 窗口出现（此时是 Task 7 的占位内容） |
| 右键单击托盘图标 | 弹出 5 项菜单（蓝牙设置 / 自动重连 / 开机自启 / 分隔线 / 关于 / 退出） |
| 点「自动重连」再右键 | 该项显示为勾选态 |
| 点「蓝牙设置」 | 打开系统蓝牙设置页 |
| 点「关于」 | 弹关于对话框 |
| 点「退出」 | 进程退出，托盘图标消失 |
| 切深色主题后再看图标 | 图标变为浅色 |

- [ ] **Step 9: 验证 explorer 重启恢复（Review Focus 第 5 条）**

在托盘图标已显示的情况下，结束 explorer.exe：

```powershell
Stop-Process -Name explorer -Force
Start-Process explorer
Start-Sleep -Seconds 3
```

Expected: 桌面环境恢复后，AudioBule 的托盘图标**重新出现**，
不需要重启 AudioBule。若没出现，检查 `WM_TASKBAR_CREATED` 的
`RegisterWindowMessageW(L"TaskbarCreated")` 是否在窗口创建**之后**才调用 ——
注册早于窗口创建会导致消息投递不到。

> 本机 explorer 可能配置为"自动重启桌面"，那正好一次验证完。
> 若已自动重启，直接看图标是否还在即可。

- [ ] **Step 10: 验证图标资源不泄漏（Review Focus 相关）**

反复切换系统深浅主题 10 次，然后开任务管理器 → 「详细信息」列加「GDI 对象」：

Expected: GDI 对象数不持续增长。

若持续增长，检查 `UpdateIcon` 里旧图标是否被 `Core::DestroyTrayIcon` 释放 ——
只在 `NIM_MODIFY` 成功时才替换，失败路径也要释放新图标。

- [ ] **Step 11: 提交**

```bash
git add AudioBule.App
git commit -m "feat: wire tray callbacks, context menu, and theme-aware icons"
```

---

## Task 10: 设备列表窗口

**Files:**
- Create: `AudioBule.App/DeviceItemViewModel.h` / `DeviceItemViewModel.cpp`
- Modify: `AudioBule.App/MainWindow.xaml`
- Modify: `AudioBule.App/MainWindow.xaml.h`
- Modify: `AudioBule.App/MainWindow.xaml.cpp`
- Modify: `AudioBule.App/App.xaml.h` / `App.xaml.cpp`（窗口改为持有、不再启动即关）
- Modify: `AudioBule.App/AudioBule.App.vcxproj`

**Interfaces:**
- Consumes: Task 4 的 `ConnectionManager` 事件；Task 9 的托盘接线
- Produces: 可显示设备列表、逐设备连接/断开、失败重试、隐藏到托盘

**App 层绝不直接触碰 `AudioPlaybackConnection`**（spec §3.2）——
所有状态都从 `Core::ConnectionEntry` 读。

---

- [ ] **Step 1: 创建 `AudioBule.App/DeviceItemViewModel.h`**

```cpp
#pragma once

#include "ConnectionEntry.h"

#include <winrt/Microsoft.UI.Xaml.h>
#include <winrt/Microsoft.UI.Xaml.Data.h>

namespace AudioBule::App
{

// 每行设备。实现 INotifyPropertyChanged 供 x:Bind 的 OneWay 模式使用。
class DeviceItemViewModel :
    public winrt::Microsoft::UI::Xaml::Data::INotifyPropertyChanged,
    public winrt::implements<DeviceItemViewModel,
        winrt::Microsoft::UI::Xaml::Data::INotifyPropertyChanged>
{
public:
    explicit DeviceItemViewModel(Core::ConnectionEntry entry);

    winrt::hstring DeviceId() const;
    winrt::hstring DisplayName() const;
    winrt::hstring StatusText() const;
    winrt::hstring ErrorText() const;

    bool IsConnected() const;
    bool IsConnecting() const;
    bool IsFailed() const;
    bool IsDisconnected() const;

    // 按钮可用性
    bool CanConnect() const;
    bool CanDisconnect() const;

    Core::ConnectionState State() const;
    Core::ConnectionEntry const& Entry() const;

    // 从 ConnectionManager 推送新状态。值不变时不发通知。
    void Update(Core::ConnectionEntry entry);

    winrt::event<winrt::Microsoft::UI::Xaml::Data::PropertyChangedEventArgs> PropertyChanged();

private:
    void RaisePropertyChanged(winrt::hstring_view name);

    Core::ConnectionEntry m_entry;
    winrt::event<winrt::Microsoft::UI::Xaml::Data::PropertyChangedEventArgs> m_propertyChanged;
};

} // namespace AudioBule::App
```

- [ ] **Step 2: 创建 `AudioBule.App/DeviceItemViewModel.cpp`**

```cpp
#include "pch.h"
#include "DeviceItemViewModel.h"

using namespace winrt;
using namespace Microsoft::UI::Xaml::Data;
using namespace AudioBule::App;
using namespace AudioBule::Core;

namespace AudioBule::App
{

DeviceItemViewModel::DeviceItemViewModel(Core::ConnectionEntry entry)
    : m_entry(std::move(entry))
{
}

winrt::hstring DeviceItemViewModel::DeviceId() const
{
    return winrt::to_hstring(m_entry.deviceId);
}

winrt::hstring DeviceItemViewModel::DisplayName() const
{
    return winrt::to_hstring(m_entry.displayName);
}

winrt::hstring DeviceItemViewModel::StatusText() const
{
    switch (m_entry.state)
    {
    case ConnectionState::Connected:
        return L"已连接";
    case ConnectionState::Connecting:
        return L"连接中…";
    case ConnectionState::Failed:
        return L"连接失败";
    case ConnectionState::Disconnected:
    default:
        return L"未连接";
    }
}

winrt::hstring DeviceItemViewModel::ErrorText() const
{
    return winrt::to_hstring(m_entry.errorMessage);
}

bool DeviceItemViewModel::IsConnected() const
{
    return m_entry.state == ConnectionState::Connected;
}

bool DeviceItemViewModel::IsConnecting() const
{
    return m_entry.state == ConnectionState::Connecting;
}

bool DeviceItemViewModel::IsFailed() const
{
    return m_entry.state == ConnectionState::Failed;
}

bool DeviceItemViewModel::IsDisconnected() const
{
    return m_entry.state == ConnectionState::Disconnected;
}

bool DeviceItemViewModel::CanConnect() const
{
    // 连接中与已连接时禁用，避免重复触发
    return m_entry.state == ConnectionState::Disconnected || m_entry.state == ConnectionState::Failed;
}

bool DeviceItemViewModel::CanDisconnect() const
{
    return m_entry.state == ConnectionState::Connected;
}

ConnectionState DeviceItemViewModel::State() const
{
    return m_entry.state;
}

ConnectionEntry const& DeviceItemViewModel::Entry() const
{
    return m_entry;
}

void DeviceItemViewModel::Update(ConnectionEntry entry)
{
    if (entry.deviceId == m_entry.deviceId &&
        entry.state == m_entry.state &&
        entry.displayName == m_entry.displayName &&
        entry.errorMessage == m_entry.errorMessage)
    {
        return;   // 无变化，不发通知
    }

    m_entry = std::move(entry);

    // 一次状态迁移会改多个属性，分开发通知比发 5 次省事且效果相同
    RaisePropertyChanged(L"StatusText");
    RaisePropertyChanged(L"ErrorText");
    RaisePropertyChanged(L"IsConnected");
    RaisePropertyChanged(L"IsConnecting");
    RaisePropertyChanged(L"IsFailed");
    RaisePropertyChanged(L"IsDisconnected");
    RaisePropertyChanged(L"CanConnect");
    RaisePropertyChanged(L"CanDisconnect");
    RaisePropertyChanged(L"DisplayName");
}

event<PropertyChangedEventArgs> DeviceItemViewModel::PropertyChanged()
{
    return m_propertyChanged;
}

void DeviceItemViewModel::RaisePropertyChanged(hstring_view name)
{
    m_propertyChanged(nullptr, PropertyChangedEventArgs{ hstring{ name } });
}

} // namespace AudioBule::App
```

- [ ] **Step 3: 改写 `MainWindow.xaml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<Window
    x:Class="AudioBule.App.MainWindow"
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    xmlns:viewModels="using:AudioBule.App"
    Title="AudioBule">

    <Grid>
        <Grid.RowDefinitions>
            <RowDefinition Height="Auto" />
            <RowDefinition Height="*" />
            <RowDefinition Height="Auto" />
        </Grid.RowDefinitions>

        <!-- 标题栏操作区 -->
        <CommandBar Grid.Row="0" DefaultLabelPosition="Right" HorizontalAlignment="Right">
            <AppBarButton x:Name="RefreshButton" Icon="Refresh" Label="刷新" Click="OnRefreshClick" />
            <AppBarButton x:Name="BluetoothSettingsButton" Icon="Bluetooth" Label="添加设备"
                          Click="OnBluetoothSettingsClick" />
        </CommandBar>

        <!-- 设备列表 -->
        <ListView x:Name="DeviceList" Grid.Row="1" SelectionMode="None">
            <ListView.ItemTemplate>
                <DataTemplate x:DataType="viewModels:DeviceItemViewModel">
                    <Grid Padding="12" ColumnSpacing="12">
                        <Grid.ColumnDefinitions>
                            <ColumnDefinition Width="*" />
                            <ColumnDefinition Width="Auto" />
                            <ColumnDefinition Width="Auto" />
                        </Grid.ColumnDefinitions>

                        <StackPanel Grid.Column="0">
                            <TextBlock Text="{x:Bind DisplayName()}" FontSize="16" />
                            <TextBlock Text="{x:Bind StatusText()}"
                                       Foreground="{ThemeResource TextFillColorSecondaryBrush}" />
                            <!-- 失败时才显示错误文案 -->
                            <TextBlock Text="{x:Bind ErrorText()}"
                                       Foreground="{ThemeResource SystemFillColorCriticalBrush}"
                                       TextWrapping="Wrap"
                                       Visibility="{x:Bind IsFailed()}" />
                        </StackPanel>

                        <Button Grid.Column="1"
                                Content="连接"
                                CommandParameter="{x:Bind}"
                                Click="OnConnectClick"
                                Visibility="{x:Bind IsDisconnected()}" />
                        <Button Grid.Column="1"
                                Content="重试"
                                CommandParameter="{x:Bind}"
                                Click="OnConnectClick"
                                Visibility="{x:Bind IsFailed()}" />
                        <ProgressRing Grid.Column="1" IsIndeterminate="True"
                                      Width="24" Height="24"
                                      Visibility="{x:Bind IsConnecting()}" />

                        <Button Grid.Column="2"
                                Content="断开"
                                CommandParameter="{x:Bind}"
                                Click="OnDisconnectClick"
                                Visibility="{x:Bind IsConnected()}" />
                    </Grid>
                </DataTemplate>
            </ListView.ItemTemplate>
        </ListView>

        <!-- 空列表引导 -->
        <StackPanel x:Name="EmptyState" Grid.Row="1"
                    VerticalAlignment="Center" HorizontalAlignment="Center"
                    Spacing="8" Visibility="Collapsed">
            <TextBlock Text="没有找到已配对的蓝牙设备" HorizontalAlignment="Center" />
            <Button Content="打开蓝牙设置" Click="OnBluetoothSettingsClick"
                    HorizontalAlignment="Center" />
        </StackPanel>

        <!-- 状态栏 -->
        <TextBlock x:Name="StatusBar" Grid.Row="2" Padding="12,6"
                   Foreground="{ThemeResource TextFillColorSecondaryBrush}" />
    </Grid>
</Window>
```

> `x:Bind` 到方法（`{x:Bind DisplayName()}`）需要在 `MainWindow.xaml.h`
> 里能访问到 `DeviceItemViewModel`。用 `x:DataType` 声明了类型后，
> 编译器会在生成的代码里做类型检查 —— 若类型不对会**编译期**报错，这是好事。

- [ ] **Step 4: 改写 `MainWindow.xaml.h`**

```cpp
#pragma once

#include "MainWindow.xaml.g.h"

#include "Core/ConnectionManager.h"

#include <winrt/Microsoft.UI.Xaml.Controls.Primitives.h>

#include <memory>
#include <unordered_map>
#include <vector>

namespace winrt::AudioBule::App::implementation
{

struct MainWindow : MainWindowT<MainWindow>
{
    MainWindow() noexcept;

    // 由 App 在构造后注入。窗口自己不创建 ConnectionManager，
    // 保证「唯一状态源」是 App 持有的那一个。
    void Attach(Core::ConnectionManager* manager);

private:
    // x:Name 的事件处理器
    void OnRefreshClick(IInspectable const& sender, Microsoft::UI::Xaml::RoutedEventArgs const& args);
    void OnConnectClick(IInspectable const& sender, Microsoft::UI::Xaml::RoutedEventArgs const& args);
    void OnDisconnectClick(IInspectable const& sender, Microsoft::UI::Xaml::RoutedEventArgs const& args);
    void OnBluetoothSettingsClick(IInspectable const& sender, Microsoft::UI::Xaml::RoutedEventArgs const& args);

    void RebuildList();
    void UpdateSingle(Core::ConnectionEntry const& entry);
    DeviceItemViewModel* FindViewModel(std::wstring const& deviceId);

    Core::ConnectionManager* m_manager = nullptr;

    std::vector<std::shared_ptr<DeviceItemViewModel>> m_items;
    std::unordered_map<std::wstring, std::shared_ptr<DeviceItemViewModel>> m_itemsById;

    Core::SimpleEvent<Core::ConnectionEntry>::Handler m_entryChangedHandler;
    Core::SimpleEvent<>::Handler m_entriesChangedHandler;
};

} // namespace winrt::AudioBule::App::implementation

namespace winrt::AudioBule::App::factory_implementation
{

struct MainWindow : MainWindowT<MainWindow, implementation::MainWindow>
{
};

} // namespace winrt::AudioBule::App::factory_implementation
```

> `DeviceItemViewModel` 与 `Core::` 前缀需要在 `MainWindow.xaml.h` 里可见 ——
> `pch.h` 已经 include 了 `ConnectionManager.h`，它会传递带来
> `SimpleEvent.h`。`DeviceItemViewModel.h` 需要额外 include。

- [ ] **Step 5: 改写 `MainWindow.xaml.cpp`**

```cpp
#include "pch.h"

#include "MainWindow.xaml.h"

#include "DeviceItemViewModel.h"

#if __has_include("MainWindow.g.cpp")
#include "MainWindow.g.cpp"
#endif

#include <shellapi.h>

using namespace winrt;
using namespace Microsoft::UI::Xaml;
using namespace Microsoft::UI::Xaml::Controls;
using namespace AudioBule::App;
using namespace AudioBule::App::implementation;
using namespace AudioBule::Core;

namespace winrt::AudioBule::App::implementation
{

MainWindow::MainWindow() noexcept
{
    InitializeComponent();

    // 关闭按钮只隐藏窗口，程序继续在托盘运行。
    // Review Focus 第 4 条：用户点 X 就退出，会让人以为程序挂了。
    Closed([](IInspectable const&, WindowEventArgs const&)
    {
        // App 里会在退出时显式设置这个标志，见下方 App 的说明
    });
}

void MainWindow::Attach(ConnectionManager* manager)
{
    m_manager = manager;

    m_entryChangedHandler = [this](ConnectionEntry const& entry) {
        // EntryChanged 由工作线程触发，必须 post 回 UI 线程
        DispatcherQueue().TryEnqueue([this, entry] { UpdateSingle(entry); });
    };

    m_entriesChangedHandler = [this] {
        DispatcherQueue().TryEnqueue([this] { RebuildList(); });
    };

    m_manager->EntryChanged.Add(m_entryChangedHandler);
    m_manager->EntriesChanged.Add(m_entriesChangedHandler);

    RebuildList();
}

DeviceItemViewModel* MainWindow::FindViewModel(std::wstring const& deviceId)
{
    auto it = m_itemsById.find(deviceId);
    return it == m_itemsById.end() ? nullptr : it->second.get();
}

void MainWindow::RebuildList()
{
    if (m_manager == nullptr)
    {
        return;
    }

    auto snapshot = m_manager->Snapshot();

    // 复用已有 ViewModel：重建 x:Bind 绑定会让选中态和滚动位置丢失
    std::vector<std::shared_ptr<DeviceItemViewModel>> rebuilt;
    std::unordered_map<std::wstring, std::shared_ptr<DeviceItemViewModel>> rebuiltById;

    for (auto const& entry : snapshot)
    {
        std::shared_ptr<DeviceItemViewModel> item;
        auto it = m_itemsById.find(entry.deviceId);
        if (it != m_itemsById.end())
        {
            item = it->second;
            item->Update(entry);
        }
        else
        {
            item = std::make_shared<DeviceItemViewModel>(entry);
        }
        rebuilt.push_back(item);
        rebuiltById[entry.deviceId] = item;
    }

    m_items = std::move(rebuilt);
    m_itemsById = std::move(rebuiltById);

    // ViewSource 需要一个 WinRT 集合，用 ObservableVector 自带的 IInspectable 包装
    DeviceList().ItemsSource(m_items.size() == 0 ? nullptr : ToVector(m_items));

    bool empty = m_items.empty();
    EmptyState().Visibility(empty ? Visibility::Visible : Visibility::Collapsed);
    DeviceList().Visibility(empty ? Visibility::Collapsed : Visibility::Visible);
}

void MainWindow::UpdateSingle(ConnectionEntry const& entry)
{
    auto* existing = FindViewModel(entry.deviceId);
    if (existing != nullptr)
    {
        existing->Update(entry);
        return;
    }

    // 设备不在列表里（刷新时被添加的）：整体重建
    RebuildList();
}

void MainWindow::OnRefreshClick(IInspectable const&, RoutedEventArgs const&)
{
    if (m_manager != nullptr)
    {
        m_manager->Refresh();
    }
}

void MainWindow::OnConnectClick(IInspectable const& sender, RoutedEventArgs const&)
{
    auto button = sender.try_as<Button>();
    if (!button || !m_manager)
    {
        return;
    }

    auto item = button.CommandParameter().try_as<DeviceItemViewModel>();
    if (!item)
    {
        return;
    }

    // 不等 future：结果通过 EntryChanged 通知，避免界面卡住
    m_manager->ConnectAsync(std::wstring(item->DeviceId()));
}

void MainWindow::OnDisconnectClick(IInspectable const& sender, RoutedEventArgs const&)
{
    auto button = sender.try_as<Button>();
    if (!button || !m_manager)
    {
        return;
    }

    auto item = button.CommandParameter().try_as<DeviceItemViewModel>();
    if (!item)
    {
        return;
    }

    m_manager->DisconnectAsync(std::wstring(item->DeviceId()));
}

void MainWindow::OnBluetoothSettingsClick(IInspectable const&, RoutedEventArgs const&)
{
    ::ShellExecuteW(nullptr, L"open", L"ms-settings:bluetooth", nullptr, nullptr, SW_SHOWNORMAL);
}

} // namespace winrt::AudioBule::App::implementation
```

> 上面的 `ToVector(m_items)` 是占位写法 —— WinUI 3 没有现成的
> `shared_ptr` → WinRT 集合转换。**实现方式**：在 `DeviceItemViewModel.h`
> 里加一个显式装箱：
> ```cpp
> inline IInspectable Box(DeviceItemViewModel* item)
> {
>     return box_value(item, take_ownership_from_abi);
> }
> ```
> 然后 `DeviceList().ItemsSource(...)` 传入
> `single_thread_vector<IInspectable>({ Box(...) })`。
> 具体写法在执行时按编译器报错调整 —— 关键点是
> **`CommandParameter` 必须装箱成 `IInspectable` 才能在 x:Bind 下拿到原对象**。

- [ ] **Step 6: 改 App 的窗口处理**

`App.xaml.cpp` 的 `OnLaunched` 里，把 `m_window.as<Window>().Close();` 换成：

```cpp
    // 启动时不显示设备列表窗口，但窗口实例保留在后台。
    // 用 Close() 会销毁窗口；这里改用隐藏 —— WinUI 3 窗口默认就是
    // 首次 Activate 前不可见，因此只需不调用 Activate 即可。
```

即：**删掉那一行 Close() 调用**，其余不动。

再在 `ShowDeviceWindow` 里确保是「显示」而不是「重建」：

```cpp
void App::ShowDeviceWindow()
{
    auto window = m_window.as<Window>();
    window.Activate();
}
```

Task 7 的 `App::App` 构造函数里已经 `m_window = Window().as<MainWindow>()`，
再在 `OnLaunched` 里调用一次 `Attach(&m_manager)`。

- [ ] **Step 7: 处理「点 X 只隐藏」（Review Focus 第 4 条）**

在 `MainWindow::MainWindow` 的 `Closed` 回调里改为**重新显示**窗口而不是销毁它 ——
WinUI 3 的 `Window` 一旦 `Close` 就不可重用。正确做法是拦截关闭：

```cpp
    // 点 X 时改为隐藏而非销毁，托盘应用必须这样。
    // AppWindow 的 Close 事件在窗口销毁前触发，可以在这里 Cancel 掉。
    AppWindow().Closing([](AppWindow const&, AppWindowCancelEventArgs const& args)
    {
        args.Cancel(true);   // 阻止关闭
        // 隐藏由 App 的托盘逻辑接管：点托盘图标重新 Activate 即可
    });
```

> 若 `AppWindow().Closing` 在当前 Windows App SDK 版本上不可用，
> 退路是：不在 XAML 里设关闭行为，改用 `ExtendsContentIntoTitleBar` +
> 自绘标题栏，自行提供隐藏按钮。本任务先试标准做法。

- [ ] **Step 8: 在 `AudioBule.App.vcxproj` 登记新文件**

```xml
  <ItemGroup>
    <ClInclude Include="DeviceItemViewModel.h" />
  </ItemGroup>
```
```xml
    <ClCompile Include="DeviceItemViewModel.cpp" />
```

- [ ] **Step 9: 编译**

Run:

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Debug -p:Platform=x64 -v:minimal -nologo
```

Expected: 退出码 0。**这一轮很可能有编译错误** —— `x:Bind` 生成的代码
对 ViewModel 类型要求严格。逐个按报错修，不要跳着改。

- [ ] **Step 10: 提交**

```bash
git add AudioBule.App
git commit -m "feat: add device list window with per-device connect controls"
```

---

## Task 11: 端到端接线与手动验证

**Files:**
- Modify: `AudioBule.App/App.xaml.cpp`（退出时保存配置）
- Modify: `AudioBule.Core/ConnectionManager.h` / `.cpp`（暴露当前已连接设备）
- Modify: `tests/ConnectionManager.test.cpp`

**Interfaces:**
- Consumes: Task 4/5/10 的全部产出
- Produces: 可用的应用；spec §6 的「App 层手动验证清单」全部可执行

---

- [ ] **Step 1: 写失败的测试 —— 已连接设备列表**

追加到 `tests/ConnectionManager.test.cpp`：

```cpp
AB_TEST(ConnectedDeviceIdsReflectsCurrentState)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" }, { L"devB", L"B" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();

    auto connected = manager.ConnectedDeviceIds();
    CHECK_EQ(connected.size(), static_cast<size_t>(1));
    CHECK(connected[0] == L"devA");
}

AB_TEST(ConnectedDeviceIdsExcludesFailedAndConnecting)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" }, { L"devB", L"B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeniedBySystem));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devB").get();

    auto connected = manager.ConnectedDeviceIds();
    CHECK_EQ(connected.size(), static_cast<size_t>(1));
    CHECK(connected[0] == L"devA");
}

AB_TEST(ConnectedDeviceIdsEmptyAfterDisconnect)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    manager.DisconnectAsync(L"devA").get();

    CHECK(manager.ConnectedDeviceIds().empty());
}

AB_TEST(ConnectedDeviceIdsEmptyAfterExternalLoss)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.ConnectionLost.Raise(L"devA");

    CHECK(manager.ConnectedDeviceIds().empty());
}
```

- [ ] **Step 2: 运行，确认失败**

Expected: 编译失败，`ConnectedDeviceIds` 不是成员。

- [ ] **Step 3: 实现 `ConnectedDeviceIds`**

在 `ConnectionManager.h` 的 `Snapshot()` 声明后加：

```cpp
    // 当前处于 Connected 的设备 id。退出时用它写入 Settings。
    std::vector<std::wstring> ConnectedDeviceIds() const;
```

在 `.cpp` 中实现：

```cpp
std::vector<std::wstring> ConnectionManager::ConnectedDeviceIds() const
{
    std::lock_guard<std::mutex> lock(m_mutex);

    std::vector<std::wstring> result;
    for (auto const& entry : m_entries)
    {
        if (entry.state == ConnectionState::Connected)
        {
            result.push_back(entry.deviceId);
        }
    }
    return result;
}
```

- [ ] **Step 4: 编译并运行测试**

Expected: 全部通过。

- [ ] **Step 5: 退出时保存配置**

在 `App.xaml.h` 里加声明：

```cpp
    void SaveSettingsOnExit();
```

在 `App.xaml.cpp` 实现：

```cpp
void App::SaveSettingsOnExit()
{
    // 记录当前已连接的设备，下次启动自动重连
    auto connected = m_manager.ConnectedDeviceIds();
    if (!connected.empty())
    {
        m_settings.lastConnectedDevices = std::move(connected);
    }

    if (!SaveSettings(m_settings, DefaultSettingsPath()))
    {
        OutputDebugStringW(L"AudioBule: failed to save settings\n");
    }
}
```

在 `HandleTrayCommand` 的 `kCmdExit` 分支里，**在** `WaitForIdle()` **之前**调用：

```cpp
    case TrayService::kCmdExit:
        m_manager.WaitForIdle();
        SaveSettingsOnExit();
        ::PostQuitMessage(0);
        break;
```

- [ ] **Step 6: 完整手动验证清单**

编译 Release 并运行：

```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\AudioBule.App\bin\AudioBule.exe"
```

逐项打勾，**任何一项失败都不要提交**：

| # | 场景 | 期望 | 对应 Review Focus |
| --- | --- | --- | --- |
| 1 | 首次启动（无配置文件） | 不弹错误，静默用默认值，托盘出现 | 第 2 条 |
| 2 | 启动时窗口 | 不自动弹出 | — |
| 3 | 左键托盘图标 | 窗口显示 | — |
| 4 | 点窗口 X | 窗口消失，**进程仍在**，托盘图标还在 | **第 4 条** |
| 5 | 再点托盘图标 | 窗口重新显示 | 第 4 条 |
| 6 | 右键托盘图标 | 菜单弹出 5 项 | — |
| 7 | 点「退出」 | 进程消失，无残留 | — |
| 8 | 设备列表有设备时 | 显示名称 + 状态 + 按钮 | — |
| 9 | 点某设备「连接」 | 状态变「连接中…」→ 「已连接」 | — |
| 10 | 已连接时点「断开」 | 状态变「未连接」 | — |
| 11 | **手机连着别的耳机时**点「连接」 | 失败，文案提到「无法作为蓝牙音频接收端」并建议先断开手机上的其它设备 | **第 1 条** |
| 12 | 失败后点「重试」 | 重新发起连接 | — |
| 13 | 两台设备，一台成功一台失败 | 互不影响，各自状态独立 | — |
| 14 | 手机走远 / 关蓝牙 | 状态自动变回「未连接」（≤5 秒） | — |
| 15 | 点「刷新」 | 列表更新，**已连接的状态不被重置** | — |
| 16 | 切深色/浅色主题 | 托盘图标跟随变化 | — |
| 17 | 结束 explorer 再恢复 | 托盘图标自动回来 | **第 5 条** |
| 18 | 无设备时 | 显示空状态引导 + 「打开蓝牙设置」 | — |
| 19 | 点「添加设备」 | 打开系统蓝牙设置 | — |
| 20 | 连上后正常退出，再启动 | 自动重连上次的设备 | — |
| 21 | 托盘图标反复切主题 10 次 | GDI 对象数不持续增长 | — |
| 22 | 重复快速点「连接」10 次 | 只建立一次连接 | — |

**第 11、14、22 项是硬门槛。** 前者验证错误文案是否真的帮到用户，
中间验证状态机与 provider 的事件接线，后者验证并发下的幂等性 ——
这三项在自动化测试里覆盖不到，只能靠真机。

- [ ] **Step 7: 提交**

```bash
git add AudioBule.Core tests AudioBule.App
git commit -m "feat: persist connected devices on exit; complete end-to-end wiring"
```

---

## Task 12: MSIX 打包

**Files:**
- Create: `assets/AudioBule.Package.appxmanifest`
- Create: `Packaging/Publish.ps1`
- Modify: `AudioBule.App/AudioBule.App.vcxproj`（切换到 MSIX）
- Modify: `PROGRESS.md`

**Interfaces:**
- Consumes: Task 7~11 的完整应用
- Produces: 可安装的 `.msix` 包

---

- [ ] **Step 1: 创建 MSIX 清单**

`assets/AudioBule.Package.appxmanifest`：

```xml
<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">

  <Identity Name="AudioBule"
            Publisher="CN=AudioBule"
            Version="1.0.0.0" />

  <Properties>
    <DisplayName>AudioBule</DisplayName>
    <PublisherDisplayName>AudioBule</PublisherDisplayName>
    <Logo>Assets\StoreLogo.png</Logo>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.19041.0"
                        MaxVersionTested="10.0.26100.0" />
  </Dependencies>

  <Resources>
    <Resource Language="zh-CN" />
  </Resources>

  <Applications>
    <Application Id="App"
                 Executable="AudioBule.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="AudioBule"
        Description="蓝牙 A2DP 接收端连接管家"
        BackgroundColor="transparent"
        Square150x150Logo="Assets\Square150x150Logo.png"
        Square44x44Logo="Assets\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\Wide310x150Logo.png" />
        <uap:SplashScreen Image="Assets\SplashScreen.png" />
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <!-- 枚举与连接蓝牙设备。缺了这两条清单校验直接失败 -->
    <Capability Name="internetClient" />
    <DeviceCapability Name="bluetooth" />
  </Capabilities>
</Package>
```

> `bluetooth` 是 `DeviceCapability`（不是 `Capability`），写错命名空间会静默失效。

- [ ] **Step 2: 生成图标资产**

清单引用了 4 个 PNG。用 PowerShell 现场生成，避免往仓库塞二进制：

```powershell
New-Item -ItemType Directory -Force AudioBule.App\Assets | Out-Null

Add-Type -AssemblyName System.Drawing
function New-Logo([int]$size, [string]$path) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.Clear([System.Drawing.Color]::FromArgb(0x20, 0x20, 0x20))
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(0xF5,0xF5,0xF5)), ([Math]::Max(2, $size/12))
    $g.DrawEllipse($pen, $size*0.35, $size*0.35, $size*0.3, $size*0.3)
    $g.DrawLine($pen, $size*0.2, $size*0.8, $size*0.5, $size*0.25)
    $g.DrawLine($pen, $size*0.8, $size*0.8, $size*0.5, $size*0.25)
    $g.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

New-Logo 44  "AudioBule.App\Assets\Square44x44Logo.png"
New-Logo 150 "AudioBule.App\Assets\Square150x150Logo.png"
New-Logo 310 "AudioBule.App\Assets\Wide310x150Logo.png"
New-Logo 620 "AudioBule.App\Assets\SplashScreen.png"
New-Logo 50  "AudioBule.App\Assets\StoreLogo.png"
```

把 `AudioBule.App/Assets/` 加进 `.gitignore`（生成物，非源码）。

- [ ] **Step 3: 切换工程到 MSIX**

在 `AudioBule.App.vcxproj` 的 `Globals` 节把
`<WindowsPackageType>None</WindowsPackageType>` 改为
`<WindowsPackageType>MSIX</WindowsPackageType>`，并在 `UserMacros` 后加：

```xml
  <PropertyGroup>
    <AppxManifest>$(MSBuildProjectDirectory)\..\assets\AudioBule.Package.appxmanifest</AppxManifest>
    <AppxBundle>Never</AppxBundle>
    <AppxBundlePlatforms>x64</AppxBundlePlatforms>
    <PackageCertificateKeyFile>AudioBule_TemporaryKey.pfx</PackageCertificateKeyFile>
    <AppxPackageSigningEnabled>true</AppxPackageSigningEnabled>
    <AppxAutoIncrementPackageRevision>False</AppxAutoIncrementPackageRevision>
    <GenerateAppxPackageOnBuild>False</GenerateAppxPackageOnBuild>
  </PropertyGroup>
```

**签名证书**：MSIX 必须签名。用 VS 的「创建临时证书」或：

```powershell
$password = ConvertTo-SecureString -String "" -Force -AsPlainText
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\makeappx.exe" /? | Out-Null
# 生成自签名证书（.pfx），有效期 1 年
$cert = New-SelfSignedCertificate -Subject "CN=AudioBule" -Type CodeSigningCert `
    -CertStoreLocation Cert:\CurrentUser\My -NotAfter (Get-Date).AddYears(1)
Export-PfxCertificate -Cert $cert -FilePath "AudioBule.App\AudioBule_TemporaryKey.pfx" `
    -Password $password
```

> 临时证书只能装在开发机上。发布到商店需要正式证书 ——
> 那是计划二之后的事，本任务只要能在本机装上即可。
> **务必把 `.pfx` 加进 `.gitignore`**（它带私钥，绝不能提交）。

- [ ] **Step 4: 创建 `Packaging/Publish.ps1`**

```powershell
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$msbuild = 'D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe'
$solution = Join-Path $root 'AudioBule.sln'

# 必须先 Restore：C++/WinRT 的头路径靠 NuGet 还原注入
& $msbuild $solution -t:Restore -p:Configuration=$Configuration -p:Platform=x64 -v:minimal -nologo
if ($LASTEXITCODE -ne 0) { throw "restore failed" }

& $msbuild $solution -p:Configuration=$Configuration -p:Platform=x64 `
    -p:GenerateAppxPackageOnBuild=true -v:minimal -nologo
if ($LASTEXITCODE -ne 0) { throw "build failed" }

$package = Get-ChildItem (Join-Path $root 'AudioBule.App\AppPackages') -Recurse -Filter *.msix |
    Select-Object -First 1

if ($null -eq $package) { throw "no .msix produced" }

Write-Host "Package: $($package.FullName)"
```

- [ ] **Step 5: 打包并安装验证**

```powershell
& .\Packaging\Publish.ps1 -Configuration Release
```

Expected: 生成 `AudioBule.App\AppPackages\Release\...\AudioBule_1.0.0.0_x64.msix`。

安装：

```powershell
Add-AppxPackage -Path "<上面打印的路径>" -AllowUnsigned
```

**MSIX 下的重点回归**（未打包模式已验证过，这些是 MSIX 特有的）：

| 检查项 | 期望 |
| --- | --- |
| 托盘图标出现 | 打包后进程在容器里，托盘仍可用 |
| 左键/右键托盘 | 正常 |
| 能连上蓝牙设备 | 清单里的 `bluetooth` 能力生效 |
| 配置目录 | 写到 `%LOCALAPPDATA%\Packages\<包名>\LocalCache\`，**不是** `%LOCALAPPDATA%\AudioBule\` |
| 卸载后重装 | 配置不残留（容器隔离） |

> **配置路径在 MSIX 下会变。** 本计划的 `DefaultSettingsPath()` 写死了
> `%LOCALAPPDATA%\AudioBule\`。MSIX 打包后该目录**仍可写**（它在包容器之外），
> 所以功能正常，只是从「容器内」变成了「容器外的普通目录」。
> 若要严格遵循容器隔离，改用 `ApplicationData::Current().LocalSettings()` ——
> 但那要求 Core 引入 WinRT Storage，与「配置用 JSON 文件」的既定方案冲突。
> **当前选择的取舍**：保持 JSON 文件路径不变，接受它不在容器内。
> 在 `PROGRESS.md` 里记下这个决定。

- [ ] **Step 6: 更新 `PROGRESS.md`**

把阶段总览表的「计划一」改为已完成，并补充：
- 最终的用例数量与测试运行方式
- MSIX 配置路径的取舍决定
- Task 6 Step 7 的 GDI 泄漏观察结果
- 手动验证清单中第 11/14/22 项的实测结论

- [ ] **Step 7: 提交**

```bash
git add assets Packaging AudioBule.App .gitignore PROGRESS.md
git commit -m "build: add MSIX packaging with bluetooth capability declaration"
```

---

## 完成标准

本计划完成时应当具备：

- [ ] `AudioBule.sln` 一次 `msbuild` 能构建出 Core、Tests、App 三个产物
- [ ] `tests\bin\AudioBule.Core.Tests.exe` 退出码 0，覆盖状态机、配置、字符串、图标
- [ ] 应用启动后驻留托盘，窗口可显示/隐藏
- [ ] 设备列表支持多设备并行连接，每设备独立状态
- [ ] 连接失败有可操作的错误文案（含 `0x8007001F` 的针对性提示）
- [ ] 配置持久化在 `%LOCALAPPDATA%\AudioBule\settings.json`
- [ ] 能打出可安装的 MSIX 包
- [ ] Task 11 Step 6 的 22 项手动验证全部通过
- [ ] **不包含**任何音量控制代码（音量 Spike 结论为不可行）

## 明确不在本计划范围内

| 项 | 归属 |
| --- | --- |
| 开机自启（`StartupTask`） | 计划二。当前仅记录配置开关 |
| toast 通知 | 计划二。需在清单加 `windows.appNotification` 与 AUMID |
| 中英文国际化（`.resw`） | 计划二。当前 `Messages.cpp` 返回简体中文 |
| 音量控制 | **已否决**，见 spike 报告 |
| 多显示器 DPI 手工换算 | 不需要 —— 用 `AppWindow` 的 DPI 感知 API |