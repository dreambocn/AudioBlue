#include <gtest/gtest.h>

#include "ConnectionManager.h"
#include "Messages.h"
#include "WinRtDeviceProvider.h"

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
#include <objbase.h>

using namespace AudioBule::Core;

namespace {

class FakeDeviceProvider final : public IAudioDeviceProvider
{
public:
    std::vector<DeviceInfo> devices;
    bool supported = true;
    bool throwOnEnumerate = false;
    bool throwOnDisconnect = false;
    std::atomic<HRESULT> connectApartmentResult{ E_FAIL };
    std::atomic<HRESULT> disconnectApartmentResult{ E_FAIL };

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

    ConnectResult Connect(std::wstring_view deviceId, LogContext const& = {}, uint64_t connectionId = 0) override
    {
        APTTYPE type{};
        APTTYPEQUALIFIER qualifier{};
        connectApartmentResult = ::CoGetApartmentType(&type, &qualifier);
        std::wstring id(deviceId);
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            ++m_connectCounts[id];
            m_connectionIds[id] = connectionId;
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

    void Disconnect(std::wstring_view deviceId, LogContext const& = {}) override
    {
        APTTYPE type{};
        APTTYPEQUALIFIER qualifier{};
        disconnectApartmentResult = ::CoGetApartmentType(&type, &qualifier);
        if (throwOnDisconnect) throw winrt::hresult_error(E_FAIL);
        std::lock_guard<std::mutex> lock(m_mutex);
        m_disconnected.insert(std::wstring(deviceId));
    }

    uint64_t Generation(std::wstring const& id) const
    {
        std::lock_guard lock(m_mutex);
        auto it = m_connectionIds.find(id);
        return it == m_connectionIds.end() ? 0 : it->second;
    }

    void Lose(std::wstring const& id) { ConnectionLost.Raise(id, Generation(id)); }

private:
    mutable std::mutex m_mutex;
    std::map<std::wstring, ConnectResult> m_connectResults;
    std::map<std::wstring, int> m_connectCounts;
    std::map<std::wstring, uint64_t> m_connectionIds;
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

TEST(ConnectionManager, InitialEnumerateFailureIsReportedAndDoesNotCrash)
{
    FakeDeviceProvider provider;
    provider.throwOnEnumerate = true;
    ConnectionManager manager(provider);

    EXPECT_FALSE(manager.Refresh());   // 失败可被调用方识别，不抛出。
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

    provider.Lose(L"devA");

    EXPECT_TRUE(StateOf(manager, L"devA") == ConnectionState::Disconnected);
}

TEST(ConnectionManager, ConnectionLostForUnknownDeviceIsIgnored)
{
    FakeDeviceProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();

    provider.Lose(L"never-seen");   // 不得崩溃

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

    provider.Lose(L"devA");

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

    provider.Lose(L"devA");
    manager.reset();   // 不得崩溃、不得挂起
}

TEST(ConnectionManager, WorkerThreadsInitializeComForRealProvider)
{
    // 假 provider 直接检查工作线程 COM 状态，防止只在真实设备上出现初始化失败。
    FakeDeviceProvider provider;
    provider.devices = { { L"devA", L"手机 A" } };
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"devA").get();
    manager.DisconnectAsync(L"devA").get();
    EXPECT_EQ(provider.connectApartmentResult.load(), S_OK);
    EXPECT_EQ(provider.disconnectApartmentResult.load(), S_OK);
}

// ---- 真实 provider 的冒烟测试 ----
// 只验证「在真实系统上不会崩、能枚举」，不断言具体设备 ——
// 测试机上不一定有可连接的蓝牙设备。真正需要设备的行为
// 由 Task 11 的手动验证清单覆盖。

TEST(WinRtDeviceProvider, IsSupportedOnDeveloperMachine)
{
    WinRtDeviceProvider provider;
    EXPECT_TRUE(provider.IsSupported());   // 开发机是 Windows 11，必支持
}

TEST(WinRtDeviceProvider, EnumerateDoesNotCrash)
{
    WinRtDeviceProvider provider;
    auto devices = provider.EnumerateDevices();
    // 不检查数量 —— 有没有配对设备取决于测试机状态
    for (auto const& device : devices)
    {
        EXPECT_FALSE(device.id.empty());
    }
}

TEST(WinRtDeviceProvider, ConnectUnknownDeviceFailsGracefully)
{
    WinRtDeviceProvider provider;
    auto result = provider.Connect(L"BTHENUM\\{00000000-0000-0000-0000-000000000000}\\0000");
    EXPECT_FALSE(result.succeeded);
    EXPECT_TRUE(result.failure != ConnectFailure::None);
}

TEST(WinRtDeviceProvider, DisconnectUnknownDeviceIsNoOp)
{
    WinRtDeviceProvider provider;
    provider.Disconnect(L"not-connected");   // 不得崩溃
}

namespace
{
// 由测试显式放行连接结果，稳定复现取消与迟到成功的竞争。
class DelayedProvider final : public IAudioDeviceProvider
{
public:
    DelayedProvider() : released(release.get_future().share()), entered(started.get_future()) {}
    std::promise<void> release, started;
    std::shared_future<void> released;
    std::future<void> entered;
    std::atomic<int> attempts{ 0 }, closed{ 0 };
    ConnectResult result{ true, ConnectFailure::None, 0 };
    bool includeA = true;
    bool IsSupported() const override { return true; }
    std::vector<DeviceInfo> EnumerateDevices() override
    {
        return includeA ? std::vector<DeviceInfo>{ {L"A", L"手机 A"}, {L"B", L"手机 B"} } : std::vector<DeviceInfo>{ {L"B", L"手机 B"} };
    }
    ConnectResult Connect(std::wstring_view id, LogContext const& = {}, uint64_t = 0) override
    {
        if (id == L"A") { ++attempts; started.set_value(); released.wait(); return result; }
        return { true, ConnectFailure::None, 0 };
    }
    void Disconnect(std::wstring_view id, LogContext const& = {}) override { if (id == L"A") ++closed; }
};
}
TEST(ConnectionManager, CancelClosesLateSuccessAndKeepsOtherDevicesConnected)
{
    DelayedProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"B").get();
    auto connection = manager.ConnectAsync(L"A");
    provider.entered.wait();
    EXPECT_TRUE(manager.CancelConnection(L"A"));
    EXPECT_FALSE(manager.CancelConnection(L"A"));
    EXPECT_TRUE(manager.IsConnectionPending(L"A"));
    // 清理完成前不可再为相同设备发起第二个底层会话。
    manager.ConnectAsync(L"A").get();
    EXPECT_EQ(provider.attempts.load(), 1);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
    provider.release.set_value();
    connection.get();
    EXPECT_EQ(provider.closed.load(), 1);
    EXPECT_FALSE(manager.IsConnectionPending(L"A"));
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
    EXPECT_EQ(StateOf(manager, L"B"), ConnectionState::Connected);
}
TEST(ConnectionManager, CanceledFailureCannotReplaceDisconnectedState)
{
    DelayedProvider provider;
    provider.result = { false, ConnectFailure::RequestTimedOut, E_FAIL };
    ConnectionManager manager(provider);
    manager.Refresh();
    auto connection = manager.ConnectAsync(L"A");
    provider.entered.wait();
    EXPECT_TRUE(manager.CancelConnection(L"A"));
    provider.release.set_value();
    connection.get();
    auto entry = Find(manager, L"A");
    ASSERT_TRUE(entry.has_value());
    EXPECT_EQ(entry->state, ConnectionState::Disconnected);
    EXPECT_TRUE(entry->errorMessage.empty());
    EXPECT_EQ(entry->failure, ConnectFailure::None);
    EXPECT_EQ(entry->extendedError, 0);
    EXPECT_EQ(provider.closed.load(), 0);
}
TEST(ConnectionManager, RemovedDeviceClosesLateConnection)
{
    DelayedProvider provider;
    ConnectionManager manager(provider);
    manager.Refresh();
    auto connection = manager.ConnectAsync(L"A");
    provider.entered.wait();
    provider.includeA = false;
    manager.Refresh();
    provider.release.set_value();
    connection.get();
    EXPECT_FALSE(Find(manager, L"A").has_value());
    EXPECT_EQ(provider.closed.load(), 1);
}
TEST(ConnectionManager, ErrorCodesSurviveForLocalizationAndClearAfterRetry)
{
    FakeDeviceProvider provider;
    provider.devices = { { L"A", L"手机 A" } };
    provider.SetConnectResult(L"A", { false, ConnectFailure::GenericFailure, static_cast<HRESULT>(0x8007001F) });
    ConnectionManager manager(provider);
    manager.Refresh();
    manager.ConnectAsync(L"A").get();
    auto failed = Find(manager, L"A");
    ASSERT_TRUE(failed.has_value());
    EXPECT_EQ(failed->failure, ConnectFailure::GenericFailure);
    EXPECT_EQ(failed->extendedError, static_cast<HRESULT>(0x8007001F));
    provider.SetConnectResult(L"A", { true, ConnectFailure::None, 0 });
    manager.ConnectAsync(L"A").get();
    auto connected = Find(manager, L"A");
    ASSERT_TRUE(connected.has_value());
    EXPECT_EQ(connected->failure, ConnectFailure::None);
    EXPECT_EQ(connected->extendedError, 0);
    EXPECT_TRUE(connected->errorMessage.empty());
}

TEST(ConnectionManager, RefreshFailureKeepsConnectedSnapshot)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    ASSERT_TRUE(manager.Refresh());
    manager.ConnectAsync(L"A").get();
    provider.throwOnEnumerate = true;
    EXPECT_FALSE(manager.Refresh());
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
    EXPECT_EQ(manager.ConnectedDeviceIds(), std::vector<std::wstring>{L"A"});
    EXPECT_FALSE(provider.IsDisconnected(L"A"));
}

