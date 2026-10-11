// SimpleEvent 是纯头文件的模板类，测试也放在头文件旁边由 Core 侧自检。
// 这里只验证几个关键契约：Raise 可重入、Remove 按身份移除、并发安全。
#include <gtest/gtest.h>

#include "SimpleEvent.h"

#include <atomic>
#include <mutex>
#include <thread>
#include <vector>

using namespace AudioBule::Core;

TEST(SimpleEvent, RaiseNotifiesAllHandlers)
{
    SimpleEvent<int> event;
    int sum = 0;
    event.Add([&](int v) { sum += v; });
    event.Add([&](int v) { sum += v; });

    event.Raise(5);
    EXPECT_EQ(sum, 10);
}

TEST(SimpleEvent, RemoveStopsNotifications)
{
    SimpleEvent<int> event;
    int calls = 0;

    auto id = event.Add([&](int) { ++calls; });
    event.Raise(1);
    event.Remove(id);
    event.Raise(1);

    EXPECT_EQ(calls, 1);
    EXPECT_TRUE(event.Empty());
}

TEST(SimpleEvent, RemoveUnknownIdIsHarmlessNoOp)
{
    SimpleEvent<int> event;
    int calls = 0;
    auto id = event.Add([&](int) { ++calls; });

    event.Remove(id + 999);   // 不存在的 id
    event.Remove(id);
    event.Remove(id);         // 重复移除

    event.Raise(1);
    EXPECT_EQ(calls, 0);
}

TEST(SimpleEvent, RaiseOnEmptyEventIsHarmless)
{
    SimpleEvent<int> event;
    event.Raise(1);
    EXPECT_TRUE(event.Empty());
}

TEST(SimpleEvent, HandlerCanReenterRaise)
{
    // Raise 在副本上遍历并在解锁后回调，因此处理器可以重入 Raise。
    // 若实现改成在遍历时持锁，这里会死锁。
    SimpleEvent<int> event;
    int calls = 0;
    int depth = 0;

    event.Add([&](int v) {
        ++calls;
        if (depth < 2)
        {
            ++depth;
            event.Raise(v);
            --depth;
        }
    });

    event.Raise(1);
    EXPECT_EQ(calls, 3);   // 外层 1 次 + 两层重入
}

TEST(SimpleEvent, ConcurrentRaiseIsSafe)
{
    SimpleEvent<int> event;
    std::atomic<int> count{ 0 };

    event.Add([&](int) { ++count; });

    std::vector<std::thread> threads;
    for (int i = 0; i < 4; ++i)
    {
        threads.emplace_back([&] {
            for (int j = 0; j < 100; ++j)
            {
                event.Raise(1);
            }
        });
    }
    for (auto& t : threads)
    {
        t.join();
    }

    EXPECT_EQ(count.load(), 400);
}