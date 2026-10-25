#include "pch.h"
#include "ConnectionManager.h"
#include "Messages.h"

#include <thread>

namespace AudioBule::Core
{

ConnectionManager::ConnectionManager(IAudioDeviceProvider& provider, LogContext log)
    : m_provider(provider), m_log(std::move(log))
{
    m_lostSubscription = m_provider.ConnectionLost.Add(
        [this, gate = m_callbacks](std::wstring const& deviceId, uint64_t connectionId) {
            auto lease = gate->TryEnter();
            if (lease) HandleConnectionLost(deviceId, connectionId);
        });
}

ConnectionManager::~ConnectionManager()
{
    // 退订不能撤销已复制的处理器；先封闭入口并排空外部回调。
    m_callbacks->CloseAndWait();
    m_provider.ConnectionLost.Remove(m_lostSubscription);
    WaitForIdle();
    m_log.Write(LogEvent::CleanupCompleted, { .stage = LogStage::Cleanup, .outcome = LogOutcome::Succeeded });
}

std::future<void> ConnectionManager::CompletedFuture()
{
    std::promise<void> promise;
    promise.set_value();
    return promise.get_future();
}

bool ConnectionManager::IsSupported() const
{
    try
    {
        return m_provider.IsSupported();
    }
    catch (...)
    {
        m_log.Write(LogEvent::SupportProbeFailed, { .hresult = winrt::to_hresult() }, LogLevel::Warning);
        return false;
    }
}

ConnectionEntry* ConnectionManager::FindLocked(std::wstring const& deviceId)
{
    for (auto& entry : m_entries)
    {
        if (entry.deviceId == deviceId)
        {
            return &entry;
        }
    }
    return nullptr;
}

ConnectionEntry const* ConnectionManager::FindLocked(std::wstring const& deviceId) const
{
    for (auto const& entry : m_entries)
    {
        if (entry.deviceId == deviceId)
        {
            return &entry;
        }
    }
    return nullptr;
}

void ConnectionManager::RaiseEntryChanged(ConnectionEntry const& entry)
{
    // 刻意不在调用方持锁时执行本函数。SimpleEvent::Raise 虽会先解锁自身，
    // 但 m_mutex 是非递归的 —— 若在持锁时 Raise，处理器调用 Snapshot() 会死锁。
    EntryChanged.Raise(entry);
}

bool ConnectionManager::Refresh()
{
    std::unique_lock refreshLock(m_refreshMutex);
    auto log = m_log.Operation();
    std::vector<DeviceInfo> devices;
    LogOutcome outcome = LogOutcome::Unsupported;
    HRESULT error = S_OK;
    try
    {
        if (IsSupported())
        {
            devices = m_provider.EnumerateDevices();
            outcome = devices.empty() ? LogOutcome::Empty : LogOutcome::Succeeded;
        }
    }
    catch (...)
    {
        error = winrt::to_hresult();
        outcome = LogOutcome::Failed;
    }

    log.Write(LogEvent::EnumerateCompleted, { .stage = LogStage::Enumerate, .outcome = outcome, .hresult = error, .count = static_cast<int64_t>(devices.size()) }, FAILED(error) ? LogLevel::Warning : LogLevel::Info);
    if (outcome == LogOutcome::Failed || outcome == LogOutcome::Unsupported) return false;
    std::vector<ConnectionEntry> updated;
    std::vector<ConnectionEntry> removedConnections;
    updated.reserve(devices.size());
    bool collectionChanged = false;

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        // 保留已有条目的状态：用户开着窗口点刷新，不能把已连上的设备打回未连接
        for (auto const& device : devices)
        {
            // 忽略损坏或重复的设备项，保证快照中的设备标识唯一。
            if (device.id.empty() || std::any_of(updated.begin(), updated.end(), [&](auto const& entry) { return entry.deviceId == device.id; })) continue;
            if (auto const* existing = FindLocked(device.id))
            {
                ConnectionEntry entry = *existing;
                entry.displayName = device.name.empty() ? device.id : device.name;
                updated.push_back(std::move(entry));
            }
            else
            {
                collectionChanged = true;
                ConnectionEntry entry;
                entry.deviceId = device.id;
                entry.displayName = device.name.empty() ? device.id : device.name;
                updated.push_back(std::move(entry));
            }
        }

        collectionChanged = collectionChanged || updated.size() != m_entries.size();
        for (auto const& entry : m_entries)
        {
            if (std::none_of(updated.begin(), updated.end(), [&](auto const& item) { return item.deviceId == entry.deviceId; }))
            {
                if (entry.state == ConnectionState::Connected)
                {
                    removedConnections.push_back(entry);
                    m_disconnectingDevices.insert(entry.deviceId);
                }
                if (entry.state != ConnectionState::Connected) m_connectionIds.erase(entry.deviceId);
            }
        }
        m_entries = std::move(updated);
    }

