#include "pch.h"
#include "DiagnosticsController.h"

namespace AudioBule::App::UI
{
Core::DiagnosticExportResult DiagnosticsController::Export(std::wstring const& target) noexcept
{
    try
    {
        // 导出解析器使用 WinRT JSON，工作线程必须显式初始化 MTA。
        winrt::init_apartment(winrt::apartment_type::multi_threaded);
        auto apartment = wil::scope_exit([] { winrt::uninit_apartment(); });
        auto snapshot = m_logger.Snapshot();
        auto result = Core::ExportDiagnostics(snapshot, target, m_cancelled);
        m_logger.Context().Write(Core::LogEvent::ExportCompleted,
            { .outcome = result.cancelled ? Core::LogOutcome::Cancelled : result.succeeded ? Core::LogOutcome::Succeeded : Core::LogOutcome::Failed,
              .win32Error = result.error, .count = static_cast<int64_t>(result.records) });
        return result;
    }
    catch (...) { Core::DiagnosticExportResult result; result.error = static_cast<DWORD>(winrt::to_hresult().value); return result; }
}
}
