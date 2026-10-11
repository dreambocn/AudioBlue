# AudioBule 项目进度

- 最后更新：2026-10-11
- 仓库：`E:\Development\Project\GitHubStar\AudioBule`
- 当前分支：`main`（无远程）

## 一句话状态

**设计规格已完成并批准；音量控制 Spike 已执行完毕并得出否定结论；主工程尚未开始。**

---

## 阶段总览

| 阶段 | 状态 | 产出 |
| --- | --- | --- |
| 设计规格（spec） | ✅ 完成并批准 | `docs/superpowers/specs/2026-10-10-audiobule-design.md` |
| 环境准备 | ✅ 完成 | 见下文「环境事实」 |
| 计划 0：音量 Spike | ✅ 执行完毕 | `docs/superpowers/spikes/2026-10-10-volume-spike-results.md` |
| 计划一：主工程 | 🔨 进行中：Core 层已完成并实测通过 | `docs/superpowers/plans/2026-10-11-audiobule-main-app.md`（12 个 Task） |
| 计划二：增强功能 | ⬜ 未编写 | 待编写 |

### 计划一当前进度

| Task | 内容 | 状态 |
| --- | --- | --- |
| 1 | 解决方案骨架 + `Directory.Build.props` + GoogleTest | ✅ 实测通过 |
| 2 | `SimpleEvent` + `StringUtil` | ✅ 实测通过 |
| 3 | `Settings` JSON 持久化 | ✅ 实测通过 |
| 4 | `ConnectionManager` 状态机 + `IAudioDeviceProvider` | ✅ 实测通过 |
| 5 | `WinRtDeviceProvider` 生产实现 | ✅ 实测通过 |
| 6 | 托盘图标（SVG → 构建期转 .ico） | ✅ 实测通过 |
| 7 | WinUI 3 App 骨架 | ⬜ 未开始 |
| 8 | `TrayIconService`（独立线程 + DispatcherQueue） | ⬜ 未开始 |
| 9 | 托盘接线：主题图标、右键菜单、explorer 重启恢复 | ⬜ 未开始 |
| 10 | 设备列表窗口 | ⬜ 未开始 |
| 11 | 端到端接线 + 手动验证清单 | ⬜ 未开始 |
| 12 | MSIX 打包 | ⬜ 未开始 |

**构建与测试**（Debug 与 Release 均已验证）：

```powershell
$env:NUGET_PACKAGES = "D:\NuGetPackages"   # 包不装在 C 盘
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -t:Restore -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    AudioBule.sln -t:Rebuild -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& ".\tests\bin\AudioBule.Core.Tests.exe"
```

当前 **67 个用例全过**。

### 图标方案（已定，勿改）

- 设计源：`assets/icons/bluetooth.svg`（Tabler Icons，MIT）
- 构建期由 `assets/icons/Build-Icons.ps1` 用 ImageMagick（装在 D 盘）转成
  深/浅两套多分辨率 `.ico`（16/24/32/48），作为 RCDATA 资源嵌入 exe
- **运行期不渲染 SVG**：Direct2D 的 SVG 支持需要硬件 D3D11 设备，
  实测 WARP 不被 Direct2D 支持（`CreateDevice` 返回 `0x80070057`），
  硬件设备创建在无 GPU 环境会阻塞 30 秒以上

---

## 已确定的产品决策

这些是 brainstorming 阶段与你确认过的，后续计划不应再回头质疑：

| 决策点 | 结论 |
| --- | --- |
| 项目性质 | **从零复刻**，不基于 AudioPlaybackConnector 改造 |
| 范围 | 复刻 + 增强 |
| 技术栈 | **C++ / WinUI 3 + Windows App SDK** |
| 分发形态 | **MSIX 打包** |
| 工程结构 | `AudioBule.Core` 静态库 + `AudioBule.App` WinUI 3 壳 |
| 托盘回调桥接 | **独立线程 + message-only HWND + DispatcherQueue** |
| 托盘点击行为 | 切换**自绘设备列表窗口**（非 DevicePicker 浮动选择器） |
| 音量控制 | **❌ 已否决**（见下节） |

