#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib.sh"

ensure_prereqs
load_outputs

required_vars=(IMAGE_URI COGNITO_USER_POOL_ID COGNITO_CLIENT_ID COGNITO_DOMAIN APP_SECRET_ARN)
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "${var} is missing. Run scripts/aws/01-bootstrap.sh and 02-build-and-push.sh first." >&2
    exit 1
  fi
done

if [[ -z "${ALB_CERT_ARN:-}" || "${ALB_CERT_ARN}" == *"replace-me"* ]]; then
  echo "Set ALB_CERT_ARN in scripts/aws/env.sh before deploy." >&2
  exit 1
fi

ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
save_output "AWS_ACCOUNT_ID" "${ACCOUNT_ID}"

VPC_ID="$(aws ec2 describe-vpcs --region "${AWS_REGION}" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)"
if [[ -z "${VPC_ID}" || "${VPC_ID}" == "None" ]]; then
  echo "No default VPC found. Create one or adapt script for a custom VPC." >&2
  exit 1
fi

readarray -t SUBNET_IDS < <(aws ec2 describe-subnets --region "${AWS_REGION}" --filters Name=vpc-id,Values="${VPC_ID}" Name=default-for-az,Values=true --query 'Subnets[].SubnetId' --output text | tr '\t' '\n' | sed '/^$/d')
if [[ "${#SUBNET_IDS[@]}" -lt 2 ]]; then
  echo "Need at least 2 default subnets in the default VPC." >&2
  exit 1
fi

ALB_SG_ID="$(aws ec2 describe-security-groups --region "${AWS_REGION}" --filters Name=group-name,Values="${ALB_SG_NAME}" Name=vpc-id,Values="${VPC_ID}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [[ -z "${ALB_SG_ID}" || "${ALB_SG_ID}" == "None" ]]; then
  ALB_SG_ID="$(aws ec2 create-security-group --region "${AWS_REGION}" --group-name "${ALB_SG_NAME}" --description "ALB SG for ${PROJECT_NAME}" --vpc-id "${VPC_ID}" --query GroupId --output text)"
fi
aws ec2 authorize-security-group-ingress --region "${AWS_REGION}" --group-id "${ALB_SG_ID}" --ip-permissions '[{"IpProtocol":"tcp","FromPort":80,"ToPort":80,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]},{"IpProtocol":"tcp","FromPort":443,"ToPort":443,"IpRanges":[{"CidrIp":"0.0.0.0/0"}]}]' >/dev/null 2>&1 || true

ECS_SG_ID="$(aws ec2 describe-security-groups --region "${AWS_REGION}" --filters Name=group-name,Values="${ECS_SG_NAME}" Name=vpc-id,Values="${VPC_ID}" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || true)"
if [[ -z "${ECS_SG_ID}" || "${ECS_SG_ID}" == "None" ]]; then
  ECS_SG_ID="$(aws ec2 create-security-group --region "${AWS_REGION}" --group-name "${ECS_SG_NAME}" --description "ECS task SG for ${PROJECT_NAME}" --vpc-id "${VPC_ID}" --query GroupId --output text)"
fi
aws ec2 authorize-security-group-ingress --region "${AWS_REGION}" --group-id "${ECS_SG_ID}" --protocol tcp --port "${APP_PORT}" --source-group "${ALB_SG_ID}" >/dev/null 2>&1 || true

ALB_ARN="$(aws elbv2 describe-load-balancers --region "${AWS_REGION}" --names "${ALB_NAME}" --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || true)"
if [[ -z "${ALB_ARN}" || "${ALB_ARN}" == "None" ]]; then
  ALB_ARN="$(aws elbv2 create-load-balancer --region "${AWS_REGION}" --name "${ALB_NAME}" --type application --scheme internet-facing --security-groups "${ALB_SG_ID}" --subnets "${SUBNET_IDS[0]}" "${SUBNET_IDS[1]}" --query 'LoadBalancers[0].LoadBalancerArn' --output text)"
fi
aws elbv2 wait load-balancer-available --region "${AWS_REGION}" --load-balancer-arns "${ALB_ARN}"
ALB_DNS="$(aws elbv2 describe-load-balancers --region "${AWS_REGION}" --load-balancer-arns "${ALB_ARN}" --query 'LoadBalancers[0].DNSName' --output text)"
save_output "ALB_DNS" "${ALB_DNS}"