TEST(ConnectionManager, RemovingConnectedDeviceClosesProviderSession)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    manager.Refresh(); manager.ConnectAsync(L"A").get();
    provider.devices.clear();
    EXPECT_TRUE(manager.Refresh());
    EXPECT_TRUE(manager.Snapshot().empty());
    EXPECT_TRUE(provider.IsDisconnected(L"A"));
}

TEST(ConnectionManager, DelayedOldCloseCannotOverwriteReconnectedDevice)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto oldGeneration = provider.Generation(L"A");
    manager.DisconnectAsync(L"A").get();
    manager.ConnectAsync(L"A").get();
    ASSERT_NE(provider.Generation(L"A"), oldGeneration);
    provider.ConnectionLost.Raise(L"A", oldGeneration);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
    provider.Lose(L"A");
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
}

TEST(ConnectionManager, CopiedLostCallbackIsSafeAfterManagerDestruction)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    std::promise<void> copied, release;
    auto resume = release.get_future().share();
    // 先注册阻塞处理器，让 Raise 已复制的 Manager 回调延后到析构之后执行。
    auto blocker = provider.ConnectionLost.Add([&](auto const&, auto) { copied.set_value(); resume.wait(); });
    auto manager = std::make_unique<ConnectionManager>(provider);
    manager->Refresh(); manager->ConnectAsync(L"A").get();
    std::atomic<int> notifications{0};
    manager->EntryChanged.Add([&](auto const&) { ++notifications; });
    std::thread lost([&] { provider.Lose(L"A"); });
    copied.get_future().wait();
    manager.reset();
    release.set_value(); lost.join();
    provider.ConnectionLost.Remove(blocker);
    EXPECT_EQ(notifications.load(), 0);
}

