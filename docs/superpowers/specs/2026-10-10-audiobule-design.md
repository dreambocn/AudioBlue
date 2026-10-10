# AudioBule 设计规格

从零复刻并增强 AudioPlaybackConnector —— Windows 蓝牙 A2DP Sink 连接管家。

- 日期：2026-10-10
- 状态：待实现
- 参考实现：`E:\Development\Project\GitHubStar\AudioPlaybackConnector`（v1.3.1，MIT-like，作者 Richard Yu）

---

## 1. 背景与目标

### 1.1 参考程序做了什么

AudioPlaybackConnector 是一个 Windows 10 2004+ 的蓝牙 A2DP Sink 连接管家。微软在 Win10 2004 内置了 A2DP Sink 能力，但需要第三方应用来管理连接。它常驻系统托盘，用户点击图标弹出系统设备选择器，选择一台已配对的蓝牙设备即可把 PC 变成该设备的音频接收端。

参考实现共六块能力：

| 能力 | 技术实现 |
| --- | --- |
| 托盘常驻 | `Shell_NotifyIconW` + `NOTIFYICON_VERSION_4`；`WS_EX_LAYERED` + `SetLayeredWindowAttributes` 构造 0×0 全透明窗口接收消息 |
| 设备选择 | `DesktopWindowXamlSource`（XAML Islands）挂到 Win32 窗口；`DevicePicker.Show(rect, Placement::Above)` 定位到托盘图标上方 |
| A2DP 连接（核心） | `AudioPlaybackConnection::TryCreateFromId` → `StartAsync()` → `OpenAsync()`；`winrt::fire_and_forget` 协程；`StateChanged` 事件回收 |
| 状态反馈 | `DevicePicker.SetDisplayStatus`（Connecting / Connected / 错误信息 + 重试按钮 / 断开按钮） |
| 配置持久化 | `JsonObject` 读写 exe 同目录 `AudioPlaybackConnector.json`，字段 `reconnect`(bool) + `lastDevices`(string[]) |
| 图标与国际化 | SVG → Direct2D `ID2D1DeviceContext5::CreateSvgDocument` → 32bpp DIB + 1bpp mask → `CreateIconIndirect`，浅色/深色两套；gettext `.po` → `translate/po2ymo.py` → 自定义 YMO 资源格式 + FNV-1a 32 位哈希查表 |

技术栈：C++17 / C++WinRT 2.0.200602.3 / WIL 1.0.200519.2 / 工具集 v142 / 静态链接 CRT / W4 + 警告即错误 / 全局单例状态（`g_audioPlaybackConnections` 等）。

### 1.2 目标

在 `AudioBule` 从零实现一个 C++/WinUI 3 版本的同类程序，行为对齐参考实现，并补齐以下增强：

1. 规范的多设备列表窗口（连接状态徽章、刷新、配对入口）
2. 多设备并行连接与独立断开
3. 开机自启
4. 连接/断开 toast 通知
5. 每设备音量控制（需先验证可行性，见 §5）

### 1.3 非目标

- 不实现蓝牙音频转码、HFP/HFP 免提、LE Audio
- 不实现音频路由/输出设备切换（系统设置已支持）
- 不做跨平台

---

## 2. 范围

### 2.1 必须实现（基础能力）

- 托盘图标常驻，左键点击显示/隐藏设备列表窗口，右键弹菜单
- 深色/浅色主题自适应托盘图标
- 蓝牙设备枚举与配对入口（跳转系统蓝牙设置）
- 单设备连接/断开，含进行中/已连接/失败/已断开状态展示
- 多设备并行连接，每设备独立操作
- 配置持久化：开机自启开关、自动重连开关、上次连接设备列表
- 系统托盘菜单：蓝牙设置、开机自启、关于、退出
- 连接/断开 toast 通知
- 国际化：中英文

### 2.2 需先验证（Spike）

- 每设备音量读取与设置。`AudioPlaybackConnection` 不暴露音量接口，A2DP Sink 仅作为 Core Audio 渲染端点存在。必须先验证能否把连接设备关联到具体端点。验证不通过则本期不做，界面隐藏音量控件。

