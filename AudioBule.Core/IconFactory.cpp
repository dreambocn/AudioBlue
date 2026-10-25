#include "pch.h"
#include "IconFactory.h"
#include <cstring>
#include <limits>

namespace AudioBule::Core
{
namespace
{
// ICO 目录字段可能未对齐，先复制再读取，避免 ARM64 上的未对齐访问。
template <typename T> T ReadField(BYTE const* data, size_t offset)
{
    T value{};
    std::memcpy(&value, data + offset, sizeof(value));
    return value;
}
}

TrayIcon CreateTrayIcon(bool darkTheme, bool connected)
{
    auto resource = ::FindResourceW(nullptr,
        MAKEINTRESOURCEW(connected ? (darkTheme ? 203 : 204) : (darkTheme ? 201 : 202)), RT_RCDATA);
    if (!resource) return {};
    auto handle = ::LoadResource(nullptr, resource);
    auto data = handle ? static_cast<BYTE*>(::LockResource(handle)) : nullptr;
    size_t size = ::SizeofResource(nullptr, resource);
    if (!data || size < 6 || ReadField<WORD>(data, 0) != 0 || ReadField<WORD>(data, 2) != 1) return {};
    size_t count = ReadField<WORD>(data, 4);
    if (!count || count > (size - 6) / 16) return {};

    int width = std::max(16, ::GetSystemMetrics(SM_CXSMICON));
    int height = std::max(16, ::GetSystemMetrics(SM_CYSMICON));
    int bestScore = std::numeric_limits<int>::max();
    DWORD selectedOffset = 0, selectedBytes = 0;
    for (size_t index = 0; index < count; ++index)
    {
        size_t entry = 6 + index * 16;
        int imageWidth = data[entry] ? data[entry] : 256;
        int imageHeight = data[entry + 1] ? data[entry + 1] : 256;
        auto bytes = ReadField<DWORD>(data, entry + 8);
        auto offset = ReadField<DWORD>(data, entry + 12);
        // 拒绝指向目录或越过资源尾部的数据，损坏资源安全回退为空图标。
        if (!bytes || offset < 6 + count * 16 || offset > size || bytes > size - offset) continue;
        int score = std::abs(imageWidth - width) + std::abs(imageHeight - height);
        if (imageWidth < width || imageHeight < height) score += 1000;
        if (score < bestScore) { bestScore = score; selectedOffset = offset; selectedBytes = bytes; }
    }
    if (!selectedBytes) return {};
    // 直接加载 ICO 中的图像帧，不创建临时文件，也不要求用户目录可写。
    auto icon = ::CreateIconFromResourceEx(data + selectedOffset, selectedBytes, TRUE, 0x00030000,
        width, height, LR_DEFAULTCOLOR);
    return { reinterpret_cast<void*>(icon) };
}

void DestroyTrayIcon(TrayIcon icon)
{
    if (icon.handle) ::DestroyIcon(reinterpret_cast<HICON>(icon.handle));
}
}
