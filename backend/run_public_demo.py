"""PUBLIC NON-PRODUCTION FICTIONAL DATA ONLY. Separate from all secure launchers."""
import argparse
import os
import sqlite3
import uvicorn
from app.public_demo import configuration,SandboxStore,create_public_app


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    try:
        settings=configuration();port=int(os.getenv('PORT','8000'))
        if not 1<=port<=65535:raise ValueError()
        store=SandboxStore();app=create_public_app(settings,store)
    except (ValueError,RuntimeError,OSError,sqlite3.Error,TypeError):parser.error('Public demo preflight failed; check the profile, original packet and exact HTTPS frontend Origin')
    print('PUBLIC DEMO ONLY: fictional packet; simulated roles; isolated expiring visitor state; FILING BLOCKED.',flush=True)
    uvicorn.run(app,host='0.0.0.0',port=port,workers=1,reload=False,access_log=False,timeout_graceful_shutdown=30)

if __name__=='__main__':main()
