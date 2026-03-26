# Releasing Guide / 发布指南

## Release Strategy / 发布策略

- 本地发布入口：`scripts\build-release.ps1`
- GitHub 自动发布入口：`.github\workflows\release.yml`
- 正式发布触发：推送 `v*` tag，例如 `v0.1.0`

## Local Release / 本地发布

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
.\scripts\build-release.ps1 -TargetArchitecture x64
```

脚本会完成：

- `uv sync --frozen --all-groups`
- `npm ci`
- Python / 前端测试
- 前端构建
- PyInstaller 打包
- 下载目标架构对应的 WebView2 离线安装器
- Inno Setup 构建当前目标架构的双安装器

本地产物目录：

- 运行 `.\scripts\build-release.ps1 -TargetArchitecture x64` 后会生成：
  - `dist\release\AudioBlue-Setup-x64.exe`
  - `dist\release\AudioBlue-Setup-With-WebView2-x64.exe`
- 运行 `.\scripts\build-release.ps1 -TargetArchitecture x86` 后会生成：
  - `dist\release\AudioBlue-Setup-x86.exe`
  - `dist\release\AudioBlue-Setup-With-WebView2-x86.exe`
- 运行 `.\scripts\build-release.ps1 -TargetArchitecture arm64` 后会生成：
  - `dist\release\AudioBlue-Setup-arm64.exe`
  - `dist\release\AudioBlue-Setup-With-WebView2-arm64.exe`

## GitHub Release / GitHub 自动发布

### 1. Ensure version is updated / 先更新版本号

在 `pyproject.toml` 中维护项目版本。  
`v*` tag 去掉前缀后的版本必须与 `pyproject.toml` 中的版本一致。

### 2. Create and push a tag / 创建并推送 tag

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
git tag v0.1.0
git push origin v0.1.0
```

### 3. Workflow output / 工作流输出

工作流会：

- 分别在 `windows-latest` 和 `windows-11-arm` 上构建 `x64`、`x86`、`ARM64` 发布产物
- 安装目标架构对应的 Python、`uv`、Node.js、Inno Setup
- 调用 `scripts\build-release.ps1 -TargetArchitecture <arch>`
- 自动生成从上一版本到当前标签的 Release Changelog 汇总摘要
- 创建 GitHub Release 并上传 6 个安装包

## Version Rule / 版本规则

- `pyproject.toml`：项目源版本
- Git tag：`v<version>`
- 如果 tag 与项目版本不一致，发布流程会直接失败

## Maintainer Checklist / 维护者检查清单

- 运行 `uv run pytest -q`
- 运行 `Set-Location '.\ui'; npm test; npm run lint; npm run build`
- 确认 `.\scripts\build-release.ps1 -TargetArchitecture x64` 本地可执行
- 确认本地目标架构对应的 `dist\release\AudioBlue-Setup-<arch>.exe` 已生成
- 确认本地目标架构对应的 `dist\release\AudioBlue-Setup-With-WebView2-<arch>.exe` 已生成
- 再推送正式 `v*` tag
