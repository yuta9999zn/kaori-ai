#!/usr/bin/env bash
# Generate a 32-byte AES-256 key for MFA secret encryption (KAORI_MFA_KEY)
# and write the base64-encoded value into .env, replacing the existing
# KAORI_MFA_KEY line.
#
# Why this script exists:
#   .env.example ships with `<BASE64_32_BYTES>` placeholders. New developers
#   copy .env.example → .env and forget to substitute. In dev, auth-service
#   falls back to a deterministic dev key + WARN log; in production
#   (SPRING_PROFILES_ACTIVE=production), auth-service refuses to start.
#   See CLAUDE.md §15 "MFA Key Management".
#
# Usage:
#   ./scripts/generate-mfa-key.sh               # writes to ./.env
#   ./scripts/generate-mfa-key.sh path/to/.env  # custom file
#
# Idempotent: skips generation if the existing value looks like a real
# Base64-encoded 32-byte key (i.e. doesn't start with `<` and isn't empty).
# Pass `--force` to regenerate anyway.
#
# !! Rotation note !!
# Rotating KAORI_MFA_KEY invalidates every previously stored MFA secret
# (the old ciphertext can't be decrypted with the new key). Existing admins
# will need to re-enrol via /platform/security/mfa. See CLAUDE.md §15 for
# the safe rotation procedure (advance-warning email + window before flip).

set -euo pipefail

FORCE=0
ENV_FILE=".env"
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=1 ;;
        *)       ENV_FILE="$arg" ;;
    esac
done

if [[ ! -f "$ENV_FILE" ]]; then
    echo "[generate-mfa-key] $ENV_FILE not found; copy .env.example to .env first" >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "[generate-mfa-key] openssl not found in PATH" >&2
    exit 1
fi

current=$(grep -E '^KAORI_MFA_KEY=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
if [[ "$FORCE" == 0 && -n "$current" && "${current:0:1}" != "<" ]]; then
    echo "[generate-mfa-key] $ENV_FILE already has KAORI_MFA_KEY set; pass --force to rotate"
    exit 0
fi

# 32 bytes of cryptographically secure random → Base64 (~44 chars w/ padding)
new_key=$(openssl rand -base64 32 | tr -d '\n')

# In-place replace; portable sed for both GNU and BSD by writing to a tmp file.
tmp_file=$(mktemp)
if grep -q '^KAORI_MFA_KEY=' "$ENV_FILE"; then
    awk -v key="KAORI_MFA_KEY=$new_key" '
        /^KAORI_MFA_KEY=/ { print key; next }
        { print }
    ' "$ENV_FILE" > "$tmp_file"
else
    cp "$ENV_FILE" "$tmp_file"
    printf "\nKAORI_MFA_KEY=%s\n" "$new_key" >> "$tmp_file"
fi
mv "$tmp_file" "$ENV_FILE"

echo "[generate-mfa-key] wrote new KAORI_MFA_KEY to $ENV_FILE"
if [[ "$FORCE" == 1 ]]; then
    echo "[generate-mfa-key] !! ROTATION WARNING !! Existing MFA enrolments are now invalid."
    echo "[generate-mfa-key]    All admins must re-enrol via /platform/security/mfa."
    echo "[generate-mfa-key]    See CLAUDE.md §15 for the safe rotation procedure."
fi