### 音量控制为何被移除

Spike 实测证明两条独立事实，各自都足以否决「每设备音量滑块」：

1. **Windows A2DP Sink 不为蓝牙设备创建独立的 Core Audio 渲染端点**。
   音频被直接送入系统已有的渲染端点（测试机上是 NVIDIA），因此不存在
   能绑定 `IAudioEndpointVolume` 的对象。
2. **设备侧不含任何端点关联信息**。两台测试设备的 `DeviceInformation`
   属性只有 7 项通用 PnP 字段，没有端点 ID、蓝牙地址或音频路由字段。
   即便端点存在，「名称模糊匹配」也不可行（端点名为「扬声器」「耳机」）。

**对主工程的约束**：不要实现 `VolumeController`，不要设计每设备音量滑块，
`ConnectionEntry` 不含音量字段。

---

## 环境事实（已实测验证，务必沿用）

| 项 | 值 |
| --- | --- |
| Visual Studio | Community **2026**，18.10.12224.181 |
| VS 安装路径 | `D:\Applications\Microsoft Visual Studio\18\Community` |
| **PlatformToolset** | **`v145`** |
| Windows SDK | **10.0.26100.0** |
| Windows SDK 路径 | **`D:\Windows Kits\10`**（非默认路径） |
| MSVC 编译器 | 14.51.36231 |
| MSBuild | 18.7.8 |
| .NET SDK | 10.0.301 |
| NuGet 缓存 | Windows App SDK 2.2.0 / WinUI 2.2.1 / C++WinRT 3.0.260520.1 / WIL 1.0.260126.7 |

**构建命令**（msbuild 不在 PATH，必须用完整路径）：
```powershell
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    <proj> -t:Restore -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
```

### 三个会让人白忙的环境坑

1. **`<PlatformToolset>` 必须写 `v145`**。`v180` 是 MSBuild 目录名与工程版本号，
   写进去会报 `MSB8020 找不到 v180 的生成工具`。实际工具集目录是
   `MSBuild\Microsoft\VC\v180\Platforms\x64\PlatformToolsets\v145`
   （**是 `Platforms\x64\PlatformToolsets`，不是 `PlatformToolsets\x64\PlatformToolsets`**）。
2. **`<WindowsTargetPlatformVersion>` 必须显式写 `10.0.26100.0`**。
   留 `10.0` 会去找默认路径 `C:\Program Files (x86)\Windows Kits\10` 而找不到。
3. **必须先 `-t:Restore`**，否则报 `无法打开包括文件: "wil/common.h"`。

---

## 已知技术陷阱（Spike 期间踩过，主工程会再遇到）

按「是否会造成静默错误」排序：

### 会静默产生错误结果

1. **`OpenAsync` 返回 `Success` ≠ 连接已建立。**
   实测返回 Success 后 `State` 长时间停留在 `1(Connecting)`，而音频实际已在流。
   `ConnectionManager` 的状态机**不能**把 `OpenAsync` 返回值当作唯一成功判据，
   必须结合 `StateChanged` 事件。

2. **验证「音频是否在流」必须用 `IAudioMeterInformation` 峰值表。**
   不能依赖人工确认播放 —— 否则无法区分「端点不存在」与「根本没播放」，
   会得出假结论。Spike 前两轮就是这么作废的。

### 会导致编译失败

3. **MSBuild 默认注入的 SDK 头路径不含 C++/WinRT 投影头。**
   注入的是 `<sdk>\Include\<ver>\winrt`（C 语言头目录），投影头实际在
   `<sdk>\Include\<ver>\cppwinrt\winrt`，需显式补进 `AdditionalIncludeDirectories`。

4. **C++/WinRT 生成的投影头是 UTF-8 无 BOM**，本机代码页 936(GBK) 会触发
   C4819，`/WX` 升级为错误。编译选项必须加 `/utf-8`。

5. **`wil::com_ptr` 定义在 `<wil/com.h>`**，不是 `com_ptr.h`。

6. **SDK 26100 中 `functiondiscoverykeysapi.h` 已不存在**，
   属性键常量在 `functiondiscoverykeys_devpkey.h`（下划线在 devpkey 前）。

