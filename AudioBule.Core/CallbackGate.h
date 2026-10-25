#pragma once

#include <condition_variable>
#include <memory>
#include <mutex>
#include <utility>

namespace AudioBule::Core
{
// 外部事件先领取执行凭据；关闭入口后，等待已进入的回调全部离开。
// 状态由回调共享持有，已经复制但尚未执行的处理器不会访问已析构的宿主。
class CallbackGate
{
    struct State
    {
        std::mutex mutex;
        std::condition_variable idle;
        bool closed = false;
        size_t active = 0;
    };
public:
    class Lease
    {
    public:
        Lease() = default;
        Lease(Lease const&) = delete;
        Lease& operator=(Lease const&) = delete;
        Lease(Lease&&) noexcept = default;
        ~Lease()
        {
            if (!m_state) return;
            std::lock_guard lock(m_state->mutex);
            if (--m_state->active == 0) m_state->idle.notify_all();
        }
        explicit operator bool() const noexcept { return static_cast<bool>(m_state); }
    private:
        friend class CallbackGate;
        explicit Lease(std::shared_ptr<State> state) : m_state(std::move(state)) {}
        std::shared_ptr<State> m_state;
    };

    Lease TryEnter()
    {
        std::lock_guard lock(m_state->mutex);
        if (m_state->closed) return {};
        ++m_state->active;
        return Lease(m_state);
    }

    // 只能由宿主销毁路径调用，不能在本入口保护的回调内部等待自身。
    void CloseAndWait()
    {
        std::unique_lock lock(m_state->mutex);
        m_state->closed = true;
        m_state->idle.wait(lock, [&] { return m_state->active == 0; });
    }
private:
    std::shared_ptr<State> m_state = std::make_shared<State>();
};
}
