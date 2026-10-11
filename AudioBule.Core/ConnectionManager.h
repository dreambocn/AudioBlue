#pragma once

#include "ConnectionEntry.h"
#include "IAudioDeviceProvider.h"
#include "SimpleEvent.h"

#include <atomic>
#include <condition_variable>
#include <future>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

namespace AudioBule::Core
{

// 多设备连接状态机，全项目唯一的状态源（spec §3.3）。
//
// 线程模型：所有公开成员都可从任意线程调用。状态迁移在 m_mutex 保护下进行，
// 事件在**解锁之后** Raise —— 处理器可以安全地重入 Snapshot() 或发起新操作。
class ConnectionManager
{
public:
    // provider 必须 outlive ConnectionManager
    explicit ConnectionManager(IAudioDeviceProvider& provider);
    ~ConnectionManager();

    ConnectionManager(ConnectionManager const&) = delete;
    ConnectionManager& operator=(ConnectionManager const&) = delete;

    // 单条状态变化。参数是变化后的条目快照。
    SimpleEvent<ConnectionEntry> EntryChanged;

    // 集合增删（刷新后设备数量/身份变了）。UI 应据此重建整个列表。
    SimpleEvent<> EntriesChanged;

    // 重新扫描设备。已存在的条目保留其状态，消失的设备被移除。
    // 系统不支持 A2DP Sink 或枚举抛异常时，得到空列表。
    void Refresh();

    // 异步发起连接。立即返回；结果通过 EntryChanged 通知。
    // 已处于 Connecting/Connected 的设备会被忽略（幂等）。
    // 未知设备会新增一条 Failed 条目，保证 UI 有东西可显示。
    std::future<void> ConnectAsync(std::wstring_view deviceId);

    // 异步断开。对非 Connected 条目是无害的空操作。
    std::future<void> DisconnectAsync(std::wstring_view deviceId);

    // 按顺序对每个 id 发起连接（开机自启用）。单个失败不影响其余。
    void ReconnectSavedDevices(std::vector<std::wstring> const& deviceIds);

    // 阻塞直到当前所有在途的 Connect/Disconnect 完成。仅供测试与关机流程使用。
    void WaitForIdle();

    // 返回条目列表的深拷贝，供 UI 绑定。
    std::vector<ConnectionEntry> Snapshot() const;

    // 当前处于 Connected 的设备 id。退出时用它写入 Settings。
    std::vector<std::wstring> ConnectedDeviceIds() const;

    bool IsSupported() const;

private:
    void ApplyConnectResult(std::wstring const& deviceId, ConnectResult const& result);
    void HandleConnectionLost(std::wstring const& deviceId);
    ConnectionEntry* FindLocked(std::wstring const& deviceId);
    ConnectionEntry const* FindLocked(std::wstring const& deviceId) const;
    void RaiseEntryChanged(ConnectionEntry const& entry);
    static std::future<void> CompletedFuture();

    IAudioDeviceProvider& m_provider;
    // 存成订阅 id 才能在析构时退订 —— 见 ConnectionManager.cpp 的说明
    SimpleEvent<std::wstring>::SubscriptionId m_lostSubscription = 0;

    mutable std::mutex m_mutex;
    std::vector<ConnectionEntry> m_entries;

    // 追踪在途异步操作，供 WaitForIdle 使用
    mutable std::mutex m_pendingMutex;
    std::condition_variable m_pendingDone;
    size_t m_pendingCount = 0;
};

} // namespace AudioBule::Core