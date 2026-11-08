"""Secure launcher. --demo explicitly opts into local development identity selection."""
import argparse
import os
import uvicorn
from app.security import Settings


def launch_settings(demo=False):
    if demo:
        if os.getenv('WORKPAPER_ENV') not in {None, 'development'}:
            raise RuntimeError('--demo is only allowed for local development; remove conflicting WORKPAPER_ENV')
        if os.getenv('WORKPAPER_MODE') not in {None, 'demo'}:
            raise RuntimeError('--demo cannot override an explicitly configured WORKPAPER_MODE')
        settings = Settings(mode='demo', environment='development',
                            origins=tuple(os.getenv('WORKPAPER_ORIGINS', 'http://localhost:3000').split(',')))
    else:
        settings = Settings.from_env()
    settings.validate()
    return settings


def main(argv=None):
    from contextlib import ExitStack
    parser = argparse.ArgumentParser(description=__doc__)
    flags=parser.add_mutually_exclusive_group()
    flags.add_argument('--hosted', action='store_true', help='Render: mounted SQLite and verified identity gateway; one worker')
    flags.add_argument('--demo', action='store_true', help='Local-only demonstration identity selection')
    args = parser.parse_args(argv)
    with ExitStack() as startup:
        try:
            settings = launch_settings(args.demo)
            port = int(os.getenv('PORT', '8000'))
            if not 1 <= port <= 65535:raise RuntimeError('PORT must be a valid TCP port')
            if args.hosted:
                if settings.environment != 'production' or settings.mode != 'access':
                    raise RuntimeError('Hosted startup requires production verified Access identity mode')
                if os.environ.get('WEB_CONCURRENCY', '1') != '1':
                    raise RuntimeError('Persistent SQLite requires exactly one worker')
                from app.hosting import hosted_storage
                startup.enter_context(hosted_storage())
        except (RuntimeError,ValueError,TypeError):
            parser.error('Invalid startup configuration or persistent storage preflight failed. Check documented settings; no server was started.')
        from app.main import create_app
        if settings.mode == 'locked':
            print('Session provider LOCKED. For an explicit local demo, use: python run_secure.py --demo', flush=True)
        elif settings.mode == 'demo':
            print('LOCAL DEMONSTRATION ONLY: selected identities are not authenticated; no legal signatures or real filing.', flush=True)
        uvicorn.run(create_app(settings), host='0.0.0.0' if args.hosted else '127.0.0.1', port=port,
                    workers=1, reload=False, timeout_graceful_shutdown=30, access_log=False)


if __name__ == '__main__':
    main()