TEST(ConnectionManager, DestructionWaitsForActiveExternalCallback)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    auto manager = std::make_unique<ConnectionManager>(provider);
    manager->Refresh(); manager->ConnectAsync(L"A").get();
    std::promise<void> entered, release, destroying;
    auto resume = release.get_future().share();
    manager->EntryChanged.Add([&](auto const&) { entered.set_value(); resume.wait(); });
    std::thread lost([&] { provider.Lose(L"A"); });
    entered.get_future().wait();
    auto destroy = std::async(std::launch::async, [&] { destroying.set_value(); manager.reset(); });
    destroying.get_future().wait();
    EXPECT_EQ(destroy.wait_for(std::chrono::milliseconds(50)), std::future_status::timeout);
    release.set_value(); lost.join(); destroy.get();
}

namespace
{
class FakePlaybackSession final : public IAudioPlaybackSession
{
public:
    ConnectResult result{true, ConnectFailure::None, 0};
    std::function<void()> onOpen;
    std::function<void(bool)> onIsOpen;
    std::atomic<bool> opened{false};
    std::atomic<int> closes{0};
    std::atomic<bool> subscribedBeforeOpen{false};
    void SetClosedHandler(std::function<void()> handler) override { std::lock_guard lock(mutex); closed = std::move(handler); }
    void ClearClosedHandler() noexcept override { std::lock_guard lock(mutex); closed = {}; }
    ConnectResult Open() override
    {
        subscribedBeforeOpen = static_cast<bool>(CaptureClosed());
        opened = result.succeeded;
        if (onOpen) onOpen();
        return result;
    }
    bool IsOpen() const override
    {
        bool value = opened;
        if (onIsOpen) onIsOpen(value);
        return value;
    }
    void Close() noexcept override { opened = false; ++closes; }
    std::function<void()> CaptureClosed() { std::lock_guard lock(mutex); return closed; }
    void Lose() { opened = false; if (auto handler = CaptureClosed()) handler(); }
private:
    std::mutex mutex;
    std::function<void()> closed;
};
}

