# Guardian Content Stream

A microservice that retrieves articles from The Guardian newspaper API and publishes them to AWS Kinesis for downstream processing.

## Overview

This service acts as a data ingestion layer in an event-driven architecture. It accepts search parameters, queries The Guardian's Open Platform API for matching articles, and publishes the results to a Kinesis stream where other applications can consume and process them.

## How It Works

1. Receives a search term and optional date filter
2. Retrieves API key from AWS Secrets Manager
3. Queries The Guardian API for matching articles
4. Publishes each article to AWS Kinesis in JSON format

## Output Format

Each article published to Kinesis contains:

```json
{
  "webPublicationDate": "2025-12-21T11:48:30Z",
  "webTitle": "Article title",
  "webUrl": "https://www.theguardian.com/..."
}
```

## Requirements

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- Guardian API key ([register here](https://open-platform.theguardian.com/access/))
- AWS credentials with appropriate permissions

## Quick Start

### 1. Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd guardian-content-stream

# Install dependencies
uv sync --extra dev

# Install AWS SAM CLI (macOS)
brew install aws-sam-cli
```

### 2. Create AWS Resources

```bash
# Create Secrets Manager secret with your Guardian API key
aws secretsmanager create-secret \
  --name guardian-api-key \
  --description "Guardian Open Platform API key" \
  --secret-string "YOUR_GUARDIAN_API_KEY" \
  --region eu-west-2

# Create Kinesis stream
aws kinesis create-stream \
  --stream-name guardian-articles \
  --shard-count 1 \
  --region eu-west-2

# Wait for stream to become active
aws kinesis wait stream-exists --stream-name guardian-articles --region eu-west-2
```

### 3. Build and Deploy

```bash
# Build the SAM application
make sam-build

# Deploy to AWS (first time - guided)
make sam-deploy-guided

# Subsequent deploys
make sam-deploy
```

### 4. Test Your Lambda

```bash
# Invoke the Lambda
aws lambda invoke \
  --function-name guardian-stream-dev \
  --region eu-west-2 \
  --payload '{"search_term": "climate change"}' \
  --cli-binary-format raw-in-base64-out \
  response.json && cat response.json
```

## Usage

### Lambda Invocation

The Lambda handler expects events in this format:

```json
{
  "search_term": "artificial intelligence",
  "date_from": "2024-01-01"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `search_term` | string | Yes | Search query for The Guardian API |
| `date_from` | string | No | Filter articles from this date (YYYY-MM-DD) |

**Response format:**

```json
{
  "statusCode": 200,
  "body": "{\"articles_found\": 10, \"articles_published\": 10}"
}
```

### CLI (Local Development)

```bash
# Set environment variables
export GUARDIAN_API_KEY="your-api-key"
export KINESIS_STREAM_NAME="guardian-articles"

# Search for articles
uv run python -m guardian_stream "climate change"

# With date filter
uv run python -m guardian_stream "renewable energy" --date-from 2024-01-01
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make sam-build` | Export dependencies and build SAM application |
| `make sam-deploy` | Deploy to AWS (requires prior `sam deploy --guided`) |
| `make sam-deploy-guided` | First-time deployment with interactive prompts |
| `make sam-validate` | Validate SAM template |
| `make sam-local-invoke` | Test Lambda locally (requires Docker) |
| `make test` | Run all tests |
| `make test-infra` | Run infrastructure tests only |
| `make clean` | Remove build artifacts |

## Configuration

### Lambda Environment Variables

| Variable | Description |
|----------|-------------|
| `GUARDIAN_API_KEY_SECRET_NAME` | Name of the Secrets Manager secret containing the API key |
| `KINESIS_STREAM_NAME` | Target Kinesis stream for publishing |

### SAM Template Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `Environment` | dev | Deployment environment (dev/staging/prod) |
| `GuardianApiKeySecretName` | guardian-api-key | Secrets Manager secret name |
| `KinesisStreamName` | guardian-articles | Kinesis stream name |

## AWS Resources

The SAM template creates:

- **Lambda Function** (`guardian-stream-{env}`)
  - Runtime: Python 3.13
  - Memory: 256 MB
  - Timeout: 30 seconds

- **IAM Role** with least-privilege permissions:
  - `secretsmanager:GetSecretValue` (scoped to specific secret)
  - `kinesis:PutRecord`, `kinesis:PutRecords` (scoped to specific stream)

**You must create these resources manually:**

- Secrets Manager secret with Guardian API key
- Kinesis Data Stream (1 shard is sufficient)

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run all tests
make test

# Run unit tests only
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=guardian_stream --cov-report=term-missing

# Security scans
uv run bandit -r src/
uv run pip-audit
```

## Project Structure

```
guardian-stream/
├── src/guardian_stream/
│   ├── handler.py        # Lambda entry point
│   ├── guardian_client.py # Guardian API client
│   ├── publisher.py      # Kinesis publisher
│   ├── orchestrator.py   # Main flow coordination
│   ├── models.py         # Pydantic schemas
│   ├── exceptions.py     # Custom exceptions
│   ├── config.py         # Environment config
│   └── cli.py            # CLI interface
├── tests/
│   ├── unit/             # Unit tests
│   └── infrastructure/   # SAM template tests
├── events/               # Test event files
├── scripts/              # Utility scripts
├── template.yaml         # SAM template
├── Makefile              # Build automation
└── pyproject.toml        # Project config
```

## Cleanup

To delete all AWS resources and avoid charges:

```bash
# Delete CloudFormation stack (Lambda + IAM role)
aws cloudformation delete-stack --stack-name guardian-stream-dev --region eu-west-2

# Delete Kinesis stream
aws kinesis delete-stream --stream-name guardian-articles --region eu-west-2

# Delete Secrets Manager secret (immediate, no recovery)
aws secretsmanager delete-secret \
  --secret-id guardian-api-key \
  --force-delete-without-recovery \
  --region eu-west-2
```

## Security

- API keys are stored in AWS Secrets Manager
- Error messages are sanitized to prevent information leakage
- Input validation rejects non-string search terms
- All dependencies are scanned for vulnerabilities
- IAM policies follow least-privilege principles
- SAM template is tested for security best practices
