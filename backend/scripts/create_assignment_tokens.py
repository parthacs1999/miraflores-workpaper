"""Generate temporary per-profile bearer tokens into private files, never stdout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--staff',nargs='+',required=True)
    args=parser.parse_args()
    from app.services.packet_service import load_packet
    repository=Path(__file__).resolve().parents[2]
    known={s['id'] for s in load_packet()['firm']['staff']}
    if args.directory.resolve().is_relative_to(repository) or not args.directory.is_absolute() or args.directory.exists() or len(args.staff)!=len(set(args.staff)) or not set(args.staff).issubset(known):
        parser.error('Use a new absolute private directory and distinct existing packet staff IDs')
    os.umask(0o077);args.directory.mkdir(mode=0o700,parents=True)
    tokens={s:secrets.token_urlsafe(32) for s in args.staff}
    (args.directory/'tokens.json').write_text(json.dumps(tokens,indent=2))
    (args.directory/'reviewers.json').write_text(json.dumps({s:hashlib.sha256(t.encode()).hexdigest() for s,t in tokens.items()}))
    print('Private token and digest files created. Deliver one token per independent reviewer using a separate confidential channel. Never commit either file.')

if __name__=='__main__':main()
