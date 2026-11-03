import os
import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
import app as module

@pytest.fixture
def client(monkeypatch):
    for key,value in {'TRACKER_PASSWORD':'test-password','SESSION_SECRET':'test-secret',
        'FINDMY_SECRETS_B64':'test','TRACKER_DEVICE_ID':'test-id','TRACKER_NAME':'Test tracker'}.items():
        monkeypatch.setenv(key,value)
    module.last_result=None
    return TestClient(module.app)

def test_anonymous_cannot_read_location(client):
    assert client.post('/api/refresh').status_code==401
    assert client.get('/').status_code==200
    assert 'no-store' in client.get('/').headers['cache-control']

def test_cookie_tampering_and_logout(client):
    assert client.post('/api/login',json={'password':'wrong'}).status_code==401
    assert client.post('/api/login',json={'password':'test-password'}).status_code==200
    cookie=client.cookies.get('tracker_session')
    assert module.valid_cookie(cookie)
    assert not module.valid_cookie(cookie+'0')
    assert client.post('/api/logout').status_code==200
    assert client.post('/api/refresh').status_code==401

def test_foreign_origin_rejected(client):
    assert client.post('/api/login',json={'password':'test-password'},headers={'Origin':'https://other.example'}).status_code==403

def test_copied_environment_quotes_do_not_break_login(client,monkeypatch):
    monkeypatch.setenv('TRACKER_PASSWORD', ' "test-password"\n')
    monkeypatch.setenv('SESSION_SECRET', " 'test-secret' ")
    response=client.post('/api/login',json={'password':'test-password'})
    assert response.status_code==200
    assert client.get('/api/session').json()['authenticated'] is True

def test_refresh_and_cooldown(client):
    client.post('/api/login',json={'password':'test-password'})
    value={'name':'Test tracker','location':{'latitude':1,'longitude':2,'timestamp':1700000000,'accuracy':10}}
    with patch.object(module.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(value),returncode=0)) as run:
        assert client.post('/api/refresh').json()==value
        assert client.post('/api/refresh').json()==value
        assert run.call_count==1

def test_backend_failure_does_not_expose_tokens(client):
    client.post('/api/login',json={'password':'test-password'})
    with patch.object(module.subprocess,'run',return_value=SimpleNamespace(stdout='',stderr='secret-token',returncode=1)):
        response=client.post('/api/refresh')
        assert response.status_code==504
        assert 'secret-token' not in response.text