### 2.3 明确排除

- 音频传输/编解码逻辑（由系统处理）
- 固件升级、设备固件信息
- 统计与遥测

---

## 3. 架构

### 3.1 工程结构

```
AudioBule/
├─ AudioBule.sln
├─ Directory.Build.props          # 公共编译设置（C++ 标准、警告级别、CRT）
├─ AudioBule.Core/
│   ├─ AudioBule.Core.vcxproj     # 静态库，无 UI 依赖
│   ├─ ConnectionManager.h/.cpp   # 多设备连接状态机（唯一状态源）
│   ├─ ConnectionEntry.h          # 单设备连接条目
│   ├─ DeviceEnumerator.h/.cpp    # 设备枚举 + 配对入口
│   ├─ VolumeController.h/.cpp    # IAudioEndpointVolume 封装（Phase 2）
│   ├─ Settings.h/.cpp            # JSON 配置持久化
│   ├─ IconFactory.h/.cpp         # SVG → HICON，深浅色
│   ├─ StringUtil.h/.cpp          # UTF-8/UTF-16 转换、模块路径
│   └─ Messages.h/.cpp            # Core 层字符串查表（错误文案等）
├─ AudioBule.App/
│   ├─ AudioBule.App.vcxproj      # WinUI 3 可执行程序
│   ├─ App.xaml / App.cpp         # 启动、生命周期、单实例
│   ├─ TrayIconService.h/.cpp     # 独立线程 + message-only HWND
│   ├─ MainWindow.xaml/.cpp       # 设备列表窗口
│   ├─ DeviceItemViewModel.h/.cpp # 每行 ViewModel
│   ├─ App.xaml                   # 样式与资源字典
│   └─ ToastNotifier.h/.cpp       # toast 封装
├─ Packaging/
│   └─ AudioBule.Package.msix     # MSIX 清单
├─ assets/
│   ├─ audiobule.svg              # 源图标
│   └─ Strings/{en-US,zh-Hans}.resw
└─ tests/
    └─ AudioBule.Core.Tests/      # 无 UI 依赖的单元测试
```

### 3.2 分层原则

- **AudioBule.Core 不引用任何 WinUI 头文件**，只依赖 WinRT/Win32，因此可用普通单元测试框架测试状态机与配置读写。
- **AudioBule.App 只做呈现与平台集成**：托盘、窗口、toast、开机自启。
- **App 不直接操作 `AudioPlaybackConnection`**，一律经由 `ConnectionManager`。

### 3.3 ConnectionManager（核心）

参考实现把所有状态放在全局 `g_audioPlaybackConnections`，且连接流程是「先 `emplace` 进字典 → 失败后再查回来 `Close` + `erase`」的补救式写法。AudioBule 用显式状态机取代：

```cpp
enum class ConnectionState { Disconnected, Connecting, Connected, Failed };

struct ConnectionEntry {
    std::wstring            deviceId;
    std::wstring            displayName;
    ConnectionState         state;
    std::wstring            errorMessage;   // 仅 Failed 时有效
    AudioPlaybackConnection connection;      // 仅 Connecting/Connected 时有效
};

class ConnectionManager {
public:
    // 事件：UI 订阅即可，无需轮询
    event_token                 EntryChanged;   // 单条状态变化
    event_token                 EntriesChanged; // 集合增删（刷新时批量触发）

    IAsyncOperation<void>      ConnectAsync(std::wstring_view deviceId);
    IAsyncOperation<void>      DisconnectAsync(std::wstring_view deviceId);
    void                       ReconnectSavedDevices();

    std::vector<ConnectionEntry> Snapshot() const;   // 线程安全拷贝，供 UI 绑定
};
```

要点：

