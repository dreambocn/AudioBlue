"""提供本机默认播放端点与音频流观测能力。"""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import POINTER, byref, c_float, c_void_p
from dataclasses import dataclass
from time import sleep
from typing import Awaitable, Protocol, TypeVar
from uuid import UUID

from winrt.windows.devices.enumeration import DeviceInformation
from winrt.windows.media.devices import AudioDeviceRole, MediaDevice

AwaitableResult = TypeVar("AwaitableResult")

_CLSCTX_INPROC_SERVER = 0x1
_COINIT_MULTITHREADED = 0x0
_S_OK = 0
_S_FALSE = 1
_RPC_E_CHANGED_MODE = -2147417850
_DEVICE_STATE_ACTIVE = 0x1
_ERENDER = 0
_ECONSOLE = 0


class AudioRouteProbe(Protocol):
    """定义连接服务依赖的本机音频路由探测能力。"""

    def get_default_render_snapshot(self) -> "LocalRenderSnapshot": ...

    def sample_audio_flow(
        self,
        *,
        render_id: str,
        sample_count: int,
        sample_interval_seconds: float,
        threshold: float,
    ) -> "AudioFlowObservation": ...


@dataclass(slots=True)
class LocalRenderSnapshot:
    """描述当前默认播放端点的基础信息。"""

    render_id: str | None
    render_name: str | None
    render_state: str
    is_active: bool
    error: str | None = None

    def to_details(self) -> dict[str, object]:
        return {
            "renderId": self.render_id,
            "renderName": self.render_name,
            "renderState": self.render_state,
            "error": self.error,
        }


@dataclass(slots=True)
class AudioFlowObservation:
    """描述一次音频流采样的结果。"""

    observed: bool
    peak_max: float
    sample_count: int
    threshold: float
    error: str | None = None

    def to_details(self) -> dict[str, object]:
        return {
            "peakMax": round(self.peak_max, 6),
            "sampleCount": self.sample_count,
            "threshold": self.threshold,
            "error": self.error,
        }


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> "_GUID":
        guid = UUID(value)
        data4 = (ctypes.c_ubyte * 8).from_buffer_copy(guid.bytes[8:])
        return cls(
            guid.time_low,
            guid.time_mid,
            guid.time_hi_version,
            data4,
        )


class _IMMDeviceEnumerator(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


class _IMMDevice(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


class _IAudioMeterInformation(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


@dataclass(slots=True)
class _MeterHandle:
    """把音量计对象与对应的 COM 生命周期绑在一起。"""

    meter: POINTER(_IAudioMeterInformation)
    com_scope: "_CoInitializeScope"


_CLSID_MMDEVICE_ENUMERATOR = _GUID.from_string("BCDE0395-E52F-467C-8E3D-C4579291692E")
_IID_IMMDEVICE_ENUMERATOR = _GUID.from_string("A95664D2-9614-4F35-A746-DE8DB63617E6")
_IID_IAUDIO_METER_INFORMATION = _GUID.from_string("C02216F6-8C67-4B5B-9D00-D008E73E0064")

_ole32 = ctypes.OleDLL("ole32")
_ole32.CoInitializeEx.argtypes = [c_void_p, ctypes.c_uint32]
_ole32.CoInitializeEx.restype = ctypes.c_long
_ole32.CoUninitialize.argtypes = []
_ole32.CoUninitialize.restype = None
_ole32.CoCreateInstance.argtypes = [
    POINTER(_GUID),
    c_void_p,
    ctypes.c_uint32,
    POINTER(_GUID),
    POINTER(c_void_p),
]
_ole32.CoCreateInstance.restype = ctypes.c_long


def run_awaitable_blocking(awaitable: Awaitable[AwaitableResult]) -> AwaitableResult:
    """在同步调用栈中等待 WinRT 异步结果。"""

    async def runner() -> AwaitableResult:
        return await awaitable

    return asyncio.run(runner())


class Win32AudioRouteProbe:
    """组合 WinRT 与 Core Audio，读取默认输出和实时峰值。"""

    def get_default_render_snapshot(self) -> LocalRenderSnapshot:
        try:
            render_id = MediaDevice.get_default_audio_render_id(AudioDeviceRole.DEFAULT)
        except Exception as exc:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="error",
                is_active=False,
                error=f"render_id:{type(exc).__name__}",
            )

        if not render_id:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="missing",
                is_active=False,
                error="render_id_missing",
            )

        render_name = _load_render_name(render_id)
        try:
            state = _get_device_state(render_id)
        except Exception as exc:
            return LocalRenderSnapshot(
                render_id=render_id,
                render_name=render_name,
                render_state="error",
                is_active=False,
                error=f"render_state:{type(exc).__name__}",
            )

        return LocalRenderSnapshot(
            render_id=render_id,
            render_name=render_name,
            render_state=state,
            is_active=state == "active",
        )

    def sample_audio_flow(
        self,
        *,
        render_id: str,
        sample_count: int,
        sample_interval_seconds: float,
        threshold: float,
    ) -> AudioFlowObservation:
        if not render_id:
            return AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=0,
                threshold=threshold,
                error="render_id_missing",
            )

        peaks: list[float] = []
        try:
            meter_handle = _open_audio_meter(render_id)
        except Exception as exc:
            return AudioFlowObservation(
                observed=False,
                peak_max=0.0,
                sample_count=0,
                threshold=threshold,
                error=f"meter_open:{type(exc).__name__}",
            )

        try:
            for index in range(max(sample_count, 0)):
                peak_value = _read_peak_value(meter_handle.meter)
                peaks.append(peak_value)
                if peak_value > threshold:
                    break
                if index < sample_count - 1 and sample_interval_seconds > 0:
                    sleep(sample_interval_seconds)
        except Exception as exc:
            return AudioFlowObservation(
                observed=False,
                peak_max=max(peaks, default=0.0),
                sample_count=len(peaks),
                threshold=threshold,
                error=f"meter_read:{type(exc).__name__}",
            )
        finally:
            _release_com_object(meter_handle.meter)
            meter_handle.com_scope.close()

        peak_max = max(peaks, default=0.0)
        return AudioFlowObservation(
            observed=peak_max > threshold,
            peak_max=peak_max,
            sample_count=len(peaks),
            threshold=threshold,
        )


