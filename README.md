# AudioBule

Windows 蓝牙音频接收工具，让电脑接收手机上的音频。原生 C++ / WinUI 3 界面，支持多个设备独立连接、系统托盘、中英文及深浅主题。

## 运行

构建后的程序是 `AudioBule.App\bin\AudioBule.exe`。保留同目录的 DLL、PRI、XBF、元数据和 Assets，不能只复制 EXE。

正常运行打开设备窗口；左键点击托盘图标打开快速面板，右键打开菜单。关闭或最小化窗口后继续在托盘运行。需要结束连接时，从设置或托盘菜单选择退出并确认。

先在 Windows 蓝牙设置中配对手机，在程序中点击刷新、连接，再在手机上播放音频。

## 界面与设置

- 设备：已配对设备、连接状态、连接/断开/取消/重试。
- 设置：自动重连、开机启动、连接状态通知、系统/浅色/深色主题、系统/简体中文/English。
- 关于：使用方式、音频接收能力、版本。
- 应用图标和托盘图标统一，托盘颜色跟随任务栏主题。
- Windows 音量合成器中的已连接手机会话使用应用图标及“AudioBule · 手机名称”；无法唯一识别会话时保留系统显示。

配置保存在 `%LOCALAPPDATA%\AudioBule\settings.json`，语言和主题切换立即生效。开机启动默认关闭，用户启用后登录仅驻留托盘。

## 开发与验证

需要 Visual Studio C++/Windows UI 开发工具、Windows SDK 26100、Windows App SDK 1.8，以及 PowerShell Core。Windows 最低版本为 10 2004。

在仓库根目录用 MSBuild 构建 `AudioBule.sln` 的 `Release|x64`，运行 `tests\bin\AudioBule.Core.Tests.exe` 和 `tools\app-smoke\Test-App.ps1`。各配置共用 bin/obj，请顺序构建。

完整本机命令、原生截图、82 项核心测试和 52 项窗口冒烟结果见 [原生 UI 实现说明](docs/native-ui/README.md)。需要保留正在运行的版本时，可使用独立输出目录构建。HTML 设计稿见 [设计预览](docs/ui-preview/README.md)。

`Packaging\Publish.ps1` 生成 MSIX；指定 `-CertificateThumbprint` 后签名。未签名包仅用于开发验证。真实音频、登录启动、通知和安装的验收边界见原生实现说明。
