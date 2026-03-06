#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/scripts/aws/env.sh"
OUTPUT_FILE="${ROOT_DIR}/scripts/aws/.stack-outputs.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy scripts/aws/env.example to env.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

APP_NAME="${APP_NAME:-comics-web}"
APP_PORT="${APP_PORT:-8080}"
DESIRED_COUNT="${DESIRED_COUNT:-1}"
DDB_TABLE_NAME="${DDB_TABLE_NAME:-comics}"
COGNITO_DOMAIN_PREFIX="${COGNITO_DOMAIN_PREFIX:-${PROJECT_NAME}-${ENV_NAME}-auth}"
APP_IMAGE_TAG="${APP_IMAGE_TAG:-latest}"

CLUSTER_NAME="${PROJECT_NAME}-${ENV_NAME}-cluster"
SERVICE_NAME="${PROJECT_NAME}-${ENV_NAME}-service"
TASK_FAMILY="${PROJECT_NAME}-${ENV_NAME}-task"
ECR_REPO_NAME="${PROJECT_NAME}-${ENV_NAME}-${APP_NAME}"
LOG_GROUP_NAME="/ecs/${PROJECT_NAME}/${ENV_NAME}/${APP_NAME}"
ALB_NAME="${PROJECT_NAME}-${ENV_NAME}-alb"
TG_NAME="${PROJECT_NAME}-${ENV_NAME}-tg"
ALB_SG_NAME="${PROJECT_NAME}-${ENV_NAME}-alb-sg"
ECS_SG_NAME="${PROJECT_NAME}-${ENV_NAME}-ecs-sg"
TASK_EXEC_ROLE_NAME="${PROJECT_NAME}-${ENV_NAME}-ecsTaskExecutionRole"
TASK_ROLE_NAME="${PROJECT_NAME}-${ENV_NAME}-taskRole"
COGNITO_POOL_NAME="${PROJECT_NAME}-${ENV_NAME}-users"
COGNITO_CLIENT_NAME="${PROJECT_NAME}-${ENV_NAME}-web-client"
SECRETS_NAME="${PROJECT_NAME}/${ENV_NAME}/webapp"

ensure_prereqs() {
  command -v aws >/dev/null || { echo "aws CLI is required" >&2; exit 1; }
  command -v jq >/dev/null || { echo "jq is required" >&2; exit 1; }
  aws sts get-caller-identity >/dev/null
}

ensure_outputs_file() {
  touch "${OUTPUT_FILE}"
}

save_output() {
  local key="$1"
  local value="$2"
  ensure_outputs_file
  grep -v "^export ${key}=" "${OUTPUT_FILE}" > "${OUTPUT_FILE}.tmp" || true
  mv "${OUTPUT_FILE}.tmp" "${OUTPUT_FILE}"
  printf 'export %s="%s"\n' "${key}" "${value}" >> "${OUTPUT_FILE}"
}

load_outputs() {
  if [[ -f "${OUTPUT_FILE}" ]]; then
    # shellcheck disable=SC1090
    source "${OUTPUT_FILE}"
  fi
}
