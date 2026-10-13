# 原生 WinUI 3 界面实现

验证日期：2026-10-12，Windows 11，PowerShell Core，VS 2026 v145，x64 Release。

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

保留 `AudioBule.App\bin` 整个目录，运行其中的 `AudioBule.exe`。电脑需要 Windows 10 2004 或更高版本、蓝牙和 Windows App Runtime 1.8；桌面材质由系统能力和用户设置决定。

```powershell
# 在仓库根目录构建和验证。
$env:NUGET_PACKAGES = 'D:\NuGetPackages'
& 'D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe' `
    AudioBule.sln -restore -t:Build -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& '.\tests\bin\AudioBule.Core.Tests.exe' --gtest_brief=1
& '.\tools\app-smoke\Test-App.ps1' -ScreenshotPath '.\docs\native-ui\screenshots\devices.png'
& '.\Packaging\Publish.ps1' -Configuration Release -SkipBuild
```

已有实例占用默认输出目录时，可使用独立目录构建：

```powershell
# 独立输出目录避免覆盖正在运行的版本；完成构建后再运行测试及打包。
$reviewDirectory = Join-Path $PWD 'AudioBule.App\bin-aligned\'
& 'D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe' `
    AudioBule.App\AudioBule.App.vcxproj -t:Build -p:Configuration=Release -p:Platform=x64 "-p:OutDir=$reviewDirectory" -v:minimal -nologo
& '.\tools\app-smoke\Test-App.ps1' -Executable (Join-Path $reviewDirectory 'AudioBule.exe') `
    -ScreenshotPath '.\docs\native-ui\screenshots\alignment-devices.png'
& '.\Packaging\Publish.ps1' -Configuration Release -SkipBuild -BinaryDirectory $reviewDirectory
```

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
