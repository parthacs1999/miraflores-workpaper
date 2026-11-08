"""Strict demonstration Playwright server backed by a disposable database."""
import os,tempfile
from pathlib import Path
import uvicorn
if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='miraflores-workflow-e2e-') as directory:
        os.environ.update(WORKPAPER_ENV='test',WORKPAPER_MODE='demo',WORKPAPER_ORIGINS='http://localhost:3200',REVIEW_DB_PATH=str(Path(directory)/'workflow.db'))
        from app.main import create_app
        from app.security import Settings
        uvicorn.run(create_app(Settings.from_env()),host='127.0.0.1',port=8200,access_log=False)
