#pragma once
#include "DiagnosticsTypes.h"
#include <string_view>

namespace AudioBule::Core::Detail
{
struct EventDefinition { char const* name; wchar_t const* message; char const* module; };
EventDefinition const& Definition(LogEvent event) noexcept;
char const* LevelName(LogLevel level) noexcept;
char const* TriggerName(LogTrigger trigger) noexcept;
char const* StageName(LogStage stage) noexcept;
char const* OutcomeName(LogOutcome outcome) noexcept;
std::string JsonQuote(std::string_view value);
std::string HexCode(uint32_t value);
std::string UtcTimestamp();
std::string RandomHex(size_t bytes);
std::string RuntimeInfoJson();
bool SafeDirectory(std::wstring const& path) noexcept;
}
