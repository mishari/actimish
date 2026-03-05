"""
RSA keypair management and HTTP signature utilities.
"""

import os
import base64
import hashlib
import datetime

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

import config


def _private_key_path():
    return os.path.join(config.KEYS_DIR, "private.pem")


def _public_key_path():
    return os.path.join(config.KEYS_DIR, "public.pem")


def ensure_keypair():
    """Generate an RSA keypair if one doesn't exist."""
    priv_path = _private_key_path()
    pub_path = _public_key_path()
    if os.path.exists(priv_path) and os.path.exists(pub_path):
        return
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    os.makedirs(config.KEYS_DIR, exist_ok=True)
    with open(priv_path, "wb") as f:
        f.write(priv_pem)
    with open(pub_path, "wb") as f:
        f.write(pub_pem)


def get_private_key():
    with open(_private_key_path(), "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def get_public_key_pem():
    with open(_public_key_path(), "rb") as f:
        return f.read().decode("utf-8")


def sign_headers(method, url, body=None, content_type=None):
    """
    Create HTTP Signature headers for an outgoing ActivityPub request.
    Returns a dict of headers to include.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.port and parsed.port not in (80, 443):
        host = f"{host}:{parsed.port}"
    path = parsed.path
    if parsed.query:
        path = f"{path}?{parsed.query}"

    now = datetime.datetime.now(datetime.timezone.utc)
    date_str = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

    headers = {"Host": host, "Date": date_str}
    signed_headers = "(request-target) host date"

    sign_string = f"(request-target): {method.lower()} {path}\nhost: {host}\ndate: {date_str}"

    if body is not None:
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode("utf-8")
        headers["Digest"] = f"SHA-256={digest}"
        signed_headers += " digest"
        sign_string += f"\ndigest: SHA-256={digest}"
        if content_type:
            headers["Content-Type"] = content_type
            signed_headers += " content-type"
            sign_string += f"\ncontent-type: {content_type}"

    key = get_private_key()
    signature = key.sign(
        sign_string.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    sig_b64 = base64.b64encode(signature).decode("utf-8")

    key_id = f"https://{config.DOMAIN}/users/{config.USERNAME}#main-key"
    sig_header = (
        f'keyId="{key_id}",'
        f'algorithm="rsa-sha256",'
        f'headers="{signed_headers}",'
        f'signature="{sig_b64}"'
    )
    headers["Signature"] = sig_header

    return headers


def verify_http_signature(request_method, request_path, request_headers, body=None):
    """
    Verify an incoming HTTP Signature.
    Returns the key_id on success, raises ValueError on failure.
    """
    import re
    import requests as http_requests

    sig_header = request_headers.get("Signature", "")
    if not sig_header:
        raise ValueError("No Signature header")

    # Parse signature header
    params = {}
    for match in re.finditer(r'(\w+)="([^"]*)"', sig_header):
        params[match.group(1)] = match.group(2)

    key_id = params.get("keyId", "")
    headers_list = params.get("headers", "").split()
    signature = base64.b64decode(params.get("signature", ""))

    if not key_id or not headers_list or not signature:
        raise ValueError("Incomplete signature")

    # Fetch the remote actor to get their public key
    actor_url = key_id.split("#")[0]
    resp = http_requests.get(
        actor_url,
        headers={"Accept": "application/activity+json"},
        timeout=10,
    )
    resp.raise_for_status()
    actor = resp.json()

    pub_key_pem = actor.get("publicKey", {}).get("publicKeyPem", "")
    if not pub_key_pem:
        raise ValueError("No public key found for actor")

    public_key = serialization.load_pem_public_key(pub_key_pem.encode("utf-8"))

    # Reconstruct the signed string
    parts = []
    for h in headers_list:
        if h == "(request-target)":
            parts.append(f"(request-target): {request_method.lower()} {request_path}")
        else:
            value = request_headers.get(h.title(), request_headers.get(h, ""))
            parts.append(f"{h}: {value}")
    sign_string = "\n".join(parts)

    # Verify
    public_key.verify(
        signature,
        sign_string.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    return key_id
