# Development Guide / 开发指南

## Environment / 环境要求

- Windows 10 2004+ 或 Windows 11
- Python `3.12`
- `uv`
- Node.js + npm
- WebView2 Runtime
- Inno Setup（仅本地构建安装器时需要）

## Setup / 初始化

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv python install 3.12
uv sync --all-groups

Set-Location '.\ui'
npm install
```

## Daily Development / 日常开发

### 1. Probe runtime capability / 检查运行时能力

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\feasibility_probe.py
```

### 2. Build frontend assets / 构建前端资源

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm run build
```

### 3. Run the desktop app / 运行桌面应用

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main
```

后台托盘模式：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main --background
```

## Test Matrix / 测试矩阵

### Python tests

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pytest -q
```

### Frontend tests

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm test
```

### Frontend lint and build

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm run lint
npm run build
```

## Packaging / 打包

### Directory build / PyInstaller 目录版

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pyinstaller AudioBlue.spec --noconfirm
```

### Asset verification / 打包校验

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text
```

### Installer build / 安装器构建

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
.\scripts\build-release.ps1
```

## Project Layout / 目录说明

- `src/audio_blue`：Python 桌面后端、规则引擎、托盘与数据存储
- `ui`：React + TypeScript 控制中心界面
- `scripts`：探针、打包校验与发布脚本
- `installer`：Inno Setup 安装器脚本与验证清单
- `tests`：Python 侧契约测试与运行时测试

## Troubleshooting / 常见问题

### WebView window does not appear / WebView 主窗口没有弹出

- 确认 WebView2 Runtime 已安装
- 确认 `ui\dist` 已存在
- 检查是否以 `--background` 模式启动

### Packaging fails at ISCC / ISCC 打包失败

- 确认 Inno Setup 已安装
- 确认 `ISCC.exe` 在 `PATH` 中，或者位于常见安装路径
- 先运行 `uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text`
