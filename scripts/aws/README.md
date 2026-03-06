# AWS CLI Deployment Scripts

These scripts provision and deploy the app using AWS CLI only.

## Prerequisites

- AWS CLI v2
- `jq`
- Docker
- An ACM certificate ARN in your target region (for HTTPS on ALB)

## Setup

1. Copy env template and set values:
   - `cp scripts/aws/env.example scripts/aws/env.sh`
   - Edit `scripts/aws/env.sh`
2. Ensure your AWS credentials are available in your shell (`aws sts get-caller-identity`).

## Run Order

1. `scripts/aws/01-bootstrap.sh`
2. `scripts/aws/05-seed-dynamodb.sh`
3. `scripts/aws/02-build-and-push.sh`
4. `scripts/aws/03-deploy.sh`
5. `scripts/aws/04-create-user.sh you@example.com`
6. Set a permanent password for the created Cognito user (command printed by script 04).

## What Gets Created

- DynamoDB table (on-demand)
- ECR repository
- Cognito User Pool, App Client, Hosted UI domain
- Secrets Manager secret for `FLASK_SECRET_KEY` and `COGNITO_CLIENT_SECRET`
- ECS cluster/service/task definition (Fargate)
- ALB + target group + listeners (HTTP redirect to HTTPS)
- IAM task execution role and task role with least-privilege policies

## Outputs

Generated values are saved to:

- `scripts/aws/.stack-outputs.env`

You can source it to inspect values:

- `source scripts/aws/.stack-outputs.env`

## Notes

- The scripts are intended for a low-cost personal account setup.
- They use your default VPC and its first two default subnets.
- For production hardening, move to a custom VPC and private subnets.
- `05-seed-dynamodb.sh` refuses to run when table has data unless `FORCE_SEED=true`.