- 状态迁移集中在 `ConnectionManager` 内部，UI 不可直接改状态。
- 依赖通过 `IAudioDeviceProvider` 接口注入，生产实现包装 `AudioPlaybackConnection` 与 `DeviceInformation`，测试实现返回假对象（见 §6）。
- `Snapshot()` 返回拷贝，避免 UI 线程与工作线程共享容器。
- `ConnectionEntry::connection` 为空时其他字段有效；为空且状态为 Disconnected 时整条可回收。
- 连接成功后写入 `Settings` 的已连接设备列表，退出时保存。

### 3.4 TrayIconService（托盘桥接）

**这是本项目最关键的技术点。** WinUI 3 的 UI 线程（STA）独占主消息循环，无法在其上再跑一个 `GetMessageW` 泵去接收 `Shell_NotifyIcon` 回调；而 WinUI 3 本身**不提供任何原生托盘 API**。

方案：

1. `TrayIconService` 自建一个 STA 工作线程，在其上 `RegisterClassEx` + `CreateWindowEx(HWND_MESSAGE, ...)` 创建 **message-only 窗口**。
2. 该线程运行独立 `GetMessageW` 循环，处理 `WM_NOTIFYICON`、`WM_SETTINGCHANGE`、`WM_TASKBAR_CREATED`、自定义 `WM_TRAY_CALLBACK`。
3. 构造时由 UI 线程传入 `winrt::Windows::UI::Dispatching::DispatcherQueue`。回调触发时，用 `TryEnqueue` 把 UI 操作 post 回 UI 线程执行。
4. `DispatcherQueue::TryEnqueue` 返回 false 表示 UI 线程已退出，此时静默丢弃事件并置停止标志。

线程间约定：

- 托盘线程**只读**自身持有的 `NOTIFYICONDATAW`，任何图标/提示文本变更都由 UI 线程 post 过来执行。
- 所有跨线程 UI 操作一律经 `DispatcherQueue`，托盘线程不直接触碰 XAML 对象。

消息处理表：

| 消息 | 处理 |
| --- | --- |
| `NIN_SELECT` / `NIN_KEYSELECT` | post → 显示并激活设备列表窗口 |
| `WM_RBUTTONUP` | post → 在光标处弹 `MenuFlyout`（记录 `FocusState::Pointer`） |
| `WM_CONTEXTMENU` | post → 弹 `MenuFlyout`（键盘可达时焦点落在最后一项） |
| `WM_SETTINGCHANGE`（`ImmersiveColorSet`） | post → 重新按主题切换图标 |
| `WM_TASKBAR_CREATED` | post → 重建托盘图标（explorer 重启后补回） |

### 3.5 MainWindow（设备列表窗口）

- 单实例窗口，`AppWindow` 控制显示/隐藏/激活。
- 标题栏含「添加设备」（跳 `ms-settings:bluetooth`）与「刷新」。
- 主体 `ListView`，每个设备一个 `DeviceItemViewModel`：
  - 显示名 + 配对状态
  - 状态徽章（已连接 / 连接中 / 未连接 / 失败）
  - 连接/断开按钮（按状态启用/禁用）
  - 音量滑块（仅在 Spike 通过后启用）
  - 失败时行内显示 `errorMessage` 与「重试」
- 空列表时显示引导文案。
- 窗口关闭（点 X）时隐藏到托盘而非退出；真正退出走托盘菜单。
- 多显示器/DPI：使用 `AppWindow` 的 DPI 感知 API，不再手动做 `USER_DEFAULT_SCREEN_DPI` 换算。

### 3.6 数据流

```
用户点托盘
  └─ TrayIconService(托盘线程) 收到 NIN_SELECT
      └─ DispatcherQueue.TryEnqueue → UI 线程
          └─ MainWindow: Show() + Activate()

用户点「连接」
  └─ MainWindow(UI 线程) 调 ConnectionManager::ConnectAsync
      └─ Core 在工作线程执行 TryCreateFromId / StartAsync / OpenAsync
          └─ 状态迁移 → 触发 EntryChanged
              └─ DispatcherQueue → UI 线程更新 ListView
                  └─ 状态变 Connected → ToastNotifier 弹通知
```

### 3.7 国际化