TEST(WinRtDeviceProvider, ListensBeforeOpeningAndRejectsClosedSuccess)
{
    auto session = std::make_shared<FakePlaybackSession>();
    session->onOpen = [session] { session->Lose(); };
    WinRtDeviceProvider provider({}, [session](auto) { return session; });
    auto result = provider.Connect(L"A", {}, 1);
    EXPECT_TRUE(session->subscribedBeforeOpen);
    EXPECT_FALSE(result.succeeded);
    EXPECT_EQ(session->closes.load(), 1);
    EXPECT_FALSE(static_cast<bool>(session->CaptureClosed()));
    session->onOpen = {};
}

TEST(WinRtDeviceProvider, RejectsClosedStateEvenWithoutAnEvent)
{
    auto session = std::make_shared<FakePlaybackSession>();
    session->onOpen = [session] { session->opened = false; };
    WinRtDeviceProvider provider({}, [session](auto) { return session; }, std::chrono::milliseconds(20));
    EXPECT_FALSE(provider.Connect(L"A", {}, 1).succeeded);
    EXPECT_EQ(session->closes.load(), 1);
    session->onOpen = {};
}

TEST(WinRtDeviceProvider, SuccessfulOpenWaitsForDelayedOpenedState)
{
    auto session = std::make_shared<FakePlaybackSession>();
    session->onOpen = [session] { session->opened = false; };
    std::promise<void> firstClosedRead;
    std::atomic<bool> reported{false};
    session->onIsOpen = [&](bool open) { if (!open && !reported.exchange(true)) firstClosedRead.set_value(); };
    WinRtDeviceProvider provider({}, [session](auto) { return session; });
    auto connection = std::async(std::launch::async, [&] { return provider.Connect(L"A", {}, 1); });
    firstClosedRead.get_future().wait();
    // 原生 API 已成功，但 State 仍未更新，此时不能立即失败并关闭连接。
    EXPECT_EQ(connection.wait_for(std::chrono::milliseconds(20)), std::future_status::timeout);
    session->opened = true;
    EXPECT_TRUE(connection.get().succeeded);
    EXPECT_EQ(session->closes.load(), 0);
    provider.Disconnect(L"A");
    session->onOpen = {};
    session->onIsOpen = {};
}

TEST(WinRtDeviceProvider, RealCloseDuringStateSynchronizationStillFails)
{
    auto session = std::make_shared<FakePlaybackSession>();
    session->onOpen = [session] { session->opened = false; };
    std::promise<void> firstClosedRead;
    std::atomic<bool> reported{false};
    session->onIsOpen = [&](bool open) { if (!open && !reported.exchange(true)) firstClosedRead.set_value(); };
    WinRtDeviceProvider provider({}, [session](auto) { return session; });
    auto connection = std::async(std::launch::async, [&] { return provider.Connect(L"A", {}, 1); });
    firstClosedRead.get_future().wait();
    session->Lose();
    EXPECT_FALSE(connection.get().succeeded);
    EXPECT_EQ(session->closes.load(), 1);
    session->onOpen = {};
    session->onIsOpen = {};
}

TEST(WinRtDeviceProvider, OldCopiedCallbackCannotRemoveReplacementSession)
{
    auto oldSession = std::make_shared<FakePlaybackSession>();
    auto newSession = std::make_shared<FakePlaybackSession>();
    int created = 0;
    WinRtDeviceProvider provider({}, [&](auto) { return created++ == 0 ? oldSession : newSession; });
    ASSERT_TRUE(provider.Connect(L"A", {}, 1).succeeded);
    auto oldCallback = oldSession->CaptureClosed();
    provider.Disconnect(L"A");
    ASSERT_TRUE(provider.Connect(L"A", {}, 2).succeeded);
    int lost = 0;
    provider.ConnectionLost.Add([&](auto const&, auto) { ++lost; });
    oldCallback();
    EXPECT_EQ(lost, 0);
    EXPECT_TRUE(newSession->opened);
    provider.Disconnect(L"A");
    EXPECT_EQ(newSession->closes.load(), 1);
}

