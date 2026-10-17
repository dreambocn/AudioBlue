# AudioBule 开发指南

本文件适用于整个仓库。开始任务时先阅读本文件及工作目录下更具体的规则，检查 Git 工作区，保留已有修改。默认中文沟通，新增代码注释、提示和日志使用中文；面向用户的界面文案同时维护中英文资源。

## 项目与文档入口

AudioBule 是原生 C++ / C++/WinRT / WinUI 3 的 Windows 蓝牙音频接收应用，支持 x64、ARM64；不是 Web 应用。保留现有品牌名 `AudioBule`，不要因远程仓库名 `AudioBlue` 而批量改名。

按任务阅读相关入口，避免把历史验证结果当成本轮结果：

- [README.md](README.md)：安装、使用、构建与发布入口。
- [原生 UI 与验证](docs/native-ui/README.md)：实际界面、桌面集成、验收记录与限制。
- [UI 设计稿](docs/ui-preview/README.md)：HTML 原型及视觉参考；原生行为以实际实现为准。
- [初始设计说明](docs/superpowers/specs/2026-10-10-audiobule-design.md)：设计背景；与现有实现不一致时先核对代码。
- [隐私说明](PRIVACY.md)、[签名策略](CODE_SIGNING.md)：数据、卸载与分发约定。

## 代码地图与职责

| 位置 | 职责与入口 |
| --- | --- |
| `AudioBule.Core` | 连接状态、设备 Provider、设置、事件及音频会话标识 |
| `AudioBule.Core\ConnectionManager.*` | 唯一连接状态源、连接/断开/取消、设备快照 |
| `AudioBule.Core\IAudioDeviceProvider.h`、`WinRtDeviceProvider.*` | 可替换的设备接口与 Windows 蓝牙音频实现 |
| `AudioBule.Core\AudioSessionIdentity.*` | 系统音量合成器中的会话名称与图标处理 |
| `AudioBule.App\App.xaml.cpp`、`MainWindow.xaml*` | 应用生命周期、主窗口、导航、设置与退出 |
| `AudioBule.App\DevicePresenter.*`、`QuickPanel.*` | 主窗口和托盘共享的设备行、快速面板 |
| `AudioBule.App\TrayIconService.*`、`DesktopIntegration.*` | 托盘、启动项与通知 |
| `AudioBule.App\UiText.*`、`Strings` | 文案读取、错误格式化、`zh-CN` / `en-US` 资源 |
| `tests` | GoogleTest 测试、模拟 Provider 和回归场景 |
| `tools`、`Packaging`、`.github\workflows\build.yml` | 环境探测、构建、边界检查、原生冒烟、安装与发布 |

## 实现约束

- Core 不依赖 WinUI；App 通过 `ConnectionManager` 操作连接，不直接调用 `AudioPlaybackConnection`。边界由 `tools\Check-Layering.ps1` 检查，App 构建会调用它。
- 主窗口与托盘使用相同的连接快照和设备行逻辑，不另建一套连接状态。连接成功不等于正在播放音频，不根据连接状态伪造播放状态。
- 保持线程模型：状态迁移受锁保护，事件在解锁后触发；设备连接/断开在工作线程执行，更新 XAML 控件回到 UI 线程。不在正常 UI 交互中阻塞等待异步操作。
- 取消应立即撤销界面请求，迟到的底层连接结果仍需清理；清理完成前同设备不能重试，其他设备不受影响。修改连接逻辑时检查设备消失、迟到成功/失败、重复操作和退出中的在途任务。
- 保持订阅、异步回调、COM/WinRT 对象及窗口生命周期一致，避免析构后的回调和锁内重入。沿用现有错误码和状态传递方式。
- 默认关闭和最小化主窗口继续驻留托盘；明确退出经过确认并完成清理。`--startup` 启动仅驻留托盘，不因界面重构改变该行为。
- 音频会话标识只在能够唯一匹配时调整名称和图标，保留回退与恢复逻辑；不顺带修改音量、静音、路由或设备名称。
- 沿用工程的 C++ 标准、预编译头、NuGet 和 CRT 配置；Core、App、测试的 Debug/Release 运行库必须兼容，不随意切换 `/MT` 与 `/MD`。

## Windows 与工作目录

- 使用 PowerShell Core（`pwsh`）及 Windows 路径。其他技能中的 Bash、POSIX 环境变量和 `/tmp` 示例应转换后执行，不引入 WSL 或额外工具链。
- 先复用现有 Visual Studio、SDK、Scoop 和依赖缓存。SDK 版本及工具集以工程文件和环境探测脚本为准，不硬编码本机 Visual Studio 安装路径。
- 正式源码保留在本仓库。临时脚本、日志、截图和复现材料放在 `C:\Users\DreamBo\Documents\Codex\work\AudioBule\<任务标识>`，或 `$env:TEMP` 下独立任务目录。
- 构建输出沿用 `artifacts\build`，发布文件沿用 `artifacts\packages`；不要为了移动临时文件改变构建结构。NuGet 沿用用户缓存，必要时只在当前进程设置 `$env:NUGET_PACKAGES`。
- 不提交构建产物、私人设备信息、证书私钥和临时诊断材料。清理前核对绝对路径归属，只处理本次创建且已不需要的内容，遵循当前用户的删除与回收站规则。

