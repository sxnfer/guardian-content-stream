# Guardian Content Stream

A microservice that retrieves articles from The Guardian newspaper API and publishes them to AWS Kinesis for downstream processing.

## Overview

This service acts as a data ingestion layer in an event-driven architecture. It accepts search parameters, queries The Guardian's Open Platform API for matching articles, and publishes the results to a Kinesis stream where other applications can consume and process them.

## How It Works

1. Receives a search term and optional date filter
2. Queries The Guardian API for matching articles
3. Returns up to 10 most recent results
4. Publishes each article to AWS Kinesis in JSON format

## Output Format

Each article published to Kinesis contains:

```json
{
  "webPublicationDate": "2023-11-21T11:11:31Z",
  "webTitle": "Article title",
  "webUrl": "https://www.theguardian.com/..."
}
```

## Deployment

Designed to run as an AWS Lambda function, invoked on-demand or on a schedule.

## Requirements

- Python 3.11+
- Guardian API key
- AWS credentials with Kinesis access

## Development

```bash
# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest tests/unit/ -v
```

## Configuration

The service requires the following environment variables:

| Variable | Description |
|----------|-------------|
| `GUARDIAN_API_KEY` | API key from The Guardian Open Platform |
| `KINESIS_STREAM_NAME` | Target Kinesis stream for publishing |
