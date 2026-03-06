#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

ensure_prereqs
load_outputs

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
save_output "AWS_ACCOUNT_ID" "${ACCOUNT_ID}"

if ! aws dynamodb describe-table --region "${AWS_REGION}" --table-name "${DDB_TABLE_NAME}" >/dev/null 2>&1; then
  aws dynamodb create-table \
    --region "${AWS_REGION}" \
    --table-name "${DDB_TABLE_NAME}" \
    --attribute-definitions AttributeName=id,AttributeType=N \
    --key-schema AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --region "${AWS_REGION}" --table-name "${DDB_TABLE_NAME}"
fi

ECR_URI="$(aws ecr describe-repositories --region "${AWS_REGION}" --repository-names "${ECR_REPO_NAME}" --query 'repositories[0].repositoryUri' --output text 2>/dev/null || true)"
if [[ -z "${ECR_URI}" || "${ECR_URI}" == "None" ]]; then
  ECR_URI="$(aws ecr create-repository --region "${AWS_REGION}" --repository-name "${ECR_REPO_NAME}" --image-scanning-configuration scanOnPush=true --query 'repository.repositoryUri' --output text)"
fi
save_output "ECR_URI" "${ECR_URI}"

USER_POOL_ID="$(aws cognito-idp list-user-pools --region "${AWS_REGION}" --max-results 60 --query "UserPools[?Name=='${COGNITO_POOL_NAME}'].Id | [0]" --output text)"
if [[ -z "${USER_POOL_ID}" || "${USER_POOL_ID}" == "None" ]]; then
  USER_POOL_ID="$(aws cognito-idp create-user-pool \
    --region "${AWS_REGION}" \
    --pool-name "${COGNITO_POOL_NAME}" \
    --policies '{"PasswordPolicy":{"MinimumLength":12,"RequireUppercase":true,"RequireLowercase":true,"RequireNumbers":true,"RequireSymbols":false}}' \
    --auto-verified-attributes email \
    --username-attributes email \
    --query 'UserPool.Id' \
    --output text)"
fi
save_output "COGNITO_USER_POOL_ID" "${USER_POOL_ID}"

if ! aws cognito-idp describe-user-pool-domain --region "${AWS_REGION}" --domain "${COGNITO_DOMAIN_PREFIX}" >/dev/null 2>&1; then
  aws cognito-idp create-user-pool-domain \
    --region "${AWS_REGION}" \
    --user-pool-id "${USER_POOL_ID}" \
    --domain "${COGNITO_DOMAIN_PREFIX}" >/dev/null
fi
COGNITO_DOMAIN="https://${COGNITO_DOMAIN_PREFIX}.auth.${AWS_REGION}.amazoncognito.com"
save_output "COGNITO_DOMAIN" "${COGNITO_DOMAIN}"

CLIENT_ID="$(aws cognito-idp list-user-pool-clients --region "${AWS_REGION}" --user-pool-id "${USER_POOL_ID}" --query "UserPoolClients[?ClientName=='${COGNITO_CLIENT_NAME}'].ClientId | [0]" --output text)"
if [[ -z "${CLIENT_ID}" || "${CLIENT_ID}" == "None" ]]; then
  CLIENT_ID="$(aws cognito-idp create-user-pool-client \
    --region "${AWS_REGION}" \
    --user-pool-id "${USER_POOL_ID}" \
    --client-name "${COGNITO_CLIENT_NAME}" \
    --generate-secret \
    --allowed-o-auth-flows code \
    --allowed-o-auth-scopes openid email profile \
    --supported-identity-providers COGNITO \
    --allowed-o-auth-flows-user-pool-client \
    --callback-urls 'https://example.com/auth/callback' \
    --logout-urls 'https://example.com/login' \
    --query 'UserPoolClient.ClientId' \
    --output text)"
fi
CLIENT_SECRET="$(aws cognito-idp describe-user-pool-client --region "${AWS_REGION}" --user-pool-id "${USER_POOL_ID}" --client-id "${CLIENT_ID}" --query 'UserPoolClient.ClientSecret' --output text)"
save_output "COGNITO_CLIENT_ID" "${CLIENT_ID}"

SECRET_ARN="$(aws secretsmanager describe-secret --region "${AWS_REGION}" --secret-id "${SECRETS_NAME}" --query 'ARN' --output text 2>/dev/null || true)"
if [[ -z "${SECRET_ARN}" || "${SECRET_ARN}" == "None" ]]; then
  FLASK_SECRET_KEY="$(openssl rand -hex 32)"
  SECRET_ARN="$(aws secretsmanager create-secret \
    --region "${AWS_REGION}" \
    --name "${SECRETS_NAME}" \
    --secret-string "$(jq -nc --arg f "$FLASK_SECRET_KEY" --arg c "$CLIENT_SECRET" '{FLASK_SECRET_KEY:$f, COGNITO_CLIENT_SECRET:$c}')" \
    --query 'ARN' \
    --output text)"
else
  CURRENT="$(aws secretsmanager get-secret-value --region "${AWS_REGION}" --secret-id "${SECRETS_NAME}" --query SecretString --output text)"
  FLASK_SECRET_KEY="$(echo "${CURRENT}" | jq -r '.FLASK_SECRET_KEY // empty')"
  if [[ -z "${FLASK_SECRET_KEY}" ]]; then
    FLASK_SECRET_KEY="$(openssl rand -hex 32)"
  fi
  aws secretsmanager put-secret-value \
    --region "${AWS_REGION}" \
    --secret-id "${SECRETS_NAME}" \
    --secret-string "$(jq -nc --arg f "$FLASK_SECRET_KEY" --arg c "$CLIENT_SECRET" '{FLASK_SECRET_KEY:$f, COGNITO_CLIENT_SECRET:$c}')" >/dev/null
fi
save_output "APP_SECRET_ARN" "${SECRET_ARN}"

echo "Bootstrap complete. Outputs written to ${OUTPUT_FILE}"