    bool succeeded = true;
    for (auto const& entry : removedConnections)
    {
        bool closed = false;
        try { m_provider.Disconnect(entry.deviceId, log); closed = true; }
        catch (...) { succeeded = false; log.Write(LogEvent::CleanupCompleted, { .stage = LogStage::Cleanup, .outcome = LogOutcome::Failed, .hresult = winrt::to_hresult() }, LogLevel::Warning); }
        std::lock_guard lock(m_mutex);
        m_disconnectingDevices.erase(entry.deviceId);
        if (!closed)
        {
            // 清理失败仍保留可操作的连接记录，避免底层会话变成不可见孤儿。
            m_entries.push_back(entry);
        }
        else { m_operations.erase(entry.deviceId); m_connectionIds.erase(entry.deviceId); }
    }
    refreshLock.unlock();
    if (collectionChanged)
    {
        EntriesChanged.Raise();
    }
    return succeeded;
}

std::future<void> ConnectionManager::ConnectAsync(std::wstring_view deviceId, LogTrigger trigger)
{
    return StartConnectionAsync(deviceId, trigger, false);
}

std::future<void> ConnectionManager::ReconnectAsync(std::wstring_view deviceId)
{
    return StartConnectionAsync(deviceId, LogTrigger::Manual, true);
}