参考实现的方案是 gettext `.po` → Python `po2ymo.py` → 自定义 YMO 二进制资源 + FNV-1a 32 位哈希查表，优点是完全不依赖 WinUI 资源系统，Core 层也能用。

AudioBule 保留这一思路但简化：

- **App 层字符串**（窗口标题、按钮、菜单项）走 WinUI 3 原生 `.resw` 资源，由 `x:Uid` 绑定。这是最地道的 WinUI 3 做法，MSBuild 自动生成 PRI，无需自建工具链。
- **Core 层字符串**（连接错误文案等）走 `Messages.h/.cpp`，以 FNV-1a 32 位哈希为键的静态表，与参考实现的 YMO 方案同源但改为编译期内联，不需要额外的资源生成脚本和 Python 环境。

两层互不重叠：Core 不产出 UI 文案，App 不硬编码 Core 的错误文案。

### 3.8 错误处理

| 场景 | 处理 |
| --- | --- |
| 系统不支持 A2DP Sink | 启动时 `ApiInformation::IsTypePresent` 检测，弹对话框说明最低系统版本后退出 |
| `TryCreateFromId` 返回 null | 状态 → `Failed`，错误文案「设备不支持 A2DP 连接」 |
| `OpenAsync` 返回 `RequestTimedOut` | 状态 → `Failed`，文案「请求超时」 |
| 返回 `DeniedBySystem` | 状态 → `Failed`，文案「被系统拒绝」 |
| 返回 `UnknownFailure` | 状态 → `Failed`，文案含 `ExtendedError` 的 HRESULT |
| 抛 `hresult_error` | 同上，格式化为 `message (0x%08X)` |
| 连接对象 `StateChanged` 到 `Closed` | 清理条目，状态 → `Disconnected`，弹断开通知 |
| 配置读写失败 | 记日志并使用默认值，不阻断启动（对齐参考实现 `CATCH_LOG` 行为） |
| 托盘图标创建失败 | 记录日志，不崩溃；窗口仍可通过其它入口打开 |

原则：任何单设备失败都不影响其它设备，也不影响程序存活。

### 3.9 持久化

沿用参考实现的 JSON 方案（简单、无依赖），配置文件放在 `%LOCALAPPDATA%\AudioBule\settings.json`（MSIX 打包下写入 exe 目录不可靠，故改用 LOCALAPPDATA）。

```json
{
  "autoReconnect": true,
  "runAtStartup": false,
  "lastConnectedDevices": [
    "BTHENUM\\{...}\\...&0000"
  ],
  "theme": "auto",
  "language": "auto"
}
```

读取失败（文件不存在/JSON 损坏/字段缺失）一律回落到默认值并正常启动。

### 3.10 开机自启与通知

- 开机自启：MSIX 打包下用 `Windows.ApplicationModel.StartupTask`；未打包场景回落到写 `HKCU\...\Run` 键。
- toast：MSIX 下用 `AppNotificationManager`。需在 Package.appxmanifest 声明 `windows.appNotification`，且 exe 需 AUMID。

---

## 4. 与参考实现的差异

| 方面 | 参考实现 | AudioBule |
| --- | --- | --- |
| UI 框架 | XAML Islands 嵌入 Win32 窗口 | WinUI 3 + Windows App SDK |
| 状态管理 | 全局变量 | `ConnectionManager` 类，事件驱动 |
| 托盘回调 | 跑在 Win32 主消息循环 | 独立线程 + `DispatcherQueue` 桥接 |
| 主交互 | `DevicePicker` 浮动选择器 | 自绘设备列表窗口 |
| 设备模型 | 单选隐式 | 多设备并行，条目独立状态 |
| 目录结构 | 单 exe + 头文件 | Core 静态库 + App 壳 + 测试 |
| 构建 | `.vcxproj` + `packages.config` | `.vcxproj` + Windows App SDK NuGet |
| 分发 | 绿色 exe | MSIX |
| 配置位置 | exe 同目录 | `%LOCALAPPDATA%` |
| 音量 | 无 | 待 Spike 验证 |
| 单元测试 | 无 | Core 层有测试 |

---

## 5. 音量控制 Spike

