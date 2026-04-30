# CLAUDE.md — AI 智能投标系统 · 项目开发行为规范

> 本文件是面向 AI 编程助手（Claude Code 等）的项目开发行为规范。
> 所有代码生成、架构决策、文件操作均须遵循本文件的约束。
> 文档编号：TSD-BIDAI-2026-001 配套规范 | 版本：V1.0

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈与版本约束](#2-技术栈与版本约束)
3. [项目结构规范](#3-项目结构规范)
4. [开发命令速查](#4-开发命令速查)
5. [代码规范](#5-代码规范)
6. [架构规范](#6-架构规范)
7. [AI 能力层开发规范](#7-ai-能力层开发规范)
8. [数据层规范](#8-数据层规范)
9. [安全规范](#9-安全规范)
10. [API 设计规范](#10-api-设计规范)
11. [测试规范](#11-测试规范)
12. [禁止行为清单](#12-禁止行为清单)

---

## 1. 项目概述

**系统名称**：AI 智能投标系统  
**定位**：覆盖投标全生命周期的企业私有化 AI 系统  
**部署模式**：企业内网私有化部署，敏感数据不出内网  
**核心原则**：AI 辅助、人工主导、数据安全优先、知识闭环驱动

### 1.1 核心功能模块

| 模块 | 服务名 | 语言 |
|------|--------|------|
| 招标文件解析引擎 | `bid-parser-service` | Python |
| AI 协同编写引擎 | `bid-writer-service` | Python |
| 投标审查服务 | `bid-review-service` | Python |
| 串标分析服务 | `collusion-analysis-service` | Python |
| 企业知识库服务 | `knowledge-service` | Python |
| 胜率预测服务 | `win-rate-service` | Python |
| 项目管理服务 | `project-service` | Java |
| 权限与用户服务 | `auth-service` | Java |
| 文档导出服务 | `export-service` | Java |
| 通知推送服务 | `notify-service` | Java |
| Web 前端 | `bid-web` | TypeScript |
| 移动端 | `bid-mobile` | TypeScript |

---

## 2. 技术栈与版本约束

> **版本锁定原则**：未经架构评审，不得擅自升级主版本号。

### 2.1 前端

```
框架：       Vue 3.4+（Composition API，禁止使用 Options API）
语言：       TypeScript 5.x（strict 模式开启）
UI 组件库：  Element Plus（最新稳定版）
移动端：     uni-app（H5 + 微信小程序双端）
状态管理：   Pinia
HTTP 客户端：Axios（统一封装，禁止裸用 fetch）
构建工具：   Vite
代码规范：   ESLint + Prettier（配置见 .eslintrc）
```

### 2.2 后端 — Python 服务（AI 能力层）

```
框架：       FastAPI 0.110+
语言：       Python 3.11+
AI 框架：    LangChain 0.2+
OCR：        PaddleOCR 2.7+（中文识别）
PDF 解析：   PyMuPDF（文本 PDF）
DOCX 解析：  python-docx
任务队列：   Celery + Redis
依赖管理：   Poetry（禁止使用 pip install 直接安装到生产镜像）
代码规范：   Ruff + Black（line-length=120）
类型检查：   mypy（strict 模式）
```

### 2.3 后端 — Java 服务（业务服务层）

```
框架：       Spring Boot 3.2+
语言：       Java 21（LTS）
构建工具：   Gradle 8.x（禁止使用 Maven）
ORM：        Spring Data JPA + QueryDSL
代码规范：   Google Java Style Guide
```

### 2.4 数据层

```
关系数据库：  PostgreSQL 15+
全文检索：    Elasticsearch 8.x（IK 中文分词器）
向量数据库：  Milvus 2.4+
对象存储：    MinIO（兼容 S3 协议）
缓存：        Redis 7+
```

### 2.5 LLM 推理

```
首选：  私有化部署 Qwen2.5 / DeepSeek-V3（GPU 节点）
降级：  外部 API（GPT-4 / Claude）—— 仅允许处理非敏感内容
框架：  vLLM 或 Ollama 管理本地模型
```

### 2.6 基础设施

```
容器编排：   Kubernetes 1.28+
API 网关：   Kong / Nginx
监控：       Prometheus + Grafana
日志：       ELK Stack（Elasticsearch + Logstash + Kibana）
链路追踪：   Jaeger
CI/CD：      GitLab CI（内网）
```

---

## 3. 项目结构规范

### 3.1 代码仓库结构

```
bid-ai-system/
├── services/
│   ├── python/
│   │   ├── bid-parser-service/       # 招标文件解析
│   │   ├── bid-writer-service/       # AI 协同编写
│   │   ├── bid-review-service/       # 投标审查
│   │   ├── collusion-analysis-service/  # 串标分析
│   │   ├── knowledge-service/        # 企业知识库
│   │   └── win-rate-service/         # 胜率预测
│   └── java/
│       ├── project-service/          # 项目管理
│       ├── auth-service/             # 权限认证
│       ├── export-service/           # 文档导出
│       └── notify-service/           # 通知推送
├── frontend/
│   ├── bid-web/                      # PC Web 端（Vue 3）
│   └── bid-mobile/                   # 移动端（uni-app）
├── infra/
│   ├── k8s/                          # Kubernetes 配置
│   ├── docker/                       # Dockerfile
│   ├── nginx/                        # 网关配置
│   └── monitoring/                   # Prometheus/Grafana 配置
├── docs/                             # 技术文档
└── scripts/                          # 运维脚本
```

### 3.2 Python 服务内部结构

每个 Python 微服务遵循统一目录结构：

```
{service-name}/
├── app/
│   ├── api/                # FastAPI 路由层
│   │   └── v1/             # API 版本（必须版本化）
│   ├── core/               # 核心配置（settings, security）
│   ├── models/             # Pydantic 数据模型（请求/响应）
│   ├── schemas/            # 数据库 ORM 模型
│   ├── services/           # 业务逻辑层
│   ├── repositories/       # 数据访问层
│   ├── ai/                 # AI 能力封装（LLM/RAG/OCR）
│   └── utils/              # 工具函数
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── Dockerfile
└── README.md
```

### 3.3 Java 服务内部结构

```
{service-name}/
├── src/
│   ├── main/
│   │   └── java/com/bidai/{service}/
│   │       ├── controller/     # REST 控制器
│   │       ├── service/        # 业务逻辑
│   │       ├── repository/     # 数据访问（JPA Repository）
│   │       ├── entity/         # JPA 实体
│   │       ├── dto/            # 数据传输对象
│   │       ├── config/         # Spring 配置
│   │       └── exception/      # 异常处理
│   └── test/
├── build.gradle
├── Dockerfile
└── README.md
```

---

## 4. 开发命令速查

### 4.1 Python 服务

```bash
# 安装依赖
poetry install

# 启动开发服务器
uvicorn app.main:app --reload --port 8000

# 运行测试
pytest tests/ -v --cov=app --cov-report=html

# 代码格式化
black app/ && ruff check app/ --fix

# 类型检查
mypy app/

# 启动 Celery Worker
celery -A app.worker worker --loglevel=info

# 生成数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

### 4.2 Java 服务

```bash
# 编译
./gradlew build

# 运行测试
./gradlew test

# 启动服务
./gradlew bootRun

# 生成 JAR
./gradlew bootJar
```

### 4.3 前端

```bash
# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 类型检查
pnpm type-check

# 构建
pnpm build

# Lint 检查
pnpm lint
```

### 4.4 基础设施

```bash
# 启动本地开发依赖（PG/Redis/Milvus/ES/MinIO）
docker compose -f infra/docker/docker-compose.dev.yml up -d

# 部署到 K8s（开发环境）
kubectl apply -f infra/k8s/dev/

# 查看服务日志
kubectl logs -f deployment/{service-name} -n bid-ai
```

---

## 5. 代码规范

### 5.1 通用规范

- **语言**：所有注释、变量名、函数名使用英文；用户界面文案使用中文
- **提交信息**：遵循 Conventional Commits，格式为 `type(scope): 描述`
  - 类型：`feat` / `fix` / `refactor` / `test` / `docs` / `chore`
  - 示例：`feat(bid-writer): add three-way routing for section generation`
- **分支命名**：`feature/{issue-id}-{brief-description}` / `fix/{issue-id}-{brief-description}`
- **禁止**：直接向 `main` / `master` 分支推送代码，必须经过 PR + Code Review

### 5.2 Python 规范

```python
# ✅ 正确：函数必须有类型注解
async def generate_section(
    section_id: str,
    constraints: list[str],
    knowledge_refs: list[str],
) -> SectionGenerateResponse:
    ...

# ❌ 错误：无类型注解
def generate_section(section_id, constraints, knowledge_refs):
    ...

# ✅ 正确：使用 Pydantic 模型定义请求/响应
class SectionGenerateRequest(BaseModel):
    section_type: Literal["TEMPLATE", "DATA_FILL", "FREE_NARRATIVE"]
    constraints: list[str]
    knowledge_refs: list[str]
    style: str = "professional"
    length_hint: Literal["brief", "standard", "detailed"] = "standard"
    extra_instruction: str | None = None

# ✅ 正确：异常处理必须细化
try:
    result = await llm_client.generate(prompt)
except LLMTimeoutError as e:
    logger.warning("LLM timeout, falling back to cache", extra={"section_id": section_id})
    raise ServiceUnavailableError("生成超时，请稍后重试") from e
except LLMAPIError as e:
    logger.error("LLM API error", exc_info=True)
    raise InternalServerError("AI 服务异常") from e
```

### 5.3 TypeScript / Vue 规范

```typescript
// ✅ 正确：使用 Composition API + <script setup>
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { BidSection } from '@/types/bid'

interface Props {
  sectionId: string
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readOnly: false,
})

// ✅ 正确：API 调用通过封装的 service 层，不直接使用 axios
import { bidWriterService } from '@/services/bidWriter'

const isGenerating = ref(false)
const handleGenerate = async () => {
  isGenerating.value = true
  try {
    await bidWriterService.generateSection(props.sectionId)
  } finally {
    isGenerating.value = false
  }
}
</script>

// ❌ 错误：直接在组件中使用 axios
import axios from 'axios'
const res = await axios.post('/api/v1/bids/...')  // 禁止
```

### 5.4 Java 规范

```java
// ✅ 正确：使用 Record 作为 DTO（Java 21）
public record ProjectCreateRequest(
    @NotBlank String name,
    @NotBlank String client,
    @Positive BigDecimal estimatedAmount,
    @NotNull LocalDate tenderDate
) {}

// ✅ 正确：Service 层异常处理
@Service
@RequiredArgsConstructor
public class ProjectService {
    private final ProjectRepository repository;

    public ProjectDTO createProject(ProjectCreateRequest request) {
        if (repository.existsByNameAndClient(request.name(), request.client())) {
            throw new BusinessException("同客户下已存在同名项目");
        }
        // ...
    }
}

// ❌ 错误：在 Controller 层写业务逻辑
```

---

## 6. 架构规范

### 6.1 微服务通信原则

- **同步调用**：使用 HTTP/REST（通过 Kong 网关路由），不使用 gRPC（现阶段）
- **异步任务**：耗时操作（OCR、LLM 生成、串标分析）必须通过 Celery 任务队列异步处理
- **服务间不直连数据库**：服务 A 需要服务 B 的数据，必须通过 B 的 API，不得跨库查询
- **超时设置**：所有服务间 HTTP 调用必须设置超时（默认 30s，LLM 生成 120s）

### 6.2 异步任务规范

```python
# ✅ 正确：耗时任务必须异步，并返回 task_id 供轮询
@router.post("/bids/{bid_id}/sections/{section_id}/generate")
async def generate_section(bid_id: str, section_id: str, request: SectionGenerateRequest):
    task = generate_section_task.delay(bid_id, section_id, request.model_dump())
    return {"task_id": task.id, "status": "pending"}

# 对应的 Celery 任务
@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)
def generate_section_task(self, bid_id: str, section_id: str, request_data: dict):
    try:
        # ... 实际生成逻辑
    except LLMAPIError as exc:
        raise self.retry(exc=exc)
```

### 6.3 LLM 降级策略

当私有化 LLM 不可用时，遵循以下降级链：

```
私有化模型（Qwen/DeepSeek） → CPU 推理降级模型 → 外部 API（仅非敏感内容）→ 返回错误
```

**敏感内容判定**：凡包含以下信息的内容，禁止发送至外部 API：
- 报价金额、成本数据
- 公司资质证书编号
- 人员身份信息
- 客户名称及联系方式
- 历史中标数据

### 6.4 RAG 检索规范

```python
# ✅ 正确：混合检索，向量 + 全文并行，结果重排序
class HybridRetriever:
    async def retrieve(self, query: str, top_k: int = 10) -> list[KnowledgeChunk]:
        # 1. 查询增强（同义词扩展、行业术语补全）
        enhanced_query = await self.query_enhancer.enhance(query)

        # 2. 并行检索
        vector_results, fulltext_results = await asyncio.gather(
            self.milvus_client.search(enhanced_query, top_k=50),
            self.es_client.search(enhanced_query, top_k=50),
        )

        # 3. 结果融合 + Cross-Encoder 重排序
        merged = self._deduplicate(vector_results + fulltext_results)
        reranked = await self.reranker.rerank(query, merged)

        return reranked[:top_k]

# ❌ 错误：仅做向量检索，丢失关键词匹配能力
results = milvus.search(query_embedding, top_k=10)  # 不完整
```

---

## 7. AI 能力层开发规范

### 7.1 Prompt 工程规范

- **所有 Prompt 模板**必须存放在 `app/ai/prompts/` 目录，使用 `.jinja2` 文件管理
- **禁止**将 Prompt 硬编码在业务代码中
- **Prompt 版本管理**：每次修改 Prompt 须更新版本号，记录在 `PROMPT_CHANGELOG.md`
- **必须包含的要素**：系统角色、任务描述、输出格式（JSON Schema）、示例

```jinja2
{# app/ai/prompts/constraint_extraction_v2.jinja2 #}
你是一位资深投标专家，擅长从招标文件中精准提取关键约束条件。

任务：从以下招标文件片段中，提取并分类所有约束条件。

分类标准：
1. 合规要求（COMPLIANCE）：不满足即废标的刚性条件
2. 内容要求（CONTENT）：标书必须包含的材料和格式规定
3. 写作引导（GUIDE）：评分标准、差异化亮点、项目背景信息

输出格式（严格 JSON，不要输出任何额外文字）：
{{ output_schema | tojson(indent=2) }}

招标文件片段：
{{ chunk }}
```

### 7.2 LLM 调用规范

```python
# ✅ 正确：统一通过 LLMClient 封装调用，含重试、超时、日志
class LLMClient:
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str = "default",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: ResponseFormat | None = None,
    ) -> LLMResponse:
        # 自动处理：私有模型优先 → 降级 → 超时 → 重试 → 审计日志
        ...

# ❌ 错误：直接调用 OpenAI SDK 或 requests
import openai
response = openai.chat.completions.create(...)  # 禁止直接使用
```

### 7.3 文档处理规范

```python
# 文件类型路由（必须严格遵守）
FILE_PROCESSORS = {
    "application/pdf": {
        "scanned": PaddleOCRProcessor,   # 扫描件 PDF
        "digital": PyMuPDFProcessor,     # 数字文本 PDF
    },
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": PythonDocxProcessor,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": OpenpyxlProcessor,
}

# 置信度门槛（不得擅自修改）
CONFIDENCE_THRESHOLDS = {
    "auto_ingest": 0.85,   # 自动入库
    "manual_confirm": 0.60, # 人工确认后入库
    "reject": 0.0,          # 低于 0.60 标注异常
}
```

### 7.4 向量化规范

- **Embedding 模型**：统一使用项目配置的模型，不得在代码中硬编码模型名称
- **Chunk 策略**：正文按 512 tokens 切块，overlap 50 tokens；表格整体保留不切块
- **向量维度**：1536 维（与 Milvus Collection Schema 保持一致）
- **批量入库**：单次批量 embedding 不超过 100 条，避免内存溢出

---

## 8. 数据层规范

### 8.1 数据库规范

```sql
-- ✅ 正确：所有表必须包含以下基础字段
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,           -- 软删除，禁止物理删除业务数据
    created_by  VARCHAR(64) NOT NULL,  -- 操作人 user_id
    -- 业务字段...
);

-- ✅ 正确：敏感字段加密存储
-- 使用 pgcrypto 扩展，应用层加密优先
ALTER TABLE personnel ADD COLUMN id_number_encrypted BYTEA;  -- 身份证号加密存储

-- ❌ 错误：直接存储敏感信息明文
ALTER TABLE personnel ADD COLUMN id_number VARCHAR(18);  -- 禁止
```

**数据库操作原则**：
- 所有 DDL 变更必须通过迁移脚本（Alembic / Flyway），不得手动执行
- 禁止在应用代码中使用 `DROP TABLE` / `TRUNCATE`
- 查询必须使用参数化查询，禁止字符串拼接 SQL
- 大查询必须加索引，上线前经过 `EXPLAIN ANALYZE` 验证

### 8.2 Redis 使用规范

```python
# Key 命名规范：{service}:{entity}:{id}:{field}
CACHE_KEYS = {
    "session": "auth:session:{user_id}",
    "bid_draft": "bid:draft:{bid_id}",
    "llm_result": "ai:llm_result:{task_id}",
    "kb_health": "kb:health_score",
}

# TTL 规范（必须设置，禁止永久缓存）
TTL_CONFIG = {
    "session": 8 * 3600,       # 8小时
    "bid_draft": 24 * 3600,    # 24小时
    "llm_result": 1 * 3600,    # 1小时
    "kb_health": 7 * 24 * 3600, # 7天
}
```

### 8.3 MinIO 文件存储规范

```
Bucket 命名规范：
  bid-raw-files/        # 原始上传文件（招标文件、素材）
  bid-exports/          # 导出的标书文件
  kb-documents/         # 知识库原始文档
  audit-logs/           # 审计日志归档

文件路径规范：
  {bucket}/{year}/{month}/{project_id}/{uuid}.{ext}
  例：bid-raw-files/2026/05/proj_abc123/tender_doc_uuid.pdf

访问控制：
  - 应用通过 Pre-signed URL 提供文件下载（有效期 15 分钟）
  - 禁止将 Bucket 设为公开访问
  - 导出文件下载须记录审计日志
```

---

## 9. 安全规范

> **安全是系统核心约束，任何功能开发不得绕过安全机制。**

### 9.1 认证与授权

- 所有 API 请求必须携带有效 JWT Token（除登录、健康检查接口外）
- Token 由 `auth-service` 签发，有效期 8 小时，支持 Refresh Token（30 天）
- 高权限操作（文件批量导出、用户管理、系统配置）须二次 MFA 验证
- RBAC 权限检查必须在 Service 层实现，不得仅依赖前端路由控制

```python
# ✅ 正确：Service 层做权限校验
class BidExportService:
    async def export_bid(self, bid_id: str, user: CurrentUser) -> ExportResult:
        bid = await self.bid_repo.get_by_id(bid_id)
        if not user.has_permission("bid:export", resource_owner=bid.project_id):
            raise ForbiddenError("无导出权限")
        # ... 导出逻辑
```

### 9.2 数据传输安全

- 所有 HTTP 通信强制使用 HTTPS（TLS 1.3）
- API 请求必须包含签名（`X-Signature` Header），防重放攻击
- 跨服务内部调用使用 mTLS 或内部 Token

### 9.3 LLM 数据安全

```python
# ✅ 正确：发送给 LLM 前必须做敏感信息检测
class SensitiveDataGuard:
    SENSITIVE_PATTERNS = [
        r"\d{18}",           # 身份证号
        r"1[3-9]\d{9}",      # 手机号
        r"\d{6,}元",         # 金额（明文）
    ]

    def check_before_llm_call(self, text: str, target: LLMTarget) -> None:
        if target == LLMTarget.EXTERNAL_API:
            for pattern in self.SENSITIVE_PATTERNS:
                if re.search(pattern, text):
                    raise SensitiveDataViolationError(
                        "检测到敏感数据，禁止发送至外部 LLM API"
                    )
```

### 9.4 文件安全

- 上传文件必须做类型白名单校验（`.pdf` / `.docx` / `.xlsx` / `.jpg` / `.png`）
- 文件大小限制：单文件不超过 100MB
- 上传后存储至 MinIO，不得直接保存至应用服务器本地磁盘
- 导出文件必须嵌入动态水印：`用户ID + 导出时间 + 项目编号`

### 9.5 审计日志

以下操作必须写入审计日志（不可绕过）：

```python
AUDIT_REQUIRED_ACTIONS = [
    "user.login", "user.logout", "user.create", "user.permission_change",
    "bid.create", "bid.export", "bid.delete",
    "knowledge.upload", "knowledge.delete",
    "document.export",
    "collusion.analyze",
    "system.config_change",
]
```

---

## 10. API 设计规范

### 10.1 URL 规范

```
版本前缀：   /api/v1/
资源命名：   复数名词，小写，连字符分隔
示例：
  POST   /api/v1/projects
  GET    /api/v1/projects/{id}
  POST   /api/v1/projects/{id}/bids
  POST   /api/v1/bids/{id}/sections/{sid}/generate  （动作用动词后缀）
  GET    /api/v1/bids/{id}/check                    （动作用动词后缀）
```

### 10.2 统一响应格式

```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { ... },
  "request_id": "req_abc123"   // 用于链路追踪
}

// 错误响应
{
  "code": 40001,               // 业务错误码（非 HTTP 状态码）
  "message": "项目名称已存在",
  "detail": "...",             // 开发调试信息（生产环境可隐藏）
  "request_id": "req_abc123"
}

// 异步任务响应
{
  "code": 202,
  "data": {
    "task_id": "task_xyz789",
    "status": "pending",
    "poll_url": "/api/v1/tasks/task_xyz789"
  }
}
```

### 10.3 错误码规范

```
1xxxx  系统错误
2xxxx  认证/权限错误
3xxxx  输入参数错误
4xxxx  业务逻辑错误
5xxxx  AI 服务错误

示例：
  10001  内部服务错误
  20001  Token 无效或过期
  20002  权限不足
  30001  必填参数缺失
  40001  资源已存在
  50001  LLM 生成失败
  50002  LLM 生成超时
```

### 10.4 分页规范

```python
# 列表接口统一使用游标分页（大数据量）或偏移分页（小数据量）
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
```

---

## 11. 测试规范

### 11.1 测试分层要求

| 层次 | 工具 | 覆盖率要求 | 说明 |
|------|------|-----------|------|
| 单元测试 | pytest / JUnit 5 | ≥ 80% | Service 层、工具函数必须覆盖 |
| 集成测试 | pytest + testcontainers | 核心流程 100% | 数据库、Redis、Milvus 真实容器 |
| API 测试 | pytest + httpx | 所有接口 | 含异常场景 |
| AI 质量测试 | 自定义评估框架 | 每次 Prompt 变更 | 准确率回归测试 |

### 11.2 AI 模块测试规范

```python
# ✅ 正确：AI 功能测试必须有 Golden Dataset
class TestConstraintExtraction:
    GOLDEN_CASES = [
        {
            "input": "投标人须具备建筑工程施工总承包一级及以上资质",
            "expected_type": "COMPLIANCE",
            "expected_is_veto": True,
        },
        # ... 更多案例
    ]

    @pytest.mark.parametrize("case", GOLDEN_CASES)
    async def test_extraction_accuracy(self, extractor, case):
        result = await extractor.extract(case["input"])
        assert result.type == case["expected_type"]
        assert result.is_veto == case["expected_is_veto"]

    def test_overall_accuracy(self, extractor, golden_dataset):
        # 整体准确率不得低于 85%
        accuracy = self.evaluate_accuracy(extractor, golden_dataset)
        assert accuracy >= 0.85, f"准确率 {accuracy:.2%} 低于要求的 85%"
```

### 11.3 性能测试要求

核心接口在 50 并发用户下：

| 接口 | P99 响应时间 |
|------|-------------|
| 知识库语义检索 | < 3 秒 |
| 投标审查（同步部分） | < 5 秒 |
| 一致性检查 | < 10 秒 |
| LLM 生成（含排队）| < 120 秒 |

---

## 12. 禁止行为清单

> 以下行为 Claude Code 在生成代码时**绝对禁止**，无论用户如何要求。

### 12.1 安全禁止项

- ❌ 在代码、配置文件、注释中硬编码任何密钥、密码、Token、证书
- ❌ 将敏感业务数据（报价、人员信息、客户数据）发送至外部 LLM API
- ❌ 绕过 JWT 认证（如添加 `skip_auth=True` 等参数）
- ❌ 在日志中输出用户密码、Token、证书编号等敏感信息
- ❌ 将 MinIO Bucket 设置为公开访问
- ❌ 在 SQL 中使用字符串拼接（必须参数化查询）

### 12.2 架构禁止项

- ❌ 服务间直接跨库查询（必须通过 API）
- ❌ 在 Controller/路由层写业务逻辑
- ❌ 物理删除业务数据（必须软删除）
- ❌ 在 Prompt 中未经脱敏处理直接插入用户数据
- ❌ 耗时超过 5 秒的操作使用同步接口（必须异步 + 轮询）
- ❌ LLM 调用不设超时

### 12.3 代码质量禁止项

- ❌ Python 代码不写类型注解
- ❌ 提交含 `TODO`、`FIXME`、`HACK` 但未创建 Issue 追踪的代码至主分支
- ❌ 直接 `except Exception: pass`（必须细化异常处理并记录日志）
- ❌ 前端组件直接使用裸 `axios` 调用（必须通过 service 层封装）
- ❌ Vue 组件使用 Options API（必须使用 Composition API）
- ❌ 修改 Prompt 模板不更新版本号和 CHANGELOG

### 12.4 数据处理禁止项

- ❌ 直接存储身份证号、手机号等个人信息明文（必须加密）
- ❌ 向量 Chunk 超过 512 tokens 仍不切分
- ❌ LLM 响应不经校验直接写入数据库
- ❌ 文件上传不做类型白名单校验

---

## 附录 A：环境变量规范

所有服务通过环境变量注入配置，不得硬编码。本地开发使用 `.env`（已加入 `.gitignore`）。

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/bidai

# Redis
REDIS_URL=redis://localhost:6379/0

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Elasticsearch
ES_URL=http://localhost:9200

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM（私有化模型）
LLM_PRIVATE_BASE_URL=http://gpu-node-1:8080/v1
LLM_PRIVATE_MODEL=qwen2.5-72b-instruct
LLM_PRIVATE_TIMEOUT=120

# LLM（外部 API 降级，仅非敏感场景）
LLM_EXTERNAL_API_KEY=sk-...         # 通过 K8s Secret 注入，禁止提交到 Git
LLM_EXTERNAL_MODEL=gpt-4o

# 安全
JWT_SECRET_KEY=...                   # 通过 K8s Secret 注入
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# 应用
APP_ENV=development                  # development / staging / production
LOG_LEVEL=INFO
```

---

## 附录 B：关键数据模型速查

### 核心实体关系

```
PROJECT (投标项目)
  ├── DOCUMENT (关联文档：招标文件、素材)
  │     └── CHUNK (文本分块)
  │           └── EMBEDDING (向量)
  ├── BID (标书)
  │     ├── SECTION (章节)
  │     ├── VARIABLE (全局变量)
  │     └── CHECK_REPORT (一致性检查报告)
  └── BID_RECORD (投标结果记录)

KNOWLEDGE_BASE (知识库)
  ├── QUALIFICATION (资质库)
  ├── PERFORMANCE (业绩库)
  ├── PERSONNEL (人员库)
  └── SOLUTION_TEMPLATE (方案模板库)
```

---

*本规范随项目演进持续更新，重大变更须在架构评审后修订版本号。*  
*最后更新：2026-04-17 | 文档负责人：架构组*
