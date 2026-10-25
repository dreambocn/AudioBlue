#pragma once

#include "ConnectionEntry.h"
#include "IAudioDeviceProvider.h"
#include "SimpleEvent.h"
#include "CallbackGate.h"

#include <atomic>
#include <condition_variable>
#include <future>
#include <mutex>
#include <map>
#include <set>
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
    explicit ConnectionManager(IAudioDeviceProvider& provider, LogContext log = {});
    ~ConnectionManager();

    ConnectionManager(ConnectionManager const&) = delete;
    ConnectionManager& operator=(ConnectionManager const&) = delete;

    // 单条状态变化。参数是变化后的条目快照。
    SimpleEvent<ConnectionEntry> EntryChanged;

    // 集合增删（刷新后设备数量/身份变了）。UI 应据此重建整个列表。
    SimpleEvent<> EntriesChanged;

    // 重新扫描设备。已存在的条目保留其状态，消失的设备被移除。
    // 失败时保留现有快照并返回 false；成功移除的连接在工作线程清理。
    bool Refresh();

    // 异步发起连接。立即返回；结果通过 EntryChanged 通知。
    // 已处于 Connecting/Connected 的设备会被忽略（幂等）。
    // 未知设备会新增一条 Failed 条目，保证 UI 有东西可显示。
    std::future<void> ConnectAsync(std::wstring_view deviceId, LogTrigger trigger = LogTrigger::Manual);

    // 一次性重建已连接设备；关闭完成后才重新打开，可通过 CancelConnection 取消。
    std::future<void> ReconnectAsync(std::wstring_view deviceId);

    // 异步断开。对非 Connected 条目是无害的空操作。
    std::future<void> DisconnectAsync(std::wstring_view deviceId);

    // 立即撤销连接或重连请求；关闭清理后停止重建，Open 完成后清理迟到结果。
    // 清理完成前同一设备不能再发起连接，其它设备不受影响。
    bool CancelConnection(std::wstring_view deviceId);
    // 取消后清理底层请求期间仍返回 true，供界面控制重试按钮。
    bool IsConnectionPending(std::wstring_view deviceId) const;

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
    std::future<void> StartConnectionAsync(std::wstring_view deviceId, LogTrigger trigger, bool reconnect);
    void ApplyConnectResult(std::wstring const& deviceId, ConnectResult const& result, LogContext const& log, ConnectionState requestedState);
    void RestoreAfterReconnectFailure(ConnectionEntry entry, uint64_t connectionId, LogContext const& previousLog, HRESULT error);
    void HandleConnectionLost(std::wstring const& deviceId, uint64_t connectionId);
    ConnectionEntry* FindLocked(std::wstring const& deviceId);
    ConnectionEntry const* FindLocked(std::wstring const& deviceId) const;
    void RaiseEntryChanged(ConnectionEntry const& entry);
    static std::future<void> CompletedFuture();

    IAudioDeviceProvider& m_provider;
    LogContext m_log;
    std::map<std::wstring, LogContext> m_operations;
    // 存成订阅 id 才能在析构时退订 —— 见 ConnectionManager.cpp 的说明
    SimpleEvent<std::wstring, uint64_t>::SubscriptionId m_lostSubscription = 0;
    std::shared_ptr<CallbackGate> m_callbacks = std::make_shared<CallbackGate>();
    inline static std::atomic<uint64_t> s_nextConnectionId{ 0 };
    std::map<std::wstring, uint64_t> m_connectionIds;

    std::mutex m_refreshMutex;
    mutable std::mutex m_mutex;
    std::vector<ConnectionEntry> m_entries;
    std::set<std::wstring> m_connectingDevices;
    std::set<std::wstring> m_disconnectingDevices;

    // 追踪在途异步操作，供 WaitForIdle 使用
    mutable std::mutex m_pendingMutex;
    std::condition_variable m_pendingDone;
    size_t m_pendingCount = 0;
};

} // namespace AudioBule::Core
