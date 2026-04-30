# AI 智能投标系统 · API 接口规范文档

**文档编号**：API-BIDAI-2026-001  
**关联方案**：TSD-BIDAI-2026-001 V1.0  
**版本**：V1.0  
**编制日期**：2026-04-28  
**规范标准**：OpenAPI 3.0.3  
**密级**：内部保密

---

## 目录

1. [概述](#1-概述)
2. [鉴权说明](#2-鉴权说明)
3. [统一规范](#3-统一规范)
4. [错误码规范](#4-错误码规范)
5. [公共 Schema 定义](#5-公共-schema-定义)
6. [接口清单总览](#6-接口清单总览)
7. [OpenAPI 3.0 完整定义](#7-openapi-30-完整定义)
   - 7.1 认证模块（auth-service）
   - 7.2 用户与权限模块（auth-service）
   - 7.3 项目管理模块（project-service）
   - 7.4 文档解析模块（bid-parser-service）
   - 7.5 知识库模块（knowledge-service）
   - 7.6 标书编写模块（bid-writer-service）
   - 7.7 投标审查模块（bid-review-service）
   - 7.8 串标分析模块（collusion-analysis-service）
   - 7.9 异步任务查询（通用）
   - 7.10 文件导出模块（export-service）
8. [附录：权限矩阵](#8-附录权限矩阵)

---

## 1. 概述

### 1.1 基本信息

本文档定义 AI 智能投标系统所有后端 API 的接口规范，涵盖请求/响应 Schema、鉴权机制、错误码体系及分页约定。所有接口遵循 RESTful 设计风格，通过 Kong API 网关统一对外暴露。

| 项目 | 值 |
|---|---|
| 接口基础路径 | `https://{host}/api/v1` |
| 协议要求 | HTTPS / TLS 1.3（强制） |
| 字符集 | UTF-8 |
| 日期格式 | ISO 8601（`YYYY-MM-DDTHH:mm:ssZ`） |
| 数字精度 | 金额类使用字符串传输，避免浮点精度丢失 |

### 1.2 服务端点映射

各微服务通过 Kong 网关路由，外部统一访问同一域名，内部按路径前缀转发：

| 路径前缀 | 对应微服务 | 语言 |
|---|---|---|
| `/api/v1/auth/**` | `auth-service` | Java |
| `/api/v1/users/**` | `auth-service` | Java |
| `/api/v1/projects/**` | `project-service` | Java |
| `/api/v1/documents/**` | `bid-parser-service` | Python |
| `/api/v1/knowledge/**` | `knowledge-service` | Python |
| `/api/v1/bids/**` | `bid-writer-service` | Python |
| `/api/v1/reviews/**` | `bid-review-service` | Python |
| `/api/v1/collusion/**` | `collusion-analysis-service` | Python |
| `/api/v1/tasks/**` | `bid-writer-service`（聚合） | Python |
| `/api/v1/export/**` | `export-service` | Java |

---

## 2. 鉴权说明

### 2.1 认证机制

系统采用 **JWT Bearer Token** 认证机制，由 `auth-service` 签发和校验。

```
认证流程：
  1. 客户端 POST /api/v1/auth/login 获取 access_token + refresh_token
  2. 后续请求在 HTTP Header 中携带：Authorization: Bearer {access_token}
  3. access_token 过期（8小时）后，使用 refresh_token 换新 Token
  4. refresh_token 有效期 30 天，每次刷新后旧 token 立即失效（单次使用）
```

### 2.2 Token 规格

| 参数 | 值 |
|---|---|
| 算法 | HS256 |
| access_token 有效期 | 8 小时 |
| refresh_token 有效期 | 30 天 |
| 签发方（iss） | `bidai-auth-service` |

### 2.3 JWT Payload 标准字段

```json
{
  "sub": "用户UUID",
  "username": "用户名",
  "roles": ["BID_STAFF", "PROJECT_MGR"],
  "permissions": ["bid:edit", "bid:export"],
  "iss": "bidai-auth-service",
  "iat": 1714291200,
  "exp": 1714320000
}
```

### 2.4 请求头规范

所有需要鉴权的接口必须携带以下 Header：

| Header | 是否必填 | 说明 |
|---|---|---|
| `Authorization` | 必填 | `Bearer {access_token}` |
| `X-Request-ID` | 推荐 | 客户端生成的请求唯一 ID，用于链路追踪；若不传，网关自动生成 |
| `Content-Type` | 必填（POST/PUT） | `application/json`（文件上传接口除外） |

### 2.5 免鉴权接口白名单

以下接口无需携带 Authorization Header：

- `POST /api/v1/auth/login` — 用户登录
- `POST /api/v1/auth/refresh` — 刷新 Token
- `GET  /api/v1/health` — 健康检查

### 2.6 高权限操作 MFA 要求

以下操作在 JWT 有效的前提下，还需验证 MFA（TOTP）：

- `POST /api/v1/users` — 创建用户
- `DELETE /api/v1/users/{id}` — 注销用户
- `POST /api/v1/export/bids/{id}` — 批量导出标书（首次）

MFA 验证通过后，服务端返回短效的 `mfa_token`（有效期 5 分钟），后续高权限操作在 Header 中附加 `X-MFA-Token: {mfa_token}`。

---

## 3. 统一规范

### 3.1 URL 规范

```
版本前缀：  /api/v1/
资源命名：  复数名词，小写，连字符分隔（kebab-case）
路径示例：
  POST   /api/v1/projects                              创建投标项目
  GET    /api/v1/projects/{id}                         获取项目详情
  GET    /api/v1/projects                              获取项目列表
  PUT    /api/v1/projects/{id}                         更新项目
  DELETE /api/v1/projects/{id}                         删除项目（软删除）
  POST   /api/v1/bids/{id}/sections/{sid}/generate     生成章节（动作用动词后缀）
  GET    /api/v1/bids/{id}/check                       一致性检查（动作用动词后缀）
```

### 3.2 统一响应格式

**成功响应（HTTP 200 / 201 / 202）：**

```json
{
  "code": 200,
  "message": "success",
  "data": { },
  "request_id": "req_abc123def456"
}
```

**分页列表响应：**

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  },
  "request_id": "req_abc123def456"
}
```

**异步任务响应（HTTP 202）：**

```json
{
  "code": 202,
  "message": "任务已提交，请轮询状态",
  "data": {
    "task_id": "task_xyz789",
    "status": "PENDING",
    "poll_url": "/api/v1/tasks/task_xyz789"
  },
  "request_id": "req_abc123def456"
}
```

**错误响应（HTTP 4xx / 5xx）：**

```json
{
  "code": 40001,
  "message": "项目名称已存在",
  "detail": "同客户下已存在名称为「XX信息系统」的项目",
  "request_id": "req_abc123def456"
}
```

### 3.3 分页参数规范

所有列表接口统一支持以下查询参数：

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `page` | integer | 1 | 页码，从 1 开始 |
| `page_size` | integer | 20 | 每页条数，1~100 |

### 3.4 软删除规范

业务数据禁止物理删除，DELETE 接口仅设置 `deleted_at` 时间戳。已删除数据不在列表接口中返回，但可通过详情接口查询（返回 404）。

### 3.5 异步接口规范

执行时长超过 5 秒的操作（LLM 生成、OCR 解析、串标分析等）统一采用异步模式：

1. 客户端发起请求，服务端立即返回 HTTP 202 及 `task_id`
2. 客户端按 `poll_url` 轮询任务状态，建议轮询间隔 2~5 秒
3. 任务状态流转：`PENDING` → `RUNNING` → `SUCCESS` / `FAILED`
4. 任务最长等待时间：LLM 生成 120 秒，其余异步任务 300 秒

---

## 4. 错误码规范

### 4.1 HTTP 状态码使用约定

| HTTP 状态码 | 使用场景 |
|---|---|
| 200 OK | 请求成功，有数据返回 |
| 201 Created | 资源创建成功 |
| 202 Accepted | 异步任务已接受 |
| 204 No Content | 删除成功，无返回体 |
| 400 Bad Request | 请求参数错误 |
| 401 Unauthorized | 未认证或 Token 失效 |
| 403 Forbidden | 已认证但权限不足 |
| 404 Not Found | 资源不存在 |
| 409 Conflict | 资源冲突（如重复创建） |
| 422 Unprocessable Entity | 业务逻辑校验失败 |
| 429 Too Many Requests | 请求频率限制 |
| 500 Internal Server Error | 服务内部错误 |
| 503 Service Unavailable | 服务不可用（LLM 降级等） |

### 4.2 业务错误码体系

业务错误码为 5 位整数，分段规划如下：

```
1xxxx  系统级错误
2xxxx  认证 / 权限错误
3xxxx  输入参数错误
4xxxx  业务逻辑错误
5xxxx  AI 服务错误
```

### 4.3 错误码详细定义

#### 系统级错误（1xxxx）

| 错误码 | HTTP 状态 | 说明 |
|---|---|---|
| 10001 | 500 | 内部服务错误（通用） |
| 10002 | 500 | 数据库操作失败 |
| 10003 | 500 | 文件存储服务异常（MinIO） |
| 10004 | 503 | 依赖服务不可用 |
| 10005 | 429 | 请求频率超限 |

#### 认证 / 权限错误（2xxxx）

| 错误码 | HTTP 状态 | 说明 |
|---|---|---|
| 20001 | 401 | Token 无效或格式错误 |
| 20002 | 401 | Token 已过期，请刷新 |
| 20003 | 401 | refresh_token 无效或已吊销 |
| 20004 | 403 | 权限不足，无法执行此操作 |
| 20005 | 403 | 无该资源的访问权限 |
| 20006 | 403 | MFA 验证失败 |
| 20007 | 403 | 账号已被锁定，请联系管理员 |
| 20008 | 401 | 用户名或密码错误（登录失败） |

#### 输入参数错误（3xxxx）

| 错误码 | HTTP 状态 | 说明 |
|---|---|---|
| 30001 | 400 | 必填参数缺失（detail 中说明具体字段） |
| 30002 | 400 | 参数类型错误 |
| 30003 | 400 | 参数值超出允许范围 |
| 30004 | 400 | 文件类型不在白名单（仅允许 pdf/docx/xlsx/jpg/png） |
| 30005 | 400 | 文件大小超过限制（单文件最大 100MB） |
| 30006 | 400 | 分页参数非法（page < 1 或 page_size 超出 1~100） |
| 30007 | 400 | 日期格式错误，应使用 ISO 8601 |
| 30008 | 400 | UUID 格式不合法 |

#### 业务逻辑错误（4xxxx）

| 错误码 | HTTP 状态 | 说明 |
|---|---|---|
| 40001 | 409 | 资源已存在（名称/编号重复） |
| 40002 | 404 | 资源不存在或已删除 |
| 40003 | 422 | 项目状态不允许此操作（如已归档的项目不能编辑） |
| 40004 | 422 | 标书状态不允许此操作（如审批中不能修改章节） |
| 40005 | 422 | 章节被其他用户锁定，无法编辑 |
| 40006 | 422 | 资质证书已过期，无法引用 |
| 40007 | 422 | 文档尚未完成解析，请等待 |
| 40008 | 422 | 知识库文档哈希重复，文件已存在 |
| 40009 | 422 | 审查任务尚在进行中，不可重复提交 |
| 40010 | 422 | 标书未达到导出条件（完成度不足或存在未通过审查项） |

#### AI 服务错误（5xxxx）

| 错误码 | HTTP 状态 | 说明 |
|---|---|---|
| 50001 | 503 | LLM 生成失败（私有模型不可用） |
| 50002 | 503 | LLM 生成超时（超过 120 秒） |
| 50003 | 503 | LLM 降级至外部 API 失败 |
| 50004 | 422 | 检测到敏感数据，禁止发送至外部 LLM |
| 50005 | 503 | 向量检索服务（Milvus）不可用 |
| 50006 | 503 | 全文检索服务（Elasticsearch）不可用 |
| 50007 | 500 | OCR 解析失败 |
| 50008 | 422 | LLM 响应格式校验失败，内容不符合预期 |

---

## 5. 公共 Schema 定义

以下 Schema 在多个接口中复用，统一在此定义。

### 5.1 CommonResponse（通用响应包装）

```yaml
CommonResponse:
  type: object
  required: [code, message, request_id]
  properties:
    code:
      type: integer
      example: 200
    message:
      type: string
      example: "success"
    data:
      description: 响应数据，具体类型由各接口定义
    request_id:
      type: string
      example: "req_abc123def456"
```

### 5.2 PaginatedResponse（分页响应）

```yaml
PaginatedResponse:
  type: object
  properties:
    items:
      type: array
    total:
      type: integer
      example: 100
    page:
      type: integer
      example: 1
    page_size:
      type: integer
      example: 20
    total_pages:
      type: integer
      example: 5
```

### 5.3 AsyncTaskResponse（异步任务响应）

```yaml
AsyncTaskResponse:
  type: object
  required: [task_id, status, poll_url]
  properties:
    task_id:
      type: string
      example: "task_xyz789abc"
    status:
      type: string
      enum: [PENDING, RUNNING, SUCCESS, FAILED, CANCELLED, RETRYING]
    poll_url:
      type: string
      example: "/api/v1/tasks/task_xyz789abc"
    estimated_seconds:
      type: integer
      description: 预计完成时间（秒），仅供参考
      example: 30
```

### 5.4 ErrorResponse（错误响应）

```yaml
ErrorResponse:
  type: object
  required: [code, message, request_id]
  properties:
    code:
      type: integer
      example: 40001
    message:
      type: string
      example: "项目名称已存在"
    detail:
      type: string
      description: 调试信息，生产环境可隐藏
      example: "同客户下已存在名称为「XX信息系统」的项目"
    request_id:
      type: string
      example: "req_abc123def456"
```

---

## 6. 接口清单总览

| 序号 | 方法 | 路径 | 功能 | 所属服务 | 需要权限 |
|---|---|---|---|---|---|
| 1 | POST | `/auth/login` | 用户登录 | auth-service | 无 |
| 2 | POST | `/auth/refresh` | 刷新 Token | auth-service | 无 |
| 3 | POST | `/auth/logout` | 退出登录 | auth-service | 已登录 |
| 4 | GET | `/auth/me` | 获取当前用户信息 | auth-service | 已登录 |
| 5 | GET | `/users` | 获取用户列表 | auth-service | `user:manage` |
| 6 | POST | `/users` | 创建用户 | auth-service | `user:manage` + MFA |
| 7 | GET | `/users/{id}` | 获取用户详情 | auth-service | `user:manage` |
| 8 | PUT | `/users/{id}` | 更新用户信息 | auth-service | `user:manage` |
| 9 | DELETE | `/users/{id}` | 注销用户 | auth-service | `user:manage` + MFA |
| 10 | PUT | `/users/{id}/roles` | 设置用户角色 | auth-service | `user:manage` |
| 11 | GET | `/projects` | 获取项目列表 | project-service | `project:read` |
| 12 | POST | `/projects` | 创建投标项目 | project-service | `project:create` |
| 13 | GET | `/projects/{id}` | 获取项目详情 | project-service | `project:read` |
| 14 | PUT | `/projects/{id}` | 更新项目信息 | project-service | `project:create` |
| 15 | DELETE | `/projects/{id}` | 归档/删除项目 | project-service | `project:create` |
| 16 | GET | `/projects/{id}/members` | 获取项目成员 | project-service | `project:read` |
| 17 | PUT | `/projects/{id}/members` | 设置项目成员 | project-service | `project:create` |
| 18 | GET | `/projects/{id}/win-rate` | 胜率预测 | project-service | `project:read` |
| 19 | POST | `/projects/{id}/bid-record` | 录入投标结果 | project-service | `project:create` |
| 20 | POST | `/documents/parse` | 上传并解析文档 | bid-parser-service | `bid:edit` |
| 21 | GET | `/documents/{id}` | 获取文档详情 | bid-parser-service | `bid:edit` |
| 22 | GET | `/documents/{id}/constraints` | 获取约束列表 | bid-parser-service | `bid:edit` |
| 23 | PUT | `/documents/{id}/constraints` | 确认/修改约束 | bid-parser-service | `bid:edit` |
| 24 | GET | `/knowledge/search` | 语义检索知识库 | knowledge-service | `bid:edit` |
| 25 | POST | `/knowledge/upload` | 上传文档入库 | knowledge-service | `knowledge:manage` |
| 26 | GET | `/knowledge/documents` | 知识库文档列表 | knowledge-service | `bid:edit` |
| 27 | GET | `/knowledge/documents/{id}` | 知识库文档详情 | knowledge-service | `bid:edit` |
| 28 | DELETE | `/knowledge/documents/{id}` | 删除知识库文档 | knowledge-service | `knowledge:manage` |
| 29 | GET | `/knowledge/stats` | 知识库统计信息 | knowledge-service | `bid:edit` |
| 30 | GET | `/knowledge/qualifications` | 资质证书列表 | knowledge-service | `bid:edit` |
| 31 | GET | `/knowledge/personnel` | 人员库列表 | knowledge-service | `bid:edit` |
| 32 | GET | `/knowledge/performances` | 业绩库列表 | knowledge-service | `bid:edit` |
| 33 | GET | `/bids/{id}` | 获取标书详情 | bid-writer-service | `bid:edit` |
| 34 | POST | `/bids/{id}/outline` | 生成标书目录 | bid-writer-service | `bid:edit` |
| 35 | GET | `/bids/{id}/sections` | 获取章节列表 | bid-writer-service | `bid:edit` |
| 36 | POST | `/bids/{id}/sections/{sid}/generate` | AI 生成章节内容 | bid-writer-service | `bid:edit` |
| 37 | GET | `/bids/{id}/sections/{sid}` | 获取章节详情 | bid-writer-service | `bid:edit` |
| 38 | PUT | `/bids/{id}/sections/{sid}` | 编辑章节内容 | bid-writer-service | `bid:edit` |
| 39 | GET | `/bids/{id}/sections/{sid}/versions` | 章节版本历史 | bid-writer-service | `bid:edit` |
| 40 | POST | `/bids/{id}/sections/{sid}/revert` | 回滚到指定版本 | bid-writer-service | `bid:edit` |
| 41 | GET | `/bids/{id}/variables` | 获取全局变量 | bid-writer-service | `bid:edit` |
| 42 | PUT | `/bids/{id}/variables` | 更新全局变量 | bid-writer-service | `bid:edit` |
| 43 | POST | `/bids/{id}/check` | 一致性检查 | bid-writer-service | `bid:edit` |
| 44 | POST | `/bids/{id}/submit` | 提交审批 | bid-writer-service | `bid:edit` |
| 45 | POST | `/reviews` | 创建审查任务 | bid-review-service | `bid:edit` |
| 46 | GET | `/reviews/{id}` | 获取审查任务状态 | bid-review-service | `report:read` |
| 47 | GET | `/reviews/{id}/result` | 获取审查结果详情 | bid-review-service | `report:read` |
| 48 | POST | `/reviews/{id}/report` | 导出审查报告 | bid-review-service | `bid:export` |
| 49 | POST | `/collusion/analyze` | 提交串标分析任务 | collusion-service | `bid:edit` |
| 50 | GET | `/collusion/{id}/result` | 获取串标分析结果 | collusion-service | `report:read` |
| 51 | GET | `/tasks/{task_id}` | 查询异步任务状态 | 各服务聚合 | 已登录 |
| 52 | POST | `/export/bids/{id}` | 导出标书文件 | export-service | `bid:export` |
| 53 | GET | `/export/bids/{id}/download` | 下载导出文件 | export-service | `bid:export` |

---

## 7. OpenAPI 3.0 完整定义

```yaml
openapi: 3.0.3

info:
  title: AI 智能投标系统 API
  description: |
    AI 智能投标系统后端接口规范，覆盖投标全生命周期。
    
    ## 鉴权
    除登录、刷新 Token 接口外，所有接口均需在 Header 中携带：
    `Authorization: Bearer {access_token}`
    
    ## 异步接口
    耗时操作（LLM生成、OCR解析、串标分析）返回 202 及 task_id，
    请通过 `GET /api/v1/tasks/{task_id}` 轮询任务状态。
  version: "1.0.0"
  contact:
    name: 架构组
    email: arch@bidai.internal
  license:
    name: 内部保密文件，未经授权不得外传

servers:
  - url: https://{host}/api/v1
    description: 内网生产环境
    variables:
      host:
        default: bidai.internal
        description: 内网域名

# ============================================================
# 安全方案定义
# ============================================================
security:
  - BearerAuth: []

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: |
        JWT Token，通过 POST /auth/login 获取。
        Header 格式：Authorization: Bearer {access_token}

  # ============================================================
  # 公共 Schema 定义
  # ============================================================
  schemas:

    # —— 通用包装 ——
    CommonResponse:
      type: object
      required: [code, message, request_id]
      properties:
        code:
          type: integer
          example: 200
        message:
          type: string
          example: success
        data:
          description: 响应数据
        request_id:
          type: string
          example: req_abc123def456

    ErrorResponse:
      type: object
      required: [code, message, request_id]
      properties:
        code:
          type: integer
          example: 40001
        message:
          type: string
          example: 项目名称已存在
        detail:
          type: string
          description: 调试详情，生产环境可隐藏
        request_id:
          type: string
          example: req_abc123def456

    PaginationMeta:
      type: object
      properties:
        total:
          type: integer
          example: 100
        page:
          type: integer
          example: 1
        page_size:
          type: integer
          example: 20
        total_pages:
          type: integer
          example: 5

    AsyncTaskResponse:
      type: object
      required: [task_id, status, poll_url]
      properties:
        task_id:
          type: string
          example: task_xyz789abc
        status:
          type: string
          enum: [PENDING, RUNNING, SUCCESS, FAILED, CANCELLED, RETRYING]
          example: PENDING
        poll_url:
          type: string
          example: /api/v1/tasks/task_xyz789abc
        estimated_seconds:
          type: integer
          example: 30

    # —— 枚举值 ——
    EntityStatus:
      type: string
      enum: [DRAFT, IN_PROGRESS, REVIEWING, APPROVED, SUBMITTED, COMPLETED, CANCELLED, ARCHIVED]
      description: |
        DRAFT-草稿, IN_PROGRESS-进行中, REVIEWING-审核中,
        APPROVED-已审批, SUBMITTED-已递交, COMPLETED-已完成,
        CANCELLED-已取消, ARCHIVED-已归档

    TaskStatus:
      type: string
      enum: [PENDING, RUNNING, SUCCESS, FAILED, CANCELLED, RETRYING]

    SectionType:
      type: string
      enum: [TEMPLATE, DATA_FILL, FREE_NARRATIVE]
      description: |
        TEMPLATE-固定模板变量替换,
        DATA_FILL-结构化数据填充,
        FREE_NARRATIVE-LLM自由论述生成

    ConstraintType:
      type: string
      enum: [COMPLIANCE, CONTENT, GUIDE]
      description: |
        COMPLIANCE-合规要求（不满足即废标）,
        CONTENT-内容要求（必备材料）,
        GUIDE-写作引导（评分导向）

    RiskLevel:
      type: string
      enum: [HIGH, MEDIUM, LOW]

    RoleCode:
      type: string
      enum: [SYS_ADMIN, COMP_ADMIN, PROJECT_MGR, BID_STAFF, APPROVER, READER]

    # —— 用户 ——
    UserBrief:
      type: object
      properties:
        id:
          type: string
          format: uuid
        username:
          type: string
        real_name:
          type: string
        department:
          type: string
        roles:
          type: array
          items:
            $ref: '#/components/schemas/RoleCode'

    UserDetail:
      allOf:
        - $ref: '#/components/schemas/UserBrief'
        - type: object
          properties:
            email:
              type: string
              format: email
            is_active:
              type: boolean
            last_login_at:
              type: string
              format: date-time
            created_at:
              type: string
              format: date-time

    # —— 投标项目 ——
    ProjectBrief:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
          example: XX市政务云平台建设项目
        client:
          type: string
          example: XX市数据局
        status:
          $ref: '#/components/schemas/EntityStatus'
        tender_date:
          type: string
          format: date
          example: "2026-06-15"
        budget_amount:
          type: string
          description: 金额（元），字符串避免精度丢失
          example: "5000000.00"
        industry:
          type: string
          example: 政务信息化
        win_rate_score:
          type: number
          format: float
          description: 胜率评分 0~1
          example: 0.72

    ProjectDetail:
      allOf:
        - $ref: '#/components/schemas/ProjectBrief'
        - type: object
          properties:
            region:
              type: string
            description:
              type: string
            tender_agency:
              type: string
              description: 招标代理机构
            members:
              type: array
              items:
                $ref: '#/components/schemas/ProjectMember'
            bid_id:
              type: string
              format: uuid
              description: 关联标书 ID
            created_by:
              type: string
            created_at:
              type: string
              format: date-time
            updated_at:
              type: string
              format: date-time

    ProjectMember:
      type: object
      properties:
        user_id:
          type: string
          format: uuid
        username:
          type: string
        real_name:
          type: string
        project_role:
          type: string
          enum: [LEADER, MEMBER, REVIEWER]
        joined_at:
          type: string
          format: date-time

    # —— 文档解析 ——
    DocumentBrief:
      type: object
      properties:
        id:
          type: string
          format: uuid
        original_filename:
          type: string
        doc_type:
          type: string
          enum: [TENDER_DOC, BID_DOC, MATERIAL]
        parse_status:
          $ref: '#/components/schemas/TaskStatus'
        page_count:
          type: integer
        created_at:
          type: string
          format: date-time

    Constraint:
      type: object
      properties:
        id:
          type: string
          format: uuid
        constraint_no:
          type: string
          description: 约束编号，格式 Cxxx
          example: C001
        constraint_type:
          $ref: '#/components/schemas/ConstraintType'
        content:
          type: string
          description: 约束原文描述
        is_veto:
          type: boolean
          description: 是否为废标条款
        source_page:
          type: integer
          description: 原文所在页码
        confirmed:
          type: boolean
          description: 是否已人工确认

    # —— 知识库 ——
    KnowledgeDocument:
      type: object
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        doc_category:
          type: string
          enum: [QUALIFICATION, PERFORMANCE, PERSONNEL, SOLUTION_TEMPLATE, GENERAL]
        tags:
          type: array
          items:
            type: string
        file_type:
          type: string
        page_count:
          type: integer
        confidence:
          type: number
          description: AI 分类置信度
        ingest_mode:
          type: string
          enum: [AUTO, MANUAL_CONFIRM, MANUAL]
        is_expired:
          type: boolean
        created_at:
          type: string
          format: date-time

    KnowledgeSearchResult:
      type: object
      properties:
        chunk_id:
          type: string
          format: uuid
        doc_id:
          type: string
          format: uuid
        doc_title:
          type: string
        content:
          type: string
          description: 匹配的文本分块内容
        page_no:
          type: integer
        score:
          type: number
          description: 相关度分数 0~1
        highlight:
          type: string
          description: 高亮片段（含 HTML 标签）

    # —— 标书 ——
    BidDetail:
      type: object
      properties:
        id:
          type: string
          format: uuid
        project_id:
          type: string
          format: uuid
        bid_title:
          type: string
        bid_version:
          type: string
          example: v1.2
        status:
          $ref: '#/components/schemas/EntityStatus'
        total_sections:
          type: integer
        done_sections:
          type: integer
        progress_pct:
          type: number
          description: 完成百分比 0~100
          example: 65.50
        updated_at:
          type: string
          format: date-time

    BidSection:
      type: object
      properties:
        id:
          type: string
          format: uuid
        bid_id:
          type: string
          format: uuid
        parent_id:
          type: string
          format: uuid
          nullable: true
        section_no:
          type: string
          example: "3.2.1"
        title:
          type: string
        section_type:
          $ref: '#/components/schemas/SectionType'
        status:
          type: string
          enum: [PENDING, IN_PROGRESS, DONE, LOCKED]
        content:
          type: string
          description: 章节正文内容（Markdown）
        word_count:
          type: integer
        depth:
          type: integer
          description: 目录层级 1~5
        locked_by:
          type: string
          nullable: true
          description: 协同锁定人，非 null 表示被锁定
        constraint_coverage:
          type: number
          description: 约束覆盖率 0~1，<0.7 时前端显示警告
        review_status:
          type: string
          enum: [PENDING, APPROVED, REJECTED, SKIPPED]

    SectionVersion:
      type: object
      properties:
        version_no:
          type: integer
        content:
          type: string
        word_count:
          type: integer
        change_summary:
          type: string
        change_type:
          type: string
          enum: [MANUAL, AI_GEN, REVERT, IMPORT]
        created_by:
          type: string
        created_at:
          type: string
          format: date-time

    # —— 审查 ——
    ReviewTask:
      type: object
      properties:
        id:
          type: string
          format: uuid
        project_id:
          type: string
          format: uuid
        status:
          $ref: '#/components/schemas/TaskStatus'
        total_requirements:
          type: integer
        compliant_count:
          type: integer
        deviated_count:
          type: integer
        missing_count:
          type: integer
        compliance_rate:
          type: number
          description: 整体响应率 0~1

    ReviewItem:
      type: object
      properties:
        id:
          type: string
          format: uuid
        requirement_desc:
          type: string
        source_page:
          type: integer
        verdict:
          type: string
          enum: [COMPLIANT, DEVIATED, MISSING, PENDING]
        bid_response:
          type: string
          description: 标书对应响应原文
        deviation_desc:
          type: string
          nullable: true
        suggestion:
          type: string
          nullable: true

    # —— 串标分析 ——
    CollusionResult:
      type: object
      properties:
        id:
          type: string
          format: uuid
        status:
          $ref: '#/components/schemas/TaskStatus'
        risk_level:
          $ref: '#/components/schemas/RiskLevel'
        overall_score:
          type: number
          description: 综合串标风险评分 0~1
        suspicious_pairs:
          type: array
          items:
            $ref: '#/components/schemas/SuspiciousPair'
        summary:
          type: string
          description: 串标分析摘要说明

    SuspiciousPair:
      type: object
      properties:
        doc_a_id:
          type: string
          format: uuid
        doc_b_id:
          type: string
          format: uuid
        similarity_score:
          type: number
        evidence_items:
          type: array
          description: 关键证据列表
          items:
            type: object
            properties:
              dimension:
                type: string
                enum: [TEXT_SIMILARITY, FORMAT_SIMILARITY, PRICE_PATTERN, METADATA, IMAGE_SIMILARITY]
              score:
                type: number
              description:
                type: string

    # —— 胜率预测 ——
    WinRatePrediction:
      type: object
      properties:
        overall_score:
          type: number
          description: 综合胜率评分 0~1
          example: 0.72
        dimensions:
          type: array
          items:
            type: object
            properties:
              name:
                type: string
                example: 资质匹配度
              score:
                type: number
              weight:
                type: number
              suggestion:
                type: string
        risk_factors:
          type: array
          items:
            type: string
          description: 主要风险提示
        generated_at:
          type: string
          format: date-time

  # ============================================================
  # 公共响应定义
  # ============================================================
  responses:
    Unauthorized:
      description: Token 无效或已过期
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: 20002
            message: Token 已过期，请刷新
            request_id: req_abc123

    Forbidden:
      description: 权限不足
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: 20004
            message: 权限不足，无法执行此操作
            request_id: req_abc123

    NotFound:
      description: 资源不存在
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: 40002
            message: 资源不存在或已删除
            request_id: req_abc123

    BadRequest:
      description: 请求参数错误
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: 30001
            message: 必填参数缺失
            detail: "字段 'name' 不能为空"
            request_id: req_abc123

    InternalError:
      description: 服务内部错误
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: 10001
            message: 内部服务错误
            request_id: req_abc123

  # ============================================================
  # 公共请求参数
  # ============================================================
  parameters:
    PageParam:
      name: page
      in: query
      schema:
        type: integer
        default: 1
        minimum: 1
      description: 页码，从 1 开始

    PageSizeParam:
      name: page_size
      in: query
      schema:
        type: integer
        default: 20
        minimum: 1
        maximum: 100
      description: 每页条数，1~100

    PathId:
      name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
      description: 资源 UUID

    PathSid:
      name: sid
      in: path
      required: true
      schema:
        type: string
        format: uuid
      description: 章节 UUID


# ============================================================
# 接口路径定义
# ============================================================
paths:

  # ——————————————————————————————————————————————
  # 7.1 认证模块
  # ——————————————————————————————————————————————

  /auth/login:
    post:
      tags: [认证]
      summary: 用户登录
      description: 使用用户名密码登录，返回 JWT access_token 和 refresh_token。连续失败 5 次后账号锁定。
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [username, password]
              properties:
                username:
                  type: string
                  example: zhangsan
                password:
                  type: string
                  format: password
                  description: 明文密码，HTTPS 传输
                  example: "P@ssw0rd123"
      responses:
        '200':
          description: 登录成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          access_token:
                            type: string
                            description: JWT access_token，有效期 8 小时
                          refresh_token:
                            type: string
                            description: Refresh Token，有效期 30 天
                          expires_in:
                            type: integer
                            description: access_token 剩余有效秒数
                            example: 28800
                          user:
                            $ref: '#/components/schemas/UserBrief'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          description: 用户名或密码错误
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 20008
                message: 用户名或密码错误
                request_id: req_abc123
        '403':
          description: 账号已锁定
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 20007
                message: 账号已被锁定，请联系管理员解锁
                request_id: req_abc123

  /auth/refresh:
    post:
      tags: [认证]
      summary: 刷新 Token
      description: 使用有效的 refresh_token 换取新的 access_token。旧 refresh_token 即时失效（单次使用）。
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [refresh_token]
              properties:
                refresh_token:
                  type: string
      responses:
        '200':
          description: 刷新成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          access_token:
                            type: string
                          refresh_token:
                            type: string
                            description: 新的 refresh_token，旧的立即失效
                          expires_in:
                            type: integer
                            example: 28800
        '401':
          description: refresh_token 无效或已吊销
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 20003
                message: refresh_token 无效或已吊销，请重新登录
                request_id: req_abc123

  /auth/logout:
    post:
      tags: [认证]
      summary: 退出登录
      description: 吊销当前用户的 refresh_token，access_token 等待自然过期。
      responses:
        '200':
          description: 退出成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CommonResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /auth/me:
    get:
      tags: [认证]
      summary: 获取当前登录用户信息
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/UserDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'


  # ——————————————————————————————————————————————
  # 7.2 用户与权限模块
  # ——————————————————————————————————————————————

  /users:
    get:
      tags: [用户管理]
      summary: 获取用户列表
      description: 需要 `user:manage` 权限。支持按角色、部门、状态过滤。
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
        - name: role
          in: query
          schema:
            $ref: '#/components/schemas/RoleCode'
          description: 按角色过滤
        - name: department
          in: query
          schema:
            type: string
        - name: is_active
          in: query
          schema:
            type: boolean
        - name: keyword
          in: query
          schema:
            type: string
          description: 按用户名或姓名模糊搜索
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/PaginationMeta'
                          - type: object
                            properties:
                              items:
                                type: array
                                items:
                                  $ref: '#/components/schemas/UserDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

    post:
      tags: [用户管理]
      summary: 创建用户
      description: 需要 `user:manage` 权限 + MFA 验证。Header 需携带 `X-MFA-Token`。
      parameters:
        - name: X-MFA-Token
          in: header
          required: true
          schema:
            type: string
          description: MFA 验证通过后获得的短效 Token
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [username, real_name, email, password, roles]
              properties:
                username:
                  type: string
                  minLength: 3
                  maxLength: 32
                real_name:
                  type: string
                email:
                  type: string
                  format: email
                password:
                  type: string
                  format: password
                  minLength: 8
                  description: 初始密码，用户首次登录强制修改
                department:
                  type: string
                roles:
                  type: array
                  items:
                    $ref: '#/components/schemas/RoleCode'
                  minItems: 1
      responses:
        '201':
          description: 创建成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/UserDetail'
        '400':
          $ref: '#/components/responses/BadRequest'
        '403':
          $ref: '#/components/responses/Forbidden'
        '409':
          description: 用户名或邮箱已存在
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40001
                message: 用户名已存在
                request_id: req_abc123

  /users/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [用户管理]
      summary: 获取用户详情
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/UserDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

    put:
      tags: [用户管理]
      summary: 更新用户信息
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                real_name:
                  type: string
                email:
                  type: string
                  format: email
                department:
                  type: string
                is_active:
                  type: boolean
      responses:
        '200':
          description: 更新成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/UserDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

    delete:
      tags: [用户管理]
      summary: 注销用户（软删除）
      description: 需要 MFA 验证。注销后用户无法登录，数据保留。
      parameters:
        - name: X-MFA-Token
          in: header
          required: true
          schema:
            type: string
      responses:
        '204':
          description: 注销成功
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

  /users/{id}/roles:
    parameters:
      - $ref: '#/components/parameters/PathId'
    put:
      tags: [用户管理]
      summary: 设置用户角色
      description: 全量替换用户角色，需要 `user:manage` 权限。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [roles]
              properties:
                roles:
                  type: array
                  items:
                    $ref: '#/components/schemas/RoleCode'
                  minItems: 1
      responses:
        '200':
          description: 设置成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CommonResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'


  # ——————————————————————————————————————————————
  # 7.3 项目管理模块
  # ——————————————————————————————————————————————

  /projects:
    get:
      tags: [项目管理]
      summary: 获取投标项目列表
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
        - name: status
          in: query
          schema:
            $ref: '#/components/schemas/EntityStatus'
        - name: industry
          in: query
          schema:
            type: string
        - name: keyword
          in: query
          schema:
            type: string
          description: 按项目名称或客户名模糊搜索
        - name: tender_date_from
          in: query
          schema:
            type: string
            format: date
        - name: tender_date_to
          in: query
          schema:
            type: string
            format: date
        - name: my_projects_only
          in: query
          schema:
            type: boolean
            default: false
          description: 仅显示本人参与的项目
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/PaginationMeta'
                          - type: object
                            properties:
                              items:
                                type: array
                                items:
                                  $ref: '#/components/schemas/ProjectBrief'
        '401':
          $ref: '#/components/responses/Unauthorized'

    post:
      tags: [项目管理]
      summary: 创建投标项目
      description: 需要 `project:create` 权限。创建后自动生成关联空白标书。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [name, client, tender_date]
              properties:
                name:
                  type: string
                  maxLength: 256
                  example: XX市政务云平台建设项目
                client:
                  type: string
                  maxLength: 256
                  example: XX市数据局
                industry:
                  type: string
                  example: 政务信息化
                region:
                  type: string
                  example: 广东省广州市
                tender_date:
                  type: string
                  format: date
                  example: "2026-06-15"
                budget_amount:
                  type: string
                  description: 预算金额（元），字符串传输
                  example: "5000000.00"
                tender_agency:
                  type: string
                  description: 招标代理机构
                description:
                  type: string
      responses:
        '201':
          description: 创建成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/ProjectDetail'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '409':
          description: 同客户下已存在同名项目
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40001
                message: 同客户下已存在同名项目
                request_id: req_abc123

  /projects/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [项目管理]
      summary: 获取项目详情
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/ProjectDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

    put:
      tags: [项目管理]
      summary: 更新项目信息
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                name:
                  type: string
                client:
                  type: string
                industry:
                  type: string
                region:
                  type: string
                tender_date:
                  type: string
                  format: date
                budget_amount:
                  type: string
                status:
                  $ref: '#/components/schemas/EntityStatus'
                description:
                  type: string
      responses:
        '200':
          description: 更新成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/ProjectDetail'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 项目状态不允许修改
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40003
                message: 已归档的项目不允许编辑
                request_id: req_abc123

    delete:
      tags: [项目管理]
      summary: 归档/删除项目（软删除）
      responses:
        '204':
          description: 操作成功
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

  /projects/{id}/win-rate:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [项目管理]
      summary: 获取项目胜率预测
      description: |
        基于企业历史中标数据、资质匹配度、行业经验等维度综合评估。
        若数据不足（知识库健康度低于70分），将返回置信度较低的评估结果。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/WinRatePrediction'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /projects/{id}/bid-record:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [项目管理]
      summary: 录入投标结果
      description: 记录开标结果，用于知识库复盘沉淀。每个项目只能录入一条结果。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [result]
              properties:
                result:
                  type: string
                  enum: [WON, LOST, INVALID, WITHDREW, PENDING]
                bid_price:
                  type: string
                  description: 我方报价（元）
                winning_price:
                  type: string
                  description: 中标价（元），未知可不填
                ranking:
                  type: integer
                  description: 评标排名
                result_announced_at:
                  type: string
                  format: date
                fail_reason:
                  type: string
                  enum: [INVALID_FORMAT, MISSING_DOC, LOW_PRICE, HIGH_PRICE, LOW_SCORE, QUALIFICATION, COMPETITOR, RELATIONSHIP, OTHER]
                fail_reason_detail:
                  type: string
                review_notes:
                  type: string
                  description: 复盘笔记
      responses:
        '201':
          description: 录入成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CommonResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '409':
          description: 该项目已存在投标结果记录
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40001
                message: 该项目已录入投标结果，如需修改请联系管理员
                request_id: req_abc123


  # ——————————————————————————————————————————————
  # 7.4 文档解析模块
  # ——————————————————————————————————————————————

  /documents/parse:
    post:
      tags: [文档解析]
      summary: 上传并解析招标文件
      description: |
        上传招标文件（PDF/DOCX），系统将异步执行 OCR + 约束提取。
        **文件要求**：仅接受 pdf、docx 格式，单文件不超过 100MB。
        **返回**：HTTP 202 及 task_id，通过 `/tasks/{task_id}` 轮询进度。
        解析完成后，可通过 `GET /documents/{id}/constraints` 获取提取结果。
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file, project_id, doc_type]
              properties:
                file:
                  type: string
                  format: binary
                  description: 文件内容（pdf/docx），最大 100MB
                project_id:
                  type: string
                  format: uuid
                  description: 关联的投标项目 ID
                doc_type:
                  type: string
                  enum: [TENDER_DOC, BID_DOC, MATERIAL]
                  description: TENDER_DOC-招标文件，BID_DOC-投标文件，MATERIAL-素材
      responses:
        '202':
          description: 解析任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/AsyncTaskResponse'
                          - type: object
                            properties:
                              document_id:
                                type: string
                                format: uuid
                                description: 已创建的文档 ID，可立即用于查询元数据
        '400':
          description: 文件类型不合法或超过大小限制
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 30004
                message: 文件类型不在白名单，仅允许 pdf/docx
                request_id: req_abc123
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

  /documents/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [文档解析]
      summary: 获取文档详情
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/DocumentBrief'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /documents/{id}/constraints:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [文档解析]
      summary: 获取文档约束条件列表
      description: 获取该招标文件解析出的所有约束条件。文档尚未解析完成时返回 422。
      parameters:
        - name: constraint_type
          in: query
          schema:
            $ref: '#/components/schemas/ConstraintType'
        - name: is_veto
          in: query
          schema:
            type: boolean
          description: 仅显示废标条款
        - name: confirmed
          in: query
          schema:
            type: boolean
          description: 按确认状态过滤
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        items:
                          $ref: '#/components/schemas/Constraint'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 文档尚未解析完成
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40007
                message: 文档尚未完成解析，请等待
                request_id: req_abc123

    put:
      tags: [文档解析]
      summary: 批量确认/修改约束条件
      description: 人工审核约束提取结果，可修改分类、内容，或删除误提取项。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [updates]
              properties:
                updates:
                  type: array
                  items:
                    type: object
                    required: [constraint_id, action]
                    properties:
                      constraint_id:
                        type: string
                        format: uuid
                      action:
                        type: string
                        enum: [CONFIRM, MODIFY, DELETE]
                      constraint_type:
                        $ref: '#/components/schemas/ConstraintType'
                      content:
                        type: string
                      is_veto:
                        type: boolean
      responses:
        '200':
          description: 更新成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          updated_count:
                            type: integer
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'


  # ——————————————————————————————————————————————
  # 7.5 知识库模块
  # ——————————————————————————————————————————————

  /knowledge/search:
    get:
      tags: [知识库]
      summary: 语义检索知识库
      description: |
        使用向量检索 + 全文检索混合模式（HybridRetriever），
        结果经 Cross-Encoder 重排序后返回，P99 响应时间 < 3 秒。
      parameters:
        - name: query
          in: query
          required: true
          schema:
            type: string
            minLength: 2
          description: 查询关键词或自然语言描述
        - name: doc_category
          in: query
          schema:
            type: string
            enum: [QUALIFICATION, PERFORMANCE, PERSONNEL, SOLUTION_TEMPLATE, GENERAL]
          description: 限定知识库分类
        - name: tags
          in: query
          schema:
            type: array
            items:
              type: string
          style: form
          explode: false
          description: 标签过滤（逗号分隔）
        - name: top_k
          in: query
          schema:
            type: integer
            default: 10
            minimum: 1
            maximum: 50
          description: 返回结果数量
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          results:
                            type: array
                            items:
                              $ref: '#/components/schemas/KnowledgeSearchResult'
                          total_found:
                            type: integer
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '503':
          description: 向量检索服务不可用
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 50005
                message: 向量检索服务暂时不可用，请稍后重试
                request_id: req_abc123

  /knowledge/upload:
    post:
      tags: [知识库]
      summary: 上传文档入库
      description: |
        上传文档至企业知识库，系统自动完成 OCR → 分块 → 向量化 → 分类。
        重复文件（SHA-256 哈希相同）将跳过入库并返回已存在文档的 ID。
        **文件要求**：支持 pdf/docx/xlsx/jpg/png，单文件不超过 100MB。
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file, doc_category]
              properties:
                file:
                  type: string
                  format: binary
                doc_category:
                  type: string
                  enum: [QUALIFICATION, PERFORMANCE, PERSONNEL, SOLUTION_TEMPLATE, GENERAL]
                title:
                  type: string
                  description: 文档标题，不填则使用原始文件名
                tags:
                  type: string
                  description: 标签列表（JSON 数组字符串）
                  example: '["政务信息化","广东省"]'
      responses:
        '202':
          description: 入库任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/AsyncTaskResponse'
                          - type: object
                            properties:
                              document_id:
                                type: string
                                format: uuid
                              is_duplicate:
                                type: boolean
                                description: 是否为重复文件
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

  /knowledge/documents:
    get:
      tags: [知识库]
      summary: 获取知识库文档列表
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
        - name: doc_category
          in: query
          schema:
            type: string
        - name: tags
          in: query
          schema:
            type: array
            items:
              type: string
          style: form
          explode: false
        - name: is_expired
          in: query
          schema:
            type: boolean
        - name: keyword
          in: query
          schema:
            type: string
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/PaginationMeta'
                          - type: object
                            properties:
                              items:
                                type: array
                                items:
                                  $ref: '#/components/schemas/KnowledgeDocument'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /knowledge/documents/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [知识库]
      summary: 获取知识库文档详情
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/KnowledgeDocument'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

    delete:
      tags: [知识库]
      summary: 删除知识库文档（软删除）
      description: 需要 `knowledge:manage` 权限。删除后向量及索引将同步清理（异步）。
      responses:
        '204':
          description: 删除成功
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

  /knowledge/stats:
    get:
      tags: [知识库]
      summary: 获取知识库统计信息
      description: 返回各分类文档数量、健康度评分、过期证书预警等聚合统计。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          total_documents:
                            type: integer
                          health_score:
                            type: number
                            description: 知识库健康度 0~100，≥70 可正常运行
                          category_stats:
                            type: array
                            items:
                              type: object
                              properties:
                                category:
                                  type: string
                                count:
                                  type: integer
                                expired_count:
                                  type: integer
                          expiring_soon:
                            type: array
                            description: 即将过期的证书（30天内）
                            items:
                              type: object
                              properties:
                                doc_id:
                                  type: string
                                  format: uuid
                                title:
                                  type: string
                                expire_date:
                                  type: string
                                  format: date
        '401':
          $ref: '#/components/responses/Unauthorized'


  # ——————————————————————————————————————————————
  # 7.6 标书编写模块
  # ——————————————————————————————————————————————

  /bids/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [标书编写]
      summary: 获取标书详情
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/BidDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/outline:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [标书编写]
      summary: AI 生成标书目录结构
      description: |
        基于招标文件约束和行业模板，AI 生成多级目录结构。
        **异步接口**，返回 task_id，完成后目录结构写入 bid_sections 表。
        若标书已有章节，需先确认覆盖才能重新生成。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [tender_doc_id]
              properties:
                tender_doc_id:
                  type: string
                  format: uuid
                  description: 招标文件 ID，约束已确认
                template_ref:
                  type: string
                  format: uuid
                  description: 参考方案模板 ID（可选）
                extra_instruction:
                  type: string
                  description: 额外目录生成指令
                  example: 增加"项目实施保障"独立章节
                force_overwrite:
                  type: boolean
                  default: false
                  description: 是否覆盖已有目录
      responses:
        '202':
          description: 目录生成任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/AsyncTaskResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 招标文件约束尚未确认，或标书已有目录且未强制覆盖
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /bids/{id}/sections:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [标书编写]
      summary: 获取标书章节列表（目录树）
      description: 返回完整目录树结构，不含章节正文内容（正文通过单章节接口获取）。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: array
                        description: 顶层章节列表，每个章节含 children 子章节
                        items:
                          allOf:
                            - $ref: '#/components/schemas/BidSection'
                            - type: object
                              properties:
                                children:
                                  type: array
                                  items:
                                    $ref: '#/components/schemas/BidSection'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/sections/{sid}/generate:
    parameters:
      - $ref: '#/components/parameters/PathId'
      - $ref: '#/components/parameters/PathSid'
    post:
      tags: [标书编写]
      summary: AI 生成章节内容（三分法路由）
      description: |
        系统根据章节类型（section_type）自动路由生成策略：
        - **TEMPLATE**：变量替换填充，秒级返回（同步）
        - **DATA_FILL**：从知识库精确查询结构化数据，< 5 秒（同步）
        - **FREE_NARRATIVE**：LLM 自由论述生成，异步返回 task_id，P99 < 120 秒
        
        生成前系统自动检测敏感数据，如包含报价/人员身份等信息将强制使用私有化模型。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                constraints:
                  type: array
                  items:
                    type: string
                  description: 需覆盖的约束编号列表，如 ["C001","C005"]
                  example: ["C001", "C005", "C012"]
                knowledge_refs:
                  type: array
                  items:
                    type: string
                    format: uuid
                  description: 引用的知识库文档 ID 列表
                style:
                  type: string
                  enum: [professional, concise, detailed]
                  default: professional
                length_hint:
                  type: string
                  enum: [brief, standard, detailed]
                  default: standard
                  description: brief≈300字, standard≈800字, detailed≈1500字
                extra_instruction:
                  type: string
                  description: 额外生成指令
                  example: 重点突出我司在数据中心领域的建设经验
      responses:
        '200':
          description: 生成完成（TEMPLATE / DATA_FILL 类型同步返回）
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          section_id:
                            type: string
                            format: uuid
                          content:
                            type: string
                          word_count:
                            type: integer
                          references:
                            type: array
                            items:
                              type: object
                              properties:
                                kb_id:
                                  type: string
                                  format: uuid
                                title:
                                  type: string
                                page:
                                  type: integer
                          constraint_coverage:
                            type: object
                            properties:
                              covered:
                                type: array
                                items:
                                  type: string
                              uncovered:
                                type: array
                                items:
                                  type: string
                              coverage_rate:
                                type: number
                                example: 0.67
                          confidence:
                            type: number
                            example: 0.82
        '202':
          description: 生成任务已提交（FREE_NARRATIVE 类型异步返回）
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/AsyncTaskResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 章节被锁定或标书状态不允许编辑
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40005
                message: 章节正在被其他用户编辑，请稍后再试
                request_id: req_abc123
        '503':
          description: LLM 服务不可用
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 50001
                message: AI 生成服务暂时不可用，已进入队列等待
                request_id: req_abc123

  /bids/{id}/sections/{sid}:
    parameters:
      - $ref: '#/components/parameters/PathId'
      - $ref: '#/components/parameters/PathSid'
    get:
      tags: [标书编写]
      summary: 获取章节详情（含正文）
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/BidSection'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

    put:
      tags: [标书编写]
      summary: 编辑章节内容
      description: |
        人工编辑或覆盖章节内容，自动写入版本历史（change_type=MANUAL）。
        编辑前需确保章节未被其他用户锁定（locked_by 为空或为当前用户）。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [content]
              properties:
                content:
                  type: string
                  description: 章节正文（Markdown 格式）
                change_summary:
                  type: string
                  description: 本次修改摘要
                  example: 补充了数据安全防护措施相关内容
      responses:
        '200':
          description: 保存成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/BidSection'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 章节被锁定
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40005
                message: 章节正在被 lisi 编辑，请稍后再试
                request_id: req_abc123

  /bids/{id}/sections/{sid}/versions:
    parameters:
      - $ref: '#/components/parameters/PathId'
      - $ref: '#/components/parameters/PathSid'
    get:
      tags: [标书编写]
      summary: 获取章节版本历史
      parameters:
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/PaginationMeta'
                          - type: object
                            properties:
                              items:
                                type: array
                                items:
                                  $ref: '#/components/schemas/SectionVersion'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/sections/{sid}/revert:
    parameters:
      - $ref: '#/components/parameters/PathId'
      - $ref: '#/components/parameters/PathSid'
    post:
      tags: [标书编写]
      summary: 回滚章节到指定版本
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [target_version_no]
              properties:
                target_version_no:
                  type: integer
                  description: 目标版本序号
      responses:
        '200':
          description: 回滚成功，返回回滚后的章节
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/BidSection'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/variables:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [标书编写]
      summary: 获取标书全局变量
      description: 全局变量用于 TEMPLATE 类型章节的占位符替换（如 {{公司名称}}）。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        description: key-value 键值对，key 为变量名
                        additionalProperties:
                          type: string
                        example:
                          公司名称: XX科技有限公司
                          注册资本: 5000万元
                          法人代表: 张三
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

    put:
      tags: [标书编写]
      summary: 批量更新全局变量
      description: 全量替换全局变量配置。更新后，所有 TEMPLATE 类型章节的预览将自动刷新。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              description: key-value 键值对
              additionalProperties:
                type: string
              example:
                公司名称: XX科技有限公司
                注册资本: 5000万元
      responses:
        '200':
          description: 更新成功
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CommonResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/check:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [标书编写]
      summary: 执行标书一致性检查
      description: |
        检测标书内跨章节的数据不一致问题，包括：
        - 全局变量引用不一致（如公司名称前后不统一）
        - 金额数字大小写不匹配
        - 日期逻辑矛盾
        - 资质/人员名称与知识库不符
        
        **异步接口**，通常 10~30 秒完成。
      responses:
        '202':
          description: 检查任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/AsyncTaskResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'

  /bids/{id}/submit:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [标书编写]
      summary: 提交标书审批
      description: 提交后标书进入 REVIEWING 状态，所有章节锁定编辑直到审批结束。
      responses:
        '200':
          description: 提交成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/BidDetail'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 标书完成度不足或存在未确认的约束
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40010
                message: 标书尚有 3 个章节未完成，无法提交审批
                request_id: req_abc123


  # ——————————————————————————————————————————————
  # 7.7 投标审查模块
  # ——————————————————————————————————————————————

  /reviews:
    post:
      tags: [投标审查]
      summary: 创建投标审查任务
      description: |
        对标书文件进行逐项合规审查，逐条比对招标文件要求。
        **异步接口**，P99 < 60 秒。
        同一标书不可同时存在两个进行中的审查任务。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [project_id, tender_doc_id, bid_doc_id]
              properties:
                project_id:
                  type: string
                  format: uuid
                tender_doc_id:
                  type: string
                  format: uuid
                  description: 招标文件 ID
                bid_doc_id:
                  type: string
                  format: uuid
                  description: 待审查标书文件 ID（已上传至文档模块）
      responses:
        '202':
          description: 审查任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/AsyncTaskResponse'
                          - type: object
                            properties:
                              review_id:
                                type: string
                                format: uuid
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '409':
          description: 该标书已有审查任务进行中
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40009
                message: 该标书已有审查任务进行中，请等待完成后再提交
                request_id: req_abc123

  /reviews/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [投标审查]
      summary: 获取审查任务状态
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/ReviewTask'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'

  /reviews/{id}/result:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [投标审查]
      summary: 获取审查结果详情
      description: 仅在审查任务状态为 SUCCESS 时可获取，返回逐项响应情况。
      parameters:
        - name: verdict
          in: query
          schema:
            type: string
            enum: [COMPLIANT, DEVIATED, MISSING, PENDING]
          description: 按审查结论过滤
        - $ref: '#/components/parameters/PageParam'
        - $ref: '#/components/parameters/PageSizeParam'
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/PaginationMeta'
                          - type: object
                            properties:
                              summary:
                                $ref: '#/components/schemas/ReviewTask'
                              items:
                                type: array
                                items:
                                  $ref: '#/components/schemas/ReviewItem'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 审查任务尚未完成
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /reviews/{id}/report:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [投标审查]
      summary: 导出审查报告
      description: |
        生成结构化审查报告（PDF/DOCX）。
        **异步接口**，完成后通过 `GET /export/download/{file_id}` 下载。
        报告含动态水印（用户ID + 导出时间）。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                format:
                  type: string
                  enum: [PDF, DOCX]
                  default: PDF
      responses:
        '202':
          description: 报告生成任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/AsyncTaskResponse'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'


  # ——————————————————————————————————————————————
  # 7.8 串标分析模块
  # ——————————————————————————————————————————————

  /collusion/analyze:
    post:
      tags: [串标分析]
      summary: 提交串标分析任务
      description: |
        对多份投标文件进行多维度相似度分析（文本、格式、元数据、报价规律、印章）。
        **异步接口**，P99 < 300 秒（取决于文件数量）。
        分析报告定位为辅助参考，不作为法律证据，首页含免责声明。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [doc_ids]
              properties:
                doc_ids:
                  type: array
                  items:
                    type: string
                    format: uuid
                  minItems: 2
                  maxItems: 20
                  description: 待分析的投标文件 ID 列表（2~20份）
                analyze_dimensions:
                  type: array
                  items:
                    type: string
                    enum: [TEXT_SIMILARITY, FORMAT_SIMILARITY, PRICE_PATTERN, METADATA, IMAGE_SIMILARITY]
                  default: [TEXT_SIMILARITY, FORMAT_SIMILARITY, PRICE_PATTERN, METADATA]
                  description: 分析维度，默认不含图像（耗时较长）
      responses:
        '202':
          description: 分析任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/AsyncTaskResponse'
                          - type: object
                            properties:
                              analysis_id:
                                type: string
                                format: uuid
        '400':
          description: 文件数量不足（至少2份）
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 30003
                message: 串标分析至少需要 2 份投标文件
                request_id: req_abc123
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'

  /collusion/{id}/result:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [串标分析]
      summary: 获取串标分析结果
      description: 仅在任务状态为 SUCCESS 时可获取完整结果。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        $ref: '#/components/schemas/CollusionResult'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 分析任务尚未完成
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'


  # ——————————————————————————————————————————————
  # 7.9 异步任务查询（通用）
  # ——————————————————————————————————————————————

  /tasks/{task_id}:
    get:
      tags: [异步任务]
      summary: 查询异步任务状态
      description: |
        通用任务状态查询接口，适用于所有返回 task_id 的异步接口。
        建议轮询间隔：2~5 秒。
        任务结果保留 24 小时，超时后返回 404。
      security:
        - BearerAuth: []
      parameters:
        - name: task_id
          in: path
          required: true
          schema:
            type: string
          description: 异步任务 ID
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          task_id:
                            type: string
                          task_type:
                            type: string
                            enum: [DOC_PARSE, DOC_EMBED, SECTION_GENERATE, CONSTRAINT_EXTRACT, WIN_RATE_CALC, REVIEW_CHECK, COLLUSION_ANALYZE, CHECK_CONSISTENCY]
                          status:
                            $ref: '#/components/schemas/TaskStatus'
                          progress:
                            type: integer
                            description: 进度百分比 0~100
                            example: 65
                          result_url:
                            type: string
                            description: 任务成功后，可通过此 URL 获取完整结果
                          error_message:
                            type: string
                            nullable: true
                          queued_at:
                            type: string
                            format: date-time
                          started_at:
                            type: string
                            format: date-time
                            nullable: true
                          completed_at:
                            type: string
                            format: date-time
                            nullable: true
                          duration_ms:
                            type: integer
                            nullable: true
        '401':
          $ref: '#/components/responses/Unauthorized'
        '404':
          description: 任务不存在或已过期（结果保留24小时）
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'


  # ——————————————————————————————————————————————
  # 7.10 文件导出模块
  # ——————————————————————————————————————————————

  /export/bids/{id}:
    parameters:
      - $ref: '#/components/parameters/PathId'
    post:
      tags: [文件导出]
      summary: 导出标书文件
      description: |
        将标书导出为 Word（DOCX）或 PDF 格式。
        **需要 `bid:export` 权限**。
        导出文件自动嵌入动态水印（用户ID + 导出时间 + 项目编号）。
        **异步接口**，通常 10~60 秒完成。
        下载链接有效期 15 分钟，过期需重新请求。
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                format:
                  type: string
                  enum: [DOCX, PDF]
                  default: DOCX
                include_check_report:
                  type: boolean
                  default: false
                  description: 是否附带一致性检查报告
                watermark:
                  type: boolean
                  default: true
                  description: 是否嵌入动态水印（生产环境强制为 true）
      responses:
        '202':
          description: 导出任务已提交
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        allOf:
                          - $ref: '#/components/schemas/AsyncTaskResponse'
                          - type: object
                            properties:
                              export_id:
                                type: string
                                format: uuid
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
        '422':
          description: 标书不满足导出条件
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
              example:
                code: 40010
                message: 标书尚有未完成章节，无法导出
                request_id: req_abc123

  /export/bids/{id}/download:
    parameters:
      - $ref: '#/components/parameters/PathId'
    get:
      tags: [文件导出]
      summary: 获取导出文件下载链接
      description: |
        返回 MinIO Pre-signed URL，直接下载导出文件，有效期 15 分钟。
        下载行为将记录至审计日志。
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/CommonResponse'
                  - type: object
                    properties:
                      data:
                        type: object
                        properties:
                          download_url:
                            type: string
                            description: Pre-signed 下载 URL，有效期 15 分钟
                          filename:
                            type: string
                            example: XX市政务云平台建设项目_标书_v2.0.docx
                          file_size_bytes:
                            type: integer
                          expires_at:
                            type: string
                            format: date-time
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          description: 导出文件不存在或尚未生成
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

# ============================================================
# 标签定义（接口分组）
# ============================================================
tags:
  - name: 认证
    description: 登录、Token 管理
  - name: 用户管理
    description: 用户 CRUD、角色权限分配
  - name: 项目管理
    description: 投标项目生命周期管理，含胜率预测
  - name: 文档解析
    description: 招标文件上传、OCR 解析、约束提取
  - name: 知识库
    description: 企业知识库管理（资质/业绩/人员/方案），语义检索
  - name: 标书编写
    description: AI 协同编写、章节管理、版本控制、一致性检查
  - name: 投标审查
    description: 合规性逐项审查，审查报告导出
  - name: 串标分析
    description: 多维度投标文件相似度分析
  - name: 异步任务
    description: 通用异步任务状态查询
  - name: 文件导出
    description: 标书 DOCX/PDF 导出，含水印
```

---

## 8. 附录：权限矩阵

### 8.1 角色与接口权限对照

| 接口 | SYS_ADMIN | COMP_ADMIN | PROJECT_MGR | BID_STAFF | APPROVER | READER |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| 用户管理（CRUD） | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 创建项目 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 查看项目 | ✅ | ✅ | ✅ | ✅* | ✅* | ✅* |
| 上传/管理知识库 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 语义检索知识库 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| AI 生成章节 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 编辑章节内容 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 提交审批 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 审批标书 | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| 导出标书 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 创建审查任务 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 查看审查报告 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 串标分析 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |

> \* 仅限被加入为项目成员的项目；PROJECT_MGR 可查看所有项目。

### 8.2 数据安全说明

- 标有 `🔐` 字段的接口，其请求/响应数据不得通过外部 LLM API 处理
- 文件导出接口会在审计日志（`audit.export_logs`）中记录操作人、时间、IP
- Pre-signed URL 有效期严格限制为 15 分钟，不可延长

---

*本文档为 AI 智能投标系统 API 接口规范，如有修订请同步更新版本号并记录变更。*

*© 2026 内部保密文件，未经授权不得外传。*  
*最后更新：2026-04-28 | 文档负责人：架构组*
