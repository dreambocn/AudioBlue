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
