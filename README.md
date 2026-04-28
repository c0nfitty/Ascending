# Maple Rugs Semantic Search

Semantic search capability for Maple Rugs' internal sales team. Processes rug images from S3, generates structured descriptions via Amazon Bedrock, and surfaces results through a Bedrock Knowledge Base + Jarvis chat interface.

## Stack

| Layer | Tool |
|---|---|
| Runtime | Python 3.11 |
| Package manager | uv |
| Agent framework | Strands Agents |
| AWS SDK | boto3 |
| LLM | TBD |
| Vector DB | Amazon Bedrock Knowledge Base |
| Web server | FastAPI + uvicorn |

## Local Development

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies
uv sync --group dev

# 3. Configure environment variables
cp .env.example .env

# 4. Start the FastAPI Server at http://localhost:8000
uv run poe start

# 5. Lint and format
uv run poe lint && uv run poe format
```

## Environment Variables

| Variable | Required | Default |
|---|---|---|
| `AWS_REGION` | Yes | — |
| `AWS_PROFILE` | Yes | — |
| `S3_BUCKET` | Yes | — |
| `BEDROCK_KNOWLEDGE_BASE_ID` | Yes | — |
| `BEDROCK_MODEL_ID` | Yes | — |
| `A2A_HOST` | No | `0.0.0.0` |
| `A2A_PORT` | No | `8080` |
| `LOG_LEVEL` | No | `INFO` |
