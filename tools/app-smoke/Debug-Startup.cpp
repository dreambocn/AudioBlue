// 启动调试器并输出崩溃栈，仅用于开发诊断，不参与产品构建。
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#include <cstdio>
#include <string>

int wmain(int argc, wchar_t** argv)
{
    if (argc != 2) return 2;
    std::wstring command = L"\"" + std::wstring(argv[1]) + L"\"";
    STARTUPINFOW startup{ sizeof(startup) };
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(nullptr, command.data(), nullptr, nullptr, FALSE,
        DEBUG_ONLY_THIS_PROCESS, nullptr, nullptr, &startup, &process)) return 3;
    DEBUG_EVENT event{};
    DWORD deadline = GetTickCount() + 20000;
    bool symbols = false;
    while (GetTickCount() < deadline)
    {
        if (!WaitForDebugEvent(&event, 1000)) continue;
        DWORD continuation = DBG_CONTINUE;
        if (event.dwDebugEventCode == CREATE_PROCESS_DEBUG_EVENT)
        {
            if (event.u.CreateProcessInfo.hFile) CloseHandle(event.u.CreateProcessInfo.hFile);
        }
        if (event.dwDebugEventCode == LOAD_DLL_DEBUG_EVENT && event.u.LoadDll.hFile)
            CloseHandle(event.u.LoadDll.hFile);
        if (event.dwDebugEventCode == OUTPUT_DEBUG_STRING_EVENT)
        {
            auto info = event.u.DebugString;
            if (info.fUnicode && info.nDebugStringLength > 0)
            {
                std::wstring message(info.nDebugStringLength, L'\0');
                SIZE_T read{};
                ReadProcessMemory(process.hProcess, info.lpDebugStringData,
                    message.data(), message.size() * sizeof(wchar_t), &read);
                wprintf(L"%s", message.c_str());
            }
            else if (info.nDebugStringLength > 0)
            {
                std::string message(info.nDebugStringLength, '\0');
                SIZE_T read{};
                ReadProcessMemory(process.hProcess, info.lpDebugStringData,
                    message.data(), message.size(), &read);
                printf("%s", message.c_str());
            }
        }
        if (event.dwDebugEventCode == EXCEPTION_DEBUG_EVENT)
        {
            auto exception = event.u.Exception;
            auto code = exception.ExceptionRecord.ExceptionCode;
            if (code == EXCEPTION_STACK_OVERFLOW || !exception.dwFirstChance)
            {
                printf("异常代码：0x%08lX\n", code);
                SetEnvironmentVariableW(L"_NT_SYMBOL_PATH", L"");
                SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_UNDNAME | SYMOPT_LOAD_LINES);
                symbols = SymInitializeW(process.hProcess, nullptr, TRUE) != FALSE;
                HANDLE thread = OpenThread(THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, event.dwThreadId);
                CONTEXT context{};
                context.ContextFlags = CONTEXT_FULL;
                GetThreadContext(thread, &context);
                STACKFRAME64 frame{};
                frame.AddrPC.Offset = context.Rip;
                frame.AddrFrame.Offset = context.Rbp;
                frame.AddrStack.Offset = context.Rsp;
                frame.AddrPC.Mode = frame.AddrFrame.Mode = frame.AddrStack.Mode = AddrModeFlat;
                for (int index = 0; index < 45; ++index)
                {
                    if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, process.hProcess, thread,
                        &frame, &context, nullptr, SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
                    alignas(SYMBOL_INFO) char buffer[sizeof(SYMBOL_INFO) + 1024]{};
                    auto symbol = reinterpret_cast<SYMBOL_INFO*>(buffer);
                    symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
                    symbol->MaxNameLen = 1024;
                    DWORD64 displacement{};
                    IMAGEHLP_MODULE64 module{};
                    module.SizeOfStruct = sizeof(module);
                    SymGetModuleInfo64(process.hProcess, frame.AddrPC.Offset, &module);
                    if (SymFromAddr(process.hProcess, frame.AddrPC.Offset, &displacement, symbol))
                        printf("%s!%s + 0x%llX\n", module.ModuleName, symbol->Name, displacement);
                    else printf("%s + 0x%llX\n", module.ModuleName, frame.AddrPC.Offset - module.BaseOfImage);
                }
                CloseHandle(thread);
                if (symbols) SymCleanup(process.hProcess);
                TerminateProcess(process.hProcess, code);
            }
            continuation = code == EXCEPTION_BREAKPOINT ? DBG_CONTINUE : DBG_EXCEPTION_NOT_HANDLED;
        }
        ContinueDebugEvent(event.dwProcessId, event.dwThreadId, continuation);
        if (event.dwDebugEventCode == EXIT_PROCESS_DEBUG_EVENT)
        {
            printf("退出代码：0x%08lX\n", event.u.ExitProcess.dwExitCode);
            break;
        }
    }
    TerminateProcess(process.hProcess, 0);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
