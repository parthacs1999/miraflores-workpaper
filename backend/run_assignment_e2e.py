"""Loopback-only disposable assignment proxy fixture; never deployed."""
from datetime import datetime,timezone,timedelta
import hashlib,json,os
from pathlib import Path
import secrets,tempfile
import uvicorn

if __name__=='__main__':
    root=Path(os.environ['PROXY_E2E_DIR']).resolve()
    if os.environ.get('WORKPAPER_ENV')!='test' or not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):raise RuntimeError('Isolated assignment fixture required')
    os.umask(0o077)
    # Reuse only the local TLS fixture generator. It does not start its server when imported.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(key,hashes.SHA256())
    (root/'tls-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(root/'tls-cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    from app.assignment_demo import BASE,configure,initialize_disposable_database,create_assignment_app
    tokens={s:secrets.token_urlsafe(32) for s in ('st-01','st-02','st-03','st-05')};(root/'tokens.json').write_text(json.dumps(tokens))
    settings={'WORKPAPER_PROFILE':'assignment-demo','WORKPAPER_ENV':'production','WORKPAPER_ORIGINS':'https://localhost:3300','WORKPAPER_ASSIGNMENT_EXPIRES_AT':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'WORKPAPER_ASSIGNMENT_REVIEWERS':json.dumps({s:hashlib.sha256(t.encode()).hexdigest() for s,t in tokens.items()}),'WORKPAPER_ASSIGNMENT_PACKET_SHA256':hashlib.sha256((BASE/'data/Instructions.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_SEED_SHA256':hashlib.sha256((BASE/'assignment_demo/seed.json').read_bytes()).hexdigest(),'WORKPAPER_ASSIGNMENT_DATA_APPROVAL':'reviewed-sanitized-assignment-only'}
    profile=configure(settings);initialize_disposable_database(profile)
    uvicorn.run(create_assignment_app(profile),host='127.0.0.1',port=8300,access_log=False)
