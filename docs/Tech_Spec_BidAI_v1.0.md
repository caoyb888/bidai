# AI 智能投标系统 · 技术规范文档（Tech Spec）

**文档编号**：TECH-BIDAI-2026-001  
**关联方案**：TSD-BIDAI-2026-001 V1.0  
**关联 API 规范**：API-BIDAI-2026-001 V1.0  
**版本**：V1.0  
**编制日期**：2026-04-28  
**文档状态**：已审阅  
**密级**：内部保密

> **本文档定位**：在技术方案（TSD）的基础上，对所有技术决策进行细化落地，是开发团队日常编码、评审、交付的执行依据。凡方案与本规范冲突，以本规范为准，变更须经架构评审。

---

## 目录

1. [文档范围与适用对象](#1-文档范围与适用对象)
2. [整体分层架构约定](#2-整体分层架构约定)
3. [Python 服务编码规范](#3-python-服务编码规范)
4. [Java 服务编码规范](#4-java-服务编码规范)
5. [前端编码规范](#5-前端编码规范)
6. [异常处理标准](#6-异常处理标准)
7. [日志格式规范](#7-日志格式规范)
8. [安全编码要求](#8-安全编码要求)
9. [AI 能力层开发规范](#9-ai-能力层开发规范)
10. [数据层编码规范](#10-数据层编码规范)
11. [测试规范](#11-测试规范)
12. [CI/CD 与发布规范](#12-cicd-与发布规范)
13. [性能设计约定](#13-性能设计约定)
14. [配置管理规范](#14-配置管理规范)
15. [禁止行为红线清单](#15-禁止行为红线清单)
16. [附录：工具链版本锁定表](#16-附录工具链版本锁定表)

---

## 1. 文档范围与适用对象

### 1.1 适用对象

| 角色 | 使用方式 |
|---|---|
| 后端开发工程师（Python / Java） | 日常编码、代码评审依据 |
| 前端开发工程师 | 组件规范、接口调用约定 |
| AI 工程师 | Prompt 工程、LLM 调用、向量化规范 |
| 测试工程师 | 测试分层要求、质量门禁 |
| 技术 Lead / 架构师 | 代码评审检查标准 |

### 1.2 核心原则

本规范基于以下四条核心原则制定，所有技术决策均需对齐：

1. **AI 辅助、人工主导** — AI 生成内容必须保留人工审核节点，不得全自动写入生产数据
2. **数据安全优先** — 敏感数据不出内网，任何安全规范不得以开发效率为由绕过
3. **可观测性内建** — 日志、链路追踪、指标监控是基础设施，不是事后补充
4. **显式优于隐式** — 类型注解、错误处理、权限校验必须显式声明，不依赖框架隐式行为

---

## 2. 整体分层架构约定

### 2.1 系统五层模型

```
┌─────────────────────────────────────────────────────┐
│  接入层   Kong API 网关 / Nginx 负载均衡               │
│           鉴权、限流、路由、TLS 终止                    │
├─────────────────────────────────────────────────────┤
│  接口层   FastAPI Router / Spring MVC Controller     │
│           参数校验、序列化/反序列化、统一响应包装          │
│           ⛔ 禁止在此层写业务逻辑                        │
├─────────────────────────────────────────────────────┤
│  业务层   Service                                    │
│           业务规则、权限校验、事务边界、编排调用            │
│           ✅ 所有权限校验必须在此层完成                   │
├─────────────────────────────────────────────────────┤
│  数据访问层  Repository / DAO                         │
│           数据库 CRUD、缓存读写、外部存储交互             │
│           ⛔ 禁止包含业务判断逻辑                        │
├─────────────────────────────────────────────────────┤
│  AI 能力层  LLMClient / RAGEngine / OCRProcessor     │
│           LLM 调用、向量检索、文档解析封装                │
│           ✅ 统一通过抽象接口调用，不直接依赖具体 SDK        │
└─────────────────────────────────────────────────────┘
         ↕ 跨层依赖方向：只允许上层调用下层
```

### 2.2 跨服务通信约定

| 通信场景 | 协议 | 规范 |
|---|---|---|
| 客户端 → 服务 | HTTPS / REST | 经 Kong 网关路由，携带 JWT |
| 服务 → 服务（同步） | HTTP / REST | 内部 Service Token，30s 超时，3 次重试 |
| 服务 → AI 能力（异步） | Celery + Redis | 任务状态持久化到 `ai_task.ai_tasks` 表 |
| 服务内 Cache | Redis | Key 命名规范见第 10 章 |

**严格禁止**：服务 A 直接读写服务 B 的数据库。所有跨服务数据访问必须通过 B 对外暴露的 REST API。

### 2.3 项目目录约定

**Python 服务统一目录结构（每个服务必须遵守）：**

```
{service-name}/
├── app/
│   ├── api/
│   │   └── v1/                  # 路由层，仅做参数校验和响应包装
│   │       ├── __init__.py
│   │       ├── deps.py           # 依赖注入（当前用户、数据库连接等）
│   │       └── endpoints/        # 每个资源一个文件
│   ├── core/
│   │   ├── config.py             # 统一 Settings（Pydantic BaseSettings）
│   │   ├── security.py           # JWT 解析、权限装饰器
│   │   ├── exceptions.py         # 自定义异常类定义
│   │   └── logging.py            # 日志配置
│   ├── models/                   # Pydantic 请求/响应模型
│   ├── schemas/                  # SQLAlchemy ORM 模型
│   ├── services/                 # 业务逻辑层（核心）
│   ├── repositories/             # 数据访问层
│   ├── ai/
│   │   ├── llm_client.py         # LLM 统一客户端
│   │   ├── rag_engine.py         # RAG 混合检索引擎
│   │   ├── ocr_processor.py      # OCR 文档处理
│   │   └── prompts/              # Jinja2 Prompt 模板（.jinja2）
│   └── utils/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── migrations/                   # Alembic 迁移脚本
├── pyproject.toml
├── Dockerfile
└── README.md
```

**Java 服务统一目录结构：**

```
{service-name}/src/main/java/com/bidai/{service}/
├── controller/      # REST 控制器，仅做参数绑定和响应包装
├── service/         # 业务逻辑（接口 + 实现分离）
│   ├── {Name}Service.java         # 接口
│   └── impl/{Name}ServiceImpl.java # 实现
├── repository/      # JPA Repository 接口
├── entity/          # JPA 实体（@Entity）
├── dto/             # 请求/响应 DTO（使用 Record）
├── config/          # Spring 配置类
├── exception/       # 自定义异常 + 全局异常处理器
├── security/        # JWT 过滤器、权限注解
└── utils/           # 工具类
```

---

## 3. Python 服务编码规范

### 3.1 语言与工具版本

| 工具 | 版本要求 | 说明 |
|---|---|---|
| Python | 3.11+ | 必须使用 3.11+，利用 `match` 语句和性能优化 |
| FastAPI | 0.110+ | 版本锁定，升级需架构评审 |
| Pydantic | v2（内置于 FastAPI） | 使用 v2 语法，禁止混用 v1 |
| mypy | 严格模式（`--strict`） | CI 必须通过 mypy 检查 |
| Ruff | 最新稳定版 | 替代 flake8，lint 检查 |
| Black | line-length=120 | 代码格式化，CI 强制执行 |

### 3.2 类型注解规范

所有函数和方法**必须**包含完整类型注解，包括参数和返回值。无类型注解的 PR 不得合并。

```python
# ✅ 正确：完整类型注解
async def generate_section(
    section_id: str,
    bid_id: str,
    constraints: list[str],
    knowledge_refs: list[str],
    style: Literal["professional", "concise", "detailed"] = "professional",
    extra_instruction: str | None = None,
) -> SectionGenerateResponse:
    ...

# ✅ 正确：使用 TypeAlias 简化复杂类型
type ConstraintList = list[Constraint]
type KnowledgeRefMap = dict[str, KnowledgeChunk]

# ❌ 错误：无类型注解（PR 将被拒绝）
def generate_section(section_id, constraints, knowledge_refs):
    ...

# ❌ 错误：使用 Any（除非有充分理由并添加注释）
from typing import Any
def process(data: Any) -> Any:  # 禁止无故使用 Any
    ...
```

### 3.3 数据模型规范

**请求/响应模型**使用 Pydantic v2 `BaseModel`，数据库模型使用 SQLAlchemy ORM：

```python
# ✅ 正确：请求模型，使用 Field 添加校验和描述
class SectionGenerateRequest(BaseModel):
    section_type: Literal["TEMPLATE", "DATA_FILL", "FREE_NARRATIVE"]
    constraints: list[str] = Field(
        default_factory=list,
        description="需覆盖的约束编号列表",
        examples=[["C001", "C005"]],
    )
    knowledge_refs: list[UUID] = Field(default_factory=list)
    style: Literal["professional", "concise", "detailed"] = "professional"
    length_hint: Literal["brief", "standard", "detailed"] = "standard"
    extra_instruction: str | None = Field(
        default=None,
        max_length=500,
        description="额外生成指令，最多 500 字",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,   # 自动去除字符串首尾空格
        str_min_length=0,
    )

# ✅ 正确：响应模型，所有字段显式声明
class SectionGenerateResponse(BaseModel):
    section_id: UUID
    content: str
    word_count: int
    constraint_coverage: ConstraintCoverage
    confidence: float = Field(ge=0.0, le=1.0)
    references: list[KnowledgeReference] = Field(default_factory=list)
```

### 3.4 异步编程规范

```python
# ✅ 正确：所有 I/O 操作使用 async/await
async def get_bid_with_sections(bid_id: UUID) -> BidWithSections:
    async with get_db_session() as session:
        bid = await session.get(Bid, bid_id)
        if bid is None:
            raise ResourceNotFoundError(f"Bid {bid_id} not found")
        await session.refresh(bid, ["sections"])  # 显式加载关联
    return BidWithSections.model_validate(bid)

# ✅ 正确：并行 I/O 使用 asyncio.gather
async def hybrid_retrieve(query: str) -> list[KnowledgeChunk]:
    vector_results, fulltext_results = await asyncio.gather(
        milvus_client.search(query, top_k=50),
        es_client.search(query, top_k=50),
        return_exceptions=False,   # 任一失败则整体失败
    )
    return deduplicate_and_rerank(vector_results + fulltext_results)

# ❌ 错误：在 async 函数中使用同步阻塞调用
async def bad_example():
    time.sleep(5)          # 阻塞事件循环，严格禁止
    requests.get(url)      # 同步 HTTP，严格禁止（使用 httpx.AsyncClient）
```

### 3.5 依赖注入规范

使用 FastAPI 的 `Depends` 机制统一注入依赖，不得在业务层直接实例化外部客户端：

```python
# app/api/v1/deps.py
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    payload = verify_jwt_token(token)   # 失败抛出 AuthenticationError
    user = await user_repo.get_by_id(db, payload.sub)
    if user is None or not user.is_active:
        raise AuthenticationError("用户不存在或已禁用")
    return CurrentUser(
        id=user.id,
        username=user.username,
        roles=user.roles,
        permissions=user.permissions,
    )

# app/api/v1/endpoints/bids.py
@router.post("/{bid_id}/sections/{section_id}/generate")
async def generate_section_endpoint(
    bid_id: UUID,
    section_id: UUID,
    request: SectionGenerateRequest,
    current_user: CurrentUser = Depends(get_current_user),   # 注入当前用户
    bid_service: BidWriterService = Depends(get_bid_service), # 注入服务
) -> CommonResponse[SectionGenerateResponse | AsyncTaskResponse]:
    return await bid_service.generate_section(bid_id, section_id, request, current_user)
```

### 3.6 命名规范

| 类型 | 风格 | 示例 |
|---|---|---|
| 变量、函数、模块 | `snake_case` | `bid_id`, `generate_section`, `bid_writer` |
| 类、Pydantic 模型 | `PascalCase` | `SectionGenerateRequest`, `BidWriterService` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE`, `LLM_TIMEOUT_SECONDS` |
| 私有方法 | `_leading_underscore` | `_validate_constraints` |
| 类型别名 | `PascalCase` | `ConstraintList`, `TaskStatusMap` |
| 文件名 | `snake_case` | `bid_writer_service.py`, `llm_client.py` |

---

## 4. Java 服务编码规范

### 4.1 语言与工具版本

| 工具 | 版本要求 | 说明 |
|---|---|---|
| Java | 21（LTS） | 使用 Record、Pattern Matching、Virtual Threads |
| Spring Boot | 3.2+ | 版本锁定，升级需架构评审 |
| Gradle | 8.x | 禁止使用 Maven |
| Checkstyle | Google Java Style | CI 强制执行 |

### 4.2 Controller 层规范

Controller 只做三件事：参数绑定、调用 Service、包装响应。**禁止在 Controller 写任何业务判断**。

```java
// ✅ 正确：Controller 简洁，业务逻辑全在 Service 层
@RestController
@RequestMapping("/api/v1/projects")
@RequiredArgsConstructor
@Tag(name = "项目管理")
public class ProjectController {

    private final ProjectService projectService;

    @PostMapping
    @Operation(summary = "创建投标项目")
    @PreAuthorize("hasPermission('project:create')")   // 声明式权限
    public ResponseEntity<CommonResponse<ProjectDTO>> createProject(
            @RequestBody @Valid ProjectCreateRequest request,
            @AuthenticationPrincipal CurrentUser currentUser
    ) {
        ProjectDTO result = projectService.createProject(request, currentUser);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(CommonResponse.success(result));
    }
}

// ❌ 错误：Controller 中写业务逻辑
@PostMapping
public ResponseEntity<?> createProject(@RequestBody ProjectCreateRequest req) {
    if (projectRepo.existsByName(req.name())) {   // ❌ 业务逻辑不在 Controller
        return ResponseEntity.badRequest().body("已存在");
    }
    // ...
}
```

### 4.3 DTO 与 Record 规范

使用 Java 21 Record 作为 DTO，不使用 Lombok `@Data`（Record 自带不可变性和 `equals/hashCode`）：

```java
// ✅ 正确：使用 Record 定义请求 DTO
public record ProjectCreateRequest(
    @NotBlank(message = "项目名称不能为空")
    @Size(max = 256, message = "项目名称不超过256字符")
    String name,

    @NotBlank(message = "客户名称不能为空")
    String client,

    @NotNull(message = "投标截止日期不能为空")
    @Future(message = "投标截止日期必须是未来日期")
    LocalDate tenderDate,

    @DecimalMin(value = "0", inclusive = false, message = "预算金额必须大于0")
    BigDecimal budgetAmount,

    String industry,
    String region
) {}

// ✅ 正确：响应 DTO 也使用 Record
public record ProjectDTO(
    UUID id,
    String name,
    String client,
    EntityStatus status,
    LocalDate tenderDate,
    BigDecimal budgetAmount,
    Instant createdAt
) {
    // 静态工厂方法从 Entity 转换
    public static ProjectDTO from(BidProject entity) {
        return new ProjectDTO(
            entity.getId(), entity.getName(), entity.getClient(),
            entity.getStatus(), entity.getTenderDate(),
            entity.getBudgetAmount(), entity.getCreatedAt()
        );
    }
}
```

### 4.4 Service 层规范

```java
// ✅ 正确：Service 接口 + 实现分离，业务逻辑清晰
public interface ProjectService {
    ProjectDTO createProject(ProjectCreateRequest request, CurrentUser operator);
    ProjectDTO getProjectById(UUID id, CurrentUser operator);
}

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)   // 默认只读事务，写操作方法单独标注
public class ProjectServiceImpl implements ProjectService {

    private final ProjectRepository projectRepository;
    private final BidRepository bidRepository;

    @Override
    @Transactional   // 写操作显式开启读写事务
    public ProjectDTO createProject(ProjectCreateRequest request, CurrentUser operator) {
        // 1. 业务校验（必须在 Service 层）
        if (projectRepository.existsByNameAndClient(request.name(), request.client())) {
            throw new BusinessException(ErrorCode.RESOURCE_ALREADY_EXISTS,
                "同客户下已存在同名项目：" + request.name());
        }

        // 2. 实体构建
        var project = BidProject.builder()
            .name(request.name())
            .client(request.client())
            .tenderDate(request.tenderDate())
            .budgetAmount(request.budgetAmount())
            .status(EntityStatus.DRAFT)
            .createdBy(operator.getId().toString())
            .build();

        // 3. 持久化
        project = projectRepository.save(project);

        // 4. 联动创建空白标书（同一事务）
        bidRepository.save(Bid.createEmpty(project.getId(), operator.getId()));

        return ProjectDTO.from(project);
    }
}
```

### 4.5 命名规范

| 类型 | 风格 | 示例 |
|---|---|---|
| 包名 | 全小写，点分隔 | `com.bidai.project.service` |
| 类、接口、枚举 | `PascalCase` | `ProjectService`, `EntityStatus` |
| 方法、变量 | `camelCase` | `createProject`, `bidAmount` |
| 常量 | `UPPER_SNAKE_CASE` | `MAX_PAGE_SIZE`, `JWT_EXPIRE_HOURS` |
| 数据库列 | `snake_case`（由 JPA 命名策略映射）| `tender_date` → `tenderDate` |

---

## 5. 前端编码规范

### 5.1 组件规范

所有组件必须使用 `<script setup lang="ts">` + Composition API，**禁止 Options API**：

```typescript
// ✅ 正确：Composition API + 完整类型
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { BidSection } from '@/types/bid'
import { bidWriterService } from '@/services/bidWriter'
import { usePermission } from '@/composables/usePermission'

interface Props {
  sectionId: string
  bidId: string
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readOnly: false,
})

const emit = defineEmits<{
  saved: [section: BidSection]
  error: [message: string]
}>()

const { hasPermission } = usePermission()
const canEdit = computed(() => hasPermission('bid:edit') && !props.readOnly)

const isGenerating = ref(false)
const section = ref<BidSection | null>(null)

const handleGenerate = async (): Promise<void> => {
  if (!canEdit.value) return
  isGenerating.value = true
  try {
    const result = await bidWriterService.generateSection(props.bidId, props.sectionId)
    section.value = result
    emit('saved', result)
  } catch (error) {
    // 统一错误处理，见第 6 章
    emit('error', getErrorMessage(error))
  } finally {
    isGenerating.value = false
  }
}
</script>
```

### 5.2 Service 层封装

**禁止在组件中直接调用 axios**，所有 API 调用必须通过 service 层封装：

```typescript
// src/services/bidWriter.ts

import { apiClient } from '@/utils/apiClient'
import type {
  SectionGenerateRequest,
  SectionGenerateResponse,
  AsyncTaskResponse,
} from '@/types/api'

export const bidWriterService = {
  async generateSection(
    bidId: string,
    sectionId: string,
    request: SectionGenerateRequest = {}
  ): Promise<SectionGenerateResponse | AsyncTaskResponse> {
    const response = await apiClient.post<SectionGenerateResponse | AsyncTaskResponse>(
      `/bids/${bidId}/sections/${sectionId}/generate`,
      request
    )
    return response.data
  },

  async updateSection(
    bidId: string,
    sectionId: string,
    content: string,
    changeSummary?: string
  ): Promise<SectionGenerateResponse> {
    const response = await apiClient.put<SectionGenerateResponse>(
      `/bids/${bidId}/sections/${sectionId}`,
      { content, change_summary: changeSummary }
    )
    return response.data
  },
}

// src/utils/apiClient.ts — 统一 axios 封装
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import { handleApiError } from './errorHandler'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL + '/api/v1',
  timeout: 30_000,
})

// 请求拦截：自动注入 Token
apiClient.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`
  }
  return config
})

// 响应拦截：统一错误处理 + Token 刷新
apiClient.interceptors.response.use(
  (response) => response.data,   // 直接返回 data，省去外层 .data.data
  async (error) => {
    if (error.response?.status === 401) {
      await useAuthStore().refreshToken()
      return apiClient.request(error.config)  // 重试一次
    }
    throw handleApiError(error)
  }
)
```

### 5.3 状态管理规范（Pinia）

```typescript
// src/stores/auth.ts
import { defineStore } from 'pinia'
import { authService } from '@/services/auth'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(null)
  const currentUser = ref<CurrentUser | null>(null)
  const isLoggedIn = computed(() => !!accessToken.value)

  async function login(username: string, password: string): Promise<void> {
    const result = await authService.login({ username, password })
    accessToken.value = result.access_token
    currentUser.value = result.user
    // refresh_token 存入 httpOnly Cookie（由后端 Set-Cookie），不存 localStorage
  }

  async function refreshToken(): Promise<void> {
    const result = await authService.refresh()
    accessToken.value = result.access_token
  }

  function logout(): void {
    accessToken.value = null
    currentUser.value = null
    // 调用后端注销接口（fire and forget）
    authService.logout().catch(() => {})
  }

  return { accessToken, currentUser, isLoggedIn, login, refreshToken, logout }
})
```

### 5.4 TypeScript 严格模式要求

`tsconfig.json` 必须开启 `strict: true`，以下配置不得关闭：

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  }
}
```

---

## 6. 异常处理标准

### 6.1 异常分类体系

```
BaseAppException（所有自定义异常的基类）
├── AuthenticationError        # HTTP 401：未认证
├── AuthorizationError         # HTTP 403：权限不足
├── ResourceNotFoundError      # HTTP 404：资源不存在
├── ResourceConflictError      # HTTP 409：资源冲突
├── ValidationError            # HTTP 400：参数校验失败
├── BusinessException          # HTTP 422：业务逻辑错误
│   ├── InvalidStatusError     #   状态流转不合法
│   ├── SectionLockedError     #   章节被锁定
│   └── DocumentNotReadyError  #   文档未就绪
├── AIServiceError             # HTTP 503：AI 服务错误
│   ├── LLMTimeoutError        #   LLM 超时
│   ├── LLMUnavailableError    #   LLM 不可用
│   └── SensitiveDataError     #   敏感数据违规
└── InternalServerError        # HTTP 500：内部错误
```

### 6.2 Python 异常处理规范

```python
# app/core/exceptions.py — 异常基类定义
from dataclasses import dataclass

@dataclass
class BaseAppException(Exception):
    message: str
    error_code: int
    detail: str | None = None

    def to_response(self) -> dict:
        return {
            "code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }

class AuthenticationError(BaseAppException):
    def __init__(self, message: str = "Token 无效或已过期"):
        super().__init__(message=message, error_code=20001)

class ResourceNotFoundError(BaseAppException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} 不存在",
            error_code=40002,
            detail=f"{resource} ID={resource_id} 不存在或已删除",
        )

class LLMTimeoutError(BaseAppException):
    def __init__(self, timeout_seconds: int = 120):
        super().__init__(
            message="AI 生成超时，请稍后重试",
            error_code=50002,
            detail=f"LLM 调用超过 {timeout_seconds} 秒未响应",
        )


# ✅ 正确：细化异常，包含足够上下文
async def get_bid_section(bid_id: UUID, section_id: UUID) -> BidSection:
    section = await section_repo.get(section_id)
    if section is None:
        raise ResourceNotFoundError("章节", str(section_id))
    if section.bid_id != bid_id:
        raise AuthorizationError("无权访问该章节")
    return section

# ✅ 正确：异常链传递，保留原始错误信息
async def call_llm_with_retry(prompt: str) -> str:
    try:
        return await llm_client.generate(prompt, timeout=120)
    except asyncio.TimeoutError as e:
        logger.warning(
            "LLM timeout",
            extra={"prompt_length": len(prompt), "timeout": 120},
        )
        raise LLMTimeoutError(120) from e   # 使用 from e 保留原始异常
    except httpx.HTTPStatusError as e:
        logger.error("LLM HTTP error", exc_info=True)
        raise LLMUnavailableError(f"LLM 返回错误状态码 {e.response.status_code}") from e

# ❌ 禁止：空 except，吞掉异常
try:
    result = await some_operation()
except Exception:
    pass   # ❌ 严格禁止，必须记录日志并重新抛出或处理


# app/api/v1/exception_handlers.py — 全局异常处理器
from fastapi import Request
from fastapi.responses import JSONResponse

async def app_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc_to_http_status(exc),
        content={
            "code": exc.error_code,
            "message": exc.message,
            "detail": exc.detail if settings.DEBUG else None,
            "request_id": request.state.request_id,
        },
    )

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception",
        exc_info=True,
        extra={"request_id": request.state.request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": 10001,
            "message": "服务内部错误",
            "request_id": request.state.request_id,
        },
    )
```

### 6.3 Java 异常处理规范

```java
// exception/BusinessException.java
public class BusinessException extends RuntimeException {
    private final ErrorCode errorCode;

    public BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public int getCode() { return errorCode.getCode(); }
}

// exception/GlobalExceptionHandler.java
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    // 业务异常（可预期）
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusiness(
            BusinessException ex, HttpServletRequest request) {
        log.warn("Business exception: code={}, msg={}, path={}",
            ex.getCode(), ex.getMessage(), request.getRequestURI());
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
            .body(ErrorResponse.of(ex.getCode(), ex.getMessage(), getRequestId(request)));
    }

    // 参数校验失败
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(
            MethodArgumentNotValidException ex, HttpServletRequest request) {
        String detail = ex.getBindingResult().getFieldErrors().stream()
            .map(fe -> fe.getField() + ": " + fe.getDefaultMessage())
            .collect(Collectors.joining("; "));
        return ResponseEntity.badRequest()
            .body(ErrorResponse.of(30001, "参数校验失败", getRequestId(request), detail));
    }

    // 未预期异常
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(
            Exception ex, HttpServletRequest request) {
        log.error("Unexpected exception: path={}", request.getRequestURI(), ex);
        return ResponseEntity.internalServerError()
            .body(ErrorResponse.of(10001, "服务内部错误", getRequestId(request)));
    }
}
```

### 6.4 前端错误处理规范

```typescript
// src/utils/errorHandler.ts
import type { AxiosError } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

interface ApiError {
  code: number
  message: string
  detail?: string
  request_id: string
}

export function handleApiError(error: AxiosError<ApiError>): never {
  const apiError = error.response?.data

  if (!error.response) {
    ElMessage.error('网络连接失败，请检查网络')
    throw new Error('NETWORK_ERROR')
  }

  const code = apiError?.code ?? 10001
  const message = apiError?.message ?? '服务异常，请稍后重试'

  // 特定错误码的特殊处理
  switch (Math.floor(code / 1000)) {
    case 20:   // 认证/权限错误
      if (code === 20002) {
        // Token 过期由拦截器处理，此处不弹 Toast
      } else {
        ElMessage.error(message)
      }
      break
    case 50:   // AI 服务错误
      ElNotification({
        title: 'AI 服务提示',
        message,
        type: 'warning',
        duration: 5000,
      })
      break
    default:
      ElMessage.error(message)
  }

  throw Object.assign(new Error(message), { code, requestId: apiError?.request_id })
}
```

---

## 7. 日志格式规范

### 7.1 日志框架选型

| 服务类型 | 日志框架 | 格式 |
|---|---|---|
| Python 服务 | `structlog` + Python `logging` | JSON 结构化 |
| Java 服务 | `Logback` + `logstash-logback-encoder` | JSON 结构化 |
| 前端 | 不写文件日志，错误上报至后端 `/api/v1/logs/frontend` | — |

### 7.2 统一 JSON 日志格式

所有服务输出的日志必须是**单行 JSON**，包含以下标准字段：

```json
{
  "timestamp": "2026-04-28T14:23:01.456Z",
  "level": "INFO",
  "service": "bid-writer-service",
  "version": "1.2.3",
  "env": "production",
  "logger": "app.services.bid_writer",
  "message": "Section generation completed",
  "request_id": "req_abc123def456",
  "trace_id": "7f3a1b2c8d4e5f6a",
  "span_id": "1a2b3c4d",
  "user_id": "usr_xyz789",
  "duration_ms": 3420,
  "extra": {
    "bid_id": "550e8400-e29b-41d4-a716-446655440000",
    "section_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "word_count": 1240,
    "model": "qwen2.5-72b-instruct"
  }
}
```

**字段说明：**

| 字段 | 必填 | 说明 |
|---|---|---|
| `timestamp` | ✅ | ISO 8601 UTC 时间，毫秒精度 |
| `level` | ✅ | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `service` | ✅ | 服务名称（与 K8s Deployment 名称一致） |
| `version` | ✅ | 服务版本号（来自 `APP_VERSION` 环境变量） |
| `env` | ✅ | development / staging / production |
| `logger` | ✅ | 模块路径，如 `app.services.bid_writer` |
| `message` | ✅ | 人类可读的描述（英文） |
| `request_id` | 推荐 | 来自 HTTP Header `X-Request-ID`，贯穿整个请求链路 |
| `trace_id` | 推荐 | Jaeger 链路追踪 ID，由 OpenTelemetry 自动注入 |
| `user_id` | 条件 | 有用户上下文时必填 |
| `duration_ms` | 条件 | 耗时操作必填 |
| `extra` | 可选 | 业务上下文字段，以 dict 形式附加 |

### 7.3 Python 日志配置

```python
# app/core/logging.py
import structlog
import logging

def configure_logging(log_level: str = "INFO", env: str = "production") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,       # 合并请求上下文
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()            # 输出 JSON
            if env == "production"
            else structlog.dev.ConsoleRenderer(),          # 开发环境彩色输出
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
    )

# 使用示例
logger = structlog.get_logger(__name__)

async def generate_section(section_id: str, bid_id: str) -> SectionResult:
    logger.info(
        "Section generation started",
        section_id=section_id,
        bid_id=bid_id,
    )
    start = time.monotonic()
    try:
        result = await _do_generate(section_id)
        logger.info(
            "Section generation completed",
            section_id=section_id,
            duration_ms=int((time.monotonic() - start) * 1000),
            word_count=result.word_count,
        )
        return result
    except LLMTimeoutError:
        logger.warning(
            "LLM timeout during section generation",
            section_id=section_id,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        raise
```

### 7.4 日志级别使用规范

| 级别 | 使用场景 | 示例 |
|---|---|---|
| `DEBUG` | 详细调试信息，生产环境不输出 | SQL 语句、LLM prompt 内容 |
| `INFO` | 正常业务流程的关键节点 | 请求开始/完成、任务状态变更 |
| `WARNING` | 可恢复的异常、降级行为 | LLM 降级到外部 API、缓存 miss、重试 |
| `ERROR` | 业务流程中断，需要人工关注 | LLM 调用失败、数据库写入失败 |
| `CRITICAL` | 系统级故障，需要立即告警 | 数据库不可用、核心服务宕机 |

### 7.5 日志中禁止出现的内容

以下内容**严格禁止**出现在任何级别的日志中：

- 用户密码、明文 Token、JWT secret
- 身份证号、手机号、银行账号（原文）
- 完整的 LLM Prompt（包含敏感业务数据时）
- MinIO Pre-signed URL（含签名参数）

```python
# ✅ 正确：脱敏后记录
logger.info("User login", username=mask_username(username), ip=client_ip)

# ❌ 错误：记录敏感信息
logger.info("User login", username=username, password=password)   # 严禁
logger.debug("LLM prompt", prompt=full_prompt_with_sensitive_data)  # 严禁
```

### 7.6 请求追踪中间件

每个服务必须实现请求追踪中间件，确保 `request_id` 和 `trace_id` 贯穿整个请求生命周期：

```python
# app/middleware/request_id.py
import uuid
import structlog.contextvars
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = (
            request.headers.get("X-Request-ID")
            or f"req_{uuid.uuid4().hex[:12]}"
        )
        request.state.request_id = request_id

        # 绑定到 structlog 上下文，所有日志自动携带
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            user_id=None,   # 认证后由认证中间件更新
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.clear_contextvars()
        return response
```

---

## 8. 安全编码要求

### 8.1 身份认证与鉴权

**鉴权校验必须在 Service 层执行**，不得仅依赖网关或前端路由控制：

```python
# ✅ 正确：Service 层显式权限校验
class BidWriterService:
    async def update_section(
        self,
        bid_id: UUID,
        section_id: UUID,
        content: str,
        current_user: CurrentUser,
    ) -> BidSection:
        # 1. 获取资源
        section = await self.section_repo.get_or_404(section_id)

        # 2. 资源归属校验（防越权）
        if section.bid_id != bid_id:
            raise AuthorizationError("章节不属于该标书")

        # 3. 功能权限校验
        if not current_user.has_permission("bid:edit"):
            raise AuthorizationError("无章节编辑权限")

        # 4. 协同锁校验
        if section.locked_by and section.locked_by != str(current_user.id):
            raise SectionLockedError(section.locked_by)

        # 5. 状态校验
        bid = await self.bid_repo.get(bid_id)
        if bid.status not in ("DRAFT", "IN_PROGRESS"):
            raise InvalidStatusError(f"标书状态 {bid.status} 不允许编辑")

        return await self.section_repo.update_content(section_id, content, current_user)
```

### 8.2 SQL 注入防护

所有数据库查询**必须**使用参数化查询，**禁止**字符串拼接：

```python
# ✅ 正确：SQLAlchemy ORM 参数化查询
sections = await db.execute(
    select(BidSection)
    .where(BidSection.bid_id == bid_id)
    .where(BidSection.deleted_at.is_(None))
    .order_by(BidSection.section_no)
)

# ✅ 正确：原生 SQL 时使用绑定参数
result = await db.execute(
    text("SELECT * FROM bid.bid_sections WHERE bid_id = :bid_id AND deleted_at IS NULL"),
    {"bid_id": str(bid_id)}
)

# ❌ 严格禁止：字符串拼接（即使看起来无害）
query = f"SELECT * FROM bid.bid_sections WHERE bid_id = '{bid_id}'"  # 严禁
```

### 8.3 文件上传安全

```python
# ✅ 正确：完整的文件校验流程
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB

async def validate_upload_file(file: UploadFile) -> None:
    # 1. 校验文件扩展名（防止绕过）
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(f"不支持的文件类型 {extension}，仅支持 {ALLOWED_EXTENSIONS}")

    # 2. 读取文件头校验真实 MIME 类型（防止伪造扩展名）
    header = await file.read(512)
    await file.seek(0)
    detected_type = magic.from_buffer(header, mime=True)
    if detected_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"文件内容类型 {detected_type} 与声明不符")

    # 3. 校验文件大小
    file_size = 0
    chunk_size = 8192
    while chunk := await file.read(chunk_size):
        file_size += len(chunk)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValidationError(f"文件大小超过限制（最大 100MB）")
    await file.seek(0)
```

### 8.4 LLM 数据安全

在将任何数据发送给 LLM（包括私有化模型）之前，必须通过 `SensitiveDataGuard` 检测：

```python
# app/ai/sensitive_guard.py
import re
from enum import Enum

class LLMTarget(str, Enum):
    PRIVATE = "private"    # 私有化模型
    EXTERNAL = "external"  # 外部 API（GPT/Claude）

# 外部 API 禁止发送的敏感信息模式
EXTERNAL_FORBIDDEN_PATTERNS = [
    (re.compile(r"\d{17}[\dX]"), "身份证号"),          # 18位身份证
    (re.compile(r"1[3-9]\d{9}"), "手机号"),            # 大陆手机号
    (re.compile(r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}"), "银行卡号"),
    (re.compile(r"(?:投标|报价|中标|合同).*?(\d[\d,.]+)\s*万?元"), "金额数据"),
]

# 所有 LLM（含私有化）禁止发送的内容
UNIVERSAL_FORBIDDEN_PATTERNS = [
    (re.compile(r"-----BEGIN.*?PRIVATE KEY-----", re.DOTALL), "私钥"),
    (re.compile(r"password\s*[=:]\s*\S+", re.IGNORECASE), "密码"),
]

class SensitiveDataGuard:
    @staticmethod
    def check(text: str, target: LLMTarget) -> None:
        patterns = UNIVERSAL_FORBIDDEN_PATTERNS.copy()
        if target == LLMTarget.EXTERNAL:
            patterns += EXTERNAL_FORBIDDEN_PATTERNS

        for pattern, data_type in patterns:
            if pattern.search(text):
                raise SensitiveDataError(
                    f"检测到 [{data_type}]，"
                    f"{'禁止发送至任何 LLM' if target == LLMTarget.PRIVATE else '禁止发送至外部 LLM API'}"
                )
```

### 8.5 密钥与配置安全

```python
# ✅ 正确：通过 Pydantic Settings 从环境变量读取配置
from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    database_url: SecretStr                 # SecretStr 防止日志泄露
    jwt_secret_key: SecretStr
    llm_private_base_url: str
    llm_external_api_key: SecretStr | None = None
    app_env: Literal["development", "staging", "production"] = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()   # 单例，全局复用

# ❌ 严格禁止：硬编码任何密钥
JWT_SECRET = "my-super-secret-key"   # 严禁提交到 Git
DATABASE_URL = "postgresql://admin:123456@..."  # 严禁
```

### 8.6 接口安全要求

```python
# ✅ 正确：限流配置（在 Kong 网关层配置，同时在代码层做二次保护）
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/login")
@limiter.limit("10/minute")   # 登录接口限流：每 IP 每分钟 10 次
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    ...

# 防重放攻击：校验 X-Timestamp（允许偏差 ±5 分钟）
async def verify_request_timestamp(
    x_timestamp: str = Header(..., alias="X-Timestamp")
) -> None:
    try:
        req_time = datetime.fromtimestamp(int(x_timestamp), tz=timezone.utc)
    except (ValueError, OSError):
        raise ValidationError("X-Timestamp 格式错误")
    delta = abs((datetime.now(timezone.utc) - req_time).total_seconds())
    if delta > 300:
        raise AuthenticationError("请求时间戳过期，请校准客户端时钟")
```

### 8.7 CORS 配置

```python
# ✅ 正确：仅允许指定来源（生产环境）
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = {
    "development": ["http://localhost:5173", "http://localhost:3000"],
    "staging": ["https://bid-staging.internal"],
    "production": ["https://bid.internal"],
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS[settings.app_env],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Timestamp"],
)
```

---

## 9. AI 能力层开发规范

### 9.1 LLM 统一客户端规范

所有 LLM 调用必须通过统一的 `LLMClient` 封装，**禁止直接调用任何 SDK**：

```python
# app/ai/llm_client.py
from dataclasses import dataclass
import httpx
import asyncio

@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int

class LLMClient:
    """
    统一 LLM 调用客户端，实现：
    - 私有模型优先 → CPU 降级模型 → 外部 API 降级链
    - 超时控制（私有 120s，外部 60s）
    - 自动重试（最多 3 次，指数退避）
    - 敏感数据检测（外部 API 调用前强制检查）
    - 审计日志记录
    """

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        sensitive_check: bool = True,
        force_private: bool = False,   # 强制使用私有模型（敏感内容）
    ) -> LLMResponse:
        prompt_text = "\n".join(m.get("content", "") for m in messages)

        # 对外部 API 调用前的敏感数据检测
        if not force_private:
            SensitiveDataGuard.check(prompt_text, LLMTarget.EXTERNAL)

        for attempt, target in enumerate(self._get_fallback_chain(force_private)):
            try:
                return await self._call(target, messages, temperature, max_tokens)
            except (LLMTimeoutError, LLMUnavailableError) as e:
                if attempt == len(self._get_fallback_chain(force_private)) - 1:
                    raise
                logger.warning(
                    "LLM fallback triggered",
                    from_target=target.value,
                    reason=str(e),
                    attempt=attempt + 1,
                )

    def _get_fallback_chain(self, force_private: bool) -> list[LLMTarget]:
        if force_private:
            return [LLMTarget.PRIVATE]
        return [LLMTarget.PRIVATE, LLMTarget.EXTERNAL]
```

### 9.2 Prompt 工程规范

```
规则一：所有 Prompt 模板存放在 app/ai/prompts/ 目录，使用 .jinja2 文件
规则二：每次修改 Prompt 必须更新版本号，并在 PROMPT_CHANGELOG.md 记录变更原因
规则三：Prompt 文件命名格式：{功能}_{版本}.jinja2，如 constraint_extraction_v3.jinja2
规则四：每个 Prompt 必须包含以下四个区块：
        ① 角色声明  ② 任务描述  ③ 输出格式（JSON Schema）  ④ 少样本示例
规则五：输出格式统一要求 JSON，并在 Prompt 末尾加：
        "只输出 JSON，不要任何解释文字、不要 Markdown 代码块"
```

Prompt 模板示例：

```jinja2
{# app/ai/prompts/section_generate_v2.jinja2 #}
{# Version: 2.1 | Last modified: 2026-04-28 | Author: AI Team #}

你是一位资深投标文件撰写专家，熟悉政府采购、工程招标及商业投标的规范要求。

## 任务
根据以下信息，撰写投标标书中「{{ section.title }}」章节的内容。

## 约束条件（必须覆盖）
{% for c in constraints %}
- [{{ c.constraint_no }}] {{ c.content }}{% if c.is_veto %} ⚠️ 废标条款{% endif %}
{% endfor %}

## 参考资料
{% for ref in knowledge_refs %}
### {{ ref.title }}（第{{ ref.page }}页）
{{ ref.content }}
{% endfor %}

## 写作要求
- 风格：{{ style_desc[style] }}
- 篇幅：{{ length_desc[length_hint] }}
- 语言：专业、严谨的投标文体，避免口语化表达
- 格式：纯文本，段落之间空行分隔
{% if extra_instruction %}
- 特殊要求：{{ extra_instruction }}
{% endif %}

## 输出格式
只输出以下 JSON，不要任何解释文字，不要 Markdown 代码块：
{
  "content": "章节正文内容（纯文本，段落用 \\n\\n 分隔）",
  "word_count": 字数统计（整数）,
  "constraint_covered": ["已覆盖的约束编号列表"],
  "confidence": 0到1之间的置信度小数
}
```

### 9.3 LLM 响应校验规范

LLM 返回的内容**必须经过校验**，不得直接写入数据库：

```python
# app/ai/response_validator.py
import json
from pydantic import BaseModel, field_validator

class SectionGenerateOutput(BaseModel):
    content: str
    word_count: int
    constraint_covered: list[str] = []
    confidence: float

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if len(v.strip()) < 50:
            raise ValueError("生成内容过短，疑似 LLM 拒绝响应")
        return v.strip()

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"置信度 {v} 超出范围 [0, 1]")
        return v

async def parse_llm_section_output(raw: str) -> SectionGenerateOutput:
    try:
        # 清理常见的 LLM 输出污染
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        data = json.loads(cleaned)
        return SectionGenerateOutput.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise LLMResponseError(f"LLM 响应格式校验失败: {e}") from e
```

### 9.4 向量化规范

```python
# 分块策略（不得擅自修改参数）
CHUNK_CONFIG = {
    "max_tokens": 512,        # 单块最大 Token 数
    "overlap_tokens": 50,     # 相邻块重叠 Token 数（保持上下文连续）
    "min_tokens": 50,         # 最小块（过小的块直接合并到上一块）
    "preserve_table": True,   # 表格整体保留，不切分
}

# Embedding 模型配置（通过环境变量注入，不得硬编码模型名）
EMBEDDING_CONFIG = {
    "model": settings.embedding_model,   # 从配置读取
    "dimensions": 1536,                   # 与 Milvus Collection Schema 保持一致
    "batch_size": 100,                    # 批量 embedding 每次不超过 100 条
}
```

---

## 10. 数据层编码规范

### 10.1 数据库操作规范

```python
# ✅ 正确：Repository 模式，封装所有数据库操作
class BidSectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_404(self, section_id: UUID) -> BidSection:
        section = await self._session.get(BidSection, section_id)
        if section is None or section.deleted_at is not None:
            raise ResourceNotFoundError("章节", str(section_id))
        return section

    async def list_by_bid(self, bid_id: UUID) -> list[BidSection]:
        result = await self._session.execute(
            select(BidSection)
            .where(BidSection.bid_id == bid_id)
            .where(BidSection.deleted_at.is_(None))
            .order_by(BidSection.depth, BidSection.section_no)
        )
        return list(result.scalars().all())

    async def soft_delete(self, section_id: UUID, operator_id: str) -> None:
        await self._session.execute(
            update(BidSection)
            .where(BidSection.id == section_id)
            .values(
                deleted_at=datetime.now(timezone.utc),
                updated_by=operator_id,
            )
        )
```

### 10.2 事务管理规范

```python
# ✅ 正确：显式事务边界（在 Service 层管理事务，不在 Repository 层）
class BidWriterService:
    async def submit_bid(self, bid_id: UUID, current_user: CurrentUser) -> BidDetail:
        async with self.db.begin():   # 显式事务
            bid = await self.bid_repo.get_or_404(bid_id)
            sections = await self.section_repo.list_by_bid(bid_id)

            # 业务校验
            incomplete = [s for s in sections if s.status != "DONE"]
            if incomplete:
                raise BusinessException(
                    ErrorCode.VALIDATION_ERROR,
                    f"还有 {len(incomplete)} 个章节未完成"
                )

            # 更新状态（同一事务）
            await self.bid_repo.update_status(bid_id, "REVIEWING", current_user.id)
            await self.section_repo.lock_all(bid_id)   # 锁定所有章节

            # 记录审计日志（同一事务，保证原子性）
            await self.audit_repo.log_action(
                action="bid.submit",
                user_id=current_user.id,
                ref_id=bid_id,
            )

        return await self.bid_repo.get_detail(bid_id)
```

### 10.3 Redis 缓存规范

```python
# Key 命名规范：{service}:{entity_type}:{id}[:field]
REDIS_KEY_PATTERNS = {
    "session":        "auth:session:{user_id}",
    "bid_draft":      "bid:draft:{bid_id}",
    "llm_result":     "ai:llm:{task_id}",
    "kb_health":      "kb:health_score",
    "section_lock":   "bid:lock:{section_id}",
    "rate_limit":     "rl:{ip}:{endpoint}",
}

# TTL 配置（所有 Key 必须设置 TTL，禁止永久缓存）
REDIS_TTL = {
    "session":      8 * 3600,       # 8 小时（与 JWT 有效期一致）
    "bid_draft":    24 * 3600,      # 24 小时
    "llm_result":   1 * 3600,       # 1 小时
    "kb_health":    7 * 24 * 3600,  # 7 天
    "section_lock": 30 * 60,        # 30 分钟（协同编辑锁超时）
}

# ✅ 正确：Cache-Aside 模式
async def get_bid_detail(bid_id: UUID) -> BidDetail:
    cache_key = f"bid:detail:{bid_id}"

    # 1. 读缓存
    cached = await redis.get(cache_key)
    if cached:
        return BidDetail.model_validate_json(cached)

    # 2. 读数据库
    bid = await bid_repo.get_detail(bid_id)
    if bid is None:
        raise ResourceNotFoundError("标书", str(bid_id))

    # 3. 写缓存（仅缓存非草稿状态，草稿实时性要求高）
    if bid.status != "DRAFT":
        await redis.setex(cache_key, 300, bid.model_dump_json())

    return bid
```

### 10.4 MinIO 文件操作规范

```python
# ✅ 正确：文件路径规范 {bucket}/{year}/{month}/{project_id}/{uuid}.{ext}
def build_file_path(
    bucket_type: Literal["bid-raw-files", "bid-exports", "kb-documents"],
    project_id: str,
    filename: str,
) -> str:
    now = datetime.now(timezone.utc)
    file_uuid = uuid.uuid4().hex
    ext = Path(filename).suffix.lower()
    return f"{bucket_type}/{now.year}/{now.month:02d}/{project_id}/{file_uuid}{ext}"

# ✅ 正确：Pre-signed URL（有效期严格 15 分钟）
async def generate_download_url(file_path: str) -> str:
    return await minio_client.presigned_get_object(
        bucket_name=extract_bucket(file_path),
        object_name=extract_object_name(file_path),
        expires=timedelta(minutes=15),   # 固定 15 分钟，不可延长
    )
```

---

## 11. 测试规范

### 11.1 测试分层要求

| 层次 | 工具（Python） | 工具（Java） | 覆盖率要求 | CI 质量门禁 |
|---|---|---|---|---|
| 单元测试 | `pytest` + `pytest-asyncio` | `JUnit 5` + `Mockito` | Service 层 ≥ 80% | 覆盖率下降则阻断合并 |
| 集成测试 | `pytest` + `testcontainers` | `Spring Boot Test` + `Testcontainers` | 核心流程 100% | 必须通过才可部署 staging |
| API 测试 | `pytest` + `httpx.AsyncClient` | `MockMvc` / `RestAssured` | 所有端点（含异常场景） | 必须通过才可部署 staging |
| AI 质量测试 | 自定义评估框架 | — | 每次 Prompt 变更 | 准确率低于阈值则阻断 |
| 性能测试 | `locust` | `Gatling` | 核心接口 50 并发 | 上线前手动触发 |

### 11.2 单元测试规范

```python
# ✅ 正确：单元测试，使用 Mock 隔离外部依赖
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

class TestBidWriterService:
    @pytest.fixture
    def service(self):
        return BidWriterService(
            bid_repo=AsyncMock(spec=BidRepository),
            section_repo=AsyncMock(spec=BidSectionRepository),
            llm_client=AsyncMock(spec=LLMClient),
            knowledge_service=AsyncMock(spec=KnowledgeService),
        )

    @pytest.mark.asyncio
    async def test_generate_section_success(self, service: BidWriterService):
        # Arrange
        section = make_test_section(section_type="FREE_NARRATIVE")
        service.section_repo.get_or_404.return_value = section
        service.llm_client.chat.return_value = LLMResponse(
            content='{"content": "测试生成内容", "word_count": 100, '
                    '"constraint_covered": ["C001"], "confidence": 0.85}',
            model="qwen2.5-72b",
            prompt_tokens=500,
            completion_tokens=200,
            latency_ms=3000,
        )

        # Act
        result = await service.generate_section(
            bid_id=section.bid_id,
            section_id=section.id,
            request=SectionGenerateRequest(constraints=["C001"]),
            current_user=make_test_user(permissions=["bid:edit"]),
        )

        # Assert
        assert result.word_count == 100
        assert result.confidence == pytest.approx(0.85)
        assert "C001" in result.constraint_coverage.covered
        service.llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_section_locked_raises_error(self, service: BidWriterService):
        # 章节被锁定时应抛出 SectionLockedError
        section = make_test_section(locked_by="other_user_id")
        service.section_repo.get_or_404.return_value = section

        with pytest.raises(SectionLockedError, match="other_user"):
            await service.generate_section(
                bid_id=section.bid_id,
                section_id=section.id,
                request=SectionGenerateRequest(),
                current_user=make_test_user(id="current_user_id"),
            )
```

### 11.3 AI 模块质量测试

AI 模块测试必须使用 Golden Dataset，**不得使用随机输入**：

```python
# tests/ai/test_constraint_extraction.py
class TestConstraintExtraction:
    # Golden Dataset：至少 20 条，覆盖各种约束类型和边界情况
    GOLDEN_CASES = [
        {
            "input": "投标人须具备建筑工程施工总承包一级及以上资质",
            "expected_type": "COMPLIANCE",
            "expected_is_veto": True,
            "description": "资质要求（废标条款）",
        },
        {
            "input": "技术方案应包含项目实施进度计划，以甘特图形式呈现",
            "expected_type": "CONTENT",
            "expected_is_veto": False,
            "description": "内容要求（非废标）",
        },
        # ... 更多 case
    ]

    @pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["description"])
    @pytest.mark.asyncio
    async def test_extraction_accuracy(self, extractor: ConstraintExtractor, case: dict):
        result = await extractor.extract(case["input"])
        assert result.constraint_type == case["expected_type"]
        assert result.is_veto == case["expected_is_veto"]

    @pytest.mark.asyncio
    async def test_overall_accuracy_above_threshold(
        self, extractor: ConstraintExtractor, golden_dataset: list[dict]
    ):
        correct = 0
        for case in golden_dataset:
            result = await extractor.extract(case["input"])
            if result.constraint_type == case["expected_type"]:
                correct += 1
        accuracy = correct / len(golden_dataset)
        assert accuracy >= 0.85, (
            f"约束提取整体准确率 {accuracy:.2%} 低于要求的 85%，"
            f"请检查 Prompt 模板"
        )
```

### 11.4 性能测试基准

核心接口在 **50 并发用户**下的 P99 响应时间要求：

| 接口 | P99 上限 | 测试工具 |
|---|---|---|
| 知识库语义检索 `GET /knowledge/search` | 3 秒 | Locust |
| 投标审查创建 `POST /reviews` | 5 秒（任务创建阶段） | Locust |
| 一致性检查 `POST /bids/{id}/check` | 10 秒（任务创建阶段）| Locust |
| LLM 章节生成（含排队）| 120 秒 | Locust（长等待场景）|
| 用户登录 `POST /auth/login` | 500 毫秒 | Locust |
| 项目列表 `GET /projects` | 300 毫秒 | Locust |

---

## 12. CI/CD 与发布规范

### 12.1 GitLab CI 流水线阶段

```yaml
# .gitlab-ci.yml（每个服务复用此模板）
stages:
  - lint          # 代码风格检查
  - test          # 单元测试 + 集成测试
  - build         # Docker 镜像构建
  - scan          # 安全扫描（依赖漏洞、SAST）
  - deploy-dev    # 部署开发环境（自动）
  - test-api      # API 测试（对开发环境）
  - deploy-staging # 部署 staging（自动，仅 main 分支）
  - test-perf     # 性能测试（手动触发）
  - deploy-prod   # 部署生产（手动审批 + 灰度）
```

### 12.2 质量门禁（合并到 main 分支前必须通过）

| 检查项 | 工具 | 失败策略 |
|---|---|---|
| 代码格式 | Black + Ruff（Python）/ Checkstyle（Java）| 阻断合并 |
| 类型检查 | mypy --strict（Python）/ javac（Java）| 阻断合并 |
| 单元测试通过率 | pytest / JUnit | 100% 通过，阻断合并 |
| 代码覆盖率 | pytest-cov / JaCoCo | Service 层 < 80% 阻断合并 |
| 依赖漏洞扫描 | Safety（Python）/ OWASP Dependency Check（Java）| 高危漏洞阻断合并 |
| SAST 静态安全扫描 | Semgrep | 高危告警阻断合并 |
| Prompt 变更测试 | 自定义评估框架 | AI 准确率下降 > 5% 阻断合并 |

### 12.3 分支与提交规范

```
分支命名：
  feature/{issue-id}-{brief-desc}     功能开发
  fix/{issue-id}-{brief-desc}         Bug 修复
  refactor/{issue-id}-{brief-desc}    重构
  hotfix/{issue-id}-{brief-desc}      生产紧急修复（从 main 分支）

提交信息（Conventional Commits）：
  feat(bid-writer): add three-way routing for section generation
  fix(auth): handle refresh token race condition
  refactor(knowledge): extract hybrid retriever as separate class
  test(bid-writer): add golden dataset for constraint extraction
  docs(api): update section generate endpoint schema
  chore(deps): upgrade fastapi to 0.115.0

规则：
  - 禁止直接向 main 分支推送（Force Push 已在 GitLab 设置中禁用）
  - PR 必须至少 1 名 Reviewer 审批（涉及安全/AI 逻辑需 2 名）
  - PR 描述必须包含：变更原因、影响范围、测试说明
```

### 12.4 生产发布规范

```
发布流程：
  1. main 分支通过所有 CI 检查
  2. 技术 Lead 审批 deploy-prod 任务
  3. 先发布 5% 流量（灰度）
  4. 观察 15 分钟：错误率、P99 响应时间、AI 质量指标
  5. 指标正常则扩大至 50% → 100%
  6. 若任何指标告警，立即回滚到上一版本

回滚操作：
  kubectl rollout undo deployment/{service-name} -n bid-ai
```

---

## 13. 性能设计约定

### 13.1 同步 vs 异步边界

| 执行时长预期 | 接口模式 | 说明 |
|---|---|---|
| < 1 秒 | 同步返回（HTTP 200） | 普通 CRUD、缓存读取 |
| 1~5 秒 | 同步返回（HTTP 200，带超时告警） | 知识库检索、数据填充类生成 |
| > 5 秒 | 异步（HTTP 202 + task_id 轮询） | LLM 生成、OCR 解析、串标分析 |

**所有超过 5 秒的操作必须异步化**，不得阻塞请求线程。

### 13.2 数据库查询优化要求

```sql
-- 规则一：所有列表查询必须有 LIMIT，禁止全表扫描返回客户端
SELECT * FROM bid.bid_sections
WHERE bid_id = $1 AND deleted_at IS NULL
ORDER BY section_no
LIMIT 500;    -- 即使不分页也要设上限

-- 规则二：N+1 查询必须消除（使用 JOIN 或批量加载）
-- ❌ 错误：循环中查询
for section in sections:
    constraints = await get_constraints(section.id)   # N+1 查询

-- ✅ 正确：批量查询
constraint_map = await get_constraints_by_section_ids([s.id for s in sections])

-- 规则三：慢查询告警阈值 2 秒，超过须添加索引或重写查询
-- 规则四：新增索引使用 CONCURRENTLY，不锁表
CREATE INDEX CONCURRENTLY idx_bid_sections_bid_status
    ON bid.bid_sections (bid_id, status)
    WHERE deleted_at IS NULL;
```

### 13.3 缓存策略

| 数据类型 | 缓存策略 | TTL | 失效时机 |
|---|---|---|---|
| 用户权限列表 | Cache-Aside | 5 分钟 | 用户角色变更时主动清除 |
| 知识库健康度 | Write-Through | 7 天 | 知识库文档增删时更新 |
| 标书详情（非草稿） | Cache-Aside | 5 分钟 | 标书更新时主动清除 |
| 异步任务状态 | 由 Celery 管理 | 24 小时 | 任务完成后保留供查询 |
| LLM 生成结果 | 仅 AI 任务表 | 永久（数据库） | 不走 Redis 缓存 |

### 13.4 限流配置

| 接口类型 | 限流规则 | 降级策略 |
|---|---|---|
| 登录接口 | 每 IP 10 次/分钟 | 超限返回 429 |
| LLM 生成接口 | 每用户 5 个并发任务 | 超限返回任务队列满提示 |
| 知识库检索 | 每服务 100 QPS | 超限返回缓存结果或 503 |
| 文件上传 | 每用户 10 个并发上传 | 超限返回 429 |
| 普通 API | 每用户 300 次/分钟 | 超限返回 429 |

---

## 14. 配置管理规范

### 14.1 环境变量分级

所有配置通过环境变量注入，按敏感程度分为三级：

| 级别 | 示例 | 管理方式 |
|---|---|---|
| 普通配置 | `APP_ENV`, `LOG_LEVEL`, `MAX_PAGE_SIZE` | K8s ConfigMap |
| 敏感配置 | `DATABASE_URL`, `JWT_SECRET_KEY`, `LLM_API_KEY` | K8s Secret（Base64 编码） |
| 超敏感配置 | 证书私钥、加密主密钥 | Vault（HashiCorp），K8s Secret 仅存引用 |

### 14.2 环境变量完整列表

```bash
# ——— 应用基础 ———
APP_ENV=production              # development / staging / production
APP_VERSION=1.2.3               # 由 CI 注入
LOG_LEVEL=INFO                  # DEBUG / INFO / WARNING / ERROR
SERVICE_NAME=bid-writer-service # 服务名称

# ——— 数据库 ———
DATABASE_URL=postgresql+asyncpg://user:pass@pg-primary:5432/bidai
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ——— Redis ———
REDIS_URL=redis://redis-cluster:6379/0
REDIS_POOL_SIZE=20

# ——— Elasticsearch ———
ES_URL=http://es-cluster:9200
ES_INDEX_PREFIX=bidai_prod

# ——— Milvus ———
MILVUS_HOST=milvus-cluster
MILVUS_PORT=19530
MILVUS_COLLECTION=bid_chunks_prod

# ——— MinIO ———
MINIO_ENDPOINT=minio-cluster:9000
MINIO_ACCESS_KEY=<from-secret>
MINIO_SECRET_KEY=<from-secret>
MINIO_SECURE=true               # 生产环境必须开启

# ——— LLM 私有模型 ———
LLM_PRIVATE_BASE_URL=http://gpu-node-1:8080/v1
LLM_PRIVATE_MODEL=qwen2.5-72b-instruct
LLM_PRIVATE_TIMEOUT=120
LLM_PRIVATE_MAX_RETRIES=3

# ——— LLM 外部 API（降级用，仅非敏感内容）———
LLM_EXTERNAL_API_KEY=<from-secret>   # 通过 K8s Secret 注入
LLM_EXTERNAL_MODEL=gpt-4o
LLM_EXTERNAL_TIMEOUT=60

# ——— Embedding ———
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIMENSIONS=1536

# ——— 安全 ———
JWT_SECRET_KEY=<from-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8
REFRESH_TOKEN_EXPIRE_DAYS=30
MFA_ISSUER=BidAI
ENCRYPTION_KEY=<from-secret>    # AES-256-GCM 主密钥（敏感字段加密）

# ——— Celery ———
CELERY_BROKER_URL=redis://redis-cluster:6379/1
CELERY_RESULT_BACKEND=redis://redis-cluster:6379/2
CELERY_TASK_TIMEOUT=300         # 默认任务超时 5 分钟

# ——— 链路追踪 ———
JAEGER_AGENT_HOST=jaeger-agent
JAEGER_AGENT_PORT=6831
OTEL_SERVICE_NAME=${SERVICE_NAME}
```

### 14.3 本地开发配置

本地开发使用 `.env` 文件，**已加入 `.gitignore`，严禁提交到仓库**。

新成员克隆项目后，从内部文档管理系统获取 `.env.example` 并填写本地配置。

---

## 15. 禁止行为红线清单

> 以下行为在任何情况下都不得出现，违反将视为严重事故。

### 15.1 安全红线

| # | 禁止行为 | 后果 |
|---|---|---|
| S1 | 在代码、配置文件、注释、commit message 中硬编码密钥/密码/Token | 立即撤销 Secret，强制 PR 重新审查 |
| S2 | 将含敏感数据（报价、人员、证件号）的内容发送至外部 LLM API | 立即停用外部 API，启动安全审查 |
| S3 | 绕过 JWT 认证（如添加 `skip_auth=True`、注释掉认证中间件） | 立即回滚，启动安全审查 |
| S4 | 在日志中输出密码、Token、证件号等敏感信息 | 立即清除日志，审查数据泄露范围 |
| S5 | 将 MinIO Bucket 设置为公开访问 | 立即关闭，审查已泄露文件 |
| S6 | 在 SQL 中使用字符串拼接（而非参数化查询） | 阻断合并，全量 SQL 安全审查 |
| S7 | 物理删除业务数据（使用 `DELETE FROM` 而非软删除） | 从备份恢复，追责责任人 |

### 15.2 架构红线

| # | 禁止行为 |
|---|---|
| A1 | 服务 A 直接读写服务 B 的数据库（必须通过 B 的 API） |
| A2 | 在 Controller / 路由层写业务逻辑或权限校验 |
| A3 | 耗时超过 5 秒的操作使用同步接口 |
| A4 | LLM 调用不设超时（必须设置，私有 120s，外部 60s） |
| A5 | 在 Prompt 中插入未脱敏的用户数据 |
| A6 | LLM 响应不经格式校验直接写入数据库 |
| A7 | 向量 Chunk 超过 512 tokens 不切分 |

### 15.3 代码质量红线

| # | 禁止行为 |
|---|---|
| Q1 | Python 代码缺少类型注解（mypy 检查失败） |
| Q2 | `except Exception: pass`（必须细化异常并记录日志） |
| Q3 | 前端组件直接使用裸 `axios`（必须通过 service 层） |
| Q4 | Vue 组件使用 Options API（必须使用 Composition API）|
| Q5 | 修改 Prompt 模板不更新版本号和 PROMPT_CHANGELOG.md |
| Q6 | 提交含 `TODO`/`FIXME`/`HACK` 但未创建 Issue 追踪的代码到 main 分支 |
| Q7 | 直接存储身份证号、手机号等个人信息明文（必须 AES-256-GCM 加密）|

---

## 16. 附录：工具链版本锁定表

> 以下版本为项目锁定版本，**未经架构评审，不得擅自升级主版本号**。

### 16.1 后端（Python 服务）

| 组件 | 锁定版本 | 用途 |
|---|---|---|
| Python | 3.11.x | 运行时 |
| FastAPI | 0.110.x | Web 框架 |
| Pydantic | 2.7.x | 数据校验 |
| SQLAlchemy | 2.0.x | ORM |
| Alembic | 1.13.x | 数据库迁移 |
| Celery | 5.3.x | 任务队列 |
| structlog | 24.x | 结构化日志 |
| httpx | 0.27.x | 异步 HTTP 客户端 |
| LangChain | 0.2.x | AI 框架 |
| PaddleOCR | 2.7.x | OCR |
| PyMuPDF | 1.24.x | PDF 解析 |
| python-docx | 1.1.x | DOCX 解析 |
| mypy | 1.10.x | 类型检查 |
| Black | 24.x | 代码格式化 |
| Ruff | 0.4.x | Lint |

### 16.2 后端（Java 服务）

| 组件 | 锁定版本 | 用途 |
|---|---|---|
| Java | 21（LTS） | 运行时 |
| Spring Boot | 3.2.x | 框架 |
| Spring Security | 6.2.x | 认证授权 |
| Spring Data JPA | 3.2.x | ORM |
| QueryDSL | 5.1.x | 类型安全查询 |
| Flyway | 10.x | 数据库迁移（Java 服务） |
| Gradle | 8.7 | 构建工具 |
| Lombok | 1.18.x | 代码生成 |
| MapStruct | 1.6.x | 对象映射 |
| JUnit 5 | 5.10.x | 测试框架 |
| Testcontainers | 1.19.x | 集成测试容器 |

### 16.3 前端

| 组件 | 锁定版本 | 用途 |
|---|---|---|
| Node.js | 20.x（LTS） | 运行时 |
| Vue | 3.4.x | UI 框架 |
| TypeScript | 5.4.x | 语言 |
| Vite | 5.x | 构建工具 |
| Element Plus | 2.7.x | UI 组件库 |
| Pinia | 2.x | 状态管理 |
| Axios | 1.7.x | HTTP 客户端 |
| ESLint | 8.x | Lint |
| Prettier | 3.x | 格式化 |
| uni-app | 最新稳定版 | 移动端跨端框架 |

### 16.4 基础设施

| 组件 | 版本要求 | 说明 |
|---|---|---|
| Kubernetes | 1.28+ | 容器编排 |
| Kong | 3.x | API 网关 |
| PostgreSQL | 15+ | 关系数据库 |
| Elasticsearch | 8.x + IK 分词 | 全文检索 |
| Milvus | 2.4+ | 向量数据库 |
| MinIO | 最新稳定版 | 对象存储 |
| Redis | 7+ | 缓存 / 消息队列 |
| Prometheus | 2.x | 指标采集 |
| Grafana | 10.x | 监控面板 |
| Jaeger | 1.x | 链路追踪 |
| GitLab CE | 16.x+ | CI/CD |

---

## 文档变更记录

| 版本 | 日期 | 变更内容 | 变更人 |
|---|---|---|---|
| V1.0 | 2026-04-28 | 初始版本，基于 TSD-BIDAI-2026-001 V1.0 和 API-BIDAI-2026-001 V1.0 细化 | 架构组 |

---

*本文档为 AI 智能投标系统技术规范，所有开发成员必须遵守。重大变更须经架构评审后更新版本号。*

*© 2026 内部保密文件，未经授权不得外传。*  
*最后更新：2026-04-28 | 文档负责人：技术 Lead*
