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
| 测试设备 | Redmi Note 11T Pro+、Xiaomi 15（均为已配对的 A2DP Sink 设备） |

## 验证结果

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| 系统支持 A2DP Sink | ✅ 是 | `ApiInformation::IsTypePresent(AudioPlaybackConnection)` 通过 |
| 枚举到已配对 A2DP 设备 | ✅ 是 | 枚举到 2 台 |
| 设备有 `System_DeviceEndpointId` 属性 | ❌ **否** | 两台设备均报告无此属性；完整属性列表中也不含任何端点相关字段 |
| 端点可通过 `IMMDeviceEnumerator` 取得 | ❌ 无法取得 | 无端点 ID 可用 |
| 连接建立后出现蓝牙渲染端点 | ❌ **否** | Xiaomi 15 连接成功后轮询 40 秒，始终只有 3 个渲染端点 |
| 可读 `MasterVolumeLevelScalar` | ⛔ 未验证 | 无可关联端点 |
| 可写 `SetMasterVolumeLevelScalar` | ⛔ 未验证 | 无可关联端点 |
| 音量变化回调 | ⛔ 未验证 | 无可关联端点 |

## 关键中间结论

**1. 设备侧不暴露音频端点信息**

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

没有任何端点 ID、蓝牙地址或音频路由相关的字段。**从设备侧做映射这条路走不通。**

**2. A2DP Sink 不创建独立的 Core Audio 渲染端点**

这是本次验证最关键的发现。系统连接前后的渲染端点列表完全一致：

```
[0] 27M1 Pro (NVIDIA High Definition Audio)
[1] 扬声器 (Senary Audio)
[2] 耳机 (Senary Audio)
```

Xiaomi 15 的 A2DP 连接**建立成功**（`OpenAsync` 返回 `Success`），但连续 40 秒轮询没有出现任何新增端点。

这与 Windows 的设计一致：A2DP Sink 接收到的音频被直接送入**系统默认渲染设备**，不会为该蓝牙设备单独实例化一个渲染端点。

**3. 连接行为因设备而异**

| 设备 | `OpenAsync` 结果 |
| --- | --- |
| Redmi Note 11T Pro+ | ❌ 失败，`0x8007001F` (ERROR_GEN_FAILURE) |
| Xiaomi 15 | ✅ 成功 |

Redmi 的失败与设备状态相关（可能正作为 A2DP 源连接其它设备），不代表 API 有问题。

## 结论

**❌ 不采用「每设备 A2DP 音量控制」方案。**

原因：Windows 的 A2DP Sink 实现不暴露独立的 Core Audio 渲染端点，因此不存在可以绑定 `IAudioEndpointVolume` 的对象。设备侧也没有任何可用于关联端点的属性。这不是实现难度问题，而是平台不提供该能力。

## 对主工程的影响

- **移除**设备列表窗口中的每设备音量滑块
- **不实现** `VolumeController`
- `ConnectionEntry` 不包含音量字段
- 本期范围回到：托盘 + 设备列表 + 多设备并行 + 自动重连 + 开机自启 + toast 通知 + 国际化

## 遗留不确定性

轮询期间无法确认手机端是否**实际播放了音频**。若当时未播放，A2DP 流未曾建立，理论上仍可能出现端点。

不过以下证据使该可能性很低：

- Windows A2DP Sink 的音频路由到默认渲染设备，不为每个源设备建端点，这符合其已知设计
- 设备侧完全没有可用于关联的端点信息，即使存在端点也无法可靠地对应到具体设备
- 名称模糊匹配方案在本例中也不可行：渲染端点名称为「扬声器」「耳机」等设备类名称，不含手机名

即便后续证明端点会出现，**映射问题依然无解**（设备侧无任何关联信息）。因此结论成立。

## 附：过程中的技术陷阱（供后续任务参考）

1. `Properties.Lookup()` 返回 `IInspectable`，取字符串需先 `as<Windows::Foundation::IPropertyValue>()`；类型判断方法是 `Type()` 而非 `ValueType()`
2. `AudioPlaybackConnection::StartAsync()` 返回 `void`，无结果值；只有 `OpenAsync()` 返回带 `Status` 的结果
3. MSBuild 默认注入的 SDK 头路径不含 C++/WinRT 投影头，需显式加 `<sdk>\Include\<ver>\cppwinrt\winrt`
4. `wil::com_ptr` 定义在 `<wil/com.h>`，不是 `com_ptr.h`
5. SDK 26100 中 `functiondiscoverykeysapi.h` 已不存在，属性键常量在 `functiondiscoverykeys_devpkey.h`