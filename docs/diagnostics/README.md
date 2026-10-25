# 日志与故障排查

AudioBule 的诊断记录仅保存在本机，不自动上传。普通日志不会记录设备原名、蓝牙地址、原始设备 ID、用户路径、配置正文或音频。设备令牌只能关联同一次进程运行，重启后变化。

## 反馈普通问题

1. 打开“设置 → 诊断”，查看日志存储是否可用。
2. 如果需要调查连接阶段，临时开启详细日志，再复现问题。详细模式最多持续 15 分钟，退出后关闭。
3. 点击“导出诊断文件”，选择保存位置。首行为清单，后续为日志记录，可以用文本编辑器打开。
4. 将复现步骤、时间、系统与应用版本以及诊断文件一起提供给维护者；是否分享由用户决定。

界面会区分完整导出与部分导出。清单中的 `incomplete`、`skipped`、`dropped` 和 `write_failures` 用来说明材料的局限；没有记录不能证明没有发生故障。即使丢弃和跳过计数为零，历史日志超出采集预算或快照等待超时也可能使导出不完整。

## 位置与保留

- 本地目录：`%LOCALAPPDATA%\AudioBule\Logs`，每次运行使用独立随机子目录。
- 格式：UTF-8 JSON Lines；稳定事件编号和字段配合中文固定消息。
- 默认等级：Info；详细模式额外记录 Debug。
- 队列：最多 2048 条，载荷不超过 4 MiB；高等级事件预留部分容量，极端过载仍可能丢弃。
- 文件：每个最多 4 MiB，每次会话最多 5 个，总载荷不超过 20 MiB。
- 历史：启动时清理超过 7 天的非活动会话，总量目标 100 MiB；不删除其它活动进程的记录，并发运行时总量可能暂时超出目标。
- 导出：最多 20 MiB，排除设置原文、安装日志和崩溃转储；按字段白名单重新生成。

快照持有文件读句柄，阻止正在导出的文件被轮转或清理。导出期间如果文件已到轮转上限，存储可能短暂降级；界面和导出清单会报告缺失，不无限增加文件。

不要在应用运行时手动修改会话文件。退出后可以通过 Windows 文件管理器删除日志目录；用户手动导出的文件需要在所选位置单独管理。

## 日志存储不可用

应用继续管理连接，日志后台按退避策略重试。检查本地目录权限与磁盘空间；仍可尝试导出已有文件及有限的内存故障尾部。日志本身不能保证记录磁盘故障期间所有事件，也不能保证断电、强杀或崩溃前的最后事件已经落盘。

`previous_session_unclean` 只表示上次没有完整结束记录，可能来自强制关闭、系统结束、断电或日志停止超时，不能单凭该事件认定应用崩溃。

## 按需采集崩溃转储

普通日志不能提供所有原生崩溃的调用栈。以下工具只有在用户明确执行时才配置 Windows WER，不由应用、构建或冒烟自动运行。启用和恢复需要管理员 PowerShell，系统策略、MSIX 场景和调试器附加可能影响实际采集，需单独验证。

```powershell
# 只读查看 AudioBule 的应用专用转储设置。
.\tools\diagnostics\Set-CrashDumps.ps1 -Mode Status

# 在管理员 PowerShell 中显式启用，保留原始设置备份。
$dumpDirectory = 'C:\Users\DreamBo\Documents\Codex\work\AudioBule\crash-dumps'
$backupPath = Join-Path $dumpDirectory 'wer-original.clixml'
.\tools\diagnostics\Set-CrashDumps.ps1 -Mode Enable -Directory $dumpDirectory -BackupPath $backupPath

# 排查结束后恢复原有值；不删除已有转储和备份。
.\tools\diagnostics\Set-CrashDumps.ps1 -Mode Restore -BackupPath $backupPath
```

转储可能包含内存中的私人设备信息及其它数据，不具备普通日志的脱敏保证。不要将 dump 或注册表备份上传到公开 Issue。工具默认保留最多 3 个小型转储，只有在适当的私密渠道且确有必要时提供。

## 构建符号

```powershell
# 保存当前架构同次构建的应用 EXE、PDB 与摘要，便于以后定位转储。
.\tools\diagnostics\Save-Symbols.ps1 -Platform x64 -Configuration Release
```

符号单独保存在 `artifacts\symbols`，不混入用户安装包。CI 使用独立的 symbols 产物保留，发布下载流程不把它并入 Release 安装文件。分析转储时必须核对架构、版本及二进制摘要，调试器还需核对实际符号匹配。

## 开发验证

```powershell
# 构建后执行日志专项回归，材料保存到任务隔离目录。
.\tools\diagnostics\Test-Logging.ps1

# 性能测试默认不随核心回归执行，显式运行 60 秒持续负载。
.\tools\diagnostics\Test-Logging.ps1 -Benchmark -Seconds 60

# 对本次构建执行真实原生保存对话框与窗口、托盘冒烟。
.\tools\app-smoke\Test-App.ps1 -Executable '.\artifacts\build\x64\Release\AudioBule.App\bin\AudioBule.exe' -TestDiagnosticPicker
```

`TestDiagnosticPicker` 只定位本轮测试进程拥有的对话框，将导出目标设置为隔离配置目录。它校验实际生成的 JSONL 清单和日志，并覆盖保存取消及焦点恢复；截图参数使用完整 PNG 文件路径。不同 Windows Shell 的自动化角色可能不同，脚本验证本机的原生编辑窗口和按钮句柄，不对其它应用发送输入。
