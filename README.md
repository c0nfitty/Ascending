# Maple Rugs Semantic Search POC

Source code for the Maple Rugs Semantic Search POC. Generates structured AI descriptions for rug images stored in S3, indexes them in a Bedrock Knowledge Base, and surfaces semantic search results through a Jarvis chat interface.

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

# 4. Start the FastAPI Server at http://localhost:8080
uv run poe start

# 5. Lint and format
uv run poe lint && uv run poe format
```

## Testing

With the server running (`uv run poe start`):

```bash
# Health check
curl http://localhost:8080/ping

# Generate structured rug description
curl -X POST http://localhost:8080/invocations -F "file=@path/to/local/image.png" | jq .
```

## Environment Variables

| Variable | Required | Default |
|---|---|---|
| `AWS_REGION` | Yes | us-east-1 |
| `AWS_PROFILE` | Yes | — |
| `S3_BUCKET` | Yes | — |
| `BEDROCK_MODEL_ID` | Yes | us.anthropic.claude-sonnet-4-5-20250929-v1:0 |
| `BEDROCK_KNOWLEDGE_BASE_ID` | Yes | — |
| `A2A_HOST` | No | `0.0.0.0` |
| `A2A_PORT` | No | `8080` |
| `LOG_LEVEL` | No | `INFO` |
