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
    app_name: str = "knowledge-service"
    app_env: str = "development"
    log_level: str = "INFO"
    debug: bool = False

    # 服务端口
    port: int = 8005

    # 数据库（异步 PostgreSQL）
    database_url: str = "postgresql+asyncpg://bidai:bidai_dev_pass@bidai-postgres:5432/bidai"

    # Redis（Celery + 缓存）
    redis_url: str = "redis://:bidai_redis_pass@bidai-redis:6379/0"

    # JWT（由 auth-service 签发，需与 auth-service 保持一致）
    jwt_secret_key: str = "dev-secret-key-change-in-production"
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

    # MinIO（对象存储）
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_kb_bucket: str = "kb-documents"

    # Embedding 外部 API 配置
    embedding_api_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embedding_batch_size: int = 100
    embedding_timeout: int = 60

    # Milvus 向量数据库配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "kb_chunks"
    milvus_username: str = ""
    milvus_password: str = ""

    # 文件上传限制
    upload_max_size_mb: int = 100
    upload_allowed_extensions: set[str] = {"pdf", "docx", "xlsx", "jpg", "png"}

    # 分块策略
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 50
    chunk_max_tokens: int = 600

    # Elasticsearch 全文检索
    es_url: str = "http://localhost:9200"
    es_index: str = "kb_chunks"
    es_username: str = ""
    es_password: str = ""

    # Cross-Encoder 重排序（外部 API）
    reranker_api_url: str = ""
    reranker_api_key: str = ""
    reranker_model: str = ""
    reranker_timeout: int = 10
    reranker_top_k: int = 50  # 参与 rerank 的候选结果数

    # 混合检索默认参数
    search_default_top_k: int = 10
    search_max_top_k: int = 50


settings = Settings()
