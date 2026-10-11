#include <gtest/gtest.h>

#include "ConnectionManager.h"
#include "Messages.h"

#include <atomic>
#include <future>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include <winrt/base.h>

using namespace AudioBule::Core;

namespace {

class FakeDeviceProvider final : public IAudioDeviceProvider
{
public:
    std::vector<DeviceInfo> devices;
    bool supported = true;
    bool throwOnEnumerate = false;

    void SetConnectResult(std::wstring const& deviceId, ConnectResult result)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_connectResults[deviceId] = result;
    }

    void SetConnectThrows(std::wstring const& deviceId)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_throwingDevices.insert(deviceId);
    }

    int ConnectCount(std::wstring const& deviceId) const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        auto it = m_connectCounts.find(deviceId);
        return it == m_connectCounts.end() ? 0 : it->second;
    }

    bool IsDisconnected(std::wstring const& deviceId) const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_disconnected.count(deviceId) > 0;
    }

    bool IsSupported() const override { return supported; }

    std::vector<DeviceInfo> EnumerateDevices() override
    {
        if (throwOnEnumerate)
        {
            throw std::runtime_error("enumerate failed");
        }
        return devices;
    }

    ConnectResult Connect(std::wstring_view deviceId) override
    {
        std::wstring id(deviceId);
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            ++m_connectCounts[id];
            if (m_throwingDevices.count(id) > 0)
            {
                throw winrt::hresult_error(E_FAIL, L"simulated");
            }
            auto it = m_connectResults.find(id);
            if (it != m_connectResults.end())
            {
                return it->second;
            }
        }
        return ConnectResult{ true, ConnectFailure::None, 0 };
    }

    void Disconnect(std::wstring_view deviceId) override
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_disconnected.insert(std::wstring(deviceId));
    }

private:
    mutable std::mutex m_mutex;
    std::map<std::wstring, ConnectResult> m_connectResults;
    std::map<std::wstring, int> m_connectCounts;
    std::set<std::wstring> m_throwingDevices;
    std::set<std::wstring> m_disconnected;
};

ConnectResult MakeFailure(ConnectFailure failure, HRESULT extended = 0)
{
    return ConnectResult{ false, failure, extended };
}

// 必须返回**拷贝**而不是指针：Snapshot() 按值返回临时 vector，
// 返回指向它的指针在函数返回后就是悬垂指针（use-after-free）。
// 之前的版本正是这样写的，导致三个用例读到已释放内存里的空字符串。
std::optional<ConnectionEntry> Find(ConnectionManager const& manager,
    std::wstring const& deviceId)
{
    auto snapshot = manager.Snapshot();
    for (auto const& entry : snapshot)
    {
        if (entry.deviceId == deviceId)
        {
            return entry;
        }
    }
    return std::nullopt;
}

ConnectionState StateOf(ConnectionManager const& manager, std::wstring const& deviceId)
{
    auto entry = Find(manager, deviceId);
    return entry ? entry->state : ConnectionState::Disconnected;
}

std::wstring ErrorOf(ConnectionManager const& manager, std::wstring const& deviceId)
{
    auto entry = Find(manager, deviceId);
    return entry ? entry->errorMessage : std::wstring{};
}

std::wstring NameOf(ConnectionManager const& manager, std::wstring const& deviceId)
{
    auto entry = Find(manager, deviceId);
    return entry ? entry->displayName : std::wstring{};
}

} // namespace

TEST(ConnectionManager, RefreshPopulatesEntriesFromProvider)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    ConnectionManager manager(provider);

    manager.Refresh();

    auto snapshot = manager.Snapshot();
    ASSERT_EQ(snapshot.size(), 2u);
    EXPECT_EQ(snapshot[0].deviceId, std::wstring(L"devA"));
    EXPECT_EQ(snapshot[0].displayName, std::wstring(L"手机 A"));
    EXPECT_TRUE(snapshot[0].state == ConnectionState::Disconnected);
}

TEST(ConnectionManager, UnsupportedSystemYieldsEmptyList)
{
    FakeDeviceProvider provider;
    provider.supported = false;
    ConnectionManager manager(provider);

    manager.Refresh();
    EXPECT_TRUE(manager.Snapshot().empty());
}

TEST(ConnectionManager, EnumerateThrowingYieldsEmptyListAndDoesNotCrash)
{
    FakeDeviceProvider provider;
    provider.throwOnEnumerate = true;
    ConnectionManager manager(provider);

    manager.Refresh();   // 不得抛出
    EXPECT_TRUE(manager.Snapshot().empty());
}

TEST(ConnectionManager, ConnectSuccessMovesEntryToConnected)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
    EXPECT_TRUE(ErrorOf(manager, L"devA").empty());
}

