#include "pch.h"
#include "Step2_EndpointId.h"

using namespace winrt::Windows::Devices::Enumeration;
using namespace winrt::Windows::Foundation;

std::vector<std::wstring> GetEndpointIdsForDevices(const std::vector<A2dpDeviceInfo>& devices)
{
    std::vector<std::wstring> endpointIds;

    for (const auto& device : devices)
    {
        // 用 device.Id 重新取一次，拿到完整的 Properties 集合
        DeviceInformation info = nullptr;
        try
        {
            info = DeviceInformation::CreateFromIdAsync(device.id).get();
        }
        catch (winrt::hresult_error const& e)
        {
            wprintf(L"[SKIP] 无法重新获取设备 %s: %s (0x%08X)\n",
                device.name.c_str(), e.message().c_str(), static_cast<uint32_t>(e.code()));
            continue;
        }

        auto properties = info.Properties();

        // Lookup 返回可能为 nullptr —— 属性不存在时必须跳过而非解引用
        if (!properties.HasKey(L"System_DeviceEndpointId"))
        {
            wprintf(L"[SKIP] 设备 %s 没有 System_DeviceEndpointId 属性\n", device.name.c_str());

            // 诊断：把该设备所有可读属性打印出来，寻找可替代的关联线索
            wprintf(L"       --- 该设备的全部属性 ---\n");
            for (auto&& [key, value] : properties)
            {
                std::wstring text;
                auto propertyValue = value.try_as<winrt::Windows::Foundation::IPropertyValue>();
                if (propertyValue)
                {
                    switch (propertyValue.Type())
                    {
                    case PropertyType::String: text = propertyValue.GetString(); break;
                    case PropertyType::UInt32: text = std::to_wstring(propertyValue.GetUInt32()); break;
                    case PropertyType::Boolean: text = propertyValue.GetBoolean() ? L"true" : L"false"; break;
                    case PropertyType::Guid:
                    {
                        auto g = propertyValue.GetGuid();
                        wchar_t buf[64]{};
                        StringFromGUID2(g, buf, 64);
                        text = buf;
                        break;
                    }
                    default: text = L"<其它类型>"; break;
                    }
                }
                wprintf(L"       %s = %s\n", key.c_str(), text.c_str());
            }
            wprintf(L"       --- 属性结束 ---\n");
            continue;
        }

        auto value = properties.Lookup(L"System_DeviceEndpointId");
        if (!value)
        {
            wprintf(L"[SKIP] 设备 %s 没有 System_DeviceEndpointId 属性\n", device.name.c_str());
            continue;
        }

        // Lookup 返回的是 IInspectable，ValueType/GetString 都在 IPropertyValue 上，
        // 必须先 as<IPropertyValue> 再调用
        auto propertyValue = value.as<winrt::Windows::Foundation::IPropertyValue>();
        if (!propertyValue || propertyValue.Type() != PropertyType::String)
        {
            wprintf(L"[SKIP] 设备 %s 的 System_DeviceEndpointId 不是字符串\n", device.name.c_str());
            continue;
        }

        auto endpointId = std::wstring(propertyValue.GetString());
        wprintf(L"[OK]   %s -> 端点 %s\n", device.name.c_str(), endpointId.c_str());
        endpointIds.push_back(endpointId);
    }

    return endpointIds;
}