7. **范围 for 遍历 WinRT 集合需要 `<winrt/Windows.Foundation.Collections.h>`**，
   缺失报 C3536/C2100。

8. **窄 `wprintf` 按控制台 ANSI 代码页解释字节**，中文输出会乱码。
   须先 `SetConsoleOutputCP(CP_UTF8)` + `_setmode(_stdout, _O_U8TEXT)`。

9. **`%zu` 在本机 UCRT 注解下不匹配 `size_t`**（C4473），
   改用 `%u` + `static_cast<unsigned>`。

### API 语义陷阱

10. **`Properties.Lookup()` 返回 `IInspectable`**，取字符串需先
    `as<Windows::Foundation::IPropertyValue>()`；类型判断方法是 `Type()`
    而非 `ValueType()`。

11. **`AudioPlaybackConnection::StartAsync()` 返回 `void`**，无结果值；
    只有 `OpenAsync()` 返回带 `Status` 的结果。

12. **`IMMDevice::GetId` 返回 CoTaskMem 分配的字符串**，需手工
    `CoTaskMemFree`，不能直接用 `wil::unique_hz`。

13. **`AudioPlaybackConnectionState` 只有 `Closed=0` 与 `Opened=1`，没有中间态。**
    `tools/volume-spike/Step2_Connect.cpp:91` 里的 `newState == 2` 判断**永远不成立**，
    是 spike 遗留的死代码。主工程不要照抄。「连接中」是 AudioBule 自己的
    `ConnectionState::Connecting`，由 `ConnectionManager` 在 `OpenAsync` 返回前维持。
    枚举定义在 `winrt/impl/windows.media.audio.0.h`。

14. **WinRT 的 `PathIO` / `StorageFile` / `FileIO` / `JsonObject::Parse`
    参数全是 `hstring`（UTF-16），没有一个收 `char const*`。**

15. **`winrt::box_value` 对 `array_view<hstring const>` 没有 `reference_traits`
    特化**，会编译失败。字符串数组必须走
    `PropertyValue::CreateStringArray(std::vector<winrt::hstring>)`。

16. **本机 NuGet 缓存中没有任何单元测试框架**（无 MSTest / Catch2 / GoogleTest）。
    主工程测试用自研的 `tests/TestHarness.h`（约 90 行控制台 exe）。

17. **WinUI 3 的 `wWinMain` 第一个参数是 `WinRT initInstance`（`IInspectable*`）**，
    不是 `HINSTANCE`/`PSTR`。这是 Windows App SDK 定义的入口约定。

## 主工程开工后新增的坑（均已实测）

### 工具链

