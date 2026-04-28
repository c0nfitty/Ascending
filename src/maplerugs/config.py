from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    s3_bucket: str = ""
    bedrock_model_id: str = "anthropic.claude-3-7-sonnet-20250219-v1:0"
    bedrock_knowledge_base_id: str = ""
    a2a_host: str = "0.0.0.0"
    a2a_port: int = 8080
    log_level: str = "INFO"


settings = Settings()
