"""Verified identity-gateway adapter. Never trusts email/staff headers alone."""
import hashlib
import json
import threading
import time
from functools import lru_cache
import httpx
import jwt


class IdentityRejected(Exception):
    pass


class IdentityUnavailable(Exception):
    pass


class AccessVerifier:
    def __init__(self, issuer, audience):
        self.issuer, self.audience = issuer, audience
        self.keys = {}
        self.valid_until = 0
        self.retry_after = 0
        self.lock = threading.Lock()

    def load_keys(self):
        # Fixed, configuration-validated destination. No JWT jku/x5u URL is followed.
        with httpx.Client(timeout=4, follow_redirects=False) as client:
            response = client.get(self.issuer + '/cdn-cgi/access/certs')
            response.raise_for_status()
            if len(response.content) > 100_000:
                raise ValueError('Oversized key set')
            return response.json()['keys']

    def verify(self, token):
        if not token or len(token) > 16_384:
            raise IdentityRejected()
        try:
            header = jwt.get_unverified_header(token)
            if header.get('alg') != 'RS256' or not isinstance(header.get('kid'), str):
                raise IdentityRejected()
            with self.lock:
                now = time.monotonic()
                if now >= self.valid_until:
                    if now < self.retry_after:
                        raise IdentityUnavailable()
                    try:
                        self.retry_after = now + 10
                        keys = self.load_keys()
                        self.keys = {key['kid']: jwt.PyJWK.from_dict(key, algorithm='RS256').key for key in keys if key.get('kty') == 'RSA' and key.get('use', 'sig') == 'sig'}
                        if not self.keys:
                            raise ValueError('Empty key set')
                        self.valid_until = now + 300
                    except Exception:
                        raise IdentityUnavailable() from None
                key = self.keys.get(header['kid'])
            # Unknown kids do not trigger an unbounded outbound refresh per request.
            if key is None:
                raise IdentityRejected()
            claims = jwt.decode(token, key, algorithms=['RS256'], issuer=self.issuer, audience=self.audience,
                                options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']}, leeway=0)
            if any(type(claims[field]) is not int for field in ('iat','exp')):raise IdentityRejected()
            if not isinstance(claims['sub'], str) or not claims['sub'] or claims.get('type') != 'app':
                raise IdentityRejected()
            if claims['exp'] - claims['iat'] > 3600 or claims['exp'] <= claims['iat']:
                raise IdentityRejected()
            return claims
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise IdentityRejected() from None


@lru_cache(maxsize=4)
def verifier(issuer, audience):
    return AccessVerifier(issuer, audience)


def identity_for(request, settings):
    values = request.headers.getlist('cf-access-jwt-assertion')
    if len(values) != 1:
        raise IdentityRejected()
    claims = verifier(settings.access_issuer, settings.access_audience).verify(values[0])
    staff_id = settings.access_staff.get(claims['sub'])
    if not staff_id:
        raise IdentityRejected()
    return {'staff_id': staff_id, 'subject_hash': hashlib.sha256((settings.access_issuer + '\0' + claims['sub']).encode()).hexdigest(), 'expires_at': claims['exp']}


def configuration_epoch(settings):
    if settings.mode != 'access':
        value = settings.credentials
    else:
        value = {'mode': 'access', 'issuer': settings.access_issuer, 'audience': settings.access_audience, 'staff': settings.access_staff, 'origins': settings.origins}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def session_matches(row, identity):
    if row is None or row['staff_id'] != identity['staff_id']:
        return False
    from app.security import session_db
    with session_db() as db:
        binding = db.execute('SELECT subject_hash FROM hosted_session_bindings WHERE token_hash=?', (row['token_hash'],)).fetchone()
    return binding is not None and binding['subject_hash'] == identity['subject_hash']
