"""Actual RSA signature verification; no live gateway or public test impersonation."""
import hashlib
import json
import time
from datetime import datetime,timezone,timedelta
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from app.main import create_app
from app.security import Settings,sha
from app.access_identity import verifier,AccessVerifier,IdentityRejected,IdentityUnavailable

ORIGIN='https://workpaper.example.test'
ISSUER='https://fixture-team.cloudflareaccess.com'
AUDIENCE='isolated-fixture-audience'

@pytest.fixture
def gate(tmp_path,monkeypatch):
    monkeypatch.setenv('REVIEW_DB_PATH',str(tmp_path/'identity.db'))
    private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()));jwk.update(kid='fixture-key',use='sig')
    verifier.cache_clear()
    monkeypatch.setattr(AccessVerifier,'load_keys',lambda self:[jwk])
    settings=Settings('access','production',(ORIGIN,),{},ISSUER,AUDIENCE,{'preparer-sub':'st-01','reviewer-sub':'st-02','partner-sub':'st-03','admin-sub':'st-05'})
    def token(subject='preparer-sub',**changes):
        now=int(time.time());claims={'iss':ISSUER,'aud':[AUDIENCE],'iat':now,'exp':now+900,'sub':subject,'type':'app'};claims.update(changes)
        return jwt.encode(claims,private,algorithm='RS256',headers={'kid':'fixture-key'})
    client=TestClient(create_app(settings),base_url=ORIGIN)
    return client,settings,token,private


def login(client,token):
    client.headers['Cf-Access-Jwt-Assertion']=token
    response=client.get('/api/workflow/session');assert response.status_code==200,response.text
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':response.json()['csrf_token']})
    return response


def test_anonymous_direct_backend_and_spoofed_staff_headers_fail_closed(gate):
    client,*_=gate
    for path in ['/api/overview','/api/workflow/session','/api/workflow/session/staff','/docs','/openapi.json']:
        response=client.get(path,headers={'Cf-Access-Authenticated-User-Email':'fake@example.test','X-Staff-ID':'st-03'})
        assert response.status_code==401 and 'fake@example.test' not in response.text
        assert 'no-store' in response.headers['cache-control']
    assert client.get('/health').status_code==200


@pytest.mark.parametrize('changes',[{'exp':1},{'iss':'https://evil.example'},{'aud':['other-app']},{'iat':int(time.time())+1000},{'type':'service'},{'sub':'unlisted-sub'},{'exp':int(time.time())+7200}])
def test_wrong_expired_future_service_or_unmapped_identity_is_rejected(gate,changes):
    client,settings,token,_=gate
    response=client.get('/api/workflow/session',headers={'Cf-Access-Jwt-Assertion':token(**changes)})
    assert response.status_code==401


def test_forged_signature_and_unsigned_algorithm_are_rejected(gate):
    client,settings,token,_=gate
    claims=jwt.decode(token(),options={'verify_signature':False})
    wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    for encoded in [jwt.encode(claims,wrong,algorithm='RS256',headers={'kid':'fixture-key'}),jwt.encode(claims,'',algorithm='none'),jwt.encode(claims,'shared-secret-for-test-only-32-bytes',algorithm='HS256',headers={'kid':'fixture-key'})]:
        assert client.get('/api/workflow/session',headers={'Cf-Access-Jwt-Assertion':encoded}).status_code==401


def test_gateway_outage_fails_closed_without_exception_leak(gate,monkeypatch):
    client,settings,token,_=gate
    def unavailable(self):raise RuntimeError('private provider transport diagnostics')
    monkeypatch.setattr(AccessVerifier,'load_keys',unavailable)
    response=client.get('/api/workflow/session',headers={'Cf-Access-Jwt-Assertion':token()})
    assert response.status_code==503 and 'private provider' not in response.text


def test_secure_cookie_expiry_bound_identity_and_no_public_impersonation(gate):
    client,settings,token,_=gate
    response=login(client,token())
    assert response.json()['staff']['id']=='st-01'
    assert response.json()['staff']['assurance']=='verified_access_profile'
    assert not response.json()['legal_signature']
    cookie=response.headers['set-cookie']
    assert all(s in cookie for s in ['Secure','HttpOnly','SameSite=strict','Path=/'])
    import re
    assert 0<int(re.search(r'Max-Age=(\d+)',cookie).group(1))<=900
    assert 'Domain=' not in cookie
    roster=client.get('/api/workflow/session/staff').json()['staff']
    assert [s['id'] for s in roster]==['st-01']
    assert client.get('/api/overview').status_code==200
    for body in [{'staff_id':'st-03'},{'staff_id':'st-02','credential':'guessed shared password'}]:
        assert client.post('/api/workflow/session',json=body).status_code==403
    assert client.post('/api/workflow/session',json={'staff_id':'st-01'}).status_code==200


