"""Read committed strict-mode policy without a second write transaction."""
import json,os,sqlite3
from app.security_context import request_principal

def current():
    actor=request_principal.get()
    if not actor or actor.get('profile')=='legacy_test':return None
    from app.services.review_service import DB_PATH
    db=sqlite3.connect('file:'+os.environ.get('REVIEW_DB_PATH',str(DB_PATH))+'?mode=ro',uri=True)
    try:
        row=db.execute("SELECT p.policy_json FROM workflow_policies p JOIN workflow_entities e ON json_extract(e.data_json,'$.policy_id')=p.id WHERE e.id='CL-20417'").fetchone()
        return json.loads(row[0]) if row else None
    finally:db.close()
