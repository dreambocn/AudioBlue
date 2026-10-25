#pragma once
#include "DiagnosticExport.h"
#include <atomic>

namespace AudioBule::App::UI
{
enum class DiagnosticsAction { OpenFolder, ToggleDetailed, Export };

// 原生交互由 App 协程负责；本模块仅协调可取消的后台诊断工作。
class DiagnosticsController final
{
public:
    explicit DiagnosticsController(Core::Logger& logger) : m_logger(logger) {}
    void BeginExport() noexcept { m_cancelled = false; }
    void Cancel() noexcept { m_cancelled = true; }
    Core::DiagnosticExportResult Export(std::wstring const& target) noexcept;
private:
    Core::Logger& m_logger;
    std::atomic<bool> m_cancelled{false};
};
}
