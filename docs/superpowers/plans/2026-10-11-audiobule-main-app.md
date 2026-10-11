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

<!-- APPEND-MARKER -->