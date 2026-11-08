"""Explicit offline disaster recovery. Refuses a live service's disk lock."""
import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.hosting import acquire_storage_lock
from scripts.backup_sqlite import backup


def restore(source, target, expected_digest):
    source, target = Path(source).resolve(), Path(target).absolute()
    if not source.is_file() or source == target.resolve() or target.is_symlink():
        raise ValueError('Separate, regular backup and target paths are required')
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected_digest:
        raise ValueError('Backup fingerprint mismatch')
    target.parent.mkdir(parents=True, exist_ok=True)
    root_text=os.environ.get('WORKPAPER_DISK_ROOT','')
    root=Path(root_text)
    if not root_text or not root.is_absolute() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Restore target must be on the configured persistent disk')
    with acquire_storage_lock(root):
        receipt=root/('.restore-receipt-'+expected_digest)
        if receipt.exists():raise ValueError('This backup was already restored; refusing an accidental repeated rollback')
        with sqlite3.connect('file:' + quote(str(source)) + '?mode=ro', uri=True) as original:
            if original.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or original.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Backup integrity failed')
        stamp = uuid.uuid4().hex
        if target.exists():
            # Retain the complete previous state, including writes newer than the chosen backup.
            backup(target,target.with_name(target.name+'.pre-restore-'+stamp+'.backup'))
        staging=target.with_name(target.name+'.restore-'+stamp)
        try:
            backup(source,staging)
            # No application connection is alive under the shared exclusive lock.
            for suffix in ('-wal','-shm','-journal'):
                Path(str(target)+suffix).unlink(missing_ok=True)
            os.replace(staging,target)
            with receipt.open('x') as record:record.write('Offline restore completed; previous database preserved in pre-restore backup.\n')
        finally:
            staging.unlink(missing_ok=True)
            staging.with_suffix(staging.suffix+'.sha256').unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--offline',action='store_true',required=True)
    args=parser.parse_args()
    try:restore(args.backup,args.database,args.sha256)
    except (OSError,ValueError,RuntimeError,sqlite3.Error):parser.exit(1,'Offline restore refused or failed; inspect paths, lock, fingerprint and integrity.\n')
    print('Offline restore completed; previous state retained. Run the hosted preflight before serving traffic.')
