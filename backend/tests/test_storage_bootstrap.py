import sqlite3
from pathlib import Path

import pytest

from backend import storage_bootstrap


def _create_database(path: Path, user_count: int = 1) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.executemany("INSERT INTO users DEFAULT VALUES", [()] * user_count)
        connection.commit()
    finally:
        connection.close()


def test_migrate_existing_data_verifies_and_copies_database_and_uploads(tmp_path: Path) -> None:
    _create_database(tmp_path / "roll_call.db", user_count=2)
    media = tmp_path / "uploads" / "presentations"
    media.mkdir(parents=True)
    (media / "deck.pptx").write_bytes(b"presentation data")

    destination = storage_bootstrap.migrate_existing_data(tmp_path)

    assert storage_bootstrap.has_valid_marker(destination)
    assert storage_bootstrap._table_counts(destination / "roll_call.db") == {"users": 2}
    assert (destination / "uploads" / "presentations" / "deck.pptx").read_bytes() == b"presentation data"
    storage_bootstrap.check_data_dir(destination)


def test_migration_refuses_nonempty_target_database(tmp_path: Path) -> None:
    _create_database(tmp_path / "roll_call.db")
    target = tmp_path / "pendriveData"
    target.mkdir()
    _create_database(target / "roll_call.db")

    with pytest.raises(RuntimeError, match="Target already has a database"):
        storage_bootstrap.migrate_existing_data(tmp_path)


def test_find_data_dirs_checks_only_marked_data_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    volume = tmp_path / "usb"
    data_dir = volume / storage_bootstrap.DATA_DIR_NAME
    data_dir.mkdir(parents=True)
    (data_dir / storage_bootstrap.MARKER_NAME).write_text(
        storage_bootstrap.MARKER_CONTENT,
        encoding="utf-8",
    )
    (volume / "nested").mkdir()
    monkeypatch.setattr(storage_bootstrap, "volume_roots", lambda project_dir: [tmp_path, volume])

    assert storage_bootstrap.find_data_dirs(tmp_path) == [data_dir.resolve()]


def test_wait_for_storage_retries_after_five_seconds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / storage_bootstrap.DATA_DIR_NAME
    (data_dir / "uploads" / "videos").mkdir(parents=True)
    (data_dir / "uploads" / "presentations").mkdir(parents=True)
    (data_dir / storage_bootstrap.MARKER_NAME).write_text(
        storage_bootstrap.MARKER_CONTENT,
        encoding="utf-8",
    )
    _create_database(data_dir / storage_bootstrap.DATABASE_NAME)

    discoveries = iter(([], [data_dir]))
    delays = []
    monkeypatch.setattr(storage_bootstrap, "find_data_dirs", lambda project_dir: next(discoveries))
    monkeypatch.setattr(storage_bootstrap.time, "sleep", delays.append)

    assert storage_bootstrap.wait_for_storage(tmp_path) == data_dir
    assert delays == [storage_bootstrap.POLL_INTERVAL_SECONDS]
