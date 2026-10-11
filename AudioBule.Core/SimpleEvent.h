#pragma once

#include <functional>
#include <mutex>
#include <utility>
#include <vector>

namespace AudioBule::Core
{

// 线程安全的轻量事件。用途：ConnectionManager 需要广播条目变更，
// 但 Core 的公开接口不允许出现 WinRT 类型（winrt::event_token 会把
// IInspectable 拖进接口面），因此自建。
//
// Raise 在副本上遍历：回调里可以安全地 Add / Remove 而不会让迭代器失效。
template <typename... Args>
class SimpleEvent
{
public:
    using Handler = std::function<void(Args...)>;
    using SubscriptionId = size_t;

    // 返回订阅 id，Remove 时用它。**不要**改成按 handler 移除 ——
    // std::function 没有 operator==（C++20 也只有极少数类型可比较），
    // 按身份移除根本无法编译。
    SubscriptionId Add(Handler handler)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        SubscriptionId id = m_nextId++;
        m_handlers.emplace_back(id, std::move(handler));
        return id;
    }

    // id 无效或已退订时静默忽略
    void Remove(SubscriptionId id)
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        for (auto it = m_handlers.begin(); it != m_handlers.end(); ++it)
        {
            if (it->first == id)
            {
                m_handlers.erase(it);
                return;
            }
        }
    }

    void Raise(Args... args) const
    {
        std::vector<Handler> copy;
        {
            std::lock_guard<std::mutex> lock(m_mutex);
            copy.reserve(m_handlers.size());
            for (auto const& entry : m_handlers)
            {
                copy.push_back(entry.second);
            }
        }
        // 解锁后再回调：回调里可以自由 Add/Remove，也可以重入调用方
        for (auto const& handler : copy)
        {
            handler(args...);
        }
    }

    bool Empty() const
    {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_handlers.empty();
    }

private:
    mutable std::mutex m_mutex;
    SubscriptionId m_nextId = 1;
    std::vector<std::pair<SubscriptionId, Handler>> m_handlers;
};

} // namespace AudioBule::Core