TEST(ConnectionManager, ConnectFailureMovesEntryToFailedWithMessage)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectResult(L"devA", MakeFailure(ConnectFailure::RequestTimedOut));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Failed);
    EXPECT_FALSE(ErrorOf(manager, L"devA").empty());
}

TEST(Messages, ErrorGenFailurePointsAtPhoneCannotBeReceiver)
{
    // Review Focus 第 1 条：手机正作为 A2DP 源连着耳机时，OpenAsync 失败且
    // 扩展错误码为 0x8007001F。文案必须让用户看出「手机现在不能当接收端」。
    auto message = MessageForConnectFailure(ConnectFailure::GenericFailure, 0x8007001Fu);
    EXPECT_FALSE(message.empty());
    EXPECT_NE(message.find(L"0x8007001F"), std::wstring::npos);
    EXPECT_NE(message.find(L"接收端"), std::wstring::npos);
}

TEST(Messages, EveryFailureKindProducesNonEmptyMessage)
{
    ConnectFailure const failures[] = {
        ConnectFailure::DeviceNotSupported,
        ConnectFailure::RequestTimedOut,
        ConnectFailure::DeniedBySystem,
        ConnectFailure::GenericFailure,
        ConnectFailure::UnknownFailure,
        ConnectFailure::HresultError,
        ConnectFailure::DeviceNotFound,
    };
    for (auto failure : failures)
    {
        EXPECT_FALSE(MessageForConnectFailure(failure, 0).empty());
        EXPECT_FALSE(MessageForConnectFailure(failure, 0x80004005u).empty());
    }
}

TEST(ConnectionManager, ConnectThrowingLeavesEntryFailedNotCrashed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectThrows(L"devA");
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();   // 不得抛出

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Failed);
    EXPECT_FALSE(ErrorOf(manager, L"devA").empty());
}

TEST(ConnectionManager, ConnectUnknownDeviceAddsFailedEntry)
{
    // 设备列表刷新后用户手机走远了，点连接时 id 仍要得到一个可读的失败态。
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"ghost").get();

    EXPECT_TRUE(StateOf(manager, L"ghost") == ConnectionState::Failed);
}

TEST(ConnectionManager, DisconnectMovesEntryToDisconnectedAndCallsProvider)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();
    EXPECT_FALSE(provider.IsDisconnected(L"devA"));

    manager.DisconnectAsync(L"devA").get();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Disconnected);
    EXPECT_TRUE(provider.IsDisconnected(L"devA"));
}

TEST(ConnectionManager, DisconnectOnDisconnectedEntryIsHarmlessNoOp)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.DisconnectAsync(L"devA").get();   // 不得崩溃

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Disconnected);
}

TEST(ConnectionManager, RetryAfterFailureIsAllowedAndCanSucceed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    provider.SetConnectResult(L"devA", MakeFailure(ConnectFailure::RequestTimedOut));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Failed);

    provider.SetConnectResult(L"devA", ConnectResult{ true, ConnectFailure::None, 0 });
    manager.ConnectAsync(L"devA").get();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
    EXPECT_TRUE(ErrorOf(manager, L"devA").empty());
}

TEST(ConnectionManager, ConnectWhileConnectedDoesNotCallProviderAgain)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devA").get();

    EXPECT_EQ(provider.ConnectCount(L"devA"), 1);
    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
}

TEST(ConnectionManager, ExternalConnectionLostMovesEntryToDisconnected)
{
    // 设备走出范围 / 手机关蓝牙：provider 从底层 StateChanged 观察到关闭
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.ConnectionLost.Raise(L"devA");

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Disconnected);
}

TEST(ConnectionManager, ConnectionLostForUnknownDeviceIsIgnored)
{
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.ConnectionLost.Raise(L"never-seen");   // 不得崩溃

    EXPECT_TRUE(manager.Snapshot().empty());
}

TEST(ConnectionManager, RefreshPreservesConnectedState)
{
    // 用户开着窗口时新插了一个设备点刷新，已连接的不能被重置。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.devices.push_back({ L"devB", L"手机 B" });
    manager.Refresh();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
    EXPECT_TRUE(StateOf(manager, L"devB") == ConnectionState::Disconnected);
    EXPECT_EQ(manager.Snapshot().size(), 2u);
}

TEST(ConnectionManager, RefreshDropsDevicesThatDisappeared)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.devices = { { L"devA", L"手机 A" } };
    manager.Refresh();

    EXPECT_EQ(manager.Snapshot().size(), 1u);
    EXPECT_TRUE(Find(manager, L"devA").has_value());
}

TEST(ConnectionManager, RefreshUpdatesDisplayName)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"旧名字" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.devices = { { L"devA", L"新名字" } };
    manager.Refresh();

    EXPECT_EQ(NameOf(manager, L"devA"), std::wstring(L"新名字"));
}

