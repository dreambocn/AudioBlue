# 原生 WinUI 3 界面实现

验证日期：2026-10-12，Windows 11，PowerShell Core，VS 2026 v145，x64 Release。

本文的验证结果按各节日期记录，不代表本次重新执行。下方「运行与复现」已按当前仓库脚本整理；通用环境要求见 [开发与构建](../../README.md#开发与构建)。

HTML 设计稿位于 `docs\ui-preview`；本目录截图来自实际 WinUI 程序和真实设备枚举。

## 已实现

- 主窗口采用 `NavigationView`、Mica、自定义标题栏和系统窗口按钮。设备、关于、设置分为独立页面；窄窗口自动变为图标导航及折叠导航。
- 设备卡片显示名称、语义状态点、连接进度、失败原因和连接/断开/取消/重试按钮。窗口与托盘使用相同的 `ConnectionManager` 快照及设备行组件。
- 托盘左键打开 352 DIP 快速面板，右键打开精简的 WinUI 菜单（打开窗口、设置、关于、退出）；主窗口隐藏时仍可操作。快速面板使用 Acrylic，失去焦点自动收起，支持 Esc。
- 日常设备页和托盘去掉重复的使用介绍；使用说明移到关于页，无设备时显示配对入口。
- 简体中文和 English 使用 `.resw` / PRI 资源；文字、错误、菜单、计数、对话框随语言切换。保留设备原始名称。
- 系统/浅色/深色即时切换并保存。应用主题和任务栏主题分别处理；托盘图标跟随系统任务栏，连接时附状态徽标。
- 自动重连、开机启动和连接通知使用实际设置。未打包版本使用 HKCU Run；MSIX 使用 StartupTask。通知使用 Windows App SDK AppNotificationManager。
- 正常启动打开主窗口；`--startup` / StartupTask 激活仅驻留托盘。关闭和最小化保留连接；明确退出经过 ContentDialog 确认并等待连接操作完成。
- 取消连接后立即撤销界面状态，清理完成前禁用该设备重试；底层迟到的成功会话被关闭。其它设备保持独立。
- 图标统一为蓝牙与声波组合。SVG 为设计源；ICO 和 PNG 在构建期生成并嵌入程序/安装包。
- 浮层去除残留的 `WS_DLGFRAME` / 传统非客户区边框，并关闭 DWM 默认亮色边缘；保留系统圆角、阴影和菜单的主题描边。鼠标打开使用 Pointer 焦点，键盘打开使用 Keyboard 焦点。
- 设置页操作区域统一为 160 DIP；开关轨道与下拉框的可见右边缘对齐，开/关状态文字放在轨道左侧，中英文使用同一布局。固定的“关闭窗口后继续运行”移到关于页。
- 显式使用 `AppWindow.SetIcon` 设置窗口/任务栏图标；外部 ICO 缺失时回退到 EXE 嵌入资源。

## 验证结果

- x64 Release 解决方案构建通过，架构边界检查通过。
- GoogleTest 77/77 通过，包括取消后的迟到成功/失败、设备消失、设备独立性、错误码清理、设置兼容与图标资源。
- 原生 UI Automation 冒烟 52 项通过：启动方式、真实枚举、导航、中英文、深色、窄窗口、托盘、确认/取消退出、第二次启动恢复设置，以及品牌图标像素、窗口边框样式、设置对齐、开关保存、键盘菜单/Esc 等。
- 系统广播与 Explorer 恢复路径经过模拟验证；本轮最终验证中重复广播 GDI 对象数保持 60 → 60。
- MSIX 已生成，MakeAppx 完整验证成功，未使用 `/nv`。包含中英文 PRI、页面、应用图标、StartupTask 与通知激活声明。
- 本机 `verification` 目录保存构建、核心测试、窗口冒烟和打包日志，不纳入版本控制。MSIX 内 EXE 哈希与最终构建一致，且包含 `Assets\AppIcon.ico`。

冒烟配置隔离在随机临时 LOCALAPPDATA；通过 `AUDIOBULE_SMOKE_TEST=1` 禁止测试进程修改真实启动项或注册通知。测试只枚举配对设备，没有主动连接手机或播放音频。

测试消息窗口按进程 ID 查找，避免多个实例同时存在时影响其它实例。对齐检查比较开关与下拉框的右边缘；测试截图中通知开关不可用，是测试模式禁用通知注册的结果。

## 音量合成器中的手机名称与图标

补充验证日期：2026-10-14。

Windows 代为播放 A2DP 音频，本机发现该会话属于 `Audiosrv`，原名为“麦克风 (DreamBo的Xiaomi 15 A2DP SNK)”，图标来自 `mmres.dll`。程序通过公开的 `IAudioSessionControl::SetDisplayName` / `SetIconPath` 将其显示为“AudioBule · 手机原名”及 EXE 中的品牌图标。

- 独立 MTA 线程按秒检查活动渲染端点，处理延后出现或切换输出后出现的会话，不阻塞窗口。
- 同时核对 Windows Audio 服务进程和完整的手机名称后缀，仅处理当前已连接设备。重名、未知格式、服务不可查询或缺少图标时保留系统显示。这是兼容性处理，不依赖驱动私有接口。
- 修改的是会话显示信息；不修改蓝牙设备名称、系统端点属性、音量、静音或音频路由。设备断开或正常退出时恢复原值；其它程序已覆盖的值不会被恢复逻辑覆盖。
- 公开的 `AudioPlaybackConnection` 不提供会话句柄，因此不能保证所有 Windows/驱动组合均可识别；当前 Windows 11 已实测通过。名称保留手机原名，中文/英文以及深浅主题共用品牌图标。

本轮 x64 Release 构建与架构边界检查通过，核心测试 **82/82**、原生窗口冒烟 **52/52** 通过；重复广播 GDI 对象保持 66 → 66。另在用户已有的真实活动会话上完成 **13 项检查**，覆盖图标提取、名称/图标写入读回、设备集合移除后恢复、重名回退、再次应用、析构恢复、缺失图标回退、其它会话保持原值以及音量/静音与活动状态保持原值。日志保存在本机 `verification\session-identity`。

这些检查没有主动断开或重新连接手机；“再次应用”检查通过更改已连接设备集合触发。实际系统混音器最终渲染、物理断开重连与输出切换仍需人工验收，不能用 API 读回替代界面验收。

参考：[会话名称](https://learn.microsoft.com/en-us/windows/win32/api/audiopolicy/nf-audiopolicy-iaudiosessioncontrol-setdisplayname)、[会话图标](https://learn.microsoft.com/en-us/windows/win32/api/audiopolicy/nf-audiopolicy-iaudiosessioncontrol-seticonpath)。

## 实际界面截图

仓库只保留最终的代表性截图，过程截图留在本地。

- [中文深色设置](screenshots/alignment-devices-settings-dark-zh.png)
- [英文深色设置](screenshots/alignment-devices-english-dark.png)
- [英文设备窗口](screenshots/alignment-devices-devices-english-dark.png)
- [深色快速面板](screenshots/alignment-devices-tray-dark.png)
- [精简右键菜单](screenshots/alignment-devices-menu.png)

## 运行与复现

以下命令在仓库根目录的 PowerShell Core 中执行。构建脚本自动探测 Visual Studio 与 Windows SDK，沿用用户 NuGet 缓存，不需要写死 MSBuild 或缓存路径。默认配置为 Release，输出位于 `artifacts\build\<架构>\<配置>\<工程>\bin`。

```powershell
# 构建 x64 Release，并执行核心测试。
.\tools\Build.ps1 -Platform x64 -Configuration Release -RunTests

# 明确指定本次构建的应用，验证真实窗口与托盘。
.\tools\app-smoke\Test-App.ps1 -Executable '.\artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe'

# 使用相同架构、配置的已有构建打包；需要 Inno Setup 6。
.\Packaging\Publish.ps1 -Platform x64 -Configuration Release -SkipBuild
```

正常启动可运行 `artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe`；保留完整的应用输出目录，不要只复制 EXE。运行电脑需要 Windows 10 2004 或更高版本、蓝牙和 Windows App Runtime 1.8；便携版本的运行时安装步骤见仓库首页。桌面材质由系统能力和用户设置决定。

构建 ARM64 时使用 `-Platform ARM64`，输出位于 `artifacts\build\ARM64\Release`；只有在 ARM64 Windows 上才能加 `-RunTests` 执行 ARM64 核心测试，窗口冒烟也应运行在支持目标架构的环境。使用 Debug 时，构建、冒烟路径及打包配置同步改为 Debug。

已有实例占用默认输出目录，或需要保留本次验证截图时，可使用独立任务目录。构建和打包必须传入同一个 `-BuildRoot`，以便同时定位二进制文件与中间状态：

```powershell
# 每次使用独立目录，将临时构建和过程截图留在 C 盘。
$taskRoot = Join-Path $env:USERPROFILE ('Documents\Codex\work\AudioBule\ui-review-' + [Guid]::NewGuid().ToString('N'))
$buildRoot = Join-Path $taskRoot 'build'
$null = New-Item -ItemType Directory -Path $taskRoot -Force

.\tools\Build.ps1 -Platform x64 -Configuration Release -BuildRoot $buildRoot -RunTests
.\tools\app-smoke\Test-App.ps1 -Executable (Join-Path $buildRoot 'x64\Release\AudioBule.App\bin\AudioBule.exe') `
    -ScreenshotPath (Join-Path $taskRoot 'devices.png')
.\Packaging\Publish.ps1 -Platform x64 -Configuration Release -BuildRoot $buildRoot -SkipBuild
```

发布文件默认生成到 `artifacts\packages`。只需开发验证时无需执行打包命令；验证完成后关闭本次测试进程，再按需清理独立任务目录。不要并发构建同一个输出目录。直接从解决方案构建仍使用工程原有 `bin` / `obj`，属于另一套输出布局，不与上述脚本示例混用。

## 验证边界

真实手机连接/音频播放、实际注销后开机启动、实际通知展示/点击、MSIX 安装与正式签名仍需设备和系统环境验收。本轮验证不替代这些步骤，也未启用用户的开机启动或发送测试通知。

当前 MSIX 是开发用未签名包，正式分发应使用签名证书。程序保留原有 Windows A2DP 接收能力边界，不新增设备音量或播放控制。

## 主要实现位置

- `AudioBule.App\MainWindow.xaml` / `.xaml.cpp`：标题栏、导航、设备页、设置、关于和退出确认。
- `AudioBule.App\QuickPanel.cpp`：托盘快速面板、菜单、工作区定位和 DPI 尺寸。
- `AudioBule.App\DevicePresenter.cpp`：两处界面共享设备行。
- `AudioBule.App\UiText.cpp` / `Strings`：语言资源及错误格式化。
- `AudioBule.App\DesktopIntegration.cpp`：启动项、通知注册和通知点击。
- `AudioBule.Core\ConnectionManager.cpp`：取消与后台会话清理。
- `assets\icons\Build-Icons.ps1`：统一图标生成。

系统集成参考 Microsoft 官方文档：
[StartupTask](https://learn.microsoft.com/en-us/uwp/api/windows.applicationmodel.startuptask) 与
[Windows App SDK 通知](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/app-notifications-quickstart?tabs=cpp)。


## 2026-10-18 本地日志与原生诊断

- 设置页增加日志目录、15 分钟详细日志与诊断导出，使用现有原生卡片和中英文资源；导出忙碌时禁用重复请求，前台操作结束后恢复焦点。
- 日志覆盖连接、取消迟到清理、设置、通知、托盘及退出；文件写入、属性探测、轮转和清理均在后台完成，日志不可写时保持业务回退。
- 本轮 x64 Release 与 Debug 核心测试各 105/105 通过，ARM64 Release 交叉构建通过；ARM64 上的实际执行未运行。
- 本轮原生冒烟 73/73 通过，包括实际系统保存对话框、隔离路径导出、JSONL 解析、焦点恢复及取消；重复广播期间 GDI 对象 130 → 130。
- 诊断文件格式、保留策略和开发命令见[日志与故障排查](../diagnostics/README.md)。完整实施记录和性能数据见[日志系统建设计划](../plans/2026-10-18-日志系统建设计划.md)。
- 以上验证未覆盖真实蓝牙音频连接、长时间设备阻塞、完整读屏/高 DPI 矩阵以及安装/MSIX 运行差异；没有替换或停止日常安装版，也未启用 WER 系统转储设置。

## 2026-10-25 审查修复与验证边界

- Manager 和 Provider 的外部事件使用可关闭并等待在途回调的 `CallbackGate`；连接通知携带代次，避免旧关闭事件污染新连接。`IAudioPlaybackSession` 将 WinRT 会话操作与可控制的模拟会话分开，便于回归打开/关闭时序。
- 枚举失败保留现有连接快照并显示刷新失败；成功移除的已连接设备在后台清理。
- 托盘线程就绪与 Shell 图标登记分离，暂时登记失败时保留重试。托盘图标直接读取嵌入 ICO，不再写临时文件。
- 设备筛选采用原生互斥选择控件；诊断导出使用与成功、部分成功、失败对应的 InfoBar 严重性。
- 新增 `Test-App.ps1 -TestTrayRecovery`，在隔离冒烟实例中注入首次托盘登记失败；`-TestDiagnosticPicker` 可继续覆盖导出交互。脚本增加筛选 UI Automation 选择状态断言。
- 本轮 x64、ARM64 Release 编译通过；连接相关 47 项测试连续执行 20 轮通过，图标及固定配置输入 10 项测试在不可用临时目录下通过。
- 全量测试实际运行 119 项，87 通过、32 失败，文件访问拒绝仍影响设置和日志测试。原生冒烟通过线程、窗口及品牌图标前置检查，但 Shell 托盘登记仍失败，未完成后续 UI 和可访问性验收。不得将这些结果表述为全量通过。

完整修改与证据见 [审查问题修复记录](../reviews/2026-10-25-审查问题修复记录.md)。真实蓝牙、登录启动、通知、读屏和高 DPI 等仍需对应环境验收。

## 2026-10-25 静默连接与一键重连

- “已连接”只表示接收连接已建立。手机暂停、未播放或静音不触发自动断开、故障提示或重复连接，也不显示未经证实的“正在播放”。
- 已连接设备右侧的 **重新连接** 图标按钮 在主窗口和托盘快速面板共用。重连先完成关闭，再重新打开一次；期间显示“重新连接中”，允许取消；同设备在清理完成前不能重复操作。
- 打开失败显示实际错误，不循环重试；关闭失败保留原会话和代次，显示错误供用户再次操作。主窗口的全局提示确保已连接筛选隐藏失败行时仍能看到错误，新操作或恢复后移除该设备的旧错误。
- 主窗口显示简短说明，托盘保留紧凑设备行；重连按钮提供中英文帮助文本及带设备名的可访问名称。
- `Test-Reconnect.ps1` 使用双标志启用虚拟设备，并停用会话标识修改；它覆盖原生控件、取消和语言，不连接手机。直接模拟本进程托盘回调仅验证面板控件，不代表 Shell 图标登记成功。

```powershell
# 构建后运行独立的原生重连控件验证；输出与隔离配置保留在指定证据目录。
.\tools\app-smoke\Test-Reconnect.ps1 -OutputDirectory 'C:\Users\DreamBo\Documents\Codex\work\AudioBule\reconnect-ux-20261025\native-smoke'
```

实施进度、测试结果与设备限制见 [一键重连体验优化计划](../plans/2026-10-25-一键重连体验优化.md)。该能力提供手动恢复入口，首次无声的系统链路原因仍以 [首次连接无音频排查](../diagnostics/2026-10-25-首次连接无音频排查.md) 的证据边界为准。

## 2026-10-25 设备筛选页签外观

“全部设备 / 已连接”使用文字页签模板，移除单选圆圈和重复指示条。原生单选角色与互斥选择语义保留，选中态统一驱动文字和下划线，键盘使用系统焦点视觉。

本轮双架构构建通过，隔离原生专项 51 项通过，已检查中文浅色、英文浅色/深色、窄窗口和实际焦点截图。完整读屏、高 DPI、真实方向键操作仍不作通过声明。实现与实际验证范围见 [设备筛选页签外观修复](../plans/2026-10-25-设备筛选页签外观修复.md)。

## 2026-10-25 原生连接状态同步修复

实机采样证实 SDK 打开调用返回成功时，State 属性可能尚未更新。Provider 改为在成功后短时间等待原生 Opened 状态同步，避免过早生成 `0x800704D4` 并关闭连接；真正关闭及同步超时仍清理，不依赖手机是否播放声音。

双架构构建与 57 项连接回归连续 20 轮通过。已更新正式安装版，日志显示等待 16 毫秒后连接成功；手机 ADB 确认 A2DP 已连接且没有播放，连接保持正常。实际音频出声未在本轮测试。详见 [打开结果与状态不同步导致连接失败](../diagnostics/2026-10-25-打开结果与状态不同步导致连接失败.md)。

## 2026-10-25 设备操作按钮对齐

主窗口与托盘快速面板的共享设备行使用固定两列操作区：重新连接图标在左，等宽的连接、断开、取消或重试按钮在右。重连图标隐藏时保留位置，避免主按钮及正文随连接状态横向移动。

本轮 x64、ARM64 Release 构建通过，`Test-Reconnect.ps1 -TestFilterTabs -TestActionLayout` 原生验证 71 项通过，覆盖两处界面的按钮边界、重连与取消、中英文、深色及窄窗口。检查了实际已连接截图；未重启或替换日常安装版。详见 [设备操作按钮对齐修复](../plans/2026-10-25-设备操作按钮对齐修复.md)。
