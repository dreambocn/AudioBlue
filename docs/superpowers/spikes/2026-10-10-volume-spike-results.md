# 音量控制 Spike 结论

- 日期：2026-10-11
- 执行方式：`tools/volume-spike`，独立控制台程序
- 完整输出：[volume-spike-output.txt](volume-spike-output.txt)

## 环境

| 项 | 值 |
| --- | --- |
| 系统 | Windows（SDK 10.0.26100.0） |
| 蓝牙适配器 | Realtek Bluetooth Adapter（状态 OK） |
| 工具集 | MSVC v145 / Visual Studio Community 2026 (18.10) |
| 测试设备 | Redmi Note 11T Pro+、Xiaomi 15 |

## 验证结果

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| 系统支持 A2DP Sink | ✅ 是 | `ApiInformation::IsTypePresent(AudioPlaybackConnection)` 通过 |
| 枚举到已配对 A2DP 设备 | ✅ 是 | 枚举到 2 台 |
| **A2DP 音频真的在流** | ✅ **是** | 峰值表连续 90 秒测到 0.02~0.05 的活动；用户确认手机端出现「这台电脑」并已选中 |
| 设备有 `System_DeviceEndpointId` 属性 | ❌ **否** | 两台设备均无此属性；完整属性列表中也不含任何端点相关字段 |
| **A2DP 流入后出现蓝牙渲染端点** | ❌ **否** | 音频流入期间渲染端点始终是固定的 3 个，无新增 |
| 可读 `MasterVolumeLevelScalar` | ⛔ 无法验证 | 不存在可绑定的蓝牙端点 |
| 可写 `SetMasterVolumeLevelScalar` | ⛔ 无法验证 | 同上 |
| 音量变化回调 | ⛔ 无法验证 | 同上 |

## 决定性证据

### 证据一：A2DP 音频确实在流

前几轮测试曾因「手机没真正播放」而无效。本轮加入峰值表自证机制，
用 `IAudioMeterInformation` 对**全部**渲染端点采样，不依赖人工确认。

音频流入证据（连续 90 秒）：

```
t= 6s  [0.031]27M1 Pro (NVIDIA High Definition Audio)
t= 7s  [0.047]27M1 Pro (NVIDIA High Definition Audio)
...
t=90s  [0.045]27M1 Pro (NVIDIA High Definition Audio)

[自证] 音频在流 = 是（端点: 27M1 Pro (NVIDIA High Definition Audio)）
```

用户侧确认：手机蓝牙音频输出列表中出现了「这台电脑」并已选中。

### 证据二：音频流入时没有产生蓝牙渲染端点

音频确实在流，但整个过程中渲染端点列表**始终未变**：

```
[0] 27M1 Pro (NVIDIA High Definition Audio)
[1] 扬声器 (Senary Audio)
[2] 耳机 (Senary Audio)
```

蓝牙音频被直接送入**系统已有的渲染端点**（本次是 NVIDIA），Windows
**不会为该蓝牙设备单独实例化一个渲染端点**。

### 证据三：设备侧完全没有端点关联信息

两台设备的所有 `DeviceInformation` 属性仅为通用 PnP 属性：

```
System.ItemNameDisplay
System.Devices.DeviceInstanceId
System.Devices.Icon
System.Devices.GlyphIcon
System.Devices.InterfaceEnabled
System.Devices.IsDefault
System.Devices.PhysicalDeviceLocation
System.Devices.ContainerId
```

没有端点 ID、蓝牙地址或任何音频路由字段。

## 结论

**❌ 不采用「每设备 A2DP 音量控制」方案。**

两条独立证据各自都足以否决该方案：

1. **没有对象可绑** —— A2DP Sink 不创建独立渲染端点，不存在能绑定
   `IAudioEndpointVolume` 的蓝牙端点。
2. **即便有也无法映射** —— 设备侧不含任何端点关联字段，「名称模糊匹配」
   同样不可行（端点名为「扬声器」「耳机」，不含手机名）。

这不是实现难度问题，而是**平台不提供该能力**。

## 对主工程的影响

- **移除**设备列表窗口中的每设备音量滑块
- **不实现** `VolumeController`
- `ConnectionEntry` 不包含音量字段
- 本期范围回到：托盘 + 设备列表 + 多设备并行 + 自动重连 + 开机自启 + toast 通知 + 国际化

## 副产品发现：连接建立的可观测性

对主工程有直接价值：

- **2026-10-25 勘误**：原记录将 `State=1` 误写为 Connecting，实际是 `Opened`；
  `AudioPlaybackConnectionState` 只有 `Closed=0` 和 `Opened=1`。
  Open 成功及 Opened 表示控制连接已打开，不能单独证明手机正在送出非静音音频。
  主工程应同时处理关闭事件，并把连接状态和音频流证据分开。
- PC 只在**程序持有活动连接期间**才会在手机的音频输出列表中出现。
  程序退出后 PC 立即消失 —— 这是符合预期的行为。
- Redmi Note 11T Pro+ 的 `OpenAsync` 失败于 `0x8007001F`
  (ERROR_GEN_FAILURE)，Xiaomi 15 成功。**连接能力因设备而异**，
  UI 需要能表达「此设备当前不可连接」。

## 附：过程中的技术陷阱（供后续任务参考）

1. `Properties.Lookup()` 返回 `IInspectable`，取字符串需先 `as<Windows::Foundation::IPropertyValue>()`；类型判断方法是 `Type()` 而非 `ValueType()`
2. `AudioPlaybackConnection::StartAsync()` 返回 `void`，无结果值；只有 `OpenAsync()` 返回带 `Status` 的结果
3. MSBuild 默认注入的 SDK 头路径不含 C++/WinRT 投影头，需显式加 `<sdk>\Include\<ver>\cppwinrt\winrt`
4. `wil::com_ptr` 定义在 `<wil/com.h>`，不是 `com_ptr.h`
5. SDK 26100 中 `functiondiscoverykeysapi.h` 已不存在，属性键常量在 `functiondiscoverykeys_devpkey.h`
6. **窄 `wprintf` 按控制台 ANSI 代码页解释字节**，中文输出须先
   `SetConsoleOutputCP(CP_UTF8)` + `_setmode(_stdout, _O_U8TEXT)`
7. **`%zu` 在本机 UCRT 注解下不匹配 `size_t`**（C4473），改用 `%u` + `static_cast<unsigned>`
8. **验证「音频是否在流」必须用 `IAudioMeterInformation` 峰值表**，
   不能依赖人工确认 —— 否则无法区分「端点不存在」与「根本没播放」
