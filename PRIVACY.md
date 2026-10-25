# Privacy policy / 隐私说明

适用范围：本仓库的原生 C++ / WinUI 3 AudioBule 应用。更新日期：2026-10-18。

This policy covers the native C++ / WinUI 3 AudioBule application maintained in this repository. Last updated: 2026-10-18.

## 音频、设备与本地设置

- 应用通过 Windows 蓝牙音频 API 枚举已配对设备、管理连接，并由 Windows 播放来自手机的蓝牙音频。应用不提供录音、音频文件保存或向项目服务器上传音频的功能。
- 设备名称、标识和连接状态用于本机设备列表、托盘和连接通知；设备名称也可能显示在 Windows 音量合成器中。
- 语言、主题、自动重连、开机启动和通知等偏好保存在本机 `%LOCALAPPDATA%\AudioBule\settings.json`。不向项目维护者同步设置或设备列表。
- 本应用没有广告、使用统计、遥测上报、远程账户或由维护者运营的后台服务。

AudioBule uses Windows Bluetooth audio APIs to discover paired devices and manage audio reception. Windows renders the incoming audio. AudioBule does not implement audio recording, audio-file storage, analytics, advertising, or a maintainer-operated upload service. Device information and preferences are used locally and are not sent to project maintainers.

## 本地日志与诊断 / Local diagnostics

应用默认在 `%LOCALAPPDATA%\AudioBule\Logs` 记录本地运行事件、错误码及耗时，不自动上传。普通日志不记录设备原名、原始设备标识、蓝牙地址、完整用户路径、配置正文、异常原文或音频；匿名设备令牌仅在同次运行内可关联，重启后变化。启动时按 7 天保留期限清理非活动会话，每次运行的日志载荷最多 20 MiB，总量目标 100 MiB；多个活动实例可暂时超过总量目标。

设置页允许临时开启最多 15 分钟的详细日志，并手动导出最多 20 MiB 的脱敏诊断文件。导出由用户选择保存位置并决定是否分享，不包含设置原文、安装日志或内存转储。导出文件不随日志过期自动删除。崩溃转储只在用户显式使用排查工具后按 Windows 的实际配置采集，可能含私人内存数据，不适合公开分享。

Local runtime logs include event codes, errors and timings and are never uploaded automatically. Raw device names, IDs, Bluetooth addresses, user paths, configuration contents, exception text and audio are excluded. Device tokens change between sessions. Inactive sessions are cleaned on startup using a seven-day retention period; each session is limited to 20 MiB, with a 100 MiB retention target that can temporarily be exceeded by active instances. Detailed logging lasts at most 15 minutes. Users can save a sanitized diagnostic file of up to 20 MiB and choose whether to share it. Exported files must be managed separately. Optional Windows crash dumps may contain private memory data and are excluded from normal exports.

## Windows 系统集成与第三方服务

开机启动由用户在设置中启用，默认关闭。启用后，EXE 安装版和便携版在当前用户启动项中登记；MSIX 版使用 Windows StartupTask。连接通知通过 Windows App SDK 的本地应用通知功能提供，用户可以在应用设置中关闭。

发布包附带微软签名的 Windows App Runtime 离线依赖。EXE 安装程序自动为当前用户安装这些组件；便携 ZIP 由用户执行安装脚本；它不把应用设置或设备信息上传给维护者。Windows、蓝牙驱动、运行时组件及系统服务的行为由其供应商控制，微软产品的隐私说明见 [Microsoft Privacy Statement](https://privacy.microsoft.com/privacystatement)。

访问项目的 GitHub 页面、提交 Issue 或下载文件时，GitHub 会按其自身政策处理网站数据，见 [GitHub Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement)。请勿在公开 Issue 中粘贴敏感的设备信息、私人日志或凭据。

Startup integration is opt-in and disabled by default. Windows features, drivers and runtime components are provided by Microsoft or their respective vendors. Visiting GitHub or submitting an issue is subject to GitHub's privacy policy; this is separate from running the local application.

## 删除与卸载

- EXE 安装版：从应用设置或托盘菜单退出后，在 Windows“设置 → 应用”中卸载 AudioBule。卸载会移除应用文件、快捷方式、安装记录及指向本安装目录的启动项，保留用户偏好和共享运行时。
- 便携版：先在应用设置中关闭开机启动，再从设置或托盘菜单选择退出，之后删除解压目录。
- MSIX 版：在 Windows“设置 → 应用 → 已安装的应用”中卸载 AudioBule。
- 如需清除本地偏好，在应用退出后删除 `%LOCALAPPDATA%\AudioBule` 文件夹。保留该文件夹会保留已有设置。
- Windows App Runtime 是可供其他应用共享的独立组件，不会随便携目录的删除而卸载；仅在确认其他应用不再使用时，通过 Windows 的应用管理功能处理相关组件。

To remove the portable app, disable its startup option, exit through the application or tray menu, and delete the extracted directory. Uninstall an MSIX installation through Windows Settings. Local preferences can be removed separately by deleting `%LOCALAPPDATA%\AudioBule` after the app exits. Shared Windows runtime components are managed separately from the application.

## 联系

隐私问题可通过 [GitHub Issues](https://github.com/dreambocn/AudioBlue/issues) 联系维护者，请仅提供处理问题所需的最少信息。
