"""Isolated signed-gateway fixture for the actual Next.js rewrite test. Never hosted."""
import json
import os
from pathlib import Path
import tempfile
import time
from datetime import datetime,timezone,timedelta
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import uvicorn

if __name__=='__main__':
    root=Path(os.environ['PROXY_E2E_DIR']).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()) or os.environ.get('WORKPAPER_ENV')!='test':raise RuntimeError('Private test fixture configuration required')
    os.umask(0o077)
    signing=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    jwk=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing.public_key()));jwk.update(kid='isolated-proxy-key',use='sig')
    issuer='https://isolated-proxy.cloudflareaccess.com';audience='isolated-proxy-audience'
    mapping={'proxy-preparer':'st-01','proxy-reviewer':'st-02','proxy-partner':'st-03','proxy-admin':'st-05'}
    now=int(time.time())
    tokens={staff:jwt.encode({'iss':issuer,'aud':[audience],'sub':subject,'iat':now,'exp':now+900,'type':'app'},signing,algorithm='RS256',headers={'kid':jwk['kid']}) for subject,staff in mapping.items()}
    (root/'tokens.json').write_text(json.dumps(tokens))
    tls=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(tls.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(tls,hashes.SHA256())
    (root/'tls-key.pem').write_bytes(tls.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    (root/'tls-cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    os.environ.update(WORKPAPER_MODE='access',WORKPAPER_ORIGINS='https://localhost:3300',WORKPAPER_ACCESS_ISSUER=issuer,WORKPAPER_ACCESS_AUDIENCE=audience,WORKPAPER_ACCESS_STAFF=json.dumps(mapping),REVIEW_DB_PATH=str(root/'proxy.db'))
    from app.access_identity import AccessVerifier
    AccessVerifier.load_keys=lambda self:[jwk]  # Only in this loopback-only disposable runner.
    from app.main import create_app
    from app.security import Settings
    uvicorn.run(create_app(Settings.from_env()),host='127.0.0.1',port=8300,access_log=False)