**问题**：`AudioPlaybackConnection` 没有音量 API。A2DP Sink 连接建立后，Windows 会创建一个 Core Audio 渲染端点承载音频，音量由 `IAudioEndpointVolume` 控制。但 API 层面没有任何从 `DeviceInformation` 到该端点的官方映射。

**待验证假设**：`DeviceInformation.Properties["System_DeviceEndpointId"]` 给出端点 ID，可直接交给 `IMMDeviceEnumerator::GetDevice(id)`。

**Spike 内容**（独立小程序，不进主分支）：

1. 枚举 `AudioPlaybackConnection::GetDeviceSelector()` 得到的设备
2. 读取 `System_DeviceEndpointId` 属性并打印
3. `IMMDeviceEnumerator::GetDevice(id)` → `Activate(IAudioEndpointVolume)`
4. `GetMasterVolumeLevelScalar` 读当前音量并打印
5. `SetMasterVolumeLevelScalar(0.5)` 验证可写
6. 确认 UI 侧音量变化能否被 `IAudioEndpointVolumeCallback::OnNotify` 捕获

**决策点**：

- 假设成立 → 按 §3 方案实现，`VolumeController` 落地
- 假设不成立但端点可枚举 → 用「设备名模糊匹配 + 端点属性比对」的兜底关联方式，并在代码中标注该关联不稳定
- 完全不可行 → 本期移除音量控件，保留接口占位

无论哪种结果，Spike 的代码都留在 `tools/volume-spike/`，作为技术决策的证据。

---

## 6. 测试策略

- **Core 层**（`tests/AudioBule.Core.Tests`）：`ConnectionManager` 状态迁移、`Settings` 读写与容错、`StringUtil` 编码转换。用接口抽象隔离 `AudioPlaybackConnection`，注入假的设备提供者。
- **App 层**：手动验证清单（托盘显示/隐藏、主题切换、explorer 重启后图标恢复、多设备并行、开机自启、toast）。
- **Spike**：手动验证，记录输出作为结论依据。

Core 层抽象是测试可行性的前提——`ConnectionManager` 依赖一个 `IAudioDeviceProvider` 接口，生产实现包 `AudioPlaybackConnection`，测试实现返回假对象。

---

## 7. 实施分期

| 阶段 | 内容 | 验收 |
| --- | --- | --- |
| 0 | 工程骨架：sln + Core/App 双工程 + MSIX + Windows App SDK 集成 | 空应用能编译、能打包、能启动 |
| 1 | Core：`Settings`、`StringUtil`、`ConnectionManager` + 抽象 + 测试 | 单元测试通过 |
| 2 | App：托盘 `TrayIconService` + 主题图标 + 菜单 | 托盘可用，点击有反应 |
| 3 | App：设备列表窗口 + 连接/断开 + 多设备并行 | 能连上真实蓝牙音箱 |
| 4 | 开机自启 + toast 通知 | 重启后自启生效，连接有通知 |
| 5 | 国际化（中英文） | 切换系统语言显示正确 |
| 6 | 音量 Spike → 按结论实现或移除 | Spike 有书面结论 |

---

## 8. 风险

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 音量不可行 | 增强功能缺失 | 已在 §5 设为独立阶段，前置 Spike，不阻塞其它阶段 |
| WinUI 3 托盘稳定性 | 托盘不显示或消息不达 | 独立线程隔离；`WM_TASKBAR_CREATED` 补回；阶段 2 单独验证 |
| MSIX toast 需要 AUMID 与快捷方式 | 通知不弹 | 阶段 0 就配置好 manifest，不留到最后 |
| C++/WinUI 3 工具链要求 VS 2022 特定版本与 Windows SDK | 环境搭建成本 | 阶段 0 先打通编译链 |
| `AudioPlaybackConnection` 需 Win10 2004+ | 老系统无法运行 | 启动时检测并给出明确提示 |
| 多设备并行未在参考实现中验证 | 系统可能不支持多路 A2DP | 阶段 3 明确验证；失败则退化为单设备并在 UI 提示 |