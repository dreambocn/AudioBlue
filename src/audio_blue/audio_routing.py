"""提供本机音频端点与音频流观测能力。"""

from __future__ import annotations

import asyncio
import ctypes
import re
import winreg
from ctypes import POINTER, byref, c_float, c_void_p
from dataclasses import dataclass
from time import sleep
from typing import Awaitable, Protocol, TypeVar
from uuid import UUID

from winrt.windows.devices.enumeration import DeviceInformation

AwaitableResult = TypeVar("AwaitableResult")

_CLSCTX_INPROC_SERVER = 0x1
_COINIT_MULTITHREADED = 0x0
_S_OK = 0
_S_FALSE = 1
_RPC_E_CHANGED_MODE = -2147417850
_DEVICE_STATE_ACTIVE = 0x1
_DEVICE_STATE_DISABLED = 0x2
_DEVICE_STATE_NOTPRESENT = 0x4
_DEVICE_STATE_UNPLUGGED = 0x8
_DEVICE_STATE_ALL = (
    _DEVICE_STATE_ACTIVE
    | _DEVICE_STATE_DISABLED
    | _DEVICE_STATE_NOTPRESENT
    | _DEVICE_STATE_UNPLUGGED
)
_ERENDER = 0
_ECAPTURE = 1
_EALL = 2
_ECONSOLE = 0
_STGM_READ = 0
_VT_EMPTY = 0
_VT_LPWSTR = 31
_VT_CLSID = 72
_MMDEVAPI_REGISTRY_PATH = r"SYSTEM\CurrentControlSet\Enum\SWD\MMDEVAPI"
_MMDEVICE_ENDPOINT_PATTERN = re.compile(
    r"(\{0\.0\.[01]\.00000000\}\.\{[0-9a-fA-F-]{36}\})"
)


