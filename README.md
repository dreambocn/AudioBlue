# AudioBlue

[![Release](https://img.shields.io/github/v/release/dreambocn/AudioBlue?display_name=tag)](https://github.com/dreambocn/AudioBlue/releases)
[![License](https://img.shields.io/github/license/dreambocn/AudioBlue)](https://github.com/dreambocn/AudioBlue/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)](https://github.com/dreambocn/AudioBlue)

Windows Bluetooth audio playback desktop utility with a Python backend and a WebView2 control center.  
一个面向 Windows 的蓝牙音频桌面工具，使用 Python 后端与 WebView2 控制中心提供现代桌面体验。

![AudioBlue hero](ui/src/assets/hero.png)

## Highlights

- **Windows-first desktop app**：为 Windows 10 2004+ / Windows 11 的蓝牙音频场景构建。  
  面向本机作为 **A2DP sink**、远端设备向本机投放音频的使用方式。
- **Hybrid architecture**：Python 负责 WinRT 设备连接、托盘、自启动、诊断与打包。  
  React + TypeScript + Vite 负责 Win11 风格控制中心界面。
- **Persistent automation**：使用 SQLite 保存设备规则、优先级、连接历史与诊断快照。  
  支持再次出现自动连接、启动时重连与设备优先级策略。
- **Release-ready packaging**：内置 PyInstaller、Inno Setup 与发布校验脚本。  
  支持本地构建安装器，也支持 GitHub Actions 基于 `v*` tag 自动发布。

## Architecture

AudioBlue 当前由三个主要层组成：

- **Desktop backend / 桌面后端**：`src/audio_blue` 中的 Python 代码负责蓝牙设备枚举、连接、规则引擎、托盘宿主、自启动与诊断导出。
- **Control center UI / 控制中心界面**：`ui` 中的 React 应用负责设备列表、自动连接设置、主题与语言切换。
- **Packaging pipeline / 打包链路**：PyInstaller 产出目录版，Inno Setup 生成安装器，`scripts/build-release.ps1` 与 GitHub Actions 统一发布入口。

## Reference Project / 参考实现

- 参考实现项目源：[`ysc3839/AudioPlaybackConnector`](https://github.com/ysc3839/AudioPlaybackConnector)
- AudioBlue 在产品目标、技术选型与界面形态上做了重新整理，但早期可行性评估和桌面音频连接方向参考了这个项目。

## Quick Start

### Runtime requirements / 运行要求

- Windows 11，或支持 `AudioPlaybackConnection` 的 Windows 10 2004+
- [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
- Python `3.12`
- `uv`
- Node.js + npm

### Install dependencies / 安装依赖

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv python install 3.12
uv sync --all-groups
Set-Location '.\ui'
npm install
```

### Run the app / 启动应用

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm run build

Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main
```

后台托盘模式：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main --background
```

## Interface Overview

- **Overview**：查看当前连接状态、最近活动与快捷控制区。
- **Devices**：管理当前可见设备、收藏状态与历史设备。
- **Automation**：配置设备再次出现时自动连接，以及自动连接尝试顺序。
- **Settings**：切换主题、语言、通知、自启动并导出诊断信息。

## Development

开发、调试、测试与本地打包的完整说明见：

- [Development Guide / 开发指南](docs/DEVELOPMENT.md)
- [Releasing Guide / 发布指南](docs/RELEASING.md)

常用命令：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pytest -q

Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm test
npm run build
```

## Packaging & Release

### Local packaging / 本地打包

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
.\scripts\build-release.ps1
```

默认会执行：

- Python 与前端依赖同步
- Python / 前端测试
- 前端构建
- PyInstaller 目录版打包
- Inno Setup 安装器构建

### GitHub Release / GitHub 自动发布

- 推送 `v*` tag 会触发 `.github/workflows/release.yml`
- 工作流会在 Windows runner 上构建安装器
- 生成的 `AudioBlue-Setup.exe` 会上传到 GitHub Release

下载入口：

- [GitHub Releases](https://github.com/dreambocn/AudioBlue/releases)

## FAQ

### Why are common Bluetooth headsets not listed? / 为什么普通蓝牙耳机不一定会出现在设备列表里？

AudioBlue 当前聚焦于 **远端设备把音频播放到本机** 的场景。  
因此界面中显示的是可以向本机投放音频的 **A2DP source** 设备，而不是所有蓝牙音频外设。

### Why is there only a tray icon after startup? / 为什么启动后可能只有托盘图标？

如果使用 `--background` 启动，或关闭主窗口但没有退出应用，AudioBlue 会继续在托盘中常驻。  
此时可以通过左键托盘图标重新打开控制中心。

### What should I check if the main window does not open? / 主界面打不开时先检查什么？

- WebView2 Runtime 是否已安装
- 是否已经构建 `ui\dist`
- 打包版中是否存在 `dist\AudioBlue\_internal\ui\index.html`

## License

This project is licensed under the MIT License.  
本项目采用 [MIT License](LICENSE) 开源协议。
