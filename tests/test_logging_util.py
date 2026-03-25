"""验证日志配置是否把记录写入 SQLite 存储。"""

import logging
import sqlite3

from audio_blue.logging_util import configure_logging


def _reset_audio_blue_logger() -> None:
    """清理测试残留 handler，避免不同用例之间互相污染。"""
    logger = logging.getLogger("audio_blue")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configure_logging_writes_records_to_sqlite(tmp_path):
    _reset_audio_blue_logger()
    legacy_log_path = tmp_path / "audioblue.log"

    logger = configure_logging(legacy_log_path)
    logger.info("hello sqlite logging")

    with sqlite3.connect(tmp_path / "audioblue.db") as connection:
        records = connection.execute("SELECT level, message FROM log_records").fetchall()

    assert ("INFO", "hello sqlite logging") in records


def test_configure_logging_migrates_legacy_log_file(tmp_path):
    _reset_audio_blue_logger()
    legacy_log_path = tmp_path / "audioblue.log"
    legacy_log_path.write_text(
        "2026-03-21 08:00:00,001 WARNING migrated legacy line",
        encoding="utf-8",
    )

    logger = configure_logging(legacy_log_path)
    logger.info("post-migration line")

    with sqlite3.connect(tmp_path / "audioblue.db") as connection:
        messages = [row[0] for row in connection.execute("SELECT message FROM log_records ORDER BY id")]

    assert "migrated legacy line" in messages
    assert "post-migration line" in messages
