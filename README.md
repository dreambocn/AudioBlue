# AudioBlue

AudioBlue 是一个仅面向 Windows 的蓝牙音频桌面工具。

当前版本已经从最小托盘 MVP 升级为 **Python 后端 + WebView2 混合 UI**：

- Python 负责 WinRT 蓝牙音频连接、规则引擎、托盘常驻、自启动、诊断与打包
- React + TypeScript + Vite 负责 Win11 风格控制中心
- `pywebview` 负责把本地构建后的前端界面嵌入桌面窗口

## 功能概览

- 托盘常驻，左键打开或激活控制中心，右键打开托盘菜单
- 主界面包含 `Overview`、`Devices`、`Automation`、`Settings`
- 设备优先级与自动连接规则
- SQLite 本地持久化，保存配置、规则、设备缓存、连接历史、诊断快照与日志
- 开机后台启动 `--background`
- 诊断导出与安装器校验脚本
- `PyInstaller + Inno Setup` 分发路径

## 场景说明

AudioBlue 当前面向 **“远端设备把音频播放到本机”** 的场景，也就是：

- 本机作为 **A2DP sink**
- 远端手机 / 平板 / 电脑作为 **A2DP source**
- 前端和探针显示的是 **可向本机投放音频的 source 设备**

这意味着：

- 你在前端看不到普通蓝牙耳机 / 音箱并不一定是异常
- 如果当前没有命中的 A2DP source，界面会明确显示“没有匹配到 source 设备”
- `scripts\feasibility_probe.py` 与运行时使用同一套 selector，因此 probe 结果应与 Control Center 设备枚举口径一致

## 环境要求

- Windows 11 或支持 `AudioPlaybackConnection` 的 Windows 10 2004+
- [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
- `uv 0.10+`
- Python `3.12`
- Node.js / npm
- 可用的蓝牙音频设备

## 首次安装开发依赖

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv python install 3.12
uv sync
Set-Location '.\ui'
npm install
```

## 开发流程

### 1. 检查 WinRT 可用性

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\feasibility_probe.py
```

当前 probe 会输出：

- `device_selector`
- `matched_device_count`
- `devices`
- `errors`

### 2. 构建前端资源

桌面宿主默认读取 `ui\dist\index.html`，所以在运行 Python 应用前先构建前端：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm run build
```

### 3. 启动应用

前台启动：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main
```

后台托盘启动：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python -m audio_blue.main --background
```

## 如何使用

### 托盘

- 左键托盘图标：打开或激活主界面 Control Center
- 右键托盘图标：打开托盘菜单
- 托盘菜单支持设备刷新、连接/断开、打开主界面、打开 Windows 蓝牙设置、退出

### 壳层状态同步契约

- Python 壳层通过同一状态通道向 WebView 推送快照：
  - `window.dispatchEvent(new CustomEvent('audioblue:state', { detail: snapshot }))`
- 设备刷新、连接状态变化、规则更新、设置更新都复用同一推送通道
- 桥接接口包含 `set_language(language)`，支持 `system`、`zh-CN`、`en-US`

### 主界面

- `Overview`：查看当前连接状态和最近活动
- `Devices`：管理设备、连接、断开、收藏
- `Automation`：配置优先级和“设备再次出现时自动连接”
- `Settings`：切换主题、通知策略、自启动、导出诊断

### 自动连接

- 自动连接由规则引擎决定，不只是“重连上次设备”
- 规则包含：
  - 手动模式
  - 启动时自动连接
  - 设备再次出现时自动连接
- 收藏设备和优先级更靠前的设备会优先尝试
- 启动时与设备再次出现时都会执行自动连接
- 回退顺序为：规则命中候选 → 收藏 / 优先级排序 → `last_devices` reconnect fallback

## 测试

### Python 测试

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pytest -q
```

### 前端测试

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm test
```

## 打包

### 1. 构建前端

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue\ui'
npm run build
```

### 2. 生成 PyInstaller 目录版

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run pyinstaller AudioBlue.spec --noconfirm
```

输出目录：

- `dist\AudioBlue\AudioBlue.exe`
- `dist\AudioBlue\_internal\ui\index.html`

### 3. 校验打包产物

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text
```

### 4. 构建 Inno Setup 安装器

如果本机已安装 Inno Setup：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
ISCC.exe .\installer\AudioBlue.iss
```

安装器人工验证清单见：

- `installer\VERIFICATION_CHECKLIST.md`

## 运行时文件

- SQLite 数据库：`%LocalAppData%\AudioBlue\audioblue.db`
- 诊断导出目录：`%LocalAppData%\AudioBlue\diagnostics\`

### 旧版本迁移

首次升级到当前版本时，AudioBlue 会自动迁移以下旧文件到 SQLite：

- `config.json`
- `audioblue.log`
- `diagnostics\*.json`

迁移完成后：

- SQLite 成为唯一常规真源
- 旧文件不会继续作为运行时主数据源
- 旧文件会保留为 `*.legacy.bak` 备份
- 日志 / 连接历史 / 诊断记录默认按 **90 天滚动清理**

## 常见问题

### 启动后只有托盘没有主界面

这通常是使用了 `--background` 启动，或者你关闭了主窗口但应用仍在托盘常驻。可通过：

- 左键托盘直接打开主界面
- 右键托盘选择 `Open Control Center`

### 主界面打不开

先检查：

- 是否已安装 WebView2 Runtime
- 是否已先执行 `npm run build`
- 打包版中是否存在 `dist\AudioBlue\_internal\ui\index.html`

### 打包校验失败

优先运行：

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
uv run python scripts\verify_packaging_assets.py --dist-root dist --installer-script installer\AudioBlue.iss --format text
```

它会指出缺失的可执行文件、前端入口或安装脚本。
