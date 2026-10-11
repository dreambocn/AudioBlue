# AudioBule · WinUI 3 UI 示意

此设计以仓库现有设备连接、托盘常驻和自动重连功能为基础，补齐产品规格中的设置与通知体验。设备和连接均为示例，不操作真实蓝牙设备。

HTML 保留设计阶段的交互场景；最终程序行为与验收以 [原生 UI 实现说明](../native-ui/README.md) 为准。

## 打开预览

无需安装依赖，直接在浏览器打开：

```powershell
# 在仓库根目录打开预览。
Start-Process (Join-Path $PWD 'docs\ui-preview\index.html')
```

入口 `index.html`、样式 `styles.css`、文案 `localization.js`、交互 `app.js` 和 `icons` 目录应放在一起。全部资源为本地文件，可离线预览。

## 设计范围

| 界面 | 内容与交互 |
| --- | --- |
| 主窗口 / 设备 | 已配对手机、独立连接与断开、连接中取消、失败重试、筛选、刷新、配对引导 |
| 主窗口 / 设置 | 自动重连、开机启动、关闭后继续运行、通知偏好、主题、中文 / 英文 |
| 主窗口 / 关于 | 应用标识、版本、产品用途 |
| 托盘左键 | 拟议的快捷面板，设备状态与主窗口同步，就地连接 / 断开 |
| 托盘右键 | 设备窗口、系统蓝牙设置、自动重连、开机启动、关于、退出确认 |
| 图标与规范 | 应用 SVG、浅色 / 深色任务栏单色 SVG、尺寸示意、语义色、字体与圆角 |
| 场景 | 日常使用、连接中、连接失败、空列表、蓝牙不可用 |

点击主窗口的最小化或关闭按钮，模拟隐藏到托盘；点击托盘的「退出」才断开全部示例连接。模拟连接使用短暂计时器，取消、切换场景或退出后不会产生迟到的连接状态。

设备页直接显示设备列表，不常驻产品介绍卡片；托盘快捷面板仅保留设备状态、连接操作和打开主窗口的入口，不重复展示收听说明。收听方式集中在「关于」页；未配对设备时由空列表提供配对引导，蓝牙不可用时提供对应操作提示。

## 多语言与深色模式

预览顶部和应用设置均可选择简体中文 / English / 跟随系统，以及浅色 / 深色 / 跟随系统。首次使用默认跟随系统，已有原型偏好继续保留。未支持的系统语言回退到英文。语言切换覆盖整个示意页、规范页、托盘菜单、弹窗、通知及无障碍标签，保留设备名称和品牌名；切换不会重置设备连接状态。

静态文案与动态消息模板位于 `localization.js`；数量使用 `Intl.PluralRules` 与 `Intl.NumberFormat`，日期时间使用 `Intl.DateTimeFormat`。英文按钮按内容宽度布局，较长描述允许换行，菜单预留更宽空间。原生工程落地时使用稳定资源键、完整句子和占位符组织 `.resw`，不要通过拼接翻译片段构造通知消息。

深色主题覆盖窗口、内容层、控件、托盘、菜单、弹窗、通知、规范页、焦点与悬停状态。语义颜色和强调色通过主题令牌切换，规范色板显示当前主题的真实数值。浅色任务栏使用深色图标，深色任务栏使用浅色图标；两个版本同时展示在规范页。原生程序应根据系统任务栏的实际明暗选择托盘图标，应用主题与任务栏主题可以不同。

已检查深色内容卡片：主要文字对比度约 13.77:1，次要文字约 7.98:1，辅助文字约 6.57:1。这是指定颜色组合的检查，不代表完整无障碍认证。

设置仅存储到浏览器的 `audiobule-design-preferences`，不写入真实应用的配置。配对按钮打开说明对话框，可模拟加入第三台手机。刷新只重新展示示例设备，不执行蓝牙扫描。连接状态表示连接关系，不推断是否有音频播放。

## WinUI 3 落地对应

| HTML 表达 | WinUI 3 对应 |
| --- | --- |
| 标题栏、浅色 / 深色窗口基底 | `AppWindow` / 自定义标题栏 / `MicaBackdrop` |
| 侧栏设备、设置、关于 | `NavigationView` |
| 设备列表、独立状态行 | `ListView` + 设备 ViewModel + `ConnectionManager` 状态 |
| 添加设备、连接、刷新 | `Button` / `AccentButtonStyle` |
| 自动重连等开关 | `ToggleSwitch` |
| 主题与语言选择 | `ComboBox` + `RequestedTheme` / `.resw` |
| 超时错误与蓝牙不可用 | 行内错误信息 / `InfoBar`；状态文字与颜色共同表达 |
| 配对说明、退出确认 | `ContentDialog` |
| 托盘快捷面板 | 独立轻量 WinUI 窗口 / `DesktopAcrylicBackdrop`，定位到托盘图标附近 |
| 托盘右键菜单 | 拟议 `MenuFlyout`；当前 `TrackPopupMenuEx` 也可沿用菜单结构 |
| 连接通知示意 | Windows `AppNotificationManager` |

主窗口使用 Mica 的层次概念；临时托盘面板使用 Acrylic 的半透明和背景模糊概念。浏览器里用 CSS 近似，无法表现真正的系统材质、窗口阴影、屏幕阅读器行为和 Windows 通知。字体优先 `Segoe UI Variable`，中文回退到 `Microsoft YaHei UI`。

