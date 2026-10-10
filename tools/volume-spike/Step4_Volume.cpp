#include "pch.h"
#include "Step4_Volume.h"

bool ReadMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float& out)
{
    float value = 0.0f;
    HRESULT hr = volume->GetMasterVolumeLevelScalar(&value);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 读取音量失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    out = value;
    wprintf(L"[OK]   当前音量: %.1f%%\n", value * 100.0f);
    return true;
}

bool WriteMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float value)
{
    // value 必须在 [0,1]，防止越界导致未定义行为
    if (value < 0.0f || value > 1.0f)
    {
        wprintf(L"[FAIL] 音量值 %.2f 超出 [0,1] 范围\n", value);
        return false;
    }

    HRESULT hr = volume->SetMasterVolumeLevelScalar(value, nullptr);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 设置音量失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    wprintf(L"[OK]   已设置音量为 %.1f%%\n", value * 100.0f);
    return true;
}

bool ReadMute(const wil::com_ptr<IAudioEndpointVolume>& volume, bool& out)
{
    BOOL muted = FALSE;
    HRESULT hr = volume->GetMute(&muted);
    if (FAILED(hr))
    {
        wprintf(L"[FAIL] 读取静音状态失败: 0x%08X\n", static_cast<uint32_t>(hr));
        return false;
    }
    out = (muted != FALSE);
    wprintf(L"[OK]   静音状态: %s\n", out ? L"是" : L"否");
    return true;
}