class AudioRouteProbe(Protocol):
    """定义连接服务依赖的本机音频路由探测能力。"""

    def get_default_render_snapshot(self) -> "LocalRenderSnapshot": ...

    def get_audio_endpoint_snapshot(
        self,
        *,
        container_id: str | None = None,
    ) -> "LocalRenderSnapshot": ...

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
    """描述当前用于验证的本机音频端点。"""

    render_id: str | None
    render_name: str | None
    render_state: str
    is_active: bool
    error: str | None = None
    container_id: str | None = None
    endpoint_flow: str | None = "render"

    def to_details(self) -> dict[str, object]:
        return {
            "renderId": self.render_id,
            "renderName": self.render_name,
            "renderState": self.render_state,
            "error": self.error,
            "containerId": self.container_id,
            "endpointFlow": self.endpoint_flow,
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


class _IMMDeviceCollection(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


class _IPropertyStore(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


class _IAudioMeterInformation(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(c_void_p))]


@dataclass(slots=True)
class _MeterHandle:
    """把音量计对象与对应的 COM 生命周期绑在一起。"""

    meter: POINTER(_IAudioMeterInformation)
    com_scope: "_CoInitializeScope"


class _PROPERTYKEY(ctypes.Structure):
    _fields_ = [
        ("fmtid", _GUID),
        ("pid", ctypes.c_uint32),
    ]


class _PROPVARIANT_UNION(ctypes.Union):
    _fields_ = [
        ("pwszVal", ctypes.c_wchar_p),
        ("puuid", POINTER(_GUID)),
    ]


class _PROPVARIANT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("value", _PROPVARIANT_UNION),
    ]


@dataclass(slots=True)
class _AudioEndpointInfo:
    """保存枚举到的本机音频端点属性。"""

    endpoint_id: str
    name: str | None
    state: str
    container_id: str | None
    flow: str


_CLSID_MMDEVICE_ENUMERATOR = _GUID.from_string("BCDE0395-E52F-467C-8E3D-C4579291692E")
_IID_IMMDEVICE_ENUMERATOR = _GUID.from_string("A95664D2-9614-4F35-A746-DE8DB63617E6")
_IID_IAUDIO_METER_INFORMATION = _GUID.from_string("C02216F6-8C67-4B5B-9D00-D008E73E0064")
_PKEY_DEVICE_FRIENDLY_NAME = _PROPERTYKEY(
    _GUID.from_string("A45C254E-DF1C-4EFD-8020-67D146A850E0"),
    14,
)
_PKEY_DEVICE_CONTAINER_ID = _PROPERTYKEY(
    _GUID.from_string("8C7ED206-3F8A-4827-B3AB-AE9E1FAEFC6C"),
    2,
)

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
_ole32.PropVariantClear.argtypes = [POINTER(_PROPVARIANT)]
_ole32.PropVariantClear.restype = ctypes.c_long
_ole32.CoTaskMemFree.argtypes = [c_void_p]
_ole32.CoTaskMemFree.restype = None


def run_awaitable_blocking(awaitable: Awaitable[AwaitableResult]) -> AwaitableResult:
    """在同步调用栈中等待 WinRT 异步结果。"""

    async def runner() -> AwaitableResult:
        return await awaitable

    return asyncio.run(runner())


class Win32AudioRouteProbe:
    """组合 WinRT 与 Core Audio，读取音频端点和实时峰值。"""

    def get_default_render_snapshot(self) -> LocalRenderSnapshot:
        try:
            endpoint = _get_default_render_endpoint_info()
        except Exception as exc:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="error",
                is_active=False,
                error=f"default_render:{type(exc).__name__}",
            )

        if not endpoint.endpoint_id:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="missing",
                is_active=False,
                error="render_id_missing",
            )

        return LocalRenderSnapshot(
            render_id=endpoint.endpoint_id,
            render_name=endpoint.name,
            render_state=endpoint.state,
            is_active=endpoint.state == "active",
            container_id=endpoint.container_id,
            endpoint_flow=endpoint.flow,
        )

    def get_audio_endpoint_snapshot(
        self,
        *,
        container_id: str | None = None,
    ) -> LocalRenderSnapshot:
        """优先返回远端设备容器对应的本机音频端点，缺省时回退到默认播放端点。"""
        normalized_container_id = _normalize_container_id(container_id)
        if normalized_container_id is None:
            return self.get_default_render_snapshot()

        try:
            endpoints = _enumerate_audio_endpoints()
        except Exception as exc:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="error",
                is_active=False,
                error=f"endpoint_enumeration:{type(exc).__name__}",
                container_id=container_id,
                endpoint_flow=None,
            )

        matched = [
            endpoint
            for endpoint in endpoints
            if _normalize_container_id(endpoint.container_id) == normalized_container_id
        ]
        if not matched:
            return LocalRenderSnapshot(
                render_id=None,
                render_name=None,
                render_state="missing",
                is_active=False,
                error="endpoint_container_missing",
                container_id=container_id,
                endpoint_flow=None,
            )

        endpoint = _choose_best_endpoint(matched)
        return LocalRenderSnapshot(
            render_id=endpoint.endpoint_id,
            render_name=endpoint.name,
            render_state=endpoint.state,
            is_active=endpoint.state == "active",
            container_id=endpoint.container_id,
            endpoint_flow=endpoint.flow,
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


def _get_default_render_endpoint_info() -> _AudioEndpointInfo:
    """通过 Core Audio 读取默认播放端点，避免调用不稳定的 WinRT MediaDevice 入口。"""
    com_scope = _CoInitializeScope()
    device = _open_default_audio_device(com_scope=com_scope)
    try:
        return _read_audio_endpoint_info(device, flow_name="render")
    finally:
        _release_com_object(device)
        com_scope.close()


def _get_device_state(render_id: str) -> str:
    com_scope = _CoInitializeScope()
    device = _open_audio_device_by_id(
        _coerce_mmdevice_endpoint_id(render_id),
        com_scope=com_scope,
    )
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
    return _device_state_to_text(state_value.value)


def _enumerate_audio_endpoints() -> list[_AudioEndpointInfo]:
    com_scope = _CoInitializeScope()
    enumerator = _create_device_enumerator()
    try:
        endpoints: list[_AudioEndpointInfo] = []
        for flow_value, flow_name in ((_ECAPTURE, "capture"), (_ERENDER, "render")):
            endpoints.extend(
                _enumerate_audio_endpoints_for_flow(
                    enumerator,
                    flow_value=flow_value,
                    flow_name=flow_name,
                )
            )
        return _merge_audio_endpoints(endpoints, _enumerate_registry_audio_endpoints())
    finally:
        _release_com_object(enumerator)
        com_scope.close()


def _enumerate_audio_endpoints_for_flow(
    enumerator: POINTER(_IMMDeviceEnumerator),
    *,
    flow_value: int,
    flow_name: str,
) -> list[_AudioEndpointInfo]:
    collection_ptr = c_void_p()
    _invoke_method(
        enumerator,
        3,
        ctypes.c_int,
        ctypes.c_uint32,
        POINTER(c_void_p),
    )(flow_value, _DEVICE_STATE_ALL, byref(collection_ptr))
    collection = ctypes.cast(collection_ptr, POINTER(_IMMDeviceCollection))
    try:
        count = ctypes.c_uint32()
        _invoke_method(collection, 3, POINTER(ctypes.c_uint32))(byref(count))
        endpoints: list[_AudioEndpointInfo] = []
        for index in range(count.value):
            device_ptr = c_void_p()
            _invoke_method(
                collection,
                4,
                ctypes.c_uint32,
                POINTER(c_void_p),
            )(index, byref(device_ptr))
            device = ctypes.cast(device_ptr, POINTER(_IMMDevice))
            try:
                endpoints.append(_read_audio_endpoint_info(device, flow_name=flow_name))
            finally:
                _release_com_object(device)
        return endpoints
    finally:
        _release_com_object(collection)


def _read_audio_endpoint_info(
    device: POINTER(_IMMDevice),
    *,
    flow_name: str,
) -> _AudioEndpointInfo:
    endpoint_id = _get_audio_device_id(device)
    state_value = ctypes.c_uint32()
    _invoke_method(device, 6, POINTER(ctypes.c_uint32))(byref(state_value))
    store = _open_property_store(device)
    try:
        return _AudioEndpointInfo(
            endpoint_id=_coerce_mmdevice_endpoint_id(endpoint_id),
            name=_read_property_string(store, _PKEY_DEVICE_FRIENDLY_NAME),
            state=_device_state_to_text(state_value.value),
            container_id=_read_property_guid_or_string(store, _PKEY_DEVICE_CONTAINER_ID),
            flow=flow_name,
        )
    finally:
        _release_com_object(store)


def _get_audio_device_id(device: POINTER(_IMMDevice)) -> str:
    endpoint_id_ptr = ctypes.c_wchar_p()
    _invoke_method(device, 5, POINTER(ctypes.c_wchar_p))(byref(endpoint_id_ptr))
    try:
        return str(endpoint_id_ptr.value or "")
    finally:
        if endpoint_id_ptr:
            _ole32.CoTaskMemFree(ctypes.cast(endpoint_id_ptr, c_void_p))


def _enumerate_registry_audio_endpoints() -> list[_AudioEndpointInfo]:
    """从 SWD\\MMDEVAPI 注册表补充读取 PnP 可见但 MMDevice 枚举遗漏的端点。"""
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _MMDEVAPI_REGISTRY_PATH)
    except OSError:
        return []

    endpoints: list[_AudioEndpointInfo] = []
    with registry_key:
        subkey_count = winreg.QueryInfoKey(registry_key)[0]
        for index in range(subkey_count):
            try:
                endpoint_id = winreg.EnumKey(registry_key, index)
            except OSError:
                continue
            endpoint = _read_registry_audio_endpoint(registry_key, endpoint_id)
            if endpoint is not None:
                endpoints.append(endpoint)
    return endpoints


