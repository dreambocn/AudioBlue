#pragma once
#include "Logger.h"
#include <atomic>

namespace AudioBule::Core
{
struct DiagnosticExportResult
{
    bool succeeded = false, incomplete = true, cancelled = false;
    uint64_t records = 0, skipped = 0;
    DWORD error = 0;
};
// 仅在已初始化 MTA 的工作线程调用；目标必须为用户选定的绝对路径。
DiagnosticExportResult ExportDiagnostics(LogSnapshot const& snapshot, std::wstring const& target,
    std::atomic<bool> const& cancelled, size_t maxBytes = 20 * 1024 * 1024) noexcept;
}
