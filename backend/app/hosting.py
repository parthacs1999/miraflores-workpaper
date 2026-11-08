"""Fail-closed single-instance hosting and persistent SQLite preflight."""
import os
import sqlite3
from pathlib import Path


def initialize_hosted_storage():
    from app.services.review_service import initialize_database, connect
    root_text = os.environ.get('WORKPAPER_DISK_ROOT', '')
    path_text = os.environ.get('REVIEW_DB_PATH', '')
    root, path = Path(root_text), Path(path_text)
    if not root_text or not path_text or not root.is_absolute() or not path.is_absolute():
        raise RuntimeError('Hosted storage requires absolute WORKPAPER_DISK_ROOT and REVIEW_DB_PATH')
    if not root.is_dir() or not os.path.ismount(root):
        raise RuntimeError('Hosted persistent disk is not mounted; refusing ephemeral storage')
    if root.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.resolve() == root.resolve():
        raise RuntimeError('Hosted database must be a file within the persistent disk')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
        raise RuntimeError('Hosted database path must not traverse symlinks')
    os.umask(0o077)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        initialize_database()
        with connect() as db:
            if db.execute('PRAGMA journal_mode=WAL').fetchone()[0].lower() != 'wal':
                raise RuntimeError('SQLite WAL mode unavailable')
            db.execute('PRAGMA synchronous=FULL')
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise RuntimeError('SQLite integrity preflight failed')
        path.chmod(0o600)
    except (OSError, sqlite3.Error) as exc:
        raise RuntimeError('Persistent database initialization failed; service not started') from None


def acquire_storage_lock(root):
    """Hold for the entire hosted process; cooperating restore tools use the same lock."""
    import fcntl
    handle = (Path(root) / '.miraflores-service.lock').open('a')
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('Another application or restore process owns this disk') from None
    return handle


from contextlib import contextmanager

@contextmanager
def hosted_storage():
    root = Path(os.environ.get('WORKPAPER_DISK_ROOT', ''))
    if not root.is_absolute() or not root.is_dir() or not os.path.ismount(root):
        raise RuntimeError('Hosted persistent disk is not mounted; refusing ephemeral storage')
    os.umask(0o077)
    with acquire_storage_lock(root):
        initialize_hosted_storage()
        yield