std::future<void> ConnectionManager::StartConnectionAsync(std::wstring_view deviceId, LogTrigger trigger, bool reconnect)
{
    std::wstring id(deviceId);

    ConnectionEntry snapshot;
    bool deviceMissing = false;
    bool ignored = false;
    uint64_t connectionId = 0;
    uint64_t previousConnectionId = 0;
    ConnectionEntry previousEntry;
    LogContext previousLog;
    auto requestedState = reconnect ? ConnectionState::Reconnecting : ConnectionState::Connecting;
    auto log = m_log.Operation(trigger, deviceId);

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(id);
        if (m_connectingDevices.contains(id) || m_disconnectingDevices.contains(id) ||
            (reconnect ? entry == nullptr || entry->state != ConnectionState::Connected :
                entry != nullptr && (entry->state == ConnectionState::Connecting || entry->state == ConnectionState::Reconnecting || entry->state == ConnectionState::Connected)))
        {
            ignored = true;
        }

        if (ignored) {}
        else if (entry == nullptr)
        {
            // 设备已不在列表里（走远了）。仍建条目并标失败，让 UI 有东西可显示。
            deviceMissing = true;
            snapshot.deviceId = id;
            snapshot.displayName = id;
            snapshot.state = ConnectionState::Failed;
            snapshot.errorMessage =
                MessageForConnectFailure(ConnectFailure::DeviceNotFound, 0);
            snapshot.failure = ConnectFailure::DeviceNotFound;
            m_entries.push_back(snapshot);
        }
        else
        {
            if (reconnect)
            {
                previousEntry = *entry;
                if (auto it = m_connectionIds.find(id); it != m_connectionIds.end()) previousConnectionId = it->second;
                if (auto it = m_operations.find(id); it != m_operations.end()) previousLog = it->second;
                log = previousLog.Operation(trigger, deviceId);
            }
            snapshot = *entry;
            snapshot.state = requestedState;
            snapshot.errorMessage.clear();
            snapshot.failure = ConnectFailure::None;
            snapshot.extendedError = 0;
            *entry = snapshot;
            m_connectingDevices.insert(id);
            m_operations[id] = log;
            connectionId = ++s_nextConnectionId;
            m_connectionIds[id] = connectionId;
        }
    }

    if (ignored) { log.Write(LogEvent::RequestIgnored, { .outcome = LogOutcome::Ignored }, LogLevel::Debug); return CompletedFuture(); }
    log.Write(reconnect ? LogEvent::ReconnectRequested : LogEvent::ConnectRequested);
    RaiseEntryChanged(snapshot);

    if (deviceMissing)
    {
        log.Write(LogEvent::ConnectCompleted, { .outcome = LogOutcome::Failed, .failure = static_cast<int32_t>(ConnectFailure::DeviceNotFound), .stateAfter = static_cast<int32_t>(ConnectionState::Failed) }, LogLevel::Warning);
        return CompletedFuture();
    }

    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        ++m_pendingCount;
    }

    auto promise = std::promise<void>();
    auto future = promise.get_future();

    // promise 必须**移动**进 lambda。捕获引用会在本函数返回后 use-after-free。
    std::thread([this, id = std::move(id), log, connectionId, reconnect, requestedState,
        previousConnectionId, previousEntry = std::move(previousEntry), previousLog, promise = std::move(promise)]() mutable {
        ConnectResult result;
        bool apartment = false;
        bool closed = !reconnect;
        std::exception_ptr closeError;
        try
        {
            // std::thread 不自动初始化 COM；真实 WinRT provider 必须在 MTA 上运行。
            winrt::init_apartment(winrt::apartment_type::multi_threaded);
            apartment = true;
            if (reconnect)
            {
                m_provider.Disconnect(id, log);
                closed = true;
                log.Write(LogEvent::DisconnectCompleted, { .stage = LogStage::Close, .outcome = LogOutcome::Succeeded });
            }
            bool open = true;
            if (reconnect)
            {
                std::lock_guard lock(m_mutex);
                auto* entry = FindLocked(id);
                // 清理期间的取消或设备移除必须在重新打开前生效。
                open = entry && entry->state == ConnectionState::Reconnecting;
            }
            if (open) result = m_provider.Connect(id, log, connectionId);
        }
        catch (winrt::hresult_error const& e)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, e.code() };
        }
        catch (...)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, E_FAIL };
        }
        if (!closed)
        {
            closeError = std::make_exception_ptr(winrt::hresult_error(result.extendedError));
            log.Write(LogEvent::DisconnectCompleted, { .stage = LogStage::Close, .outcome = LogOutcome::Failed, .hresult = result.extendedError }, LogLevel::Warning);
        }

        try
        {
            if (closeError)
            {
                RestoreAfterReconnectFailure(std::move(previousEntry), previousConnectionId, previousLog, result.extendedError);
                log.Write(LogEvent::ConnectCompleted, { .stage = LogStage::Close, .outcome = LogOutcome::Failed,
                    .hresult = result.extendedError, .failure = static_cast<int32_t>(result.failure),
                    .stateBefore = static_cast<int32_t>(requestedState), .stateAfter = static_cast<int32_t>(ConnectionState::Connected) }, LogLevel::Warning);
            }
            else ApplyConnectResult(id, result, log, requestedState);
            { std::lock_guard lock(m_mutex); m_connectingDevices.erase(id); }
            if (closeError) promise.set_exception(closeError); else promise.set_value();
        }
        catch (...) { { std::lock_guard lock(m_mutex); m_connectingDevices.erase(id); } promise.set_exception(std::current_exception()); }
        if (apartment) winrt::uninit_apartment();

        {
            std::lock_guard<std::mutex> lock(m_pendingMutex);
            --m_pendingCount;
            // 在锁内通知：计数归零后析构可能立即返回，之后不能再访问成员。
            m_pendingDone.notify_all();
        }
    }).detach();

    return future;
}