基础控件和设备、设置卡片圆角 4px，窗口与浮层圆角 8px，尺寸基于 4px 网格。常用操作图标优先调用系统 `Segoe Fluent Icons`，字体不可用时使用本地 SVG 后备，不分发微软字体文件。应用图标保留蓝色层次，托盘图标使用单色。当前 SVG 供设计评审；正式 ICO 仍需针对 16 / 20 / 24 / 32 等尺寸栅格化并做像素检查。

## 官方应用对照调整

2026-10-11 查看 Microsoft Learn 上的 PowerToys 设置界面官方截图，结合 WinUI Gallery、NavigationView、Typography 和 Segoe Fluent Icons 的官方资料调整设计。截图用于观察布局与控件关系，不作为当前最新 PowerToys 版本的声明。

- 标题栏保留一次品牌标识，移除侧栏的重复品牌块和常驻接收说明；加入可操作的导航展开按钮，设置入口固定在侧栏底部。
- 采用中性 Mica 基底与内容层近似：浅色 `#F3F3F3 / #F9F9F9`，深色 `#202020 / #272727 / #2D2D2D`。这些 CSS 色值是原型取值，真实 Mica 随系统和背景变化。
- 设备图标采用单色轮廓，状态以文字和小点表达，移除日常设备行的彩色标签底色与重复的「已配对 · 手机」。设备操作采用普通按钮，添加设备使用强调按钮。
- 设置项分别使用紧邻的独立卡片，标题 28/36、正文 14/20、辅助文字 12/16，普通控件至少 32px 高；避免窄窗口缩小产品文字。
- 根据示意窗口本身的宽度切换导航：800px 以下折叠为图标，480px 以下只保留标题栏菜单按钮；展开时覆盖内容，选择页面或按 Escape 后收起。这是为 AudioBule 调整的断点，不是 WinUI 的默认断点。
- 中英文长文本通过换行和控件布局适配；托盘菜单、快捷面板、对话框和通知同步使用同一套文字和主题规则。

## 已有功能与拟议变化

- 已有：设备枚举、独立连接状态、连接 / 断开 / 重试、配对入口、刷新、关闭到托盘、启动时自动重连、浅深主题托盘图标。
- 新设计：`NavigationView`、设置页面、托盘快捷面板、统一的品牌图标与状态呈现。
- 尚需工程接入：开机启动、Windows 通知及其偏好、窗口主题选项、完整中英资源切换。当前托盘「开机自启」菜单仍是禁用项。
- 交互变化：当前左键托盘图标显示 / 隐藏主窗口；本示意提出左键快捷面板，面板再打开主窗口。落地时需要同步修改托盘入口，并验证键盘定位、多显示器、DPI、失焦收起与 Explorer 重启恢复。
- 不加入每设备音量：遵循 `2026-10-10-volume-spike-results.md` 的验证结论。
- 不加入播放控制、实时音量波形或输出设备切换：现有产品不提供这些能力。

## 图标文件

- `icons/app.svg`：应用图标，96 × 96 矢量画布。
- `icons/tray-dark.svg`：浅色任务栏上的深色图标，20 × 20 矢量画布。
- `icons/tray-light.svg`：深色任务栏上的浅色图标，20 × 20 矢量画布。

## 参考

- [Microsoft：PowerToys 常规设置及官方截图](https://learn.microsoft.com/en-us/windows/powertoys/general)
- [Microsoft：WinUI Gallery](https://github.com/microsoft/WinUI-Gallery)
- [Microsoft：NavigationView](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/navigationview)
- [Microsoft：Segoe Fluent Icons 字形表](https://learn.microsoft.com/en-us/windows/apps/design/iconography/segoe-fluent-icons-font)
- [Microsoft：Windows 应用材质](https://learn.microsoft.com/windows/apps/design/signature-experiences/materials)
- [Microsoft：Mica](https://learn.microsoft.com/windows/apps/design/style/mica)
- [Microsoft：Typography](https://learn.microsoft.com/windows/apps/design/signature-experiences/typography)

此阶段仅交付 HTML 设计，未替换原生 XAML、真实托盘图标或系统功能。

## 浏览器验收

2026-10-11 已通过 Chromium 交互验收。覆盖连接 / 取消 / 独立断开 / 失败重试、空列表与蓝牙不可用、配对引导、设置与托盘同步、中英切换、系统主题变化、托盘键盘操作、退出与重新打开、原型偏好保存。检查 1920 / 1440 / 1024 / 768 / 640 / 390 像素视口，页面无横向溢出，控制台无错误。

代表性截图：[英文深色窗口](preview-en-dark.png)、[深色图标规范](preview-icons-dark.png)。其余过程截图与本机 `verification*.json` 记录不纳入版本控制。

另有 13 项语言与主题验收：覆盖中英文 × 浅深色组合、跟随系统、英文长文案、开放弹窗和通知的即时语言刷新、单复数、偏好持久化和深色文字对比度。检查 1440 / 1024 / 663 / 390 像素视口。

官方应用对照调整后，以上 20 项交互检查与 13 项语言、主题检查再次通过；另有 5 项导航与图标字体检查，覆盖桌面折叠、窄窗口覆盖导航、Escape、页面切换自动收起、字号保留以及系统图标字体缺失时的 SVG 后备。
