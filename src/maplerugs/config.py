from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    s3_bucket: str = ""
    bedrock_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    bedrock_knowledge_base_id: str = ""
    a2a_host: str = "0.0.0.0"
    a2a_port: int = 8080
    a2a_base_url: str = "http://localhost:8080"
    log_level: str = "INFO"


settings = Settings()