18. **NuGet 上的 `googletest` 1.8.3 在 v145 下无法编译**。它用了已被移除的
    `std::tr1::tuple`，报 `C3083: "tr1"`。已改用 GoogleTest **1.17.0 源码**
    内置于 `third_party/googletest/`，把 `gtest-all.cc` 编进测试工程即可。
    注意 `gtest-all.cc` 会 `#include` 其余 `.cc` 文件，**不能**删减 `src\` 下的文件。

19. **`<RuntimeLibrary>` 必须设在 `ClCompile` 节，不是 `Link` 节。**
    设成默认 `/MD` 会与 Core 的 `/MT` 冲突，链接期报
    `LNK2038: MT_StaticRelease 不匹配 MD_DynamicRelease`。

20. **`std::function` 没有 `operator==`**。事件退订不能按 handler 对象比较，
    必须用 `SimpleEvent::SubscriptionId`（`Add` 返回 id，`Remove` 收 id）。

21. **别用 PowerShell 的 `Get-Content`/`Set-Content` 改源码或工程文件。**
    它们会破坏 UTF-8 无 BOM 编码（中文注释变乱码，甚至把语法改坏、
    报 `C2447: 缺少函数标题`）。用编辑工具改，或整体重写。

22. **`%zu` 与 `hstring::size_type` 等非 `size_t` 类型不匹配**（`C4477`），
    `/WX` 升级为错误。用 `%u` + `static_cast<unsigned>`。

### WinRT / Json

23. **`IJsonObject` 没有任何 `Lookup` 成员**。`JsonObject` 没有工厂，
    C++/WinRT 不为它生成投影类，只生成接口。写成 `json.Lookup(key)`
    会在运行期抛 `0x8000000B(E_BOUNDS)` 或 `0x80004002(E_NOINTERFACE)`，
    而且**编译能过**——极难定位。

24. **`IJsonObject` 的 `GetNamed*` 在字段不存在或类型不符时会抛异常**
    （`0x83750009`），不像 `Lookup` 返回 null。要用
    `GetNamedBoolean(key)` / `GetNamedArray(key)`，
    并**在每个调用点自带 try/catch** —— 这就是「LoadSettings 永不抛出」的实现处。

25. **`IJsonValue` 不继承 `IPropertyValue`**。用 `try_as<IPropertyValue>()`
    会永远失败，导致「JSON 里写了 `false` 却读成默认 `true`」这种静默错误。
    类型判断用 `IJsonValue::ValueType()` 与 `JsonValueType` 比较。

26. **`StorageFile::GetFileFromPathAsync` 在文件不存在时抛 `0x80070002`**，
    所以它**不能用来创建**文件（配置首启时文件必然不存在，`SaveSettings` 会永远失败）。
    正确做法：`StorageFolder::GetFolderFromPathAsync(parent)` +
    `folder.CreateFileAsync(name, CreationCollisionOption::ReplaceExisting)`。

27. **CppWinRT 生成的 `winrt/base.h` 里没有 `std::wstring` 的 `to_hstring` 重载**。
    且 `std::wstring → std::wstring_view → param::hstring` 是两次用户定义转换，
    隐式转换序列不允许（报「无法推导模板参数」）。
    显式构造一次即可：`winrt::hstring p{ std::wstring_view{ path } };`

28. **`hstring` 不会隐式转成 `std::wstring`**（它只有到 `wstring_view` 的转换）。
    要 `std::wstring(hstring)` 显式构造。

29. **`JsonObject::Insert` 要的是 `IJsonValue`，不是 `IInspectable`**。
    用 `JsonValue::CreateBooleanValue()` / `CreateStringValue()`，
    字符串数组先 `JsonArray` 再 `Append`。

30. **测试工程需要自己初始化 WinRT apartment**。Core 用了 `PathIO`/`JsonObject`
    等静态 API，测试入口必须 `winrt::init_apartment(multi_threaded)`
    （多线程，因为 `ConnectionManager` 会起后台线程跑连接）。
    因此**不用 `gtest_main.cc` 的默认 `main`**，自定义入口。

31. **NuGet 包目录设为 `D:\NuGetPackages`（非 C 盘）**，构建前需
    `$env:NUGET_PACKAGES = "D:\NuGetPackages"`。

---

## 设备兼容性观察

| 设备 | `OpenAsync` 结果 |
| --- | --- |
| Xiaomi 15 | ✅ 成功 |
| Redmi Note 11T Pro+ | ❌ 失败，`0x8007001F` (ERROR_GEN_FAILURE) |

**对主工程的约束**：UI 必须能表达「此设备当前不可连接」，
不能假定所有设备都能连上。

**另一个行为**：PC 只在程序**持有活动连接期间**才出现在手机的蓝牙音频输出列表中，
程序退出后立即消失。这是符合预期的行为，但会影响用户预期，需在文档中说明。

---

## 尚未编写的计划

### 计划一：主工程（计划已写完，待执行）

**计划文件**：`docs/superpowers/plans/2026-10-11-audiobule-main-app.md`

范围：工程骨架 + `AudioBule.Core` + `AudioBule.App` + 托盘服务 + 设备列表窗口 + 连接

对应 spec §7 的阶段 0~3，预期产出**可用的应用**。Task 划分：

| Task | 内容 |
| --- | --- |
| 1 | 解决方案骨架 + `Directory.Build.props` + 自研测试框架 |
| 2 | `SimpleEvent` + `StringUtil` |
| 3 | `Settings` JSON 持久化 |
| 4 | `ConnectionManager` 状态机 + `IAudioDeviceProvider` 抽象 |
| 5 | `WinRtDeviceProvider` 生产实现 |
| 6 | `IconFactory` 托盘图标 |
| 7 | WinUI 3 App 骨架（**风险最高**，含排查表） |
| 8 | `TrayIconService`（**最关键**：独立线程 + DispatcherQueue） |
| 9 | 托盘接线：主题图标、右键菜单、explorer 重启恢复 |
| 10 | 设备列表窗口 |
| 11 | 端到端接线 + 22 项手动验证清单 |
| 12 | MSIX 打包 |

需要落实的关键点：

- `AudioBule.sln` + 双工程（Core 静态库 / App WinUI 3 壳）
- `Directory.Build.props` 统一编译设置（含 `/utf-8`、工具集、SDK 版本）
- `ConnectionManager` 显式状态机，**依赖通过 `IAudioDeviceProvider` 接口注入**
  （这是 Core 层可单元测试的前提）
- `TrayIconService` 独立线程 + message-only HWND + `DispatcherQueue.TryEnqueue` 桥接
  （WinUI 3 无原生托盘 API，且 UI 线程独占主消息循环，这是全项目最关键的技术点）
- 设备列表窗口：多设备并行、每设备独立连接/断开、状态徽章、失败重试
- 配置持久化到 `%LOCALAPPDATA%\AudioBule\settings.json`（MSIX 下不能写 exe 目录）
- MSIX 打包

### 计划二：增强功能

范围：开机自启 + toast 通知 + 中英文国际化

对应 spec §7 的阶段 4~5。**注意**：音量控制已移除，不再包含。

- 开机自启：MSIX 下用 `StartupTask`，需在阶段 0 就配好 manifest
- toast：`AppNotificationManager`，需声明 `windows.appNotification`
  与 COM CLSID（AUMID），否则通知不弹
- 国际化：App 层走 `.resw`（`x:Uid`），Core 层走哈希静态表（两层互不重叠）

---

## 复现 Spike 的方法

```powershell
# 构建
& "D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe" `
    tools\volume-spike\volume-spike.sln /p:Configuration=Release /p:Platform=x64 /t:Rebuild -v:minimal -nologo

# 运行（需手机已配对且可连接）
& "E:\Development\Project\GitHubStar\AudioBule\tools\volume-spike\bin\volume-spike.exe"
```