TEST(WinRtDeviceProvider, CopiedCallbackIsSafeAfterProviderDestruction)
{
    auto session = std::make_shared<FakePlaybackSession>();
    std::function<void()> copied;
    {
        WinRtDeviceProvider provider({}, [session](auto) { return session; });
        ASSERT_TRUE(provider.Connect(L"A", {}, 1).succeeded);
        copied = session->CaptureClosed();
    }
    EXPECT_EQ(session->closes.load(), 1);
    EXPECT_FALSE(static_cast<bool>(session->CaptureClosed()));
    copied();   // 宿主已释放，旧委托只能看到已关闭的生命周期入口。
}

TEST(WinRtDeviceProvider, DestructionWaitsForActiveStateCallback)
{
    auto session = std::make_shared<FakePlaybackSession>();
    auto provider = std::make_unique<WinRtDeviceProvider>(LogContext{}, [session](auto) { return session; });
    ASSERT_TRUE(provider->Connect(L"A", {}, 1).succeeded);
    std::promise<void> entered, release, destroying;
    auto resume = release.get_future().share();
    provider->ConnectionLost.Add([&](auto const&, auto) { entered.set_value(); resume.wait(); });
    std::thread lost([&] { session->Lose(); });
    entered.get_future().wait();
    auto destroy = std::async(std::launch::async, [&] { destroying.set_value(); provider.reset(); });
    destroying.get_future().wait();
    EXPECT_EQ(destroy.wait_for(std::chrono::milliseconds(50)), std::future_status::timeout);
    release.set_value(); lost.join(); destroy.get();
}

TEST(ConnectionManager, RefreshCleanupFailureKeepsAnOperableConnection)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    manager.Refresh(); manager.ConnectAsync(L"A").get();
    provider.devices.clear(); provider.throwOnDisconnect = true;
    EXPECT_FALSE(manager.Refresh());
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
    EXPECT_FALSE(manager.IsConnectionPending(L"A"));
    provider.throwOnDisconnect = false;
    manager.DisconnectAsync(L"A").get();
    EXPECT_TRUE(provider.IsDisconnected(L"A"));
}

TEST(ConnectionManager, CollectionHandlerCanRefreshAgainWithoutDeadlock)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    bool reentered = false;
    manager.EntriesChanged.Add([&] { reentered = manager.Refresh(); });
    EXPECT_TRUE(manager.Refresh());
    EXPECT_TRUE(reentered);
}

TEST(ConnectionManager, ManualReconnectClosesThenOpensExactlyOnce)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider);
    manager.Refresh(); manager.ConnectAsync(L"A").get();
    // 没有播放信号这一输入；空闲刷新不能自行重建或误报失败。
    manager.Refresh(); manager.Refresh();
    EXPECT_EQ(provider.ConnectCount(L"A"), 1);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
    auto generation = provider.Generation(L"A");
    manager.ReconnectAsync(L"A").get();
    EXPECT_TRUE(provider.IsDisconnected(L"A"));
    EXPECT_EQ(provider.ConnectCount(L"A"), 2);
    EXPECT_NE(provider.Generation(L"A"), generation);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
}

TEST(ConnectionManager, ReconnectRequiresAnExistingConnectedDevice)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider); manager.Refresh();
    manager.ReconnectAsync(L"A").get();
    manager.ReconnectAsync(L"unknown").get();
    EXPECT_EQ(provider.ConnectCount(L"A"), 0);
    EXPECT_EQ(manager.Snapshot().size(), 1u);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
}

TEST(ConnectionManager, ReconnectOpenFailureIsReportedWithoutAutomaticRetry)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    provider.SetConnectResult(L"A", {false, ConnectFailure::RequestTimedOut, E_FAIL});
    manager.ReconnectAsync(L"A").get();
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Failed);
    EXPECT_EQ(provider.ConnectCount(L"A"), 2);
    auto entry = Find(manager, L"A"); ASSERT_TRUE(entry.has_value());
    EXPECT_EQ(entry->failure, ConnectFailure::RequestTimedOut);
    EXPECT_EQ(entry->extendedError, E_FAIL);
}

