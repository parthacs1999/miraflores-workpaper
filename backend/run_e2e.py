"""Disposable Playwright API process. Never connects to the user's reviews.db."""
import os
import tempfile
from pathlib import Path

import uvicorn


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='miraflores-e2e-') as directory:
        os.environ['WORKPAPER_ENV'] = 'test'
        os.environ['WORKPAPER_MODE'] = 'legacy_test'
        os.environ['REVIEW_DB_PATH'] = str(Path(directory) / 'reviews.db')
        os.environ['EXTRA_CORS_ORIGINS'] = 'http://localhost:3100'
        uvicorn.run('app.main:app', host='127.0.0.1', port=8100, access_log=False)