退出码：`0` 全部通过 / `3` 结论为不可行 / `4` 连接失败 / `6` 测试无效（音频未流入）。

原始输出：`docs/superpowers/spikes/volume-spike-output.txt`

---

## 提交历史

计划一编写过程（`docs/superpowers/plans/2026-10-11-audiobule-main-app.md`）：
```
e1db843 docs: fix plan self-review findings
ee6492f docs: add plan tasks 10-12
185a327 docs: add plan task 9
19a10e9 docs: add plan task 8
204a733 docs: add plan task 7
8d70b1c docs: add plan task 6
3af1058 docs: add plan task 5
c06f43c docs: add plan task 4
d880b21 docs: add plan tasks 2-3
86a1ac8 docs: add main project implementation plan
```

主工程开工前：
```
38ad793 fix: self-verify audio flow via peak meter; confirm volume control infeasible
c0a3c2e docs: add volume control spike results (negative: not feasible)
d5a2acb feat: poll for A2DP endpoint after live connection
8ff9334 feat: establish A2DP connection before endpoint enumeration
09d1cf5 feat: enumerate render endpoints to investigate fallback association
2982727 feat: map A2DP devices to Core Audio endpoint IDs
9108114 feat: add A2DP device enumeration with OS support detection
ec548ba build: add volume control feasibility spike project
97261aa docs: correct toolset to v145 and record verified environment facts
6c002d2 docs: align spike plan with VS2026 v180 toolset and local environment
999130a docs: add volume control spike implementation plan
a756bbb docs: add AudioBule design spec
```

**注意**：`97261aa` 的提交信息写的是「v180」，但实际修正是 `v145` —— 提交信息与内容不符，
看 `git show 97261aa` 时不要被误导。