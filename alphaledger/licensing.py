"""Offline license handling for AlphaLedger Pro.

A license is a small JSON file: {"payload": {...}, "sig": "<base64 ed25519>"}.
The payload is signed with an Ed25519 private key that never leaves the vendor;
verification only needs the public key embedded below, so no network call and
no telemetry are involved.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

PUBLIC_KEY_B64 = (
    "LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUNvd0JRWURLMlZ3QXlFQW9md3lFcWZnZkJ3Z0NXMER6TmVO"
    "d25IeTNyRU5GTjAzR1FERGRFNERhWXM9Ci0tLS0tRU5EIFBVQkxJQyBLRVktLS0tLQo="
)
PRODUCT = "alphaledger"
LICENSE_ENV = "ALPHALEDGER_LICENSE"
DEFAULT_PATHS = (
    Path("~/alphaledger-license.json").expanduser(),
    Path("~/.alphaledger/license.json").expanduser(),
)

PRO_FEATURES = {
    "multi_asset_compare": "Compare unlimited strategies side by side",
    "walk_forward": "Walk-forward consistency audit",
    "monte_carlo": "Monte Carlo drawdown stress test",
    "advanced_metrics": "30+ pro metrics (PSR, Ulcer, CVaR, Kelly...)",
    "excel_export": "Excel / CSV metric export",
    "batch": "Batch processing of many files",
}


class LicenseError(RuntimeError):
    """Raised when a Pro-only feature is requested without a valid license."""


@dataclass
class License:
    tier: str = "free"
    email: str = ""
    expires: Optional[date] = None
    key_id: str = ""
    source: str = "none"

    @property
    def is_pro(self) -> bool:
        if self.tier != "pro":
            return False
        if self.expires and self.expires < date.today():
            return False
        return True

    def describe(self) -> str:
        if self.is_pro:
            exp = self.expires.isoformat() if self.expires else "lifetime"
            return f"Pro license · {self.email or 'licensed user'} · expires {exp}"
        if self.tier == "pro" and self.expires:
            return f"Pro license expired on {self.expires.isoformat()}"
        return "Free tier"


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _verify_signature(payload: dict, sig_b64: str) -> bool:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except Exception:
        return False

    pub = load_pem_public_key(base64.b64decode(PUBLIC_KEY_B64))
    assert isinstance(pub, Ed25519PublicKey)
    try:
        pub.verify(base64.b64decode(sig_b64), _canonical(payload))
        return True
    except InvalidSignature:
        return False


def parse_license(raw: str | bytes | dict) -> License:
    """Parse and verify a license document. Invalid input returns free tier."""
    try:
        doc = raw if isinstance(raw, dict) else json.loads(raw)
    except Exception:
        return License(source="invalid")

    payload = doc.get("payload")
    sig = doc.get("sig")
    if not isinstance(payload, dict) or not isinstance(sig, str):
        return License(source="invalid")
    if payload.get("product") != PRODUCT:
        return License(source="invalid")
    if not _verify_signature(payload, sig):
        return License(source="invalid")

    expires = None
    if payload.get("expires"):
        try:
            expires = datetime.strptime(str(payload["expires"]), "%Y-%m-%d").date()
        except ValueError:
            return License(source="invalid")

    return License(
        tier=str(payload.get("tier", "pro")),
        email=str(payload.get("email", "")),
        expires=expires,
        key_id=str(payload.get("key_id", "")),
        source="file",
    )


def find_license_file() -> Optional[Path]:
    env = os.environ.get(LICENSE_ENV)
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    for p in DEFAULT_PATHS:
        if p.exists():
            return p
    return None


def current_license() -> License:
    path = find_license_file()
    if not path:
        return License()
    try:
        lic = parse_license(path.read_text(encoding="utf-8"))
    except Exception:
        return License(source="invalid")
    lic.source = str(path)
    return lic


_CACHE: Optional[License] = None


def get_license(refresh: bool = False) -> License:
    global _CACHE
    if _CACHE is None or refresh:
        _CACHE = current_license()
    return _CACHE


def is_pro() -> bool:
    return get_license().is_pro


def require_pro(feature: str) -> None:
    if is_pro():
        return
    label = PRO_FEATURES.get(feature, feature)
    raise LicenseError(
        f"'{label}' is a Pro feature.\n"
        "Unlock it with an AlphaLedger Pro license: https://alphaledger.gumroad.com\n"
        f"Then save your key file to {DEFAULT_PATHS[0]} or set {LICENSE_ENV}=/path/to/key.json"
    )


def sign_license(payload: dict, private_key_path: str | Path) -> dict:
    """Vendor-side helper used when issuing keys (kept out of the wheel build)."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(Path(private_key_path).read_bytes(), password=None)
    payload = {"product": PRODUCT, **payload}
    sig = key.sign(_canonical(payload))
    return {"payload": payload, "sig": base64.b64encode(sig).decode()}
