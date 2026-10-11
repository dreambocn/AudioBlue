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

<!-- APPEND-MARKER -->