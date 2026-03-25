from audio_blue.storage import SQLiteStorage, get_default_storage, get_storage


def test_runtime_storage_factory_returns_default_sqlite_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    storage = get_storage()
    default_storage = get_default_storage()

    assert isinstance(storage, SQLiteStorage)
    assert isinstance(default_storage, SQLiteStorage)
    assert storage.db_path == (tmp_path / "AudioBlue" / "audioblue.db").resolve()
    assert default_storage.db_path == storage.db_path
