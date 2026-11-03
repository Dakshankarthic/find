import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.mount('/assets', StaticFiles(directory=ROOT / 'public'), name='assets')
lock = threading.Lock()
last_result = None
last_checked = 0.0


def clean_env(key: str, default: str = '') -> str:
    val = os.environ.get(key, default)
    if isinstance(val, str):
        return val.strip('"\' \t\r\n')
    return val


def configured():
    return all(clean_env(k) for k in ('TRACKER_PASSWORD', 'SESSION_SECRET', 'FINDMY_SECRETS_B64', 'TRACKER_DEVICE_ID'))


def signature(value):
    return hmac.new(clean_env('SESSION_SECRET').encode(), value.encode(), hashlib.sha256).hexdigest()


def valid_cookie(value):
    if not configured() or not value:
        return False
    try:
        issued, nonce, supplied = value.split('.')
        age = time.time() - int(issued)
        return 0 <= age < 86400 and hmac.compare_digest(signature(f'{issued}.{nonce}'), supplied)
    except (ValueError, TypeError):
        return False


def authorize(request):
    if not valid_cookie(request.cookies.get('tracker_session')):
        raise HTTPException(401, 'Please sign in.')


def same_origin(request):
    origin = request.headers.get('origin')
    if origin and origin != f'{request.url.scheme}://{request.headers.get("host")}':
        raise HTTPException(403, 'Request origin is not allowed.')


@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src https://maps.google.com; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    return response


@app.get('/')
def home():
    return FileResponse(ROOT / 'public' / 'index.html')


@app.get('/api/session')
def session(request: Request):
    return {'configured': configured(), 'authenticated': valid_cookie(request.cookies.get('tracker_session')),
            'name': clean_env('TRACKER_NAME', 'My tracker')}


@app.post('/api/login')
async def login(request: Request):
    same_origin(request)
    if not configured():
        raise HTTPException(503, 'Add the required Vercel environment variables, then redeploy.')
    if int(request.headers.get('content-length', '0')) > 2048:
        raise HTTPException(413, 'Request too large.')
    body = await request.json()
    supplied = body.get('password', '')
    if isinstance(supplied, str):
        supplied = supplied.strip('"\' \t\r\n')
    expected = clean_env('TRACKER_PASSWORD')
    if not isinstance(supplied, str) or not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, 'Incorrect website password.')
    value = f'{int(time.time())}.{secrets.token_hex(16)}'
    result = JSONResponse({'ok': True})
    result.set_cookie('tracker_session', f'{value}.{signature(value)}', httponly=True,
                      secure=request.url.scheme == 'https', samesite='strict', max_age=86400)
    return result


@app.post('/api/logout')
def logout(request: Request):
    same_origin(request)
    response = JSONResponse({'ok': True})
    response.delete_cookie('tracker_session')
    return response


@app.post('/api/refresh')
def refresh(request: Request):
    global last_result, last_checked
    same_origin(request)
    authorize(request)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, 'A location request is already running. Please wait.')
    try:
        if last_result is not None and time.monotonic() - last_checked < 30:
            return last_result
        try:
            child = subprocess.run([sys.executable, '-u', str(ROOT / 'location_worker.py')],
                                   cwd=ROOT, capture_output=True, text=True, timeout=54,
                                   encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
            data = json.loads(child.stdout)
        except (subprocess.TimeoutExpired, ValueError):
            raise HTTPException(504, 'Location request timed out. Please try again.')
        if child.returncode != 0 or 'error' in data:
            raise HTTPException(502, data.get('error', 'Location retrieval failed.'))
        last_result, last_checked = data, time.monotonic()
        return data
    finally:
        lock.release()
