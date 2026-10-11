#include "pch.h"
#include "Settings.h"
#include "StringUtil.h"

#include <winrt/Windows.Data.Json.h>
#include <winrt/Windows.Foundation.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <system_error>
#include <vector>

namespace AudioBule::Core
{

using namespace winrt::Windows::Data::Json;
using namespace winrt::Windows::Foundation;

namespace {

constexpr wchar_t kAutoReconnectKey[] = L"autoReconnect";
constexpr wchar_t kRunAtStartupKey[] = L"runAtStartup";
constexpr wchar_t kLastDevicesKey[] = L"lastConnectedDevices";

// 去重、去掉空 id、限制条数，防止配置文件被改坏导致条目无限增长。
void NormalizeDeviceList(std::vector<std::wstring>& devices)
{
    constexpr size_t kMaxDevices = 32;

    devices.erase(std::unique(devices.begin(), devices.end()), devices.end());
    devices.erase(std::remove_if(devices.begin(), devices.end(),
                      [](std::wstring const& id) { return id.empty(); }),
        devices.end());

    if (devices.size() > kMaxDevices)
    {
        devices.resize(kMaxDevices);
    }
}

// ⚠️ IJsonObject 的所有 GetNamed* 在**字段不存在或类型不符时都会抛异常**
// （0x83750009 等），不像 Lookup 返回 null。所以每个读取都必须自带 try/catch，
// 这正是「LoadSettings 永不抛出」契约的实现处。
//
// 另外：IJsonValue 不继承 IPropertyValue；JsonObject 也没有工厂，
// C++/WinRT 不为它生成投影类，只有接口。优先用 IJsonObject 提供的
// GetNamedBoolean / GetNamedArray 快捷方法，别自己 QueryInterface。
bool TryGetBool(IJsonObject const& json, wchar_t const* key, bool defaultValue)
{
    try
    {
        return json.GetNamedBoolean(key);
    }
    catch (winrt::hresult_error const&)
    {
        return defaultValue;
    }
}

// 取字符串数组。字段不存在 / 不是数组 / 元素非字符串时返回空或部分结果，不抛异常。
std::vector<std::wstring> TryGetStringArray(IJsonObject const& json, wchar_t const* key)
{
    std::vector<std::wstring> result;

    JsonArray array = nullptr;
    try
    {
        array = json.GetNamedArray(key);
    }
    catch (winrt::hresult_error const&)
    {
        return result;   // 字段不存在或不是数组
    }

    if (!array)
    {
        return result;
    }

    // JsonArray 是 IVector<IJsonValue>，可以范围 for
    for (auto const& element : array)
    {
        if (!element || element.ValueType() != JsonValueType::String)
        {
            continue;   // 跳过非字符串项，而不是让整个数组作废
        }
        // GetString() 返回 hstring，它不会隐式转成 std::wstring，必须显式构造。
        result.push_back(std::wstring(element.GetString()));
    }
    return result;
}

} // namespace

std::wstring DefaultSettingsPath()
{
    wchar_t localAppData[MAX_PATH] = {};
    DWORD length = ::GetEnvironmentVariableW(L"LOCALAPPDATA", localAppData, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
    {
        return L"AudioBule\\settings.json";
    }

    std::wstring base(localAppData, length);
    return base + L"\\AudioBule\\settings.json";
}

AppSettings LoadSettings(std::wstring const& path)
{
    AppSettings settings; // 默认值

    if (path.empty())
    {
        return settings;
    }

    try
    {
        // 同步配置接口使用文件流，避免在 WinUI STA 上调用 WinRT 异步操作的 get()。
        std::filesystem::path target(path);
        std::error_code ec;
        auto length = std::filesystem::file_size(target, ec);
        if (ec || length == 0 || length > 1024 * 1024) return settings;
        std::ifstream file(target, std::ios::binary);
        std::string content(static_cast<size_t>(length), '\0');
        if (!file.read(content.data(), static_cast<std::streamsize>(content.size()))) return settings;
        // 兼容用户用编辑器保存的 UTF-8 BOM。
        if (content.starts_with("\xEF\xBB\xBF")) content.erase(0, 3);
        if (content.empty())
        {
            return settings; // 空文件 → 默认值
        }

        auto json = JsonObject::Parse(winrt::hstring(Utf8ToWide(content)));
        if (!json)
        {
            return settings;
        }

        settings.autoReconnect = TryGetBool(json, kAutoReconnectKey, settings.autoReconnect);
        settings.runAtStartup = TryGetBool(json, kRunAtStartupKey, settings.runAtStartup);
        settings.lastConnectedDevices = TryGetStringArray(json, kLastDevicesKey);
    }
    catch (winrt::hresult_error const&)
    {
        // 文件不存在（0x80070002）、JSON 语法错误（0x83750007）等一律回落默认值。
        // 这里刻意不记日志：首次启动时「文件不存在」是常态，记日志会污染输出。
        return AppSettings{};
    }
    catch (std::exception const&)
    {
        return AppSettings{};
    }

    NormalizeDeviceList(settings.lastConnectedDevices);
    return settings;
}

bool SaveSettings(AppSettings const& settings, std::wstring const& path)
{
    if (path.empty())
    {
        return false;
    }

    AppSettings normalized = settings;
    NormalizeDeviceList(normalized.lastConnectedDevices);

    try
    {
        JsonObject json;
        // JsonObject::Insert 要的是 IJsonValue，不是 IInspectable。
        json.Insert(kAutoReconnectKey,
            JsonValue::CreateBooleanValue(normalized.autoReconnect));
        json.Insert(kRunAtStartupKey,
            JsonValue::CreateBooleanValue(normalized.runAtStartup));

        JsonArray deviceArray;
        for (auto const& id : normalized.lastConnectedDevices)
        {
            deviceArray.Append(JsonValue::CreateStringValue(winrt::hstring(id)));
        }
        json.Insert(kLastDevicesKey, deviceArray);

        std::filesystem::path target(path);
        auto parent = target.parent_path();
        if (parent.empty())
        {
            return false;
        }

        // 父目录不存在时自己创建 —— 用户可能从未运行过旧版本
        std::error_code ec;
        std::filesystem::create_directories(parent, ec);
        if (ec)
        {
            return false;
        }

        // 写同目录临时文件后原子替换，写入中断不会截断用户原来的配置。
        auto temporary = target.wstring() + L"." + std::to_wstring(::GetCurrentProcessId()) +
            L"." + std::to_wstring(::GetCurrentThreadId()) + L".tmp";
        auto cleanup = wil::scope_exit([&] { ::DeleteFileW(temporary.c_str()); });
        std::ofstream file(std::filesystem::path(temporary), std::ios::binary | std::ios::trunc);
        auto content = WideToUtf8(std::wstring(json.Stringify()));
        file.write(content.data(), static_cast<std::streamsize>(content.size()));
        file.flush();
        bool written = file.good();
        file.close();
        return written && !file.fail() && ::MoveFileExW(temporary.c_str(), path.c_str(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) != FALSE;
    }
    catch (winrt::hresult_error const&)
    {
        return false;
    }
    catch (std::exception const&)
    {
        return false;
    }
}

} // namespace AudioBule::Core
