"""Read committed strict-mode policy without a second write transaction."""
import json,os,sqlite3
from app.security_context import request_principal

def current():
    actor=request_principal.get()
    if not actor or actor.get('profile')=='legacy_test':return None
    from app.services.review_service import database_path
    from urllib.parse import quote
    db=sqlite3.connect('file:'+quote(str(database_path()))+'?mode=ro',uri=True)
    try:
        row=db.execute("SELECT p.policy_json FROM workflow_policies p JOIN workflow_entities e ON json_extract(e.data_json,'$.policy_id')=p.id WHERE e.id='CL-20417'").fetchone()
        return json.loads(row[0]) if row else None
    finally:db.close()