void ConnectionManager::ApplyConnectResult(std::wstring const& deviceId,
    ConnectResult const& result, LogContext const& log, ConnectionState requestedState)
{
    ConnectionEntry snapshot;
    bool discarded = false;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(deviceId);
        if (entry == nullptr || entry->state != requestedState)
        {
            discarded = true;
        }
        else
        {
            snapshot = *entry;
            if (result.succeeded)
            {
                snapshot.state = ConnectionState::Connected;
                snapshot.errorMessage.clear();
            }
            else
            {
                snapshot.state = ConnectionState::Failed;
                snapshot.errorMessage = MessageForConnectFailure(result.failure, result.extendedError);
            }
            snapshot.failure = result.succeeded ? ConnectFailure::None : result.failure;
            snapshot.extendedError = result.succeeded ? 0 : result.extendedError;
            *entry = snapshot;
        }
    }
    // 不能只忽略迟到状态：成功的底层会话必须在锁外关闭。
    if (discarded)
    {
        log.Write(LogEvent::LateResult, { .outcome = result.succeeded ? LogOutcome::Succeeded : LogOutcome::Failed, .hresult = result.extendedError });
        if (result.succeeded)
        {
            try { m_provider.Disconnect(deviceId, log); log.Write(LogEvent::CleanupCompleted, { .stage = LogStage::Cleanup, .outcome = LogOutcome::Succeeded }); }
            catch (...) { log.Write(LogEvent::CleanupCompleted, { .stage = LogStage::Cleanup, .outcome = LogOutcome::Failed, .hresult = winrt::to_hresult() }, LogLevel::Error); }
        }
    }
    else RaiseEntryChanged(snapshot);
    log.Write(LogEvent::ConnectCompleted, { .outcome = discarded ? LogOutcome::Cancelled : result.succeeded ? LogOutcome::Succeeded : LogOutcome::Failed,
        .hresult = result.extendedError, .failure = static_cast<int32_t>(result.failure), .stateBefore = static_cast<int32_t>(requestedState),
        .stateAfter = discarded ? -1 : static_cast<int32_t>(snapshot.state) }, !discarded && !result.succeeded ? LogLevel::Warning : LogLevel::Info);
    if (discarded || !result.succeeded) { std::lock_guard lock(m_mutex); m_operations.erase(deviceId); m_connectionIds.erase(deviceId); }
}

void ConnectionManager::RestoreAfterReconnectFailure(ConnectionEntry entry, uint64_t connectionId, LogContext const& previousLog, HRESULT error)
{
    entry.failure = ConnectFailure::HresultError;
    entry.extendedError = error;
    entry.errorMessage = MessageForConnectFailure(entry.failure, error);
    {
        std::lock_guard lock(m_mutex);
        // 关闭失败不能丢弃原会话记录，也不能继续尝试打开第二个会话。
        if (auto* current = FindLocked(entry.deviceId)) *current = entry;
        else m_entries.push_back(entry);
        m_connectionIds[entry.deviceId] = connectionId;
        m_operations[entry.deviceId] = previousLog;
    }
    RaiseEntryChanged(entry);
}

bool ConnectionManager::CancelConnection(std::wstring_view deviceId)
{
    ConnectionEntry snapshot;
    LogContext log;
    {
        std::lock_guard lock(m_mutex);
        auto* entry = FindLocked(std::wstring(deviceId));
        if (!entry || (entry->state != ConnectionState::Connecting && entry->state != ConnectionState::Reconnecting)) return false;
        entry->state = ConnectionState::Disconnected;
        entry->errorMessage.clear();
        entry->failure = ConnectFailure::None;
        entry->extendedError = 0;
        snapshot = *entry;
        if (auto it = m_operations.find(std::wstring(deviceId)); it != m_operations.end()) log = it->second;
    }
    log.Write(LogEvent::CancelRequested, { .outcome = LogOutcome::Cancelled });
    RaiseEntryChanged(snapshot);
    return true;
}

bool ConnectionManager::IsConnectionPending(std::wstring_view deviceId) const
{
    std::lock_guard lock(m_mutex);
    return m_connectingDevices.contains(std::wstring(deviceId)) || m_disconnectingDevices.contains(std::wstring(deviceId));
}

