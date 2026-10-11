# 主工程运行验证记录

验证时间：2026-10-11；平台：Windows、PowerShell Core、VS 2026 v145、Windows SDK 26100、x64。

## 当前结论

Task 8–10 已实现。Task 11 的自动验证通过，真实蓝牙连接验收待完成。
Task 12 已产出开发用 MSIX，安装与正式签名待验证。主工程尚不能标记为全部验收完成。

## 本轮修复的实际问题

1. 基线 exe 编译成功但启动以 `0xC00000FD` 退出。调试栈重复出现
   `XamlTypeInfoProvider::CheckOtherMetadataProvidersForName` 和 `XamlMetaDataProvider::GetXamlType`。
   `CppWinRTAddXamlReferences` 的输出目录通配符引入旧 `AudioBule.winmd`，使生成的
   `OtherProviders()` 包含自身。构建前删除旧命名元数据后，启动和窗口加载均通过。
2. 托盘使用 `Microsoft.UI.Dispatching.DispatcherQueue`，而不是计划示例中的 UWP 队列。
   `NOTIFYICON_VERSION_4` 的事件来自 `LOWORD(lParam)`，坐标来自 `wParam`。
3. message-only 窗口不接收广播，另建同线程隐藏顶层窗口接收主题和 `TaskbarCreated`。
   全部图标操作由托盘线程执行，析构使排队回调失效并唤醒消息循环。
4. `std::thread` 连接/断开工作线程显式初始化 MTA。待完成计数归零后，在锁内通知，
   避免析构已返回而工作线程仍访问条件变量。
5. 配置改用 UTF-8 文件流和同目录临时文件原子替换，避免在 WinUI STA 上 `.get()`
   WinRT 异步存储操作。原配置格式与默认值保持一致。
6. 最低系统目标修正为 `NTDDI_WIN10_VB`，对应 Windows 10 2004；旧值 RS3 不符合原注释。
7. NuGet SDK.BuildTools 使用实际可还原的 `10.0.26100.7627`，消除版本回退警告。

## 自动验证

- Debug 与 Release：`-restore -t:Rebuild` 成功。
- GoogleTest：69 个用例全部通过，新增真实 provider 工作线程的 COM 检查与 STA 配置往返检查。
- 故意复制一份旧命名 `AudioBule.winmd` 后重新构建，旧文件被自动清除且应用仍可正常启动。
- PowerShell 冒烟：`tools\app-smoke\Test-App.ps1`，测试配置用临时 LOCALAPPDATA，用户配置不受影响。
- 显示本机两台已配对手机；未主动连接或播放设备音频。
- 托盘图标 Shell 登记、启动隐藏、点击显示、X 隐藏后驻留、再次显示通过。
- 隐藏窗口时右键菜单、菜单文字、Esc 取消通过。
- 20 轮恢复和主题模拟广播后，图标仍存在，GDI 对象数 `14 → 14`。
- UI Automation 刷新和退出、正常退出码 0、无残留进程、托盘移除、配置保存通过。
- MakeAppx 完整校验通过，未使用 `/nv`；开发包包含 exe、XAML/PRI、运行时依赖和三种尺寸 PNG。

广播验证覆盖处理路径，不能代替真实结束 Explorer 或切换系统主题。

## 复现命令

在仓库根目录执行：

```powershell
$env:NUGET_PACKAGES = 'D:\NuGetPackages'
& 'D:\Applications\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe' `
    AudioBule.sln -restore -t:Rebuild -p:Configuration=Release -p:Platform=x64 -v:minimal -nologo
& '.\tests\bin\AudioBule.Core.Tests.exe' --gtest_brief=1
& '.\tools\app-smoke\Test-App.ps1'
& '.\Packaging\Publish.ps1' -Configuration Release -SkipBuild
```

需要实际切换配置时重新构建；当前工程各配置共用 bin/obj，不能并行构建两种配置。

## MSIX 产物与限制

产物：`Packaging\AppPackages\AudioBule_1.0.0.0_x64_Release_unsigned.msix`。

未签名开发包使用微软规定的 OID Publisher，供 Windows 11 的开发验证使用。
带 exe 的未签名包安装通常需要管理员权限。本轮未安装包，未创建或信任证书。
可向 `Publish.ps1` 传入已有 `-CertificateThumbprint` 生成签名包，证书主题需为 `CN=AudioBule`。

MSIX 清单声明 `runFullTrust`、`bluetooth` 和 `Microsoft.WindowsAppRuntime.1.8` 依赖。
有包身份时 bootstrap 设置为 NoOp，运行时由清单依赖提供。
配置仍用 `%LOCALAPPDATA%\AudioBule\settings.json`；安装后的实际重定向路径待验证。

## 剩余人工验收

- 两台真实手机的连接、断开、失败重试和同时播放行为。
- 手机已连接其它耳机时的错误消息与手机关闭蓝牙后的状态恢复。
- 连接进行中退出、已连接退出后重新启动自动重连。
- 真实系统主题切换、Explorer 重启、不同 DPI/多显示器。
- 签名包或开发包安装后的启动、托盘、蓝牙与配置路径。

开机自启、toast 和中英文国际化属于尚未实施的计划二。
菜单中的开机自启明确显示为未启用并禁用，避免只保存开关而给用户错误预期。

## API 依据

- [Shell_NotifyIconW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw)
- [NOTIFYICONDATAW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-notifyicondataw)
- [Message-only windows](https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features#message-only-windows)
- [MakeAppx](https://learn.microsoft.com/en-us/windows/msix/package/create-app-package-with-makeappx-tool)
- [未签名 MSIX 开发包](https://learn.microsoft.com/en-us/windows/msix/package/unsigned-package)
