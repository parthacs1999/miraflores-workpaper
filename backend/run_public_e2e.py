"""Private local TLS fixture, exercising the real public boundary without a public deployment."""
from datetime import datetime,timezone,timedelta
import os
from pathlib import Path
import tempfile
import uvicorn

if __name__=='__main__':
    root=Path(os.environ['PROXY_E2E_DIR']).resolve()
    if os.environ.get('WORKPAPER_ENV')!='test' or not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):raise RuntimeError('Isolated public fixture required')
    os.umask(0o077)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False).sign(key,hashes.SHA256())
    (root/'tls-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));(root/'tls-cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    from app.public_demo import configuration,SandboxStore,create_public_app
    settings=configuration({'WORKPAPER_PROFILE':'public-demo','WORKPAPER_ORIGINS':'https://localhost:3300'})
    uvicorn.run(create_public_app(settings,SandboxStore()),host='127.0.0.1',port=8300,access_log=False)
