from __future__ import annotations

import asyncio
import json
from typing import Any


def _load_audio_namespace():
    import winrt.windows.media.audio as audio

    return audio


def _load_enumeration_namespace():
    import winrt.windows.devices.enumeration as enumeration

    return enumeration


async def _enumerate_devices() -> list[dict[str, str]]:
    enumeration = _load_enumeration_namespace()
    devices = await enumeration.DeviceInformation.find_all_async()
    return [
        {
            "id": device.id,
            "name": device.name,
        }
        for device in devices
    ]


def run_probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "audio_namespace_available": False,
        "enumeration_namespace_available": False,
        "device_selector": None,
        "devices": [],
        "errors": [],
    }

    try:
        audio = _load_audio_namespace()
    except Exception as exc:
        result["errors"].append(f"audio_import_failed: {exc}")
        return result

    result["audio_namespace_available"] = True

    try:
        result["device_selector"] = audio.AudioPlaybackConnection.get_device_selector()
    except Exception as exc:
        result["errors"].append(f"device_selector_failed: {exc}")

    try:
        _load_enumeration_namespace()
        result["enumeration_namespace_available"] = True
    except Exception as exc:
        result["errors"].append(f"enumeration_import_failed: {exc}")
        return result

    try:
        result["devices"] = asyncio.run(_enumerate_devices())
    except Exception as exc:
        result["errors"].append(f"device_enumeration_failed: {exc}")

    return result


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2, ensure_ascii=False))
