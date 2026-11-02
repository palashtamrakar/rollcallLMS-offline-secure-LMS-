import argparse
import hashlib
import os
import shutil
import sqlite3
import string
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Iterable


PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR_NAME = "pendriveData"
MARKER_NAME = ".rollcall-storage"
MARKER_CONTENT = "rollcall-storage-v1\n"
DATABASE_NAME = "roll_call.db"
POLL_INTERVAL_SECONDS = 5


def _windows_drive_roots() -> Iterable[Path]:
    if os.name != "nt":
        return ()

    import ctypes

    roots = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if ctypes.windll.kernel32.GetDriveTypeW(str(root)) != 1:
            roots.append(root)
    return roots


def volume_roots(project_dir: Path) -> list[Path]:
    roots = [project_dir]
    if os.name == "nt":
        roots.extend(_windows_drive_roots())
    else:
        volumes = Path("/Volumes")
        if volumes.is_dir():
            roots.extend(path for path in volumes.iterdir() if path.is_dir())
        for mount_root in (Path("/media"), Path("/run/media")):
            if mount_root.is_dir():
                for user_mount in mount_root.iterdir():
                    if user_mount.is_dir():
                        roots.extend(path for path in user_mount.iterdir() if path.is_dir())
        mount_root = Path("/mnt")
        if mount_root.is_dir():
            roots.extend(path for path in mount_root.iterdir() if path.is_dir())

    unique_roots = []
    seen = set()
    for root in roots:
        try:
            resolved = root.resolve(strict=True)
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            unique_roots.append(resolved)
    return unique_roots


def has_valid_marker(data_dir: Path) -> bool:
    try:
        return (data_dir / MARKER_NAME).read_text(encoding="utf-8") == MARKER_CONTENT
    except OSError:
        return False


def find_data_dirs(project_dir: Path = PROJECT_DIR) -> list[Path]:
    matches = []
    seen = set()
    for root in volume_roots(project_dir):
        data_dir = root / DATA_DIR_NAME
        if not has_valid_marker(data_dir):
            continue
        try:
            resolved = data_dir.resolve(strict=True)
        except OSError:
            continue
        if resolved not in seen:
            seen.add(resolved)
            matches.append(resolved)
    return matches


def check_data_dir(data_dir: Path) -> None:
    if not has_valid_marker(data_dir):
        raise RuntimeError(f"Roll Call storage marker is missing or invalid: {data_dir}")
    if not (data_dir / DATABASE_NAME).is_file():
        raise RuntimeError(f"Database is missing from {data_dir}")
    try:
        connection = sqlite3.connect(f"file:{(data_dir / DATABASE_NAME).resolve()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise RuntimeError(f"Database is not readable: {data_dir / DATABASE_NAME}: {error}") from error
    if result != ("ok",):
        raise RuntimeError(f"Database integrity check failed for {data_dir / DATABASE_NAME}: {result}")
    for subdir in ("uploads/videos", "uploads/presentations"):
        if not (data_dir / subdir).is_dir():
            raise RuntimeError(f"Required folder is missing: {data_dir / subdir}")

    probe = data_dir / f".write-check-{os.getpid()}"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as error:
        probe.unlink(missing_ok=True)
        raise RuntimeError(f"Storage is not writable: {data_dir}: {error}") from error


def _table_counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for (table,) in tables
        }
    finally:
        connection.close()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_database(source: Path, destination: Path) -> None:
    source_connection = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def migrate_existing_data(project_dir: Path = PROJECT_DIR) -> Path:
    source_database = project_dir / DATABASE_NAME
    source_uploads = project_dir / "uploads"
    backend_database = project_dir / "backend" / DATABASE_NAME
    destination = project_dir / DATA_DIR_NAME
    staging = project_dir / f".{DATA_DIR_NAME}-migration"

    if not source_database.is_file():
        raise RuntimeError(f"Current database not found: {source_database}")
    if destination.exists():
        if (destination / DATABASE_NAME).exists():
            raise RuntimeError(f"Target already has a database: {destination / DATABASE_NAME}")
        unexpected_items = [path for path in destination.iterdir() if path.name != MARKER_NAME]
        if unexpected_items:
            raise RuntimeError(f"Target is not empty: {destination}")
    if staging.exists():
        raise RuntimeError(f"Previous migration staging folder exists: {staging}")

    if backend_database.is_file() and any(_table_counts(backend_database).values()):
        raise RuntimeError(
            f"{backend_database} contains records; refusing to ignore a second non-empty database"
        )

    staging.mkdir()
    try:
        (staging / MARKER_NAME).write_text(MARKER_CONTENT, encoding="utf-8")
        _copy_database(source_database, staging / DATABASE_NAME)
        if source_uploads.is_dir():
            shutil.copytree(source_uploads, staging / "uploads")
        else:
            (staging / "uploads" / "videos").mkdir(parents=True)
            (staging / "uploads" / "presentations").mkdir(parents=True)

        if _table_counts(source_database) != _table_counts(staging / DATABASE_NAME):
            raise RuntimeError("Database verification failed: table counts do not match")
        source_files = sorted(
            path.relative_to(source_uploads)
            for path in source_uploads.rglob("*")
            if path.is_file()
        ) if source_uploads.is_dir() else []
        for relative_path in source_files:
            copied_file = staging / "uploads" / relative_path
            if not copied_file.is_file() or _file_hash(source_uploads / relative_path) != _file_hash(copied_file):
                raise RuntimeError(f"Upload verification failed: {relative_path}")

        (staging / "uploads" / "videos").mkdir(parents=True, exist_ok=True)
        (staging / "uploads" / "presentations").mkdir(parents=True, exist_ok=True)
        if destination.exists():
            (destination / MARKER_NAME).unlink(missing_ok=True)
            destination.rmdir()
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return destination


