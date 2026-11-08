"""Isolated, synthetic local capacity probe. Not a Render performance certification."""
import base64
from datetime import datetime,timezone,timedelta
import hashlib
import json
import os
from pathlib import Path
import resource
import secrets
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__=='__main__':
    from app.assignment_demo import BASE,configure,initialize_disposable_database,create_assignment_app
    from fastapi.testclient import TestClient
    token=secrets.token_urlsafe(32)
    os.environ.update(WORKPAPER_ENV='production',WORKPAPER_MODE='locked')
    env={'WORKPAPER_PROFILE':'assignment-demo','WORKPAPER_ENV':'production','WORKPAPER_ORIGINS':'https://capacity.vercel.app','WORKPAPER_ASSIGNMENT_EXPIRES_AT':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'WORKPAPER_ASSIGNMENT_REVIEWERS':json.dumps({'st-01':hashlib.sha256(token.encode()).hexdigest()}),'WORKPAPER_ASSIGNMENT_PACKET_SHA256':hashlib.sha256((BASE/'data/Instructions.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_SEED_SHA256':hashlib.sha256((BASE/'assignment_demo/seed.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_DATA_APPROVAL':'reviewed-sanitized-assignment-only'}
    started=time.monotonic();profile=configure(env);initialize_disposable_database(profile)
    client=TestClient(create_assignment_app(profile),base_url='https://capacity.vercel.app')
    bootstrap=client.get('/api/workflow/session').json();headers={'Origin':env['WORKPAPER_ORIGINS'],'X-CSRF-Token':bootstrap['csrf_token']}
    session=client.post('/api/workflow/session',headers=headers,json={'staff_id':'st-01','credential':token});session.raise_for_status()
    startup=time.monotonic()-started;headers['X-CSRF-Token']=session.json()['csrf_token']
    codes={}
    for path in ('/api/overview','/api/documents','/api/reconciliations','/api/workflow/readiness','/api/version-comparison','/api/product/changes?wait_seconds=0'):
        response=client.get(path);response.raise_for_status();codes[path]=response.status_code
    payload={'area':'business','title':'Isolated capacity fixture','note':'Synthetic text, not extracted evidence','filename':'capacity.txt','media_type':'text/plain','content_base64':base64.b64encode(b'a'*(5*1024*1024)).decode(),'links':[{'kind':'document','id':'D14'}]}
    upload=client.post('/api/product/attachments',headers=headers,json=payload);upload.raise_for_status()
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024*1024 if sys.platform=='darwin' else 1024)
    print(json.dumps({'startup_and_login_seconds':round(startup,3),'representative_routes':codes,'maximum_upload_status':upload.status_code,'peak_process_rss_mib':round(peak,1),'scope':'single-process local TestClient; no cloud CPU quota, concurrency or edge validation'},indent=2))
