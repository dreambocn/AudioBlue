#include "pch.h"
#include "ConnectionManager.h"
#include "Messages.h"

#include <thread>

namespace AudioBule::Core
{

ConnectionManager::ConnectionManager(IAudioDeviceProvider& provider)
    : m_provider(provider)
{
    m_lostSubscription = m_provider.ConnectionLost.Add(
        [this](std::wstring const& deviceId) { HandleConnectionLost(deviceId); });
}

ConnectionManager::~ConnectionManager()
{
    WaitForIdle();

    // 退订：provider 通常是成员，析构顺序在本对象之后。
    // 不退订的话 provider 上会残留指向已析构 this 的 handler，
    // 之后 provider 若再 Raise 就会访问已释放内存。
    m_provider.ConnectionLost.Remove(m_lostSubscription);
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

void ConnectionManager::Refresh()
{
    std::vector<DeviceInfo> devices;
    try
    {
        if (IsSupported())
        {
            devices = m_provider.EnumerateDevices();
        }
    }
    catch (...)
    {
        devices.clear();
    }

    std::vector<ConnectionEntry> updated;
    updated.reserve(devices.size());
    bool collectionChanged = false;

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        // 保留已有条目的状态：用户开着窗口点刷新，不能把已连上的设备打回未连接
        for (auto const& device : devices)
        {
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
        m_entries = std::move(updated);
    }

    if (collectionChanged)
    {
        EntriesChanged.Raise();
    }
}

std::future<void> ConnectionManager::ConnectAsync(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

    ConnectionEntry snapshot;
    bool deviceMissing = false;

    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(id);
        if (entry != nullptr && (entry->state == ConnectionState::Connecting ||
                                 entry->state == ConnectionState::Connected))
        {
            // 幂等：重复点「连接」不应产生第二次真实连接尝试
            return CompletedFuture();
        }

        if (entry == nullptr)
        {
            // 设备已不在列表里（走远了）。仍建条目并标失败，让 UI 有东西可显示。
            deviceMissing = true;
            snapshot.deviceId = id;
            snapshot.displayName = id;
            snapshot.state = ConnectionState::Failed;
            snapshot.errorMessage =
                MessageForConnectFailure(ConnectFailure::DeviceNotFound, 0);
            m_entries.push_back(snapshot);
        }
        else
        {
            snapshot = *entry;
            snapshot.state = ConnectionState::Connecting;
            snapshot.errorMessage.clear();
            *entry = snapshot;
        }
    }

    RaiseEntryChanged(snapshot);

    if (deviceMissing)
    {
        return CompletedFuture();
    }

    {
        std::lock_guard<std::mutex> lock(m_pendingMutex);
        ++m_pendingCount;
    }

    auto promise = std::promise<void>();
    auto future = promise.get_future();

    // promise 必须**移动**进 lambda。捕获引用会在本函数返回后 use-after-free。
    std::thread([this, id = std::move(id), promise = std::move(promise)]() mutable {
        ConnectResult result;
        bool apartment = false;
        try
        {
            // std::thread 不自动初始化 COM；真实 WinRT provider 必须在 MTA 上运行。
            winrt::init_apartment(winrt::apartment_type::multi_threaded);
            apartment = true;
            result = m_provider.Connect(id);
        }
        catch (winrt::hresult_error const& e)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, e.code() };
        }
        catch (std::exception const&)
        {
            result = ConnectResult{ false, ConnectFailure::HresultError, E_FAIL };
        }

        try
        {
            ApplyConnectResult(id, result);
            promise.set_value();
        }
        catch (...) { promise.set_exception(std::current_exception()); }
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
    ConnectResult const& result)
{
    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

        auto* entry = FindLocked(deviceId);
        if (entry == nullptr)
        {
            return;   // 连接期间设备被 Refresh 掉了：静默丢弃结果
        }

        snapshot = *entry;
        if (result.succeeded)
        {
            snapshot.state = ConnectionState::Connected;
            snapshot.errorMessage.clear();
        }
        else
        {
            snapshot.state = ConnectionState::Failed;
            snapshot.errorMessage =
                MessageForConnectFailure(result.failure, result.extendedError);
        }
        *entry = snapshot;
    }

    RaiseEntryChanged(snapshot);
}

std::future<void> ConnectionManager::DisconnectAsync(std::wstring_view deviceId)
{
    std::wstring id(deviceId);

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

        snapshot = *entry;
        snapshot.state = ConnectionState::Disconnected;
        snapshot.errorMessage.clear();
        *entry = snapshot;
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

    std::thread([this, id = std::move(id), promise = std::move(promise)]() mutable {
        bool apartment = false;
        try
        {
            winrt::init_apartment(winrt::apartment_type::multi_threaded);
            apartment = true;
            m_provider.Disconnect(id);
        }
        catch (...)
        {
            // 断开失败不改变 UI 状态：用户已看到「已断开」，
            // 系统侧残留会在 ConnectionLost 里自然收敛
        }

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
        ConnectAsync(id);
    }
}

void ConnectionManager::HandleConnectionLost(std::wstring const& deviceId)
{
    ConnectionEntry snapshot;
    {
        std::lock_guard<std::mutex> lock(m_mutex);

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
        *entry = snapshot;
    }

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
