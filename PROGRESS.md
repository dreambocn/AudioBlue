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
| 计划一：主工程 | ⬜ 未编写 | 待编写 |
| 计划二：增强功能 | ⬜ 未编写 | 待编写 |

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
   写进去会报 `MSB8020 找不到 v180 的生成工具`。判断依据是
   `MSBuild\Microsoft\VC\v180\PlatformToolsets\x64\PlatformToolsets\` 下的目录名。
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

### 计划一：主工程（建议下一步写）

范围：工程骨架 + `AudioBule.Core` + `AudioBule.App` + 托盘服务 + 设备列表窗口 + 连接

对应 spec §7 的阶段 0~3，预期产出**可用的应用**。需要落实的关键点：

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