def _read_registry_audio_endpoint(registry_key, endpoint_id: str) -> _AudioEndpointInfo | None:
    flow = _infer_endpoint_flow(endpoint_id)
    if flow is None:
        return None
    try:
        with winreg.OpenKey(registry_key, endpoint_id) as endpoint_key:
            container_id = _read_registry_string(endpoint_key, "ContainerID")
            name = _read_registry_string(endpoint_key, "FriendlyName")
    except OSError:
        return None

    try:
        state = _get_device_state(endpoint_id)
    except Exception:
        state = "inactive"

    return _AudioEndpointInfo(
        endpoint_id=endpoint_id,
        name=name,
        state=state,
        container_id=container_id,
        flow=flow,
    )


def _read_registry_string(endpoint_key, value_name: str) -> str | None:
    try:
        value, _value_type = winreg.QueryValueEx(endpoint_key, value_name)
    except OSError:
        return None
    return str(value) if isinstance(value, str) and value else None


def _open_property_store(device: POINTER(_IMMDevice)) -> POINTER(_IPropertyStore):
    store_ptr = c_void_p()
    _invoke_method(
        device,
        4,
        ctypes.c_uint32,
        POINTER(c_void_p),
    )(_STGM_READ, byref(store_ptr))
    return ctypes.cast(store_ptr, POINTER(_IPropertyStore))