TEST(ConnectionManager, ReconnectCloseFailurePreservesOriginalConnectionAndGeneration)
{
    FakeDeviceProvider provider;
    provider.devices = {{L"A", L"手机 A"}};
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto generation = provider.Generation(L"A");
    provider.throwOnDisconnect = true;
    EXPECT_THROW(manager.ReconnectAsync(L"A").get(), winrt::hresult_error);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
    EXPECT_EQ(provider.ConnectCount(L"A"), 1);
    auto entry = Find(manager, L"A"); ASSERT_TRUE(entry.has_value());
    EXPECT_EQ(entry->extendedError, E_FAIL);
    EXPECT_FALSE(manager.IsConnectionPending(L"A"));
    // 原会话仍属于原代次，后续系统关闭通知仍须生效。
    provider.ConnectionLost.Raise(L"A", generation);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
}

namespace
{
class ReconnectGateProvider final : public IAudioDeviceProvider
{
public:
    bool blockClose = false, blockOpen = false, includeA = true;
    std::atomic<int> opens{0}, closes{0};
    std::promise<void> closeEntered, closeRelease, openEntered, openRelease;
    std::shared_future<void> closeReady = closeRelease.get_future().share();
    std::shared_future<void> openReady = openRelease.get_future().share();
    bool IsSupported() const override { return true; }
    std::vector<DeviceInfo> EnumerateDevices() override
    {
        return includeA ? std::vector<DeviceInfo>{{L"A", L"手机 A"},{L"B", L"手机 B"}} : std::vector<DeviceInfo>{{L"B", L"手机 B"}};
    }
    ConnectResult Connect(std::wstring_view id, LogContext const& = {}, uint64_t = 0) override
    {
        if (id == L"A" && ++opens > 1 && blockOpen) { openEntered.set_value(); openReady.wait(); }
        return {true, ConnectFailure::None, 0};
    }
    void Disconnect(std::wstring_view id, LogContext const& = {}) override
    {
        if (id == L"A" && closes.fetch_add(1) == 0 && blockClose) { closeEntered.set_value(); closeReady.wait(); }
    }
};
}

TEST(ConnectionManager, ReconnectReservesDeviceAcrossCloseAndKeepsOtherDevicesIndependent)
{
    ReconnectGateProvider provider; provider.blockClose = true;
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto operation = manager.ReconnectAsync(L"A"); provider.closeEntered.get_future().wait();
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Reconnecting);
    EXPECT_TRUE(manager.IsConnectionPending(L"A"));
    manager.ReconnectAsync(L"A").get(); manager.ConnectAsync(L"A").get();
    manager.ConnectAsync(L"B").get();
    EXPECT_EQ(provider.opens.load(), 1);
    EXPECT_EQ(StateOf(manager, L"B"), ConnectionState::Connected);
    provider.closeRelease.set_value(); operation.get();
    EXPECT_EQ(provider.opens.load(), 2);
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Connected);
}

TEST(ConnectionManager, CancelDuringReconnectClosePreventsReopening)
{
    ReconnectGateProvider provider; provider.blockClose = true;
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto operation = manager.ReconnectAsync(L"A"); provider.closeEntered.get_future().wait();
    EXPECT_TRUE(manager.CancelConnection(L"A"));
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
    manager.ConnectAsync(L"A").get();
    EXPECT_EQ(provider.opens.load(), 1);
    provider.closeRelease.set_value(); operation.get();
    EXPECT_EQ(provider.opens.load(), 1);
    EXPECT_FALSE(manager.IsConnectionPending(L"A"));
}

TEST(ConnectionManager, CancelDuringReconnectOpenClosesLateSuccess)
{
    ReconnectGateProvider provider; provider.blockOpen = true;
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto operation = manager.ReconnectAsync(L"A"); provider.openEntered.get_future().wait();
    EXPECT_TRUE(manager.CancelConnection(L"A"));
    provider.openRelease.set_value(); operation.get();
    EXPECT_EQ(StateOf(manager, L"A"), ConnectionState::Disconnected);
    EXPECT_EQ(provider.closes.load(), 2);
    EXPECT_FALSE(manager.IsConnectionPending(L"A"));
}

TEST(ConnectionManager, DeviceRemovalDuringReconnectCloseStopsReopening)
{
    ReconnectGateProvider provider; provider.blockClose = true;
    ConnectionManager manager(provider); manager.Refresh(); manager.ConnectAsync(L"A").get();
    auto operation = manager.ReconnectAsync(L"A"); provider.closeEntered.get_future().wait();
    provider.includeA = false; manager.Refresh();
    provider.closeRelease.set_value(); operation.get();
    EXPECT_FALSE(Find(manager, L"A").has_value());
    EXPECT_EQ(provider.opens.load(), 1);
}
