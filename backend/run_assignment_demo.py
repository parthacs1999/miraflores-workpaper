"""NON-PRODUCTION, disposable assignment server. Never use for real client data."""
import argparse
import os
import sqlite3
import uvicorn
from app.assignment_demo import configure,initialize_disposable_database,create_assignment_app


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-tunnel',action='store_true',help='Loopback bind for a scheduled HTTPS tunnel; same auth and expiry checks')
    args=parser.parse_args()
    try:
        profile=configure()
        port=int(os.getenv('PORT','8000'))
        if not 1<=port<=65535:raise ValueError()
        initialize_disposable_database(profile)
        app=create_assignment_app(profile)
    except (ValueError,RuntimeError,OSError,TypeError,KeyError,sqlite3.Error):
        parser.error('Assignment preflight failed. Review approval hashes, expiry, token digests and HTTPS origin. No server started.')
    print('NON-PRODUCTION ASSIGNMENT: temporary access; all review changes may disappear on restart. No real filing.',flush=True)
    uvicorn.run(app,host='127.0.0.1' if args.local_tunnel else '0.0.0.0',port=port,workers=1,reload=False,access_log=False,timeout_graceful_shutdown=30)

if __name__=='__main__':main()
