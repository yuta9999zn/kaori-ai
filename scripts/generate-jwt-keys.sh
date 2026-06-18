#!/usr/bin/env bash
# Generate an RSA-2048 key pair for JWT (RS256) signing and write the
# base64-encoded PEMs into .env, replacing the JWT_PRIVATE_KEY and
# JWT_PUBLIC_KEY lines.
#
# Why this script exists:
#   .env.example ships with `<BASE64_ENCODED_PRIVATE_KEY>` placeholders.
#   New developers copy .env.example → .env and forget to substitute.
#   auth-service then crashes at startup with the cryptic
#   `Illegal base64 character 3c` (the `<` char) because it tries to
#   decode the literal placeholder.
#
# Usage:
#   ./scripts/generate-jwt-keys.sh               # writes to ./.env
#   ./scripts/generate-jwt-keys.sh path/to/.env  # custom file
#
# Idempotent: skips generation if the existing values look like real
# base64-encoded PEMs (i.e. don't start with `<` and aren't empty).
# Pass `--force` to regenerate anyway.

set -euo pipefail

# Parse args: --force is a flag, anything else is the env file path.
FORCE=0
ENV_FILE=".env"
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        *)       ENV_FILE="$arg" ;;
    esac
done

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[generate-jwt-keys] $ENV_FILE not found; copy .env.example to .env first" >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "[generate-jwt-keys] openssl not found in PATH" >&2
    exit 1
fi

current_priv=$(grep -E '^JWT_PRIVATE_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
if [[ "$FORCE" == 0 && -n "$current_priv" && "${current_priv:0:1}" != "<" ]]; then
    echo "[generate-jwt-keys] $ENV_FILE already has JWT keys; pass --force to overwrite"
    exit 0
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

openssl genrsa -out "$tmp/private.pem" 2048 2>/dev/null
openssl rsa    -in  "$tmp/private.pem" -pubout -out "$tmp/public.pem" 2>/dev/null

# Convert PEM → DER. Java's PKCS8EncodedKeySpec / X509EncodedKeySpec
# want raw DER bytes; base64-of-PEM-text fails with `extra data at the
# end` because the DER parser trips on the BEGIN/END markers.
#
# Private side must be PKCS#8 (Java's PKCS8EncodedKeySpec parses the
# algorithm identifier from the PKCS#8 wrapper). On OpenSSL 3.x,
# `openssl pkey -outform DER` strips the wrapper and outputs raw
# PKCS#1 RSAPrivateKey — Java rejects that with `algid parse error,
# not a sequence`. Use `openssl pkcs8 -topk8` to force PKCS#8.
openssl pkcs8 -topk8 -nocrypt -in "$tmp/private.pem" -outform DER -out "$tmp/private.der" 2>/dev/null
openssl pkey  -pubin -in "$tmp/public.pem" -outform DER -out "$tmp/public.der" 2>/dev/null

# base64, no line wrapping (Java strips whitespace anyway, but keep tidy).
b64_priv=$(base64 -w0 < "$tmp/private.der" 2>/dev/null || base64 < "$tmp/private.der" | tr -d '\n')
b64_pub=$(base64 -w0  < "$tmp/public.der"  2>/dev/null || base64 < "$tmp/public.der"  | tr -d '\n')

# Replace the two lines in-place. Use a delimiter that won't collide with base64.
python3 - "$ENV_FILE" "$b64_priv" "$b64_pub" <<'PY'
import sys, pathlib
env_path, priv, pub = sys.argv[1], sys.argv[2], sys.argv[3]
text = pathlib.Path(env_path).read_text()
out_lines = []
seen_priv = seen_pub = False
for line in text.splitlines(keepends=True):
    if line.startswith("JWT_PRIVATE_KEY="):
        out_lines.append(f"JWT_PRIVATE_KEY={priv}\n"); seen_priv = True
    elif line.startswith("JWT_PUBLIC_KEY="):
        out_lines.append(f"JWT_PUBLIC_KEY={pub}\n"); seen_pub = True
    else:
        out_lines.append(line)
if not seen_priv: out_lines.append(f"JWT_PRIVATE_KEY={priv}\n")
if not seen_pub:  out_lines.append(f"JWT_PUBLIC_KEY={pub}\n")
pathlib.Path(env_path).write_text("".join(out_lines))
PY

echo "[generate-jwt-keys] wrote new RS256 keypair to $ENV_FILE"
