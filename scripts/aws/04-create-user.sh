#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <email>" >&2
  exit 1
fi

EMAIL="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

ensure_prereqs
load_outputs

if [[ -z "${COGNITO_USER_POOL_ID:-}" ]]; then
  echo "COGNITO_USER_POOL_ID missing. Run scripts/aws/01-bootstrap.sh first." >&2
  exit 1
fi

aws cognito-idp admin-create-user \
  --region "${AWS_REGION}" \
  --user-pool-id "${COGNITO_USER_POOL_ID}" \
  --username "${EMAIL}" \
  --user-attributes Name=email,Value="${EMAIL}" Name=email_verified,Value=true \
  --message-action SUPPRESS >/dev/null

echo "User created: ${EMAIL}"
echo "Set a permanent password now:"
echo "aws cognito-idp admin-set-user-password --region ${AWS_REGION} --user-pool-id ${COGNITO_USER_POOL_ID} --username ${EMAIL} --password 'ChangeMe123!' --permanent"
