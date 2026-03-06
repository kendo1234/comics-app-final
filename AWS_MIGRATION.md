# AWS Migration Plan

## Service Assessment (Best Fit for This App)

This is a Flask web app with server-rendered pages and CRUD operations. The most practical secure AWS target is:

- Amazon ECS Fargate (web app container)
- Amazon DynamoDB (comic data CRUD)
- Amazon Cognito (user authentication)
- AWS Application Load Balancer with HTTPS (TLS termination + routing)
- Amazon ECR (container image registry)
- AWS Secrets Manager + IAM roles (secret and credential management)

## Why This Stack

- Secure: Cognito handles user auth; TLS via ALB; no hardcoded credentials in code.
- Managed: No OS patching or server management.
- Cost-conscious: small Fargate task + DynamoDB on-demand keeps costs low for low traffic while remaining production-safe.
- Minimal rewrite: Flask app remains a web app and gets auth + DynamoDB support with limited code change.

## Implemented in This Branch

- Added DynamoDB-backed storage mode in `comic_service.py`.
- Added Cognito login/logout flow and auth enforcement in `app.py`.
- Added `templates/login.html` and authenticated nav updates.
- Added dependencies: `boto3`, `authlib`, `gunicorn`.

## Required Environment Variables

- `FLASK_SECRET_KEY`
- `AUTH_REQUIRED=true`
- `COMICS_STORAGE_BACKEND=dynamodb`
- `DYNAMODB_TABLE_NAME=comics`
- `AWS_REGION=us-east-1`
- `COGNITO_DOMAIN=https://<your-domain>.auth.<region>.amazoncognito.com`
- `COGNITO_CLIENT_ID=<app-client-id>`
- `COGNITO_CLIENT_SECRET=<app-client-secret>`
- `COGNITO_REGION=<region>`
- `COGNITO_USER_POOL_ID=<user-pool-id>`
- `POST_LOGOUT_REDIRECT_URI=https://<your-app-domain>/login`

## DynamoDB Table

Create table:

- Table name: `comics`
- Partition key: `id` (Number)
- Billing mode: On-demand

## Authentication Model

- All routes are protected when `AUTH_REQUIRED=true`.
- Unauthenticated users are redirected to Cognito Hosted UI via `/login`.
- API routes return `401` when not authenticated.

## Deployment Outline

1. Build and push container image to ECR.
2. Create DynamoDB table.
3. Create Cognito User Pool + App Client + Hosted UI domain.
4. Deploy ECS Fargate service behind ALB (HTTPS only).
5. Configure app environment variables and IAM task role permissions for DynamoDB read/write.
6. Validate login flow and CRUD operations.

## AWS CLI Automation

Run the included scripts in order:

1. `scripts/aws/01-bootstrap.sh`
2. `scripts/aws/05-seed-dynamodb.sh`
3. `scripts/aws/02-build-and-push.sh`
4. `scripts/aws/03-deploy.sh`
5. `scripts/aws/04-create-user.sh you@example.com`

Before running, copy `scripts/aws/env.example` to `scripts/aws/env.sh` and set `ALB_CERT_ARN` and other values.

## Security Controls

- Store secrets in Secrets Manager or ECS secrets integration.
- Use least-privilege IAM policies (only required DynamoDB table actions).
- Enforce HTTPS and secure session cookies.
- Keep AWS credentials out of the repository.
