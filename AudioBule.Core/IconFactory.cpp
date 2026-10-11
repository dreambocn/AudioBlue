#include "pch.h"
#include "IconFactory.h"

namespace AudioBule::Core
{

namespace {

// 托盘图标的 SVG 设计源是 assets/icons/tray-light.svg 和 tray-dark.svg。
// 由 assets/icons/Build-Icons.ps1 用 ImageMagick 在构建期光栅化成
// 多分辨率 .ico，并作为 RCDATA 资源嵌进 exe。
//
// 为什么运行期不直接渲染 SVG：
// Direct2D 的 SVG 支持（ID2D1DeviceContext5::DrawSvgDocument）要求**硬件**
// D3D11 设备 —— Direct2D 不支持 WARP 软件适配器。实测：
//   - D3D_DRIVER_TYPE_WARP → factory->CreateDevice 失败，HRESULT 0x80070057
//   - D3D_DRIVER_TYPE_HARDWARE → 无可用 GPU 的机器上阻塞 30 秒以上后失败
// 对一个 32x32 的静态托盘图标来说，构建期转换是更划算的架构。
//
// 这些十六进制值必须与 assets/icons/Build-Icons.ps1 里的主题色保持一致。
constexpr COLORREF kDarkThemeColor = RGB(0xF5, 0xF5, 0xF5);
constexpr COLORREF kLightThemeColor = RGB(0x20, 0x20, 0x20);

} // namespace

TrayIcon CreateTrayIcon(bool darkTheme, bool connected)
{
    // 深色任务栏上要画浅色图形，反之亦然
    const COLORREF color = darkTheme ? kDarkThemeColor : kLightThemeColor;

    HRSRC resource = ::FindResourceW(nullptr,
        MAKEINTRESOURCEW(connected ? (darkTheme ? 203 : 204) : (darkTheme ? 201 : 202)), RT_RCDATA);
    if (resource == nullptr)
    {
        return TrayIcon{};
    }

    HGLOBAL handle = ::LoadResource(nullptr, resource);
    if (handle == nullptr)
    {
        return TrayIcon{};
    }

    auto* bytes = static_cast<BYTE*>(::LockResource(handle));
    auto size = ::SizeofResource(nullptr, resource);
    if (bytes == nullptr || size == 0)
    {
        return TrayIcon{};
    }

    // 写到临时文件再让 LoadImage 读 —— LoadImage 从内存加载 .ico 只能拿到
    // 第一帧（16x16），托盘在深/浅色下都需要合适尺寸时体验很差。
    wchar_t tempPath[MAX_PATH] = {};
    DWORD length = ::GetTempPathW(MAX_PATH, tempPath);
    if (length == 0 || length >= MAX_PATH)
    {
        return TrayIcon{};
    }

    // 随机文件名隔离多个实例及并行图标创建，避免互相覆盖。
    wchar_t temporaryFile[MAX_PATH]{};
    if (!::GetTempFileNameW(tempPath, L"ABT", 0, temporaryFile)) return TrayIcon{};
    std::wstring filePath(temporaryFile);
    bool wrote = false;
    {
        // ⚠️ 不能用 FILE_FLAG_DELETE_ON_CLOSE：CloseHandle 会当场把文件删掉，
        // 随后的 LoadImage 就打不开了，图标静默失败。改为写完显式删除。
        HANDLE file = ::CreateFileW(filePath.c_str(), GENERIC_WRITE, 0, nullptr,
            CREATE_ALWAYS, FILE_ATTRIBUTE_TEMPORARY, nullptr);
        if (file != INVALID_HANDLE_VALUE)
        {
            DWORD written = 0;
            wrote = ::WriteFile(file, bytes, static_cast<DWORD>(size), &written, nullptr) != 0 && written == size;
            ::CloseHandle(file);
        }
    }

    if (!wrote)
    {
        ::DeleteFileW(filePath.c_str());
        return TrayIcon{};
    }

    // 0 = 不缩放，取 .ico 内置的最佳尺寸（托盘按当前缩放比挑选）。
    HICON icon = static_cast<HICON>(::LoadImageW(nullptr, filePath.c_str(),
        IMAGE_ICON, 0, 0, LR_LOADFROMFILE));

    ::DeleteFileW(filePath.c_str());

    if (icon == nullptr)
    {
        return TrayIcon{};
    }

    (void)color;   // 颜色已烘焙进各自的 .ico 资源
    return TrayIcon{ reinterpret_cast<void*>(icon) };
}

void DestroyTrayIcon(TrayIcon icon)
{
    if (icon.handle != nullptr)
    {
        ::DestroyIcon(reinterpret_cast<HICON>(icon.handle));
    }
}

} // namespace AudioBule::Core