def test_different_verified_user_cannot_use_a_copied_session(gate):
    client,settings,token,_=gate
    login(client,token())
    assert client.get('/api/overview',headers={'Cf-Access-Jwt-Assertion':token('reviewer-sub')}).status_code==401
    assert client.get('/api/overview').status_code==200


def test_csrf_role_clearance_audit_and_real_filing_blockers_survive_gateway(gate):
    client,settings,token,_=gate
    response=login(client,token())
    assert client.post('/api/workflow/notes',json={},headers={'X-CSRF-Token':''}).status_code==403
    assert client.post('/api/workflow/notes',json={},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/workflow/policies',json={'expected_revision':1,'changes':{'partner_threshold':'1000'},'rationale':'Unauthorized policy attempt'}).status_code==403
    assert '666-41-2287' not in client.get('/api/documents/D71').text
    readiness=client.get('/api/workflow/readiness').json();assert readiness['filing_ready'] is False
    assert client.get('/api/product/attachments/missing/download').status_code in {403,404}
    login(client,token('partner-sub'))
    audit=client.get('/api/workflow/access-history').json()['events']
    assert any(e['action']=='identity_login' for e in audit)
    assert token() not in json.dumps(audit)


def test_expired_app_session_and_revoked_subject_configuration_are_rejected(gate):
    client,settings,token,_=gate
    login(client,token())
    from app.security import session_db
    with session_db() as db:db.execute("UPDATE workflow_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert client.get('/api/overview').status_code==401
    login(client,token())
    settings.access_staff['preparer-sub']='st-02'
    assert client.get('/api/overview').status_code==401


def test_identity_binding_audit_is_immutable(gate):
    client,settings,token,_=gate;login(client,token())
    from app.security import session_db
    import sqlite3
    with session_db() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM hosted_session_bindings')
        with pytest.raises(sqlite3.IntegrityError):db.execute("UPDATE hosted_session_bindings SET subject_hash='forged'")


@pytest.mark.parametrize('field,value',[('access_issuer','http://fixture-team.cloudflareaccess.com'),('access_issuer','https://evil.example'),('access_staff',{}),('access_staff',{'subject':'st-unknown'}),('access_audience',''),('credentials',{'st-01':'x'*32}),('origins',('https://*.example.test',)),('origins',(ORIGIN+'/nested',))])
def test_hosted_security_configuration_is_explicit(gate,field,value):
    _,settings,*_=gate;setattr(settings,field,value)
    with pytest.raises(RuntimeError):settings.validate()


def test_unknown_keys_do_not_force_a_refresh_for_every_request(gate,monkeypatch):
    _,settings,token,private=gate
    instance=verifier(ISSUER,AUDIENCE);instance.verify(token())
    calls=[];monkeypatch.setattr(instance,'load_keys',lambda:calls.append(1))
    claims=jwt.decode(token(),options={'verify_signature':False})
    for i in range(5):
        with pytest.raises(IdentityRejected):instance.verify(jwt.encode(claims,private,algorithm='RS256',headers={'kid':str(i)}))
    assert calls==[]

def test_security_headers_also_cover_failures_health_and_bootstrap(gate):
    client,settings,token,_=gate
    responses=[client.get('/health'),client.get('/api/overview'),login(client,token()),client.get('/api/documents/missing')]
    for response in responses:
        assert response.headers['x-content-type-options']=='nosniff'
        assert response.headers['referrer-policy']=='no-referrer'
        assert response.headers['x-frame-options']=='DENY'
        assert 'no-store' in response.headers['cache-control']
        assert 'Cf-Access-Jwt-Assertion' in response.headers['vary']
        assert response.headers['strict-transport-security']=='max-age=31536000'


def test_large_session_request_and_secret_validation_errors_are_sanitized(gate):
    client,settings,token,_=gate;login(client,token())
    secret='never-echo-this-private-credential'
    response=client.post('/api/workflow/session',json={'credential':secret*1000})
    assert response.status_code==413 and secret not in response.text
    response=client.post('/api/workflow/session',json={'staff_id':['private-example-value']})
    assert response.status_code==422 and 'private-example-value' not in response.text
