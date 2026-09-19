from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

directory = Path(__file__).resolve().parents[1] / ".keys"
private_path = directory / "access-private.pem"
public_path = directory / "access-public.pem"
if private_path.exists() or public_path.exists():
    raise SystemExit("Key files already exist; refusing to overwrite them.")
directory.mkdir(exist_ok=True)
key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
private_path.write_bytes(
    key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
)
public_path.write_bytes(
    key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
)
print("Generated local signing keys. Only the public key may be shared with resource APIs.")
