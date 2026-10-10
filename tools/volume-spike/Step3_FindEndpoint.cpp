#include "pch.h"
#include "Step3_FindEndpoint.h"

wil::com_ptr<IMMDevice> FindDevice(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::wstring& endpointId)
{
    constexpr int kMaxAttempts = 5;
    constexpr int kRetryDelayMs = 500;

    for (int attempt = 1; attempt <= kMaxAttempts; ++attempt)
    {
        wil::com_ptr<IMMDevice> device;
        HRESULT hr = enumerator->GetDevice(endpointId.c_str(), device.put());
        if (SUCCEEDED(hr))
        {
            wprintf(L"[OK]   找到端点（第 %d 次尝试）\n", attempt);
            return device;
        }

        wprintf(L"[WAIT] 端点尚不可用（尝试 %d/%d，hr=0x%08X），%dms 后重试\n",
            attempt, kMaxAttempts, static_cast<uint32_t>(hr), kRetryDelayMs);
        Sleep(kRetryDelayMs);
    }

    wprintf(L"[FAIL] 端点在 %d 次尝试后仍不可用\n", kMaxAttempts);
    return nullptr;
}

namespace
{
    std::wstring GetPropertyString(const wil::com_ptr<IMMDevice>& device, const PROPERTYKEY& key)
    {
        wil::com_ptr<IPropertyStore> store;
        if (FAILED(device->OpenPropertyStore(STGM_READ, store.put())) || !store)
        {
            return {};
        }

        PROPVARIANT value;
        PropVariantInit(&value);
        if (FAILED(store->GetValue(key, &value)))
        {
            PropVariantClear(&value);
            return {};
        }

        std::wstring result;
        if (value.vt == VT_LPWSTR && value.pwszVal != nullptr)
        {
            result = value.pwszVal;
        }
        else if (value.vt == VT_BSTR && value.bstrVal != nullptr)
        {
            result = value.bstrVal;
        }

        PropVariantClear(&value);
        return result;
    }
}

std::vector<RenderEndpointInfo> ListRenderEndpoints(const wil::com_ptr<IMMDeviceEnumerator>& enumerator)
{
    std::vector<RenderEndpointInfo> result;

    wil::com_ptr<IMMDeviceCollection> collection;
    HRESULT hr = enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, collection.put());
    if (FAILED(hr) || !collection)
    {
        wprintf(L"[FAIL] 枚举渲染端点失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return result;
    }

    UINT count = 0;
    collection->GetCount(&count);
    wprintf(L"[INFO] 系统当前有 %u 个活动渲染端点：\n", count);

    for (UINT i = 0; i < count; ++i)
    {
        wil::com_ptr<IMMDevice> device;
        if (FAILED(collection->Item(i, device.put())) || !device)
        {
            continue;
        }

        // GetId 返回的字符串由 CoTaskMem 分配，必须自行释放
        LPWSTR pId = nullptr;
        std::wstring id;
        if (SUCCEEDED(device->GetId(&pId)) && pId != nullptr)
        {
            id = pId;
            CoTaskMemFree(pId);
        }

        RenderEndpointInfo info;
        info.id = id;
        info.friendlyName = GetPropertyString(device, PKEY_Device_FriendlyName);

        wprintf(L"[OK]   [%u] %s\n         Id: %s\n",
            i,
            info.friendlyName.empty() ? L"(无名)" : info.friendlyName.c_str(),
            info.id.c_str());

        result.push_back(std::move(info));
    }

    return result;
}

std::vector<RenderEndpointInfo> PollForNewEndpoints(
    const wil::com_ptr<IMMDeviceEnumerator>& enumerator,
    const std::vector<std::wstring>& baseline,
    int maxSeconds)
{
    wprintf(L"       >>> 请立刻在小米 15 上开始播放音频，本程序将轮询 %d 秒...\n", maxSeconds);

    for (int second = 1; second <= maxSeconds; ++second)
    {
        Sleep(1000);

        auto current = ListRenderEndpoints(enumerator);
        std::vector<RenderEndpointInfo> added;

        for (const auto& endpoint : current)
        {
            bool existed = false;
            for (const auto& id : baseline)
            {
                if (id == endpoint.id) { existed = true; break; }
            }
            if (!existed)
            {
                added.push_back(endpoint);
            }
        }

        if (!added.empty())
        {
            wprintf(L"       >>> 第 %d 秒检测到 %u 个新端点！\n", second, static_cast<unsigned>(added.size()));
            return added;
        }

        wprintf(L"       ... %d 秒，暂无新端点（当前共 %u 个）\n", second, static_cast<unsigned>(current.size()));
    }

    return {};
}