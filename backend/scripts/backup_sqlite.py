"""Create a consistent, non-overwriting online backup. No raw database copy."""
import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
from urllib.parse import quote


def backup(source: Path, destination: Path):
    source, destination = source.resolve(), destination.absolute()
    if not source.is_file() or source == destination.resolve():
        raise ValueError('A separate existing source database is required')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental overwrite; restrictive permissions protect data.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect('file:' + quote(str(source)) + '?mode=ro', uri=True) as original:
            with sqlite3.connect(destination) as copy:
                original.backup(copy, pages=256, sleep=0.05)
                if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or copy.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Backup failed integrity validation')
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        with destination.with_suffix(destination.suffix + '.sha256').open('x') as manifest:
            manifest.write(digest + '  ' + destination.name + '\n')
        return digest
    except Exception:
        destination.unlink(missing_ok=True)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    arguments = parser.parse_args()
    try:
        backup(arguments.source, arguments.destination)
    except (OSError, ValueError, sqlite3.Error):
        parser.exit(1, 'Backup failed; check paths, permissions and database integrity.\n')
    print('Consistent backup and SHA-256 manifest created; protect and export both files.')