TG_ARN="$(aws elbv2 describe-target-groups --region "${AWS_REGION}" --names "${TG_NAME}" --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || true)"
if [[ -z "${TG_ARN}" || "${TG_ARN}" == "None" ]]; then
  TG_ARN="$(aws elbv2 create-target-group --region "${AWS_REGION}" --name "${TG_NAME}" --protocol HTTP --port "${APP_PORT}" --target-type ip --vpc-id "${VPC_ID}" --health-check-path /health --health-check-protocol HTTP --query 'TargetGroups[0].TargetGroupArn' --output text)"
fi

LISTENER_80_ARN="$(aws elbv2 describe-listeners --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --query "Listeners[?Port==\`80\`].ListenerArn | [0]" --output text)"
if [[ -z "${LISTENER_80_ARN}" || "${LISTENER_80_ARN}" == "None" ]]; then
  aws elbv2 create-listener --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --protocol HTTP --port 80 --default-actions Type=redirect,RedirectConfig="{Protocol=HTTPS,Port=443,StatusCode=HTTP_301}" >/dev/null
fi

LISTENER_443_ARN="$(aws elbv2 describe-listeners --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --query "Listeners[?Port==\`443\`].ListenerArn | [0]" --output text)"
if [[ -z "${LISTENER_443_ARN}" || "${LISTENER_443_ARN}" == "None" ]]; then
  aws elbv2 create-listener --region "${AWS_REGION}" --load-balancer-arn "${ALB_ARN}" --protocol HTTPS --port 443 --certificates CertificateArn="${ALB_CERT_ARN}" --default-actions Type=forward,TargetGroupArn="${TG_ARN}" >/dev/null
fi

if ! aws iam get-role --role-name "${TASK_EXEC_ROLE_NAME}" >/dev/null 2>&1; then
  aws iam create-role --role-name "${TASK_EXEC_ROLE_NAME}" --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
  aws iam attach-role-policy --role-name "${TASK_EXEC_ROLE_NAME}" --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
fi

aws iam put-role-policy --role-name "${TASK_EXEC_ROLE_NAME}" --policy-name "${TASK_EXEC_ROLE_NAME}-secrets" --policy-document "$(jq -nc --arg secretArn "${APP_SECRET_ARN}" '{Version:"2012-10-17",Statement:[{Effect:"Allow",Action:["secretsmanager:GetSecretValue","kms:Decrypt"],Resource:[$secretArn]}]}')" >/dev/null

if ! aws iam get-role --role-name "${TASK_ROLE_NAME}" >/dev/null 2>&1; then
  aws iam create-role --role-name "${TASK_ROLE_NAME}" --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null
fi

DDB_TABLE_ARN="$(aws dynamodb describe-table --region "${AWS_REGION}" --table-name "${DDB_TABLE_NAME}" --query 'Table.TableArn' --output text)"
aws iam put-role-policy --role-name "${TASK_ROLE_NAME}" --policy-name "${TASK_ROLE_NAME}-ddb" --policy-document "$(jq -nc --arg arn "${DDB_TABLE_ARN}" '{Version:"2012-10-17",Statement:[{Effect:"Allow",Action:["dynamodb:DescribeTable","dynamodb:PutItem","dynamodb:GetItem","dynamodb:DeleteItem","dynamodb:UpdateItem","dynamodb:Scan"],Resource:[$arn]}]}')" >/dev/null

for role_name in "${TASK_EXEC_ROLE_NAME}" "${TASK_ROLE_NAME}"; do
  aws iam wait role-exists --role-name "${role_name}"
done

TASK_EXEC_ROLE_ARN="$(aws iam get-role --role-name "${TASK_EXEC_ROLE_NAME}" --query 'Role.Arn' --output text)"
TASK_ROLE_ARN="$(aws iam get-role --role-name "${TASK_ROLE_NAME}" --query 'Role.Arn' --output text)"

aws logs create-log-group --region "${AWS_REGION}" --log-group-name "${LOG_GROUP_NAME}" >/dev/null 2>&1 || true

POST_LOGOUT_REDIRECT_URI="https://${ALB_DNS}/login"
TASKDEF_FILE="$(mktemp)"
cat > "${TASKDEF_FILE}" <<JSON
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${TASK_EXEC_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}",
      "image": "${IMAGE_URI}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": ${APP_PORT},
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "AUTH_REQUIRED", "value": "true"},
        {"name": "COMICS_STORAGE_BACKEND", "value": "dynamodb"},
        {"name": "DYNAMODB_TABLE_NAME", "value": "${DDB_TABLE_NAME}"},
        {"name": "AWS_REGION", "value": "${AWS_REGION}"},
        {"name": "COGNITO_REGION", "value": "${AWS_REGION}"},
        {"name": "COGNITO_USER_POOL_ID", "value": "${COGNITO_USER_POOL_ID}"},
        {"name": "COGNITO_CLIENT_ID", "value": "${COGNITO_CLIENT_ID}"},
        {"name": "COGNITO_DOMAIN", "value": "${COGNITO_DOMAIN}"},
        {"name": "SESSION_COOKIE_SECURE", "value": "true"},
        {"name": "POST_LOGOUT_REDIRECT_URI", "value": "${POST_LOGOUT_REDIRECT_URI}"}
      ],
      "secrets": [
        {"name": "FLASK_SECRET_KEY", "valueFrom": "${APP_SECRET_ARN}:FLASK_SECRET_KEY::"},
        {"name": "COGNITO_CLIENT_SECRET", "valueFrom": "${APP_SECRET_ARN}:COGNITO_CLIENT_SECRET::"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "${LOG_GROUP_NAME}",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
JSON

TASK_DEF_ARN="$(aws ecs register-task-definition --region "${AWS_REGION}" --cli-input-json "file://${TASKDEF_FILE}" --query 'taskDefinition.taskDefinitionArn' --output text)"
rm -f "${TASKDEF_FILE}"

aws ecs create-cluster --region "${AWS_REGION}" --cluster-name "${CLUSTER_NAME}" >/dev/null 2>&1 || true

SERVICE_ARN="$(aws ecs describe-services --region "${AWS_REGION}" --cluster "${CLUSTER_NAME}" --services "${SERVICE_NAME}" --query 'services[0].serviceArn' --output text)"
if [[ -z "${SERVICE_ARN}" || "${SERVICE_ARN}" == "None" ]]; then
  aws ecs create-service \
    --region "${AWS_REGION}" \
    --cluster "${CLUSTER_NAME}" \
    --service-name "${SERVICE_NAME}" \
    --task-definition "${TASK_DEF_ARN}" \
    --desired-count "${DESIRED_COUNT}" \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_IDS[0]},${SUBNET_IDS[1]}],securityGroups=[${ECS_SG_ID}],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=${TG_ARN},containerName=${APP_NAME},containerPort=${APP_PORT}" >/dev/null
else
  aws ecs update-service --region "${AWS_REGION}" --cluster "${CLUSTER_NAME}" --service "${SERVICE_NAME}" --task-definition "${TASK_DEF_ARN}" --desired-count "${DESIRED_COUNT}" >/dev/null
fi

aws ecs wait services-stable --region "${AWS_REGION}" --cluster "${CLUSTER_NAME}" --services "${SERVICE_NAME}"

aws cognito-idp update-user-pool-client \
  --region "${AWS_REGION}" \
  --user-pool-id "${COGNITO_USER_POOL_ID}" \
  --client-id "${COGNITO_CLIENT_ID}" \
  --client-name "${COGNITO_CLIENT_NAME}" \
  --allowed-o-auth-flows code \
  --allowed-o-auth-scopes openid email profile \
  --supported-identity-providers COGNITO \
  --allowed-o-auth-flows-user-pool-client \
  --callback-urls "https://${ALB_DNS}/auth/callback" \
  --logout-urls "https://${ALB_DNS}/login" >/dev/null

echo "Deploy complete"
echo "App URL: https://${ALB_DNS}"
echo "To create first user:"
echo "aws cognito-idp admin-create-user --region ${AWS_REGION} --user-pool-id ${COGNITO_USER_POOL_ID} --username you@example.com --user-attributes Name=email,Value=you@example.com Name=email_verified,Value=true"