TEST(ConnectionManager, SnapshotReturnsIndependentCopy)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    auto copy = manager.Snapshot();
    copy[0].state = ConnectionState::Failed;
    copy[0].displayName = L"篡改";

    auto fresh = manager.Snapshot();
    EXPECT_TRUE(fresh[0].state == ConnectionState::Disconnected);
    EXPECT_EQ(fresh[0].displayName, std::wstring(L"手机 A"));
}

TEST(ConnectionManager, MultipleDevicesConnectIndependently)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeniedBySystem));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devB").get();

    // 一台成功一台失败，互不影响 —— spec §3.8
    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
    EXPECT_TRUE(StateOf(manager, L"devB") == ConnectionState::Failed);
}

TEST(ConnectionManager, ConcurrentConnectsOnDifferentDevicesBothSucceed)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" }, { L"devB", L"B" }, { L"devC", L"C" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    std::vector<std::future<void>> futures;
    for (auto const& device : provider.devices)
    {
        futures.push_back(manager.ConnectAsync(device.id));
    }
    for (auto& future : futures)
    {
        future.get();
    }

    for (auto const& device : provider.devices)
    {
        EXPECT_TRUE(StateOf(manager, device.id) == ConnectionState::Connected);
    }
}

TEST(ConnectionManager, EntryChangedFiresOnEachTransition)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    std::atomic<int> entryChangedCount{ 0 };
    std::atomic<int> entriesChangedCount{ 0 };

    manager.EntryChanged.Add([&](ConnectionEntry const&) { ++entryChangedCount; });
    manager.EntriesChanged.Add([&] { ++entriesChangedCount; });

    manager.ConnectAsync(L"devA").get();
    manager.DisconnectAsync(L"devA").get();

    // Connecting → Connected → Disconnected，三次迁移三次通知
    EXPECT_EQ(entryChangedCount.load(), 3);
    EXPECT_EQ(entriesChangedCount.load(), 0);
}

TEST(ConnectionManager, EntriesChangedFiresWhenCollectionGrows)
{
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    std::atomic<int> entriesChangedCount{ 0 };
    manager.EntriesChanged.Add([&] { ++entriesChangedCount; });

    provider.devices = { { L"devA", L"手机 A" } };
    manager.Refresh();

    EXPECT_EQ(entriesChangedCount.load(), 1);
}

TEST(ConnectionManager, ReconnectSavedDevicesConnectsEachAndSkipsFailures)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" }, { L"devB", L"手机 B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeviceNotFound));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ReconnectSavedDevices({ L"devA", L"devB" });
    manager.WaitForIdle();

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
    EXPECT_TRUE(StateOf(manager, L"devB") == ConnectionState::Failed);
}

TEST(ConnectionManager, ConnectedDeviceIdsReflectsCurrentState)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" }, { L"devB", L"B" } };
    provider.SetConnectResult(L"devB", MakeFailure(ConnectFailure::DeniedBySystem));
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.ConnectAsync(L"devA").get();
    manager.ConnectAsync(L"devB").get();

    auto connected = manager.ConnectedDeviceIds();
    ASSERT_EQ(connected.size(), 1u);
    EXPECT_EQ(connected[0], std::wstring(L"devA"));

    manager.DisconnectAsync(L"devA").get();
    EXPECT_TRUE(manager.ConnectedDeviceIds().empty());
}

TEST(ConnectionManager, ConnectedDeviceIdsEmptyAfterExternalLoss)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();

    provider.ConnectionLost.Raise(L"devA");

    EXPECT_TRUE(manager.ConnectedDeviceIds().empty());
}

TEST(ConnectionManager, EventHandlerCanCallSnapshotWithoutDeadlock)
{
    // Raise 在 SimpleEvent 内部先解锁再回调，但 ConnectionManager 若在持有
    // 自身互斥量时 Raise，这里就会死锁。用一个会重入 Snapshot 的处理器钉住。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();

    manager.EntryChanged.Add([&](ConnectionEntry const&) {
        auto snapshot = manager.Snapshot();
        (void)snapshot.size();
    });

    manager.ConnectAsync(L"devA").get();   // 若死锁则测试永久挂起

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Connected);
}

TEST(ConnectionManager, DestructionWaitsForInFlightWork)
{
    // 析构必须等在途连接结束，否则 detached 线程会访问已析构的 this。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    auto manager = std::make_unique<ConnectionManager>(provider);
    manager->Refresh();
    manager->ConnectAsync(L"devA").get();

    provider.ConnectionLost.Raise(L"devA");
    manager.reset();   // 不得崩溃、不得挂起
}