def _load_render_name(render_id: str) -> str | None:
    try:
        device = run_awaitable_blocking(DeviceInformation.create_from_id_async(render_id))
    except Exception:
        return None
    name = getattr(device, "name", None)
    return str(name) if isinstance(name, str) else None


def _get_device_state(render_id: str) -> str:
    com_scope = _CoInitializeScope()
    device = _open_audio_device_by_id(render_id, com_scope=com_scope)
    try:
        state_value = ctypes.c_uint32()
        _invoke_method(
            device,
            6,
            POINTER(ctypes.c_uint32),
        )(byref(state_value))
    finally:
        _release_com_object(device)
        com_scope.close()
    if state_value.value & _DEVICE_STATE_ACTIVE:
        return "active"
    return "inactive"


def _open_audio_meter(render_id: str) -> _MeterHandle:
    com_scope = _CoInitializeScope()
    device = _open_audio_device_by_id(render_id, com_scope=com_scope)
    try:
        meter_ptr = c_void_p()
        _invoke_method(
            device,
            3,
            POINTER(_GUID),
            c_void_p,
            ctypes.c_uint32,
            POINTER(c_void_p),
        )(
            byref(_IID_IAUDIO_METER_INFORMATION),
            None,
            _CLSCTX_INPROC_SERVER,
            byref(meter_ptr),
        )
        return _MeterHandle(
            meter=ctypes.cast(meter_ptr, POINTER(_IAudioMeterInformation)),
            com_scope=com_scope,
        )
    except Exception:
        com_scope.close()
        raise
    finally:
        _release_com_object(device)


def _open_default_audio_device(
    *,
    com_scope: "_CoInitializeScope",
) -> POINTER(_IMMDevice):
    enumerator = _create_device_enumerator()
    try:
        device_ptr = c_void_p()
        _invoke_method(
            enumerator,
            4,
            ctypes.c_int,
            ctypes.c_int,
            POINTER(c_void_p),
        )(_ERENDER, _ECONSOLE, byref(device_ptr))
        return ctypes.cast(device_ptr, POINTER(_IMMDevice))
    finally:
        _release_com_object(enumerator)


def _open_audio_device_by_id(
    render_id: str,
    *,
    com_scope: "_CoInitializeScope",
) -> POINTER(_IMMDevice):
    if not render_id:
        return _open_default_audio_device(com_scope=com_scope)
    enumerator = _create_device_enumerator()
    try:
        device_ptr = c_void_p()
        _invoke_method(
            enumerator,
            5,
            ctypes.c_wchar_p,
            POINTER(c_void_p),
        )(render_id, byref(device_ptr))
        return ctypes.cast(device_ptr, POINTER(_IMMDevice))
    finally:
        _release_com_object(enumerator)


def _create_device_enumerator() -> POINTER(_IMMDeviceEnumerator):
    try:
        enumerator_ptr = c_void_p()
        _check_hresult(
            _ole32.CoCreateInstance(
                byref(_CLSID_MMDEVICE_ENUMERATOR),
                None,
                _CLSCTX_INPROC_SERVER,
                byref(_IID_IMMDEVICE_ENUMERATOR),
                byref(enumerator_ptr),
            )
        )
        return ctypes.cast(enumerator_ptr, POINTER(_IMMDeviceEnumerator))
    except Exception:
        raise


def _read_peak_value(meter: POINTER(_IAudioMeterInformation)) -> float:
    peak_value = c_float()
    _invoke_method(
        meter,
        3,
        POINTER(c_float),
    )(byref(peak_value))
    return float(peak_value.value)


def _invoke_method(interface, index: int, *argtypes):
    """按 vtable 下标调用 COM 方法，并在失败时抛出 OSError。"""

    def caller(*args):
        prototype = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, *argtypes)
        address = interface.contents.lpVtbl[index]
        method = prototype(address)
        result = method(interface, *args)
        _check_hresult(result)
        return result

    return caller


def _release_com_object(interface) -> None:
    if not interface:
        return
    prototype = ctypes.WINFUNCTYPE(ctypes.c_uint32, c_void_p)
    release = prototype(interface.contents.lpVtbl[2])
    release(interface)


class _CoInitializeScope:
    """在当前线程初始化 COM，并在合适时机安全释放。"""

    def __init__(self) -> None:
        result = _ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        if result not in {_S_OK, _S_FALSE, _RPC_E_CHANGED_MODE}:
            _check_hresult(result)
        self._should_uninitialize = result in {_S_OK, _S_FALSE}

    def close(self) -> None:
        if self._should_uninitialize:
            _ole32.CoUninitialize()
            self._should_uninitialize = False

    def __del__(self) -> None:
        self.close()


def _check_hresult(result: int) -> None:
    if result < 0:
        code = result & 0xFFFFFFFF
        raise OSError(code, f"Win32 HRESULT 0x{code:08X}")
