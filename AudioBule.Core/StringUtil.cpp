#include "pch.h"
#include "StringUtil.h"

namespace AudioBule::Core
{

std::string WideToUtf8(std::wstring_view text)
{
    if (text.empty())
    {
        return {};
    }

    // wcslen 语义：std::wstring_view 可能含内嵌 NUL，显式按首个 NUL 截断
    size_t length = text.find(L'\0');
    if (length == std::wstring_view::npos)
    {
        length = text.size();
    }

    int required = ::WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(length), nullptr, 0, nullptr, nullptr);
    if (required <= 0)
    {
        return {};
    }

    std::string result(static_cast<size_t>(required), '\0');
    int written = ::WideCharToMultiByte(
        CP_UTF8, 0, text.data(), static_cast<int>(length),
        result.data(), required, nullptr, nullptr);
    if (written <= 0)
    {
        return {};
    }
    result.resize(static_cast<size_t>(written));
    return result;
}

std::wstring Utf8ToWide(std::string_view text)
{
    if (text.empty())
    {
        return {};
    }

    // 不传 MB_ERR_INVALID_CHORS：无效字节按 WinAPI 默认行为替换为 U+FFFD，
    // 抛异常对「读一条可能损坏的错误文案」这种场景太激进了。
    int required = ::MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0);
    if (required <= 0)
    {
        return {};
    }

    std::wstring result(static_cast<size_t>(required), L'\0');
    int written = ::MultiByteToWideChar(
        CP_UTF8, 0, text.data(), static_cast<int>(text.size()),
        result.data(), required);
    if (written <= 0)
    {
        return {};
    }
    result.resize(static_cast<size_t>(written));
    return result;
}

std::wstring FormatWin32Error(DWORD code)
{
    wchar_t buffer[16] = {};
    swprintf_s(buffer, L"0x%08X", static_cast<unsigned>(code));
    return std::wstring(buffer);
}

std::wstring FormatMessageForHresult(HRESULT hr)
{
    LPWSTR text = nullptr;
    DWORD length = ::FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM |
            FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr, static_cast<DWORD>(hr),
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&text), 0, nullptr);

    if (length == 0 || text == nullptr)
    {
        // 系统无本地化文本 —— 用十六进制兜底，保证调用方永远拿到非空字符串
        if (text != nullptr)
        {
            ::LocalFree(text);
        }
        return FormatWin32Error(static_cast<DWORD>(hr));
    }

    std::wstring result(text, length);
    ::LocalFree(text);

    // FormatMessageW 的文本带尾随 CRLF，UI 上显示会多出空白
    while (!result.empty() &&
           (result.back() == L'\r' || result.back() == L'\n' || result.back() == L' '))
    {
        result.pop_back();
    }

    return result.empty() ? FormatWin32Error(static_cast<DWORD>(hr)) : result;
}

} // namespace AudioBule::Core