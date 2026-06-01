# ============================================================
# AI 智能投标系统 · Python 服务统一配置模块
# 所有服务通过环境变量注入配置，禁止硬编码
# ============================================================

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用基础
    app_name: str = "win-rate-service"
    app_env: str = "development"
    log_level: str = "INFO"
    debug: bool = False

    # 服务端口
    port: int = 8006

    # 数据库（异步 PostgreSQL）
    database_url: str = "postgresql+asyncpg://bidai:bidai_dev_pass@bidai-postgres:5432/bidai"

    # Redis（Celery + 缓存）
    redis_url: str = "redis://:bidai_redis_pass@bidai-redis:6379/0"

    # JWT（由 auth-service 签发）
    jwt_secret_key: str = "dev-jwt-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # LLM（私有化模型）
    llm_private_base_url: str = ""
    llm_private_model: str = ""
    llm_private_timeout: int = 120

    # LLM 外部 API — Kimi（Moonshot AI）降级备用
    llm_kimi_api_key: str = ""
    llm_kimi_model: str = "moonshot-v1-8k"
    llm_kimi_timeout: int = 60

    # LLM 外部 API — DeepSeek 降级备用
    llm_deepseek_api_key: str = ""
    llm_deepseek_model: str = "deepseek-chat"
    llm_deepseek_timeout: int = 60


settings = Settings()
