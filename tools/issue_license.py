#!/usr/bin/env python
"""Vendor tool — issue an AlphaLedger Pro license key after a Gumroad sale.

Usage:
    python tools/issue_license.py --email buyer@example.com --days 365 \
        --key ./.private/signing_key.pem --out license_<email>.json

The private key must NEVER be committed. Keep it offline (1Password, a USB key).
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alphaledger import licensing  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--days", type=int, default=365, help="0 = lifetime")
    p.add_argument("--key", required=True, help="path to the Ed25519 private key (PEM)")
    p.add_argument("--key-id", default=None)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    expires = ""
    if args.days:
        expires = (date.today() + timedelta(days=args.days)).isoformat()

    key_id = args.key_id or f"AL-{date.today():%Y%m}-{abs(hash(args.email)) % 10**6:06d}"
    payload = {"tier": "pro", "email": args.email, "expires": expires, "key_id": key_id}
    doc = licensing.sign_license(payload, args.key)

    out = Path(args.out or f"license_{args.email.split('@')[0]}.json")
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"issued {key_id} for {args.email} (expires {expires or 'lifetime'}) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
