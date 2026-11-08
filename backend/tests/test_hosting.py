import importlib.util
from pathlib import Path
import sqlite3
import pytest
from app.hosting import initialize_hosted_storage

spec=importlib.util.spec_from_file_location('sqlite_backup',Path(__file__).parents[1]/'scripts/backup_sqlite.py')
backup_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup_module)

@pytest.fixture
def mounted(tmp_path,monkeypatch):
    root=tmp_path/'disk';root.mkdir();path=root/'workpaper.db'
    monkeypatch.setenv('WORKPAPER_DISK_ROOT',str(root));monkeypatch.setenv('REVIEW_DB_PATH',str(path));monkeypatch.setattr('os.path.ismount',lambda p:Path(p)==root)
    return path

def test_empty_hosted_disk_migrates_and_survives_restart(mounted):
    initialize_hosted_storage()
    with sqlite3.connect(mounted) as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
        db.execute("INSERT INTO reviews VALUES('v3','deployment-only-fixture','open','isolated test','test',NULL)")
    initialize_hosted_storage()
    with sqlite3.connect(mounted) as db:
        assert db.execute("SELECT note FROM reviews WHERE finding_id='deployment-only-fixture'").fetchone()[0]=='isolated test'
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert mounted.stat().st_mode&0o777==0o600

def test_missing_mount_refuses_ephemeral_database(mounted,monkeypatch):
    monkeypatch.setattr('os.path.ismount',lambda p:False)
    with pytest.raises(RuntimeError,match='not mounted'):initialize_hosted_storage()
    assert not mounted.exists()

@pytest.mark.parametrize('path',['relative.db','/tmp/outside.db'])
def test_hosted_path_must_be_on_the_disk(mounted,monkeypatch,path):
    monkeypatch.setenv('REVIEW_DB_PATH',path)
    with pytest.raises(RuntimeError):initialize_hosted_storage()

def test_corrupt_database_prevents_startup(mounted):
    mounted.write_bytes(b'not a sqlite database')
    with pytest.raises(RuntimeError,match='initialization failed'):initialize_hosted_storage()

def test_backup_preserves_data_and_append_only_triggers(mounted,tmp_path):
    initialize_hosted_storage();destination=tmp_path/'copy.backup'
    digest=backup_module.backup(mounted,destination)
    assert digest in destination.with_suffix('.backup.sha256').read_text()
    with sqlite3.connect(destination) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='wf_events_delete'").fetchone()
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    with pytest.raises(FileExistsError):backup_module.backup(mounted,destination)
    with pytest.raises(ValueError):backup_module.backup(mounted,mounted)

def test_backups_capture_concurrent_commits_consistently(mounted,tmp_path):
    initialize_hosted_storage()
    from concurrent.futures import ThreadPoolExecutor
    def mutate(i):
        with sqlite3.connect(mounted,timeout=10) as db:db.execute('INSERT INTO reviews VALUES(?,?,?,?,?,?)',('test',str(i),'open','isolated','test',None))
    with ThreadPoolExecutor(max_workers=3) as executor:
        pending=[executor.submit(mutate,i) for i in range(12)]
        backup_module.backup(mounted,tmp_path/'concurrent.backup')
        for task in pending:task.result()
    with sqlite3.connect(mounted) as db:assert db.execute("SELECT COUNT(*) FROM reviews WHERE version='test'").fetchone()[0]==12

def test_disk_lock_prevents_multiple_instances_and_live_restore(mounted,tmp_path):
    initialize_hosted_storage()
    from app.hosting import acquire_storage_lock
    source=tmp_path/'restore.backup';digest=backup_module.backup(mounted,source)
    from scripts.restore_sqlite import restore
    with acquire_storage_lock(mounted.parent):
        with pytest.raises(RuntimeError,match='owns this disk'):acquire_storage_lock(mounted.parent)
        with pytest.raises(RuntimeError):restore(source,mounted,digest)
    restore(source,mounted,digest)
    assert list(mounted.parent.glob('*.pre-restore-*.backup'))
    with pytest.raises(ValueError,match='already restored'):restore(source,mounted,digest)
    with pytest.raises(ValueError,match='fingerprint'):restore(source,mounted,'bad')


def test_hosted_launcher_is_single_worker_public_bind_and_no_reload(mounted,monkeypatch):
    import run_secure
    from app.security import Settings
    settings=Settings('access','production',('https://workpaper.example.test',),{},'https://fixture-team.cloudflareaccess.com','fixture-aud',{'subject':'st-01'})
    monkeypatch.setattr(run_secure,'launch_settings',lambda demo:settings)
    monkeypatch.setenv('PORT','12345');monkeypatch.setenv('WEB_CONCURRENCY','1')
    calls=[];monkeypatch.setattr(run_secure.uvicorn,'run',lambda app,**kwargs:calls.append(kwargs))
    run_secure.main(['--hosted'])
    assert calls==[{'host':'0.0.0.0','port':12345,'workers':1,'reload':False,'timeout_graceful_shutdown':30,'access_log':False}]
    monkeypatch.setenv('WEB_CONCURRENCY','2')
    with pytest.raises(SystemExit):run_secure.main(['--hosted'])
    with pytest.raises(SystemExit):run_secure.main(['--hosted','--demo'])


def test_hosted_start_never_accepts_shared_credential_or_demo_mode(mounted,monkeypatch):
    import run_secure
    from app.security import Settings
    for mode in ['locked','credential','demo','legacy_test']:
        monkeypatch.setattr(run_secure,'launch_settings',lambda demo,m=mode:Settings(m,'production'))
        with pytest.raises(SystemExit):run_secure.main(['--hosted'])
