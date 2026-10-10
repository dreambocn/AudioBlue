#pragma once

// 以下函数均假定参数非空；调用方负责检查。
// com_ptr 按 const 引用传递 —— 避免每次调用都做引用计数增减。
bool ReadMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float& out);
bool WriteMasterVolume(const wil::com_ptr<IAudioEndpointVolume>& volume, float value);
bool ReadMute(const wil::com_ptr<IAudioEndpointVolume>& volume, bool& out);