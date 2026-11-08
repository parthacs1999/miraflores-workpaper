"""The ordinary uvicorn launch is intentionally locked; demo is an explicit local opt-in."""
import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security import Settings

spec = importlib.util.spec_from_file_location('secure_launcher', Path(__file__).parents[1] / 'run_secure.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
ORIGIN = 'http://localhost:3000'


@pytest.fixture
def local_environment(tmp_path, monkeypatch):
    for key in ('WORKPAPER_ENV', 'WORKPAPER_MODE', 'WORKPAPER_ORIGINS', 'WORKPAPER_CREDENTIALS'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('REVIEW_DB_PATH', str(tmp_path / 'local-demo.db'))


def test_default_uvicorn_configuration_explains_actual_locked_failure(local_environment):
    settings = launcher.launch_settings()
    assert settings.mode == 'locked' and settings.environment == 'production'
    client = TestClient(create_app(settings))
    response = client.get('/api/workflow/session', headers={'origin': ORIGIN})
    assert response.status_code == 200 and response.json()['mode'] == 'locked'
    assert 'csrf_token' not in response.json()
    assert client.get('/api/workflow/session/staff').status_code == 403
    assert client.get('/api/overview').status_code == 401
    assert response.headers['access-control-allow-origin'] == ORIGIN


@pytest.mark.parametrize('staff_id', ['st-01', 'st-02', 'st-03'])
def test_explicit_local_demo_bootstraps_staff_cookie_origin_and_csrf(local_environment, staff_id):
    settings = launcher.launch_settings(demo=True)
    assert settings.environment == 'development' and settings.mode == 'demo'
    client = TestClient(create_app(settings))
    response = client.get('/api/workflow/session', headers={'origin': ORIGIN})
    session = response.json()
    assert session['mode'] == 'demo' and session['staff'] is None and session['csrf_token']
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['access-control-allow-origin'] == ORIGIN
    assert response.headers['access-control-allow-credentials'] == 'true'
    options = client.get('/api/workflow/session/staff', headers={'origin': ORIGIN})
    assert {'st-01', 'st-02', 'st-03'} <= {s['id'] for s in options.json()['staff']}
    assert client.post('/api/workflow/session', json={'staff_id': staff_id}).status_code == 403
    headers = {'origin': ORIGIN, 'x-csrf-token': session['csrf_token']}
    assert client.post('/api/workflow/session', json={'staff_id': staff_id}, headers={**headers, 'origin': 'https://evil.example'}).status_code == 403
    preflight = client.options('/api/workflow/session', headers={'origin': ORIGIN, 'access-control-request-method': 'POST', 'access-control-request-headers': 'content-type,x-csrf-token'})
    assert preflight.status_code == 200 and preflight.headers['access-control-allow-credentials'] == 'true'
    selected = client.post('/api/workflow/session', json={'staff_id': staff_id}, headers=headers)
    assert selected.status_code == 200 and selected.json()['staff']['id'] == staff_id
    assert selected.json()['demonstration'] and not selected.json()['legal_signature']
    assert selected.json()['csrf_token'] != session['csrf_token']
    assert client.get('/api/overview').status_code == 200
    assert client.post('/api/workflow/session', json={'staff_id': 'st-01'}, headers=headers).status_code == 403
    renewed = client.get('/api/workflow/session')
    assert renewed.json()['staff']['id'] == staff_id
    assert renewed.json()['csrf_token'] != selected.json()['csrf_token']


@pytest.mark.parametrize(('key', 'value'), [('WORKPAPER_ENV', 'production'), ('WORKPAPER_ENV', 'test'), ('WORKPAPER_MODE', 'credential'), ('WORKPAPER_MODE', 'legacy_test'), ('WORKPAPER_MODE', 'locked')])
def test_demo_flag_cannot_override_explicit_security_configuration(local_environment, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError):
        launcher.launch_settings(demo=True)


def test_production_still_rejects_environment_demo(local_environment, monkeypatch):
    monkeypatch.setenv('WORKPAPER_ENV', 'production')
    monkeypatch.setenv('WORKPAPER_MODE', 'demo')
    with pytest.raises(RuntimeError):
        launcher.launch_settings()
    with pytest.raises(RuntimeError):
        create_app(Settings('demo', 'production'))
