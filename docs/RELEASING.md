# Releasing Guide / 发布指南

## Release Strategy / 发布策略

- 本地发布入口：`scripts\build-release.ps1`
- GitHub 自动发布入口：`.github\workflows\release.yml`
- 正式发布触发：推送 `v*` tag，例如 `v0.1.0`

## Local Release / 本地发布

```powershell
Set-Location 'E:\Development\Project\PythonProjects\AudioBlue'
.\scripts\build-release.ps1
```

脚本会完成：

- `uv sync --frozen --all-groups`
- `npm ci`
- Python / 前端测试
- 前端构建
- PyInstaller 打包
- Inno Setup 构建安装器
- 生成 `dist\release\SHA256SUMS.txt`

本地产物目录：

- `dist\release\AudioBlue-Setup.exe`
- `dist\release\SHA256SUMS.txt`

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

- 在 `windows-latest` 上构建发布产物
- 安装 Python、`uv`、Node.js、Inno Setup
- 调用 `scripts\build-release.ps1`
- 创建 GitHub Release 并上传安装器与校验文件

## Version Rule / 版本规则

- `pyproject.toml`：项目源版本
- Git tag：`v<version>`
- 如果 tag 与项目版本不一致，发布流程会直接失败

## Maintainer Checklist / 维护者检查清单

- 运行 `uv run pytest -q`
- 运行 `Set-Location '.\ui'; npm test; npm run lint; npm run build`
- 确认 `.\scripts\build-release.ps1` 本地可执行
- 确认 `dist\release\AudioBlue-Setup.exe` 已生成
- 再推送正式 `v*` tag