def _read_property_string(
    store: POINTER(_IPropertyStore),
    key: _PROPERTYKEY,
) -> str | None:
    value = _read_property_value(store, key)
    try:
        if value.vt == _VT_LPWSTR and value.pwszVal:
            return str(value.pwszVal)
        return None
    finally:
        _ole32.PropVariantClear(byref(value))


def _read_property_guid_or_string(
    store: POINTER(_IPropertyStore),
    key: _PROPERTYKEY,
) -> str | None:
    value = _read_property_value(store, key)
    try:
        if value.vt == _VT_CLSID and value.puuid:
            guid = value.puuid.contents
            raw_bytes = (
                int(guid.Data1).to_bytes(4, "little")
                + int(guid.Data2).to_bytes(2, "little")
                + int(guid.Data3).to_bytes(2, "little")
                + bytes(guid.Data4)
            )
            return str(UUID(bytes_le=raw_bytes))
        if value.vt == _VT_LPWSTR and value.pwszVal:
            return str(value.pwszVal)
        return None
    finally:
        _ole32.PropVariantClear(byref(value))


def _read_property_value(
    store: POINTER(_IPropertyStore),
    key: _PROPERTYKEY,
) -> _PROPVARIANT:
    value = _PROPVARIANT()
    _invoke_method(
        store,
        5,
        POINTER(_PROPERTYKEY),
        POINTER(_PROPVARIANT),
    )(byref(key), byref(value))
    return value


def _device_state_to_text(state_value: int) -> str:
    if state_value & _DEVICE_STATE_ACTIVE:
        return "active"
    if state_value & _DEVICE_STATE_DISABLED:
        return "disabled"
    if state_value & _DEVICE_STATE_NOTPRESENT:
        return "not_present"
    if state_value & _DEVICE_STATE_UNPLUGGED:
        return "unplugged"
    return "inactive"


def _choose_best_endpoint(endpoints: list[_AudioEndpointInfo]) -> _AudioEndpointInfo:
    return sorted(
        endpoints,
        key=lambda endpoint: (
            0 if endpoint.state == "active" else 1,
            0 if endpoint.flow == "capture" else 1,
            endpoint.name or "",
        ),
    )[0]


def _infer_endpoint_flow(endpoint_id: str) -> str | None:
    normalized = endpoint_id.lower()
    if normalized.startswith("{0.0.1."):
        return "capture"
    if normalized.startswith("{0.0.0."):
        return "render"
    return None


def _merge_audio_endpoints(
    primary: list[_AudioEndpointInfo],
    supplemental: list[_AudioEndpointInfo],
) -> list[_AudioEndpointInfo]:
    merged: dict[str, _AudioEndpointInfo] = {}
    for endpoint in [*primary, *supplemental]:
        key = _coerce_mmdevice_endpoint_id(endpoint.endpoint_id).lower()
        existing = merged.get(key)
        if existing is None:
            merged[key] = endpoint
            continue
        if existing.container_id is None and endpoint.container_id is not None:
            merged[key] = endpoint
    return list(merged.values())


def _normalize_container_id(container_id: str | None) -> str | None:
    if not isinstance(container_id, str):
        return None
    normalized = container_id.strip().strip("{}").lower()
    return normalized or None


def _coerce_mmdevice_endpoint_id(endpoint_id: str) -> str:
    """把 WinRT 音频接口 id 转为 IMMDevice.GetDevice 可接受的 MMDevice 端点 id。"""
    match = _MMDEVICE_ENDPOINT_PATTERN.search(endpoint_id)
    if match is None:
        return endpoint_id
    return match.group(1)


def _open_audio_meter(render_id: str) -> _MeterHandle:
    com_scope = _CoInitializeScope()
    device = _open_audio_device_by_id(
        _coerce_mmdevice_endpoint_id(render_id),
        com_scope=com_scope,
    )
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
