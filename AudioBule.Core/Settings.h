#pragma once

#include <string>
#include <vector>

namespace AudioBule::Core
{

struct AppSettings
{
    bool autoReconnect = true;
    bool runAtStartup = false;
    bool connectionNotifications = true;
    // 只接受 system / light / dark 和 system / zh-CN / en-US。
    std::wstring theme = L"system";
    std::wstring language = L"system";
    std::vector<std::wstring> lastConnectedDevices;
};

// %LOCALAPPDATA%\AudioBule\settings.json
// 不用 exe 同目录：MSIX 打包后安装目录只读，写不进去。
std::wstring DefaultSettingsPath();

// 读配置。**永不抛出、永不返回错误码** —— 文件不存在、JSON 损坏、
// 字段缺失、类型不符，一律回落到默认值。对齐 spec §3.8
// 「配置读写失败 → 记日志并使用默认值，不阻断启动」。
AppSettings LoadSettings(std::wstring const& path);

// 写配置。失败返回 false（调用方记日志即可），不抛异常。
bool SaveSettings(AppSettings const& settings, std::wstring const& path);

} // namespace AudioBule::Core