## 构建与验证

以下命令在仓库根目录的 PowerShell Core 中执行：

```powershell
# 快速检查 Core 与 App 的架构边界。
.\tools\Check-Layering.ps1

# 构建 x64 Release，并执行核心测试。
.\tools\Build.ps1 -Platform x64 -Configuration Release -RunTests

# 交叉构建 ARM64；ARM64 核心测试需在 ARM64 Windows 上执行。
.\tools\Build.ps1 -Platform ARM64 -Configuration Release

# 对本次 x64 构建运行真实窗口与托盘冒烟。
.\tools\app-smoke\Test-App.ps1 -Executable '.\artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe'
```

构建脚本自动探测 Visual Studio 与 Windows SDK，并按架构、配置和工程隔离输出。不要并发启动写入同一输出目录的构建；直接使用解决方案默认输出时顺序构建，避免覆盖运行中的二进制。

按改动选择验证范围：

- 纯文档：核对路径、命令与描述，执行 `git diff --check`，无需为文档运行整个应用构建。
- Core、状态机、设置：运行相关 GoogleTest；异步和状态变更应补能捕获故障的回归场景，优先复用模拟 Provider。
- XAML、托盘、语言、主题或生命周期：构建并运行原生冒烟，针对变更检查实际窗口与交互。
- 打包、依赖、版本或 CI：检查两个架构的相关路径，按需生成包并在隔离环境验证安装流程。

报告本次实际执行的命令与结果。旧文档中的测试数量不是固定验收指标；未运行、受设备限制或环境缺失的检查明确标注，不宣称通过。

## UI 与可访问性验收

- 保持现有 Fluent、系统控件、主题资源、布局及共享组件风格；依据任务范围改进，不因通用设计技能偏好而重新设计整个应用。
- 同时检查主窗口、托盘快速面板及菜单；覆盖系统/浅色/深色、中文/英文、窄窗口、长设备名和高 DPI 下的布局。
- 界面文案走 `.resw` / PRI 与 `UiText`；同步维护稳定资源键、占位符及两种语言，保留用户设备原名。应用主题与任务栏主题可以不同，托盘图标应遵循任务栏主题。
- 检查键盘导航、可见焦点、Esc、弹窗关闭后的焦点恢复、图标按钮的可访问名称，以及控件经 UI Automation 暴露的角色与状态。不要将 Web 的 ARIA/DOM/CSS 修复直接套到 XAML。
- 验证空列表、不支持/不可用、连接中、取消清理中、已连接和失败重试等实际状态；错误信息应帮助用户确定下一步。
- HTML 原型和浏览器测试只能验证原型。截图只能证明视觉，不能替代原生键盘、读屏、状态通知和动态交互验收；自动冒烟通过不代表完整可访问性合规。
- 真实蓝牙音频、断开重连、输出设备切换、登录启动、通知展示及系统混音器渲染需要对应设备与系统环境。先确认现有连接和任务范围，避免测试干扰用户正在使用的设备。

## 打包与发布

```powershell
# 使用已有同架构 Release 构建生成安装包、ZIP、MSIX 与校验文件。
.\Packaging\Publish.ps1 -Platform x64 -Configuration Release -SkipBuild
.\Packaging\Publish.ps1 -Platform ARM64 -Configuration Release -SkipBuild
```

- 安装验证入口为 `Packaging\Test-Installer.ps1 -Installer <安装包完整路径>`，会实际安装和卸载；仅在符合脚本要求的干净测试环境运行，不在用户日常安装上试跑。
- 版本变更同步 `assets\AudioBule.Package.appxmanifest` 与关于页的中英文版本资源；标签与清单版本匹配规则以 CI 为准。
- 未签名 MSIX 与最终 EXE 安装包用途不同，签名和运行时分发沿用 `CODE_SIGNING.md` 及现有脚本。保留完整运行资源，不以单个 EXE 代替应用目录。
- 创建标签、推送、发布 Release 或更改签名状态须属于用户本次明确要求的范围；一般代码任务完成后先交付本地改动和验证结果。

## 完成交付

完成前检查 diff、无关改动及临时文件。说明行为变化、关键文件、实际验证结果和剩余限制；必要时更新对应开发或 UI 文档。技能用于辅助实现，用户要求、项目约束和真实代码决定最终行为。
