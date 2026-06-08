"""覆盖音频路由探测优先使用指定 render_id 的行为。"""

from __future__ import annotations

import audio_blue.audio_routing as audio_routing


class _DummyCoScope:
    """模拟 COM 生命周期对象，避免测试依赖真实 COM 初始化。"""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_get_device_state_prefers_requested_render_device_before_default_fallback(monkeypatch):
    requested_ids: list[str] = []
    fake_device = object()

    monkeypatch.setattr(audio_routing, "_CoInitializeScope", _DummyCoScope)
    monkeypatch.setattr(
        audio_routing,
        "_open_audio_device_by_id",
        lambda render_id, *, com_scope: requested_ids.append(render_id) or fake_device,
    )
    monkeypatch.setattr(
        audio_routing,
        "_open_default_audio_device",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不应回退到默认播放端点")),
    )
    monkeypatch.setattr(audio_routing, "_release_com_object", lambda _interface: None)

    def fake_invoke(_interface, _index, *_argtypes):
        def caller(state_ptr):
            state_ptr._obj.value = audio_routing._DEVICE_STATE_ACTIVE

        return caller

    monkeypatch.setattr(audio_routing, "_invoke_method", fake_invoke)

    assert audio_routing._get_device_state("render-target") == "active"
    assert requested_ids == ["render-target"]


def test_open_audio_meter_prefers_requested_render_device_before_default_fallback(monkeypatch):
    requested_ids: list[str] = []
    fake_device = object()

    monkeypatch.setattr(audio_routing, "_CoInitializeScope", _DummyCoScope)
    monkeypatch.setattr(
        audio_routing,
        "_open_audio_device_by_id",
        lambda render_id, *, com_scope: requested_ids.append(render_id) or fake_device,
    )
    monkeypatch.setattr(
        audio_routing,
        "_open_default_audio_device",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不应回退到默认播放端点")),
    )
    monkeypatch.setattr(audio_routing, "_release_com_object", lambda _interface: None)

    def fake_invoke(_interface, _index, *_argtypes):
        def caller(*args):
            meter_ptr_ref = args[-1]
            meter_ptr_ref._obj.value = 1

        return caller

    monkeypatch.setattr(audio_routing, "_invoke_method", fake_invoke)

    handle = audio_routing._open_audio_meter("render-target")

    assert requested_ids == ["render-target"]
    handle.com_scope.close()


def test_audio_endpoint_snapshot_matches_registry_endpoint_when_core_audio_misses_container(monkeypatch):
    monkeypatch.setattr(audio_routing, "_enumerate_audio_endpoints", lambda: [
        audio_routing._AudioEndpointInfo(
            endpoint_id="default-render",
            name="耳机 (Senary Audio)",
            state="active",
            container_id="default-container",
            flow="render",
        ),
        audio_routing._AudioEndpointInfo(
            endpoint_id="{0.0.1.00000000}.{phone-endpoint}",
            name="麦克风 (Phone A2DP SNK)",
            state="active",
            container_id="{PHONE-CONTAINER}",
            flow="capture",
        ),
    ])

    snapshot = audio_routing.Win32AudioRouteProbe().get_audio_endpoint_snapshot(
        container_id="phone-container"
    )

    assert snapshot.render_id == "{0.0.1.00000000}.{phone-endpoint}"
    assert snapshot.render_name == "麦克风 (Phone A2DP SNK)"
    assert snapshot.render_state == "active"
    assert snapshot.endpoint_flow == "capture"
    assert snapshot.container_id == "{PHONE-CONTAINER}"


def test_default_render_snapshot_uses_core_audio_without_winrt_media_device(monkeypatch):
    class _CrashingMediaDevice:
        """模拟 WinRT MediaDevice 入口在原生层不可靠的场景。"""

        @staticmethod
        def get_default_audio_render_id(_role):
            raise AssertionError("不应调用 Windows.Media.Devices.MediaDevice")

    fake_device = object()

    monkeypatch.setattr(audio_routing, "MediaDevice", _CrashingMediaDevice, raising=False)
    monkeypatch.setattr(audio_routing, "_CoInitializeScope", _DummyCoScope)
    monkeypatch.setattr(
        audio_routing,
        "_open_default_audio_device",
        lambda **_kwargs: fake_device,
    )
    monkeypatch.setattr(
        audio_routing,
        "_read_audio_endpoint_info",
        lambda device, *, flow_name: audio_routing._AudioEndpointInfo(
            endpoint_id="{0.0.0.00000000}.{DEFAULT-RENDER}",
            name="扬声器",
            state="active",
            container_id="{DEFAULT-CONTAINER}",
            flow=flow_name,
        ),
    )
    monkeypatch.setattr(audio_routing, "_release_com_object", lambda _interface: None)

    snapshot = audio_routing.Win32AudioRouteProbe().get_default_render_snapshot()

    assert snapshot.render_id == "{0.0.0.00000000}.{DEFAULT-RENDER}"
    assert snapshot.render_name == "扬声器"
    assert snapshot.render_state == "active"
    assert snapshot.is_active is True
    assert snapshot.endpoint_flow == "render"
    assert snapshot.container_id == "{DEFAULT-CONTAINER}"


def test_coerce_mmdevice_endpoint_id_strips_winrt_interface_suffix():
    assert audio_routing._coerce_mmdevice_endpoint_id(
        r"\\?\SWD#MMDEVAPI#{0.0.1.00000000}.{ABCDEFAB-1111-2222-3333-ABCDEFABCDEF}#{2eef81be-33fa-4800-9670-1cd474972c3f}"
    ) == "{0.0.1.00000000}.{ABCDEFAB-1111-2222-3333-ABCDEFABCDEF}"
