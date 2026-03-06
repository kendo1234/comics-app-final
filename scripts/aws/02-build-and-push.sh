#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

ensure_prereqs
load_outputs

if [[ -z "${ECR_URI:-}" ]]; then
  echo "ECR_URI missing. Run scripts/aws/01-bootstrap.sh first." >&2
  exit 1
fi

ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

IMAGE_URI="${ECR_URI}:${APP_IMAGE_TAG}"
docker build -t "${IMAGE_URI}" "${ROOT_DIR}"
docker push "${IMAGE_URI}"
save_output "IMAGE_URI" "${IMAGE_URI}"

echo "Image pushed: ${IMAGE_URI}"
