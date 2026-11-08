"""Additive, transactional migration; also run with python -m app.migrate."""
import argparse
import sqlite3
from pathlib import Path

from app.services.review_service import DB_PATH


def migrate(connection):
    scripts = sorted(Path(__file__).with_name('migrations').glob('[0-9][0-9][0-9]_*.sql'))
    try:
        for script in scripts:
            review_backfill=False
            if script.name.startswith('006_'):
                installed=connection.execute("SELECT 1 FROM sqlite_master WHERE name='product_schema_migrations'").fetchone()
                installed=installed and connection.execute('SELECT 1 FROM product_schema_migrations WHERE version=6').fetchone()
                columns={r[1] for r in connection.execute('PRAGMA table_info(review_events)')}
                review_backfill=not installed and {'finding_id','new_status','actor_name','created_at','id'}<=columns
            sql=script.read_text()
            if review_backfill:
                backfill="INSERT OR IGNORE INTO product_changes(engagement_id,area,category,resource_id,action,actor_id,created_at,source_table,source_id) SELECT 'CL-20417','finding','review',finding_id,new_status,actor_name,created_at,'review_events',id FROM review_events;\n"
                sql=sql.replace('COMMIT;',backfill+'COMMIT;')
            connection.executescript(sql)
    except Exception:
        connection.rollback()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DB_PATH)
    args = parser.parse_args()
    with sqlite3.connect(args.database) as db:
        migrate(db)
    print('Applied available additive migrations to', args.database)
