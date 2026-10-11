#pragma once

// AudioBule 统一目标版本：Windows 10 2004 (build 19041)。
// AudioPlaybackConnection 由该版本引入，更低版本需优雅退出。
#define _WIN32_WINNT 0x0A00
#define WINVER 0x0A00
#define NTDDI_VERSION NTDDI_WIN10_RS3