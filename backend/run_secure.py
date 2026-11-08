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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Local-only demonstration sessions; never legal identity assurance')
    args = parser.parse_args()
    try:
        settings = launch_settings(args.demo)
    except RuntimeError as error:
        parser.error(str(error))
    from app.main import create_app
    if settings.mode == 'locked':
        print('Session provider LOCKED. For an explicit local demo, use: python run_secure.py --demo', flush=True)
    elif settings.mode == 'demo':
        print('LOCAL DEMONSTRATION ONLY: selected identities are not authenticated; no legal signatures or real filing.', flush=True)
    uvicorn.run(create_app(settings), host='127.0.0.1', port=int(os.getenv('PORT', '8000')), access_log=False)


if __name__ == '__main__':
    main()