std::future<void> ConnectionManager::DisconnectAsync(std::wstring_view deviceId)
{
    std::wstring id(deviceId);
    auto log = m_log.Operation(LogTrigger::Manual, deviceId);

    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(id);
        if (entry == nullptr || entry->state != ConnectionState::Connected)
        {
            // 非 Connected 是无害空操作：按钮在 UI 上本就禁用，
            // 且外部断开事件可能已先行处理过
            return CompletedFuture();
        }

        if (auto it = m_operations.find(id); it != m_operations.end()) { log = it->second.Operation(LogTrigger::Manual, deviceId); m_operations.erase(it); }
        snapshot = *entry;
        snapshot.state = ConnectionState::Disconnected;
        snapshot.errorMessage.clear();
        snapshot.failure = ConnectFailure::None;
        snapshot.extendedError = 0;
        *entry = snapshot;
        m_disconnectingDevices.insert(id);
        m_connectionIds.erase(id);
    }

    // 先更新状态并通知 UI，再让 provider 真正断开 ——
    // provider 可能阻塞，反过来会让界面卡住
    RaiseEntryChanged(snapshot);

    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        ++m_pendingCount;
    }

    auto promise = std::promise<void>();
    auto future = promise.get_future();

    std::thread([this, id = std::move(id), log, promise = std::move(promise)]() mutable {
        bool apartment = false;
        try
        {
            winrt::init_apartment(winrt::apartment_type::multi_threaded);
            apartment = true;
            m_provider.Disconnect(id, log);
            log.Write(LogEvent::DisconnectCompleted, { .stage = LogStage::Close, .outcome = LogOutcome::Succeeded });
        }
        catch (...)
        {
            log.Write(LogEvent::DisconnectCompleted, { .stage = LogStage::Close, .outcome = LogOutcome::Failed, .hresult = winrt::to_hresult() }, LogLevel::Warning);
            // 断开失败不改变 UI 状态：用户已看到「已断开」，
            // 系统侧残留会在 ConnectionLost 里自然收敛
        }

        { std::lock_guard lock(m_mutex); m_disconnectingDevices.erase(id); }
        promise.set_value();
        if (apartment) winrt::uninit_apartment();

        {
            std::lock_guard<std::mutex> lock(m_pendingMutex);
            --m_pendingCount;
            m_pendingDone.notify_all();
        }
    }).detach();

    return future;
}

void ConnectionManager::ReconnectSavedDevices(std::vector<std::wstring> const& deviceIds)
{
    for (auto const& id : deviceIds)
    {
        // 故意不等每个 future：开机时多台设备并行连，逐个串行会很慢
        ConnectAsync(id, LogTrigger::Startup);
    }
}

void ConnectionManager::HandleConnectionLost(std::wstring const& deviceId, uint64_t connectionId)
{
    ConnectionEntry snapshot;
    LogContext log = m_log.WithDevice(deviceId);
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto generation = m_connectionIds.find(deviceId);
        if (generation == m_connectionIds.end() || generation->second != connectionId) return;
        auto* entry = FindLocked(deviceId);
        if (entry == nullptr)
        {
            return;   // 未知设备的断开事件，忽略
        }

        if (entry->state == ConnectionState::Disconnected)
        {
            return;   // 已经断开了，重复通知无意义
        }

        snapshot = *entry;
        snapshot.state = ConnectionState::Disconnected;
        snapshot.errorMessage.clear();
        snapshot.failure = ConnectFailure::None;
        snapshot.extendedError = 0;
        *entry = snapshot;
        m_connectionIds.erase(deviceId);
        if (auto it = m_operations.find(deviceId); it != m_operations.end()) { log = it->second; m_operations.erase(it); }
    }

    log.Write(LogEvent::ConnectionClosed, { .stateAfter = static_cast<int32_t>(ConnectionState::Disconnected) });
    RaiseEntryChanged(snapshot);
}

void ConnectionManager::WaitForIdle()
{
    std::unique_lock<std::mutex> lock(m_pendingMutex);
    m_pendingDone.wait(lock, [this] { return m_pendingCount == 0; });
}

std::vector<ConnectionEntry> ConnectionManager::Snapshot() const
{
    std::lock_guard<std::mutex> lock(m_mutex);
    return m_entries;
}

std::vector<std::wstring> ConnectionManager::ConnectedDeviceIds() const
{
    std::lock_guard<std::mutex> lock(m_mutex);

    std::vector<std::wstring> result;
    for (auto const& entry : m_entries)
    {
        if (entry.state == ConnectionState::Connected)
        {
            result.push_back(entry.deviceId);
        }
    }
    return result;
}

} // namespace AudioBule::Core
