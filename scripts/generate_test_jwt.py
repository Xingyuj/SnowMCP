"""Generate a short-lived HS256 JWT for local MCP scope tests."""

import argparse
import base64
import hashlib
import hmac
import json
import time


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def generate_token(
    secret: str, issuer: str, audience: str, subject: str, scopes: list[str], lifetime: int
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "iat": now,
        "exp": now + lifetime,
        "scope": " ".join(scopes),
    }
    parts = [
        _encode(json.dumps(item, separators=(",", ":")).encode()) for item in (header, payload)
    ]
    signing_input = ".".join(parts).encode("ascii")
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    return f"{parts[0]}.{parts[1]}.{_encode(signature)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--issuer", default="https://local.test")
    parser.add_argument("--audience", default="servicenow-knowledge-mcp")
    parser.add_argument("--subject", default="local-test-user")
    parser.add_argument("--lifetime", type=int, default=900)
    parser.add_argument("scopes", nargs="*")
    args = parser.parse_args()
    print(
        generate_token(
            args.secret,
            args.issuer,
            args.audience,
            args.subject,
            args.scopes,
            args.lifetime,
        )
    )


if __name__ == "__main__":
    main()