def initialize_simulation(project_dir: Path = PROJECT_DIR) -> Path:
    destination = project_dir / DATA_DIR_NAME
    if destination.exists() and has_valid_marker(destination):
        check_data_dir(destination)
        return destination
    return migrate_existing_data(project_dir)


def wait_for_storage(project_dir: Path = PROJECT_DIR) -> Path:
    while True:
        matches = find_data_dirs(project_dir)
        if len(matches) == 1:
            try:
                check_data_dir(matches[0])
                print(f"Using Roll Call data at: {matches[0]}", flush=True)
                return matches[0]
            except RuntimeError as error:
                print(f"Storage found but not ready: {error}", flush=True)
        elif len(matches) > 1:
            print(
                "More than one Roll Call storage folder was found. Leave only the intended "
                "pendriveData folder connected; checking again in 5 seconds.",
                flush=True,
            )
        else:
            print(
                "Waiting for the Roll Call pendriveData folder. Connect the drive; "
                "checking again in 5 seconds.",
                flush=True,
            )
        time.sleep(POLL_INTERVAL_SECONDS)


def run_app(data_dir: Path, project_dir: Path = PROJECT_DIR) -> int:
    environment = os.environ.copy()
    environment["PENDRIVE_DATA_DIR"] = str(data_dir)
    environment["UPLOAD_DIR"] = str(data_dir / "uploads" / "videos")
    environment["PRESENTATIONS_DIR"] = str(data_dir / "uploads" / "presentations")
    environment.pop("DATABASE_URL", None)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=project_dir,
        env=environment,
    )
    time.sleep(1)
    if process.poll() is None:
        webbrowser.open("http://127.0.0.1:8000")
    return process.wait()


def main() -> int:
    parser = argparse.ArgumentParser(description="Locate and launch Roll Call using pendriveData.")
    parser.add_argument(
        "--initialize-simulation",
        action="store_true",
        help="Copy the current database and uploads into the local pendriveData simulation folder.",
    )
    args = parser.parse_args()

    if args.initialize_simulation:
        data_dir = initialize_simulation()
        print(f"Initialized storage at: {data_dir}", flush=True)
        return 0

    try:
        return run_app(wait_for_storage())
    except KeyboardInterrupt:
        print("\nRoll Call startup stopped.", flush=True)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
