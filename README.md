# AudioBule

[![构建与发布](https://github.com/dreambocn/AudioBlue/actions/workflows/build.yml/badge.svg)](https://github.com/dreambocn/AudioBlue/actions/workflows/build.yml)

Windows 蓝牙音频接收工具，让电脑接收手机上的音频。原生 C++ / WinUI 3 界面，支持多个设备独立连接、系统托盘、中英文及深浅主题。

## 下载

从 [Releases](https://github.com/dreambocn/AudioBlue/releases/latest) 下载适合设备的 ZIP：Intel / AMD 64 位电脑选择 `x64`，Windows on ARM 选择 `arm64`。需要 Windows 10 2004 或更高版本及蓝牙硬件。

完整解压后，首次使用在该目录打开 PowerShell，运行下方命令，安装附带的微软签名 Windows App Runtime 1.8，再打开 `AudioBule.exe`。运行时依赖已放在包内，无需另行下载。

```powershell
# 在完整解压的发布包目录运行，安装当前用户的运行时依赖。
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-Runtime.ps1
.\AudioBule.exe
```

发布页同时提供 SHA-256 校验文件和未签名 MSIX 开发包。常规使用请选择 ZIP；MSIX 正式分发需要签名证书。

上述执行策略仅对安装脚本进程生效，不更改系统策略。

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

需要 Visual Studio 2022（v143）或 2026（v145）的 C++/Windows UI 开发工具、Windows SDK 26100，以及 PowerShell Core。ARM64 构建还需要安装对应的 C++ ARM64 工具；Windows App SDK 1.8 等 NuGet 依赖在构建时自动还原。

```powershell
# 在仓库根目录构建 x64，并运行核心测试。
.\tools\Build.ps1 -Platform x64 -RunTests

# 交叉构建 ARM64；ARM64 核心测试需在 ARM64 Windows 上加 -RunTests 执行。
.\tools\Build.ps1 -Platform ARM64

# 对应架构构建成功后，生成 ZIP、MSIX 和 SHA-256 校验文件。
.\Packaging\Publish.ps1 -Platform x64 -SkipBuild
.\Packaging\Publish.ps1 -Platform ARM64 -SkipBuild

# 使用独立构建产物进行本机窗口冒烟。
.\tools\app-smoke\Test-App.ps1 -Executable '.\artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe'
```

脚本自动探测 Visual Studio 与 Windows SDK，不依赖固定盘符。构建输出按架构、配置、工程隔离在 `artifacts\build`，发布文件在 `artifacts\packages`。NuGet 默认使用用户缓存；可通过 `$env:NUGET_PACKAGES` 指定缓存目录。直接从解决方案构建仍使用各工程原有的 `bin/obj`，此方式应顺序构建。

完整本机命令、原生截图、82 项核心测试和 52 项窗口冒烟结果见 [原生 UI 实现说明](docs/native-ui/README.md)。需要保留正在运行的版本时，可使用独立输出目录构建。HTML 设计稿见 [设计预览](docs/ui-preview/README.md)。

`Packaging\Publish.ps1` 指定 `-CertificateThumbprint` 后可签名 MSIX。真实音频、登录启动、通知和安装的验收边界见原生实现说明。

## 自动构建与发布

- 推送 `main`、提交 Pull Request 或手动运行 [构建与发布](https://github.com/dreambocn/AudioBlue/actions/workflows/build.yml)，自动构建 x64 和 ARM64，并在各自架构的 Windows 运行器上执行核心测试。
- 成功后可在该次 Actions 运行的 Artifacts 下载 `AudioBule-x64`、`AudioBule-ARM64`，保存 30 天。
- 推送与清单版本一致的标签（例如清单 `1.0.0.0` 对应 `v1.0.0`），双架构构建、测试、打包全部成功后自动创建 GitHub Release，附上两套 ZIP、MSIX 和校验文件。
- 更新版本时修改 `assets\AudioBule.Package.appxmanifest` 与应用关于页版本，再推送对应标签。标签版本不匹配时流水线会停止发布。

项目采用 [MIT 许可证](LICENSE)。
