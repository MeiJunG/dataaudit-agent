"""Serve only generated analysis records, with explicit attachment headers."""
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse


def record_download_app(directory):
    root = Path(directory).resolve()
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @application.get('/analysis-records/{filename}')
    def download_record(filename: str):
        if not re.fullmatch(r'analysis-[0-9a-f]{64}\.json', filename):
            raise HTTPException(404)
        path = root / filename
        if not path.is_file() or path.is_symlink():
            raise HTTPException(404)
        return FileResponse(path, filename=filename, media_type='application/json',
                            headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})

    return application
