# AI 智能投标系统 · 数据库设计文档

**文档编号**：DB-BIDAI-2026-001  
**关联方案**：TSD-BIDAI-2026-001 V1.0  
**版本**：V1.0  
**编制日期**：2026-04-21  
**数据库引擎**：PostgreSQL 15+  
**密级**：内部保密

---

## 目录

1. [设计原则与约定](#1-设计原则与约定)
2. [数据库全局 ERD](#2-数据库全局-erd)
3. [Schema 划分](#3-schema-划分)
4. [DDL：基础扩展与公共对象](#4-ddl基础扩展与公共对象)
5. [DDL：用户与权限域（auth）](#5-ddl用户与权限域auth)
6. [DDL：项目管理域（project）](#6-ddl项目管理域project)
7. [DDL：知识库域（knowledge）](#7-ddl知识库域knowledge)
8. [DDL：标书编写域（bid）](#8-ddl标书编写域bid)
9. [DDL：AI 任务与审查域（ai_task）](#9-ddlai-任务与审查域ai_task)
10. [DDL：审计日志域（audit）](#10-ddl审计日志域audit)
11. [索引策略](#11-索引策略)
12. [分区策略](#12-分区策略)
13. [视图与物化视图](#13-视图与物化视图)
14. [触发器与函数](#14-触发器与函数)
15. [数据字典](#15-数据字典)
16. [迁移管理规范](#16-迁移管理规范)

---

## 1. 设计原则与约定

### 1.1 全局字段约定

所有业务表**必须**包含以下基础字段：

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `id` | `UUID` | 主键，`gen_random_uuid()` 生成，禁止使用自增整数 |
| `created_at` | `TIMESTAMPTZ` | 创建时间，`NOW()` 默认值 |
| `updated_at` | `TIMESTAMPTZ` | 更新时间，触发器自动维护 |
| `deleted_at` | `TIMESTAMPTZ` | 软删除时间戳，`NULL` 表示未删除 |
| `created_by` | `VARCHAR(64)` | 创建人 `user_id`，冗余存储 |
| `updated_by` | `VARCHAR(64)` | 最后修改人 `user_id` |

### 1.2 命名规范

- **Schema**：小写单词，按业务域划分（`auth` / `project` / `knowledge` / `bid` / `ai_task` / `audit`）
- **表名**：`schema名.实体名`，蛇形命名，复数形式（如 `project.bid_projects`）
- **字段名**：蛇形命名，含义清晰（如 `tender_date` 而非 `td`）
- **索引名**：`idx_{表名}_{字段列表}`
- **外键名**：`fk_{表名}_{引用表名}`
- **唯一约束**：`uq_{表名}_{字段列表}`
- **分区表**：`{主表名}_{分区标识}`（如 `audit_logs_2026_q2`）

### 1.3 数据类型规范

| 场景 | 推荐类型 | 禁止使用 |
|------|----------|----------|
| 主键 / 外键 | `UUID` | `SERIAL` / `BIGSERIAL` |
| 金额 | `NUMERIC(18, 2)` | `FLOAT` / `DOUBLE` |
| 时间 | `TIMESTAMPTZ` | `TIMESTAMP`（无时区）|
| 日期 | `DATE` | `VARCHAR` |
| 布尔 | `BOOLEAN` | `SMALLINT` / `CHAR(1)` |
| 枚举状态 | `VARCHAR(32)` + `CHECK` | 裸 `INT` 魔法数字 |
| 长文本 | `TEXT` | `VARCHAR(n)`（超过 1000 字符）|
| JSON 结构 | `JSONB` | `JSON` / `TEXT` |
| 敏感信息 | `BYTEA`（应用层加密）| 明文 `VARCHAR` |
| 评分 / 置信度 | `NUMERIC(5, 4)`（0.0000~1.0000）| `FLOAT` |
| 向量 ID 引用 | `VARCHAR(128)` | — |

### 1.4 软删除规范

- 所有业务数据禁止物理删除，统一使用 `deleted_at IS NOT NULL` 标记删除
- 所有查询须通过视图或 WHERE 条件过滤 `deleted_at IS NULL`
- 审计日志、操作记录表**不设** `deleted_at`（不可删除）

### 1.5 敏感字段加密规范

以下字段在应用层使用 AES-256-GCM 加密后以 `BYTEA` 存储，列名以 `_enc` 后缀标识：

- 人员身份证号 → `id_number_enc`
- 人员手机号 → `phone_enc`
- 银行账号 → `bank_account_enc`
- 法定代表人信息 → 通过加密字段存储

---

## 2. 数据库全局 ERD

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AUTH DOMAIN                                                            │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐    ┌──────────────┐  │
│  │  users   │───<│ user_roles   │>───│  roles   │───<│role_perms    │  │
│  └──────────┘    └──────────────┘    └──────────┘    └──────────────┘  │
│       │                                                    │            │
│       │                                             ┌──────────────┐   │
│       │                                             │ permissions  │   │
│       │                                             └──────────────┘   │
└───────┼─────────────────────────────────────────────────────────────────┘
        │ created_by / assigned_to
        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PROJECT DOMAIN                                                         │
│  ┌────────────────┐    ┌───────────────────┐    ┌───────────────────┐  │
│  │  bid_projects  │───<│ project_members   │    │  bid_records      │  │
│  └───────┬────────┘    └───────────────────┘    └───────────────────┘  │
│          │  1                                            ▲             │
│          │  └── bid_projects.id ──────────────────────── ┘             │
└──────────┼──────────────────────────────────────────────────────────────┘
           │ project_id
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  KNOWLEDGE DOMAIN                                                        │
│  ┌───────────────┐   ┌───────────┐   ┌───────────────┐                 │
│  │  kb_documents │──<│ kb_chunks │──<│ kb_chunk_tags │                 │
│  └──────┬────────┘   └─────┬─────┘   └───────────────┘                 │
│         │                  │                                            │
│  ┌──────┴──────────┐       │ (milvus_id ref)                           │
│  │qualifications   │       │                                            │
│  ├─────────────────┤  ┌────┴──────────────┐    ┌──────────────────┐   │
│  │performances     │  │ kb_embeddings_ref │    │  kb_tags         │   │
│  ├─────────────────┤  └───────────────────┘    └──────────────────┘   │
│  │personnel        │                                                    │
│  └─────────────────┘                                                    │
└──────────────────────────────────────────────────────────────────────────┘
           │ knowledge refs
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  BID DOMAIN                                                              │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │   bids   │─<│ bid_sections │  │ bid_variables  │  │bid_var_refs  │  │
│  └──────────┘  └──────┬───────┘  └────────────────┘  └──────────────┘  │
│                       │                                                  │
│              ┌────────┴────────┐  ┌────────────────┐                   │
│              │ section_versions│  │ bid_check_rpts │                   │
│              └─────────────────┘  └────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘
           │ bid_id / project_id
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  AI_TASK DOMAIN                                                          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────┐    │
│  │  ai_tasks    │  │ review_tasks   │  │ collusion_analysis_tasks │    │
│  └──────────────┘  └────────────────┘  └──────────────────────────┘    │
│  ┌──────────────┐  ┌────────────────┐                                   │
│  │ review_items │  │doc_constraints │                                   │
│  └──────────────┘  └────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────┘
           │ all operations
           ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  AUDIT DOMAIN                                                            │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────────────┐    │
│  │  audit_logs  │  │  export_logs   │  │  llm_call_logs           │    │
│  └──────────────┘  └────────────────┘  └──────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Schema 划分

```sql
-- ============================================================
-- 创建业务域 Schema
-- ============================================================
CREATE SCHEMA IF NOT EXISTS auth;       -- 用户、角色、权限
CREATE SCHEMA IF NOT EXISTS project;   -- 投标项目、项目成员、投标记录
CREATE SCHEMA IF NOT EXISTS knowledge; -- 企业知识库（文档、分块、资质、业绩、人员）
CREATE SCHEMA IF NOT EXISTS bid;       -- 标书编写（标书、章节、变量、检查报告）
CREATE SCHEMA IF NOT EXISTS ai_task;   -- AI 任务队列、审查、串标分析、约束提取
CREATE SCHEMA IF NOT EXISTS audit;     -- 审计日志、导出记录、LLM 调用日志

-- 搜索路径（应用连接时设置）
-- SET search_path = auth, project, knowledge, bid, ai_task, audit, public;
```

---

## 4. DDL：基础扩展与公共对象

```sql
-- ============================================================
-- 启用必要扩展
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid(), 加密函数
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- 中文模糊搜索支持
CREATE EXTENSION IF NOT EXISTS "btree_gin";   -- GIN 索引支持 B-tree 操作符
CREATE EXTENSION IF NOT EXISTS "unaccent";    -- 文本标准化

-- ============================================================
-- 公共函数：自动维护 updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION public.fn_update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- 公共枚举类型
-- ============================================================

-- 通用状态枚举（适用于项目、标书等主实体）
CREATE TYPE public.entity_status AS ENUM (
    'DRAFT',        -- 草稿
    'IN_PROGRESS',  -- 进行中
    'REVIEWING',    -- 审核中
    'APPROVED',     -- 已审批
    'SUBMITTED',    -- 已提交
    'COMPLETED',    -- 已完成
    'CANCELLED',    -- 已取消
    'ARCHIVED'      -- 已归档
);

-- AI 任务状态枚举
CREATE TYPE public.task_status AS ENUM (
    'PENDING',      -- 等待执行
    'RUNNING',      -- 执行中
    'SUCCESS',      -- 成功
    'FAILED',       -- 失败
    'CANCELLED',    -- 已取消
    'RETRYING'      -- 重试中
);

-- 投标结果枚举
CREATE TYPE public.bid_result AS ENUM (
    'WON',          -- 中标
    'LOST',         -- 未中标
    'INVALID',      -- 废标
    'WITHDREW',     -- 撤标
    'PENDING'       -- 待定（结果未出）
);

-- 文档类型枚举
CREATE TYPE public.document_type AS ENUM (
    'TENDER_DOC',       -- 招标文件
    'QUALIFICATION',    -- 资质证书
    'PERFORMANCE',      -- 业绩材料
    'PERSONNEL',        -- 人员材料
    'SOLUTION',         -- 技术方案
    'TEMPLATE',         -- 标书模板
    'MISC'              -- 其他
);

-- 章节类型枚举（三分法路由）
CREATE TYPE public.section_type AS ENUM (
    'TEMPLATE',         -- 固定模板（变量填充）
    'DATA_FILL',        -- 结构化数据填充
    'FREE_NARRATIVE'    -- 自由论述（LLM 生成）
);

-- 约束类型枚举
CREATE TYPE public.constraint_type AS ENUM (
    'COMPLIANCE',   -- 合规要求（废标条款）
    'CONTENT',      -- 内容要求（必备材料）
    'GUIDE'         -- 写作引导（评分导向）
);

-- 审查结论枚举
CREATE TYPE public.review_verdict AS ENUM (
    'COMPLIANT',    -- 符合
    'DEVIATED',     -- 偏离
    'MISSING',      -- 缺失
    'PENDING'       -- 待确认
);

-- 风险等级枚举
CREATE TYPE public.risk_level AS ENUM (
    'HIGH',   -- 高风险
    'MEDIUM', -- 中风险
    'LOW'     -- 低风险
);

-- 检查项结论枚举
CREATE TYPE public.check_result AS ENUM (
    'PASS',   -- 通过（绿色）
    'WARN',   -- 警告（橙色）
    'FAIL'    -- 否决（红色）
);
```

---

## 5. DDL：用户与权限域（auth）

```sql
-- ============================================================
-- auth.users — 系统用户表
-- ============================================================
CREATE TABLE auth.users (
    -- 基础主键
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 业务字段
    username        VARCHAR(64)  NOT NULL,
    display_name    VARCHAR(128) NOT NULL,
    email           VARCHAR(256) NOT NULL,
    phone_enc       BYTEA,                          -- 手机号（AES-256 加密存储）
    department      VARCHAR(128),                   -- 所属部门
    job_title       VARCHAR(128),                   -- 职务
    avatar_url      VARCHAR(512),                   -- 头像 MinIO 路径
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,

    -- 认证信息
    password_hash   VARCHAR(256) NOT NULL,          -- bcrypt 哈希
    last_login_at   TIMESTAMPTZ,
    login_fail_cnt  SMALLINT     NOT NULL DEFAULT 0, -- 连续登录失败次数
    locked_until    TIMESTAMPTZ,                    -- 账号锁定截止时间

    -- MFA
    mfa_enabled     BOOLEAN      NOT NULL DEFAULT FALSE,
    mfa_secret_enc  BYTEA,                          -- TOTP 密钥（加密存储）

    -- 公共字段
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by      VARCHAR(64)  NOT NULL DEFAULT 'system',

    -- 约束
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email)
);

COMMENT ON TABLE  auth.users                IS '系统用户表，存储所有可登录用户信息';
COMMENT ON COLUMN auth.users.id             IS '用户唯一标识，UUID v4';
COMMENT ON COLUMN auth.users.username       IS '登录用户名，全局唯一，3~64位字母数字下划线';
COMMENT ON COLUMN auth.users.display_name   IS '显示名称（中文真实姓名）';
COMMENT ON COLUMN auth.users.email          IS '企业邮箱，全局唯一，用于通知推送';
COMMENT ON COLUMN auth.users.phone_enc      IS '手机号码，AES-256-GCM 加密后的字节数据';
COMMENT ON COLUMN auth.users.password_hash  IS 'bcrypt 哈希密码，不存明文';
COMMENT ON COLUMN auth.users.login_fail_cnt IS '连续登录失败次数，超过5次触发账号锁定';
COMMENT ON COLUMN auth.users.locked_until   IS '账号锁定截止时间，NULL表示未锁定';
COMMENT ON COLUMN auth.users.mfa_secret_enc IS 'TOTP 二次认证密钥，加密存储';
COMMENT ON COLUMN auth.users.deleted_at     IS '软删除时间戳，非NULL表示用户已注销';

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- auth.roles — 角色表
-- ============================================================
CREATE TABLE auth.roles (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    role_code   VARCHAR(32)  NOT NULL,               -- 角色编码（系统标识）
    role_name   VARCHAR(64)  NOT NULL,               -- 角色显示名称
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE, -- 系统内置角色不可删除
    sort_order  SMALLINT     NOT NULL DEFAULT 0,

    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    created_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by  VARCHAR(64)  NOT NULL DEFAULT 'system',

    CONSTRAINT uq_roles_code UNIQUE (role_code)
);

COMMENT ON TABLE  auth.roles            IS '角色定义表，对应方案中的6种角色';
COMMENT ON COLUMN auth.roles.role_code  IS '角色编码：SYS_ADMIN/COMP_ADMIN/PROJECT_MGR/BID_STAFF/APPROVER/READER';
COMMENT ON COLUMN auth.roles.is_system  IS '是否为系统内置角色，内置角色不允许删除修改编码';

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON auth.roles
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- 初始化6种角色
INSERT INTO auth.roles (role_code, role_name, description, is_system, sort_order, created_by, updated_by) VALUES
    ('SYS_ADMIN',    '超级管理员', '系统最高权限，管理所有配置和用户', TRUE, 10, 'system', 'system'),
    ('COMP_ADMIN',   '公司管理员', '管理本公司用户和知识库',           TRUE, 20, 'system', 'system'),
    ('PROJECT_MGR',  '项目经理',   '创建和管理投标项目，审批导出',     TRUE, 30, 'system', 'system'),
    ('BID_STAFF',    '投标专员',   '编写标书，使用AI辅助功能',         TRUE, 40, 'system', 'system'),
    ('APPROVER',     '审批人',     '审批标书，查阅审查报告',           TRUE, 50, 'system', 'system'),
    ('READER',       '只读查阅',   '仅查阅报告，无编辑权限',           TRUE, 60, 'system', 'system');

-- ============================================================
-- auth.permissions — 权限点表
-- ============================================================
CREATE TABLE auth.permissions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    perm_code   VARCHAR(64)  NOT NULL,   -- 权限编码，如 bid:export
    perm_name   VARCHAR(128) NOT NULL,   -- 权限显示名称
    resource    VARCHAR(64)  NOT NULL,   -- 资源类型，如 bid / knowledge / user
    action      VARCHAR(32)  NOT NULL,   -- 操作类型，如 create/read/update/delete/export
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT TRUE,

    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by  VARCHAR(64)  NOT NULL DEFAULT 'system',

    CONSTRAINT uq_permissions_code UNIQUE (perm_code)
);

COMMENT ON TABLE  auth.permissions           IS '权限点定义表，对应方案中P1~P8及细粒度权限';
COMMENT ON COLUMN auth.permissions.perm_code IS '权限编码格式: {resource}:{action}，如 bid:export、knowledge:manage';
COMMENT ON COLUMN auth.permissions.resource  IS '被保护的资源名称';
COMMENT ON COLUMN auth.permissions.action    IS '操作动词：create/read/update/delete/export/manage/approve';

-- ============================================================
-- auth.role_permissions — 角色权限关联表
-- ============================================================
CREATE TABLE auth.role_permissions (
    role_id     UUID    NOT NULL REFERENCES auth.roles(id)       ON DELETE CASCADE,
    perm_id     UUID    NOT NULL REFERENCES auth.permissions(id) ON DELETE CASCADE,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by  VARCHAR(64) NOT NULL,

    PRIMARY KEY (role_id, perm_id)
);

COMMENT ON TABLE auth.role_permissions IS '角色-权限关联表，多对多';

-- ============================================================
-- auth.user_roles — 用户角色关联表
-- ============================================================
CREATE TABLE auth.user_roles (
    user_id     UUID    NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_id     UUID    NOT NULL REFERENCES auth.roles(id) ON DELETE RESTRICT,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by  VARCHAR(64) NOT NULL,
    expires_at  TIMESTAMPTZ,   -- 角色有效期，NULL 表示永久

    PRIMARY KEY (user_id, role_id)
);

COMMENT ON TABLE  auth.user_roles          IS '用户-角色关联表，多对多，支持角色有效期';
COMMENT ON COLUMN auth.user_roles.expires_at IS '角色过期时间，NULL表示永久有效，用于临时授权场景';

-- ============================================================
-- auth.refresh_tokens — Refresh Token 表
-- ============================================================
CREATE TABLE auth.refresh_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(256) NOT NULL,        -- SHA-256 哈希，不存原始 token
    device_info VARCHAR(512),                  -- User-Agent 等设备标识
    ip_address  INET,                          -- 登录 IP
    expires_at  TIMESTAMPTZ  NOT NULL,
    revoked_at  TIMESTAMPTZ,                   -- 主动注销时间
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_refresh_tokens_hash UNIQUE (token_hash)
);

COMMENT ON TABLE  auth.refresh_tokens            IS 'JWT Refresh Token 存储表，有效期30天';
COMMENT ON COLUMN auth.refresh_tokens.token_hash IS 'Refresh Token 的 SHA-256 哈希，原始 Token 不落库';
COMMENT ON COLUMN auth.refresh_tokens.revoked_at IS '主动注销时间，非NULL表示该Token已失效';
```

---

## 6. DDL：项目管理域（project）

```sql
-- ============================================================
-- project.bid_projects — 投标项目主表
-- ============================================================
CREATE TABLE project.bid_projects (
    -- 主键
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 项目基本信息
    project_no          VARCHAR(64)     NOT NULL,            -- 项目编号（人工编制）
    project_name        VARCHAR(512)    NOT NULL,            -- 项目名称
    client_name         VARCHAR(256)    NOT NULL,            -- 招标方名称
    client_contact      VARCHAR(128),                        -- 招标方联系人
    industry            VARCHAR(64)     NOT NULL,            -- 行业分类
    region              VARCHAR(64)     NOT NULL,            -- 地区（省/市）
    project_category    VARCHAR(64),                         -- 项目类别：政府采购/工程/商业

    -- 金额信息
    budget_amount       NUMERIC(18, 2),                      -- 预算金额（元）
    bid_amount          NUMERIC(18, 2),                      -- 实际投标报价（元）

    -- 时间节点
    release_date        DATE,                                -- 招标文件发布日期
    tender_date         DATE            NOT NULL,            -- 开标日期
    deadline            TIMESTAMPTZ     NOT NULL,            -- 递交截止时间

    -- 评标信息
    evaluation_method   VARCHAR(32),                         -- 评标方法：综合评分/最低价/技术标
    tech_score_weight   NUMERIC(5, 2),                       -- 技术分权重（%）
    price_score_weight  NUMERIC(5, 2),                       -- 价格分权重（%）
    business_score_weight NUMERIC(5, 2),                     -- 商务分权重（%）

    -- 胜率预测
    win_rate_score      NUMERIC(5, 2),                       -- 胜率评分（0~100）
    win_rate_grade      CHAR(1),                             -- 胜率等级：A/B/C/D
    win_rate_calc_at    TIMESTAMPTZ,                         -- 最后一次计算时间

    -- 状态
    status              public.entity_status NOT NULL DEFAULT 'DRAFT',
    is_participate      BOOLEAN          NOT NULL DEFAULT TRUE,  -- 是否决定参与
    not_participate_reason TEXT,                              -- 不参与原因

    -- 公共字段
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64)      NOT NULL,
    updated_by          VARCHAR(64)      NOT NULL,

    -- 约束
    CONSTRAINT uq_bid_projects_no UNIQUE (project_no),
    CONSTRAINT chk_bid_projects_score_weight CHECK (
        tech_score_weight IS NULL OR
        (tech_score_weight + price_score_weight + business_score_weight = 100)
    ),
    CONSTRAINT chk_bid_projects_win_grade CHECK (
        win_rate_grade IS NULL OR win_rate_grade IN ('A', 'B', 'C', 'D')
    )
);

COMMENT ON TABLE  project.bid_projects                   IS '投标项目主表，每条记录对应一次参与的招标项目';
COMMENT ON COLUMN project.bid_projects.project_no        IS '项目编号，格式建议：BID-YYYY-NNNN，人工录入唯一';
COMMENT ON COLUMN project.bid_projects.industry          IS '行业分类：IT/建筑/医疗/教育/交通/能源等，对应胜率模型特征';
COMMENT ON COLUMN project.bid_projects.evaluation_method IS '评标方法决定标书编写策略，影响章节优先级排序';
COMMENT ON COLUMN project.bid_projects.win_rate_score    IS '0~100分，由胜率预测模型计算，≥80=A，60~79=B，40~59=C，<40=D';
COMMENT ON COLUMN project.bid_projects.tender_date       IS '开标日期，是项目时间轴的核心节点，倒排计划基准';
COMMENT ON COLUMN project.bid_projects.deadline          IS '标书递交截止时间，系统据此自动提醒，带时区';

CREATE TRIGGER trg_bid_projects_updated_at
    BEFORE UPDATE ON project.bid_projects
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- project.project_members — 项目成员表
-- ============================================================
CREATE TABLE project.project_members (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID        NOT NULL REFERENCES project.bid_projects(id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL REFERENCES auth.users(id)           ON DELETE RESTRICT,
    role        VARCHAR(32) NOT NULL,    -- 项目内角色：LEADER/WRITER/REVIEWER/OBSERVER
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at     TIMESTAMPTZ,             -- 退出时间，NULL 表示仍在项目中

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(64) NOT NULL,
    updated_by  VARCHAR(64) NOT NULL,

    CONSTRAINT uq_project_members UNIQUE (project_id, user_id),
    CONSTRAINT chk_project_members_role CHECK (
        role IN ('LEADER', 'WRITER', 'REVIEWER', 'OBSERVER')
    )
);

COMMENT ON TABLE  project.project_members      IS '项目成员表，记录参与每个项目的人员及其角色';
COMMENT ON COLUMN project.project_members.role IS '项目内职责：LEADER-项目负责人，WRITER-编写人员，REVIEWER-审核人员，OBSERVER-只读观察';

CREATE TRIGGER trg_project_members_updated_at
    BEFORE UPDATE ON project.project_members
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- project.bid_records — 投标结果记录表
-- ============================================================
CREATE TABLE project.bid_records (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID            NOT NULL REFERENCES project.bid_projects(id) ON DELETE CASCADE,

    -- 结果信息
    result              public.bid_result NOT NULL DEFAULT 'PENDING',
    final_bid_amount    NUMERIC(18, 2),                  -- 最终递交投标价
    winning_amount      NUMERIC(18, 2),                  -- 中标价（结果公示后录入）
    winning_company     VARCHAR(256),                    -- 中标单位（非本司中标时记录）

    -- 评分结果
    tech_score          NUMERIC(6, 2),                   -- 获得技术分
    business_score      NUMERIC(6, 2),                   -- 获得商务分
    price_score         NUMERIC(6, 2),                   -- 获得价格分
    total_score         NUMERIC(6, 2),                   -- 综合得分
    rank                SMALLINT,                        -- 排名

    -- 废标/未中标分析
    fail_reason         VARCHAR(32),                     -- 失败原因分类
    fail_reason_detail  TEXT,                            -- 失败原因详述（复盘填写）
    is_reviewed         BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否已完成复盘
    review_notes        TEXT,                            -- 复盘笔记
    quality_content_ids UUID[],                          -- 可入知识库的优质内容 ID 列表

    -- 时间
    result_announced_at DATE,                            -- 结果公示日期
    reviewed_at         TIMESTAMPTZ,                     -- 复盘完成时间
    reviewed_by         VARCHAR(64),

    -- 公共字段
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64) NOT NULL,
    updated_by          VARCHAR(64) NOT NULL,

    CONSTRAINT uq_bid_records_project UNIQUE (project_id),
    CONSTRAINT chk_bid_records_fail_reason CHECK (
        fail_reason IS NULL OR fail_reason IN (
            'INVALID_FORMAT',   -- 格式废标
            'MISSING_DOC',      -- 缺少文件
            'LOW_PRICE',        -- 报价过低
            'HIGH_PRICE',       -- 报价过高
            'LOW_SCORE',        -- 综合分不足
            'QUALIFICATION',    -- 资质不满足
            'COMPETITOR',       -- 竞争对手更强
            'RELATIONSHIP',     -- 关系因素
            'OTHER'             -- 其他
        )
    )
);

COMMENT ON TABLE  project.bid_records                    IS '投标结果记录表，每个项目对应唯一一条结果，用于复盘和知识沉淀';
COMMENT ON COLUMN project.bid_records.fail_reason        IS '失败原因标准分类，用于统计分析废标/失标分布，驱动系统改进方向';
COMMENT ON COLUMN project.bid_records.quality_content_ids IS '本次标书中值得入知识库的优质章节/素材 UUID 数组，复盘时人工标注';
COMMENT ON COLUMN project.bid_records.is_reviewed        IS '是否完成复盘，知识库健康度评估依赖此字段统计活跃度';

CREATE TRIGGER trg_bid_records_updated_at
    BEFORE UPDATE ON project.bid_records
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();
```

---

## 7. DDL：知识库域（knowledge）

```sql
-- ============================================================
-- knowledge.kb_documents — 知识库文档主表
-- ============================================================
CREATE TABLE knowledge.kb_documents (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID                    REFERENCES project.bid_projects(id) ON DELETE SET NULL,

    -- 文档属性
    doc_type        public.document_type    NOT NULL,
    title           VARCHAR(512)            NOT NULL,
    file_path       VARCHAR(1024)           NOT NULL,    -- MinIO 对象路径
    file_name       VARCHAR(256)            NOT NULL,    -- 原始文件名
    file_size_bytes BIGINT                  NOT NULL,
    mime_type       VARCHAR(128)            NOT NULL,
    file_hash       VARCHAR(64)             NOT NULL,    -- SHA-256，用于去重

    -- 解析状态
    parse_status    public.task_status      NOT NULL DEFAULT 'PENDING',
    parse_error     TEXT,                               -- 解析失败原因
    parsed_at       TIMESTAMPTZ,

    -- 内容信息
    page_count      INT,                                -- 总页数
    word_count      INT,                                -- 解析后字数
    language        VARCHAR(8)              DEFAULT 'zh-CN',

    -- 分类与标签
    industry        VARCHAR(64),                        -- 所属行业
    region          VARCHAR(64),                        -- 地区
    tags            TEXT[],                             -- 标签数组（快速过滤）
    keywords        TEXT[],                             -- NLP 抽取关键词

    -- 置信度与质量
    confidence      NUMERIC(5, 4)           NOT NULL DEFAULT 0.0,  -- AI 分类置信度
    quality_score   NUMERIC(5, 2),                     -- 人工评定质量分（1~5）
    ingest_mode     VARCHAR(16)             NOT NULL DEFAULT 'AUTO',

    -- 有效期管理（证书类文档）
    effective_date  DATE,                               -- 生效日期
    expire_date     DATE,                               -- 失效日期（证书到期）
    is_expired      BOOLEAN                 GENERATED ALWAYS AS (
                        expire_date IS NOT NULL AND expire_date < CURRENT_DATE
                    ) STORED,                           -- 计算列：是否已过期

    -- ES / Milvus 同步状态
    es_indexed      BOOLEAN                 NOT NULL DEFAULT FALSE,
    es_indexed_at   TIMESTAMPTZ,
    milvus_synced   BOOLEAN                 NOT NULL DEFAULT FALSE,
    milvus_synced_at TIMESTAMPTZ,

    -- 公共字段
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64)             NOT NULL,
    updated_by      VARCHAR(64)             NOT NULL,

    CONSTRAINT uq_kb_documents_hash UNIQUE (file_hash),
    CONSTRAINT chk_kb_documents_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT chk_kb_documents_ingest_mode CHECK (
        ingest_mode IN ('AUTO', 'MANUAL_CONFIRM', 'MANUAL')
    )
);

COMMENT ON TABLE  knowledge.kb_documents                 IS '知识库文档主表，存储所有入库文档的元数据，原始文件存于MinIO';
COMMENT ON COLUMN knowledge.kb_documents.file_hash       IS 'SHA-256文件哈希，用于上传去重，同一文件不重复入库';
COMMENT ON COLUMN knowledge.kb_documents.confidence      IS 'AI自动分类的置信度：≥0.85自动入库，0.60~0.85人工确认，<0.60标注异常';
COMMENT ON COLUMN knowledge.kb_documents.is_expired      IS '计算列，自动判断证书是否过期，驱动知识库健康度评估中的时效性维度';
COMMENT ON COLUMN knowledge.kb_documents.ingest_mode     IS '入库方式：AUTO-自动入库，MANUAL_CONFIRM-人工确认，MANUAL-人工录入';
COMMENT ON COLUMN knowledge.kb_documents.tags            IS 'PostgreSQL数组类型，支持 @> 操作符过滤标签';
COMMENT ON COLUMN knowledge.kb_documents.es_indexed      IS 'Elasticsearch全文索引同步状态，FALSE时由定时任务触发重新索引';

CREATE TRIGGER trg_kb_documents_updated_at
    BEFORE UPDATE ON knowledge.kb_documents
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.kb_chunks — 文档分块表
-- ============================================================
CREATE TABLE knowledge.kb_chunks (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID        NOT NULL REFERENCES knowledge.kb_documents(id) ON DELETE CASCADE,

    -- 分块内容
    content         TEXT        NOT NULL,               -- 分块文本内容
    content_hash    VARCHAR(64) NOT NULL,               -- SHA-256，用于去重
    chunk_index     INT         NOT NULL,               -- 在文档中的序号（从0开始）
    page_no         INT,                                -- 所在页码
    section_title   VARCHAR(256),                       -- 所属章节标题

    -- 分块元数据
    token_count     INT         NOT NULL,               -- Token 数量（≤512）
    char_count      INT         NOT NULL,               -- 字符数
    chunk_type      VARCHAR(16) NOT NULL DEFAULT 'TEXT', -- TEXT / TABLE / IMAGE_CAPTION

    -- Milvus 向量引用
    milvus_id       VARCHAR(128),                       -- Milvus 中对应向量的主键
    embedding_model VARCHAR(64),                        -- 向量化使用的模型版本
    embedded_at     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_kb_chunks_doc_index UNIQUE (doc_id, chunk_index),
    CONSTRAINT chk_kb_chunks_token    CHECK (token_count > 0 AND token_count <= 600),
    CONSTRAINT chk_kb_chunks_type     CHECK (chunk_type IN ('TEXT', 'TABLE', 'IMAGE_CAPTION'))
);

COMMENT ON TABLE  knowledge.kb_chunks               IS '文档分块表，每条记录对应一个语义切块，与Milvus向量一一对应';
COMMENT ON COLUMN knowledge.kb_chunks.chunk_index   IS '文档内分块序号，从0开始，与chunk_doc_id联合唯一';
COMMENT ON COLUMN knowledge.kb_chunks.token_count   IS 'Token数量，正文分块≤512，表格整体保留不切分（可超512但≤600）';
COMMENT ON COLUMN knowledge.kb_chunks.milvus_id     IS 'Milvus Collection中对应向量的Primary Key，用于反向查找原文';
COMMENT ON COLUMN knowledge.kb_chunks.chunk_type    IS 'TEXT-正文段落，TABLE-表格（整体保留），IMAGE_CAPTION-图片说明文字';

CREATE TRIGGER trg_kb_chunks_updated_at
    BEFORE UPDATE ON knowledge.kb_chunks
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.qualifications — 资质证书库
-- ============================================================
CREATE TABLE knowledge.qualifications (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID        REFERENCES knowledge.kb_documents(id) ON DELETE SET NULL,

    -- 证书基本信息
    cert_name       VARCHAR(256) NOT NULL,              -- 证书名称
    cert_no         VARCHAR(128) NOT NULL,              -- 证书编号
    cert_level      VARCHAR(32),                        -- 证书等级（一级/二级/甲级等）
    cert_type       VARCHAR(64)  NOT NULL,              -- 证书类别
    issuer          VARCHAR(256) NOT NULL,              -- 颁发机构
    issued_to       VARCHAR(256) NOT NULL,              -- 持证主体（公司/个人）

    -- 有效期
    issue_date      DATE         NOT NULL,              -- 颁证日期
    expire_date     DATE,                               -- 到期日期（NULL表示长期有效）
    is_expired      BOOLEAN      GENERATED ALWAYS AS (
                        expire_date IS NOT NULL AND expire_date < CURRENT_DATE
                    ) STORED,

    -- 文件存储
    cert_file_path  VARCHAR(1024),                      -- 证书扫描件 MinIO 路径
    cert_file_hash  VARCHAR(64),                        -- 扫描件文件哈希

    -- 元数据
    scope           TEXT,                               -- 许可范围/业务范围描述
    notes           TEXT,                               -- 备注（续期提醒等）
    alert_days      SMALLINT NOT NULL DEFAULT 90,       -- 到期前多少天发送提醒

    -- 公共字段
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64) NOT NULL,
    updated_by      VARCHAR(64) NOT NULL,

    CONSTRAINT uq_qualifications_cert_no UNIQUE (cert_no)
);

COMMENT ON TABLE  knowledge.qualifications            IS '企业资质证书库，存储所有有效资质及扫描件引用';
COMMENT ON COLUMN knowledge.qualifications.cert_no   IS '证书编号，全局唯一，是证书核验的关键字段';
COMMENT ON COLUMN knowledge.qualifications.is_expired IS '计算列，自动标记过期。胜率预测资质匹配时过滤过期证书';
COMMENT ON COLUMN knowledge.qualifications.alert_days IS '提前预警天数，默认90天，可按证书类型单独配置';

CREATE TRIGGER trg_qualifications_updated_at
    BEFORE UPDATE ON knowledge.qualifications
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.performances — 项目业绩库
-- ============================================================
CREATE TABLE knowledge.performances (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    ref_project_id      UUID            REFERENCES project.bid_projects(id) ON DELETE SET NULL,

    -- 业绩基本信息
    perf_name           VARCHAR(512)    NOT NULL,       -- 业绩项目名称
    client_name         VARCHAR(256)    NOT NULL,       -- 业主名称
    contract_no         VARCHAR(128),                   -- 合同编号
    contract_amount     NUMERIC(18, 2)  NOT NULL,       -- 合同金额（元）

    -- 分类标签
    industry            VARCHAR(64)     NOT NULL,       -- 所属行业
    region              VARCHAR(64)     NOT NULL,       -- 项目地区
    project_scale       VARCHAR(16)     NOT NULL,       -- 项目规模：SMALL/MEDIUM/LARGE/MEGA
    tech_stack          TEXT[],                         -- 技术栈标签数组

    -- 时间
    start_date          DATE            NOT NULL,       -- 项目开始日期
    end_date            DATE,                           -- 项目完成日期
    completion_year     SMALLINT        GENERATED ALWAYS AS (EXTRACT(YEAR FROM end_date)::SMALLINT) STORED,

    -- 内容描述（用于语义检索）
    project_summary     TEXT            NOT NULL,       -- 项目概述（500字以内）
    key_achievements    TEXT,                           -- 核心成果亮点
    tech_highlights     TEXT,                           -- 技术亮点描述
    client_feedback     TEXT,                           -- 客户评价/验收意见

    -- 证明材料
    contract_file_path  VARCHAR(1024),                  -- 合同首尾页 MinIO 路径
    acceptance_file_path VARCHAR(1024),                 -- 验收报告 MinIO 路径
    award_file_path     VARCHAR(1024),                  -- 获奖证书 MinIO 路径（如有）

    -- 向量检索
    embedding_doc_id    UUID            REFERENCES knowledge.kb_documents(id),

    -- 公共字段
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64)     NOT NULL,
    updated_by          VARCHAR(64)     NOT NULL,

    CONSTRAINT chk_performances_scale CHECK (
        project_scale IN ('SMALL', 'MEDIUM', 'LARGE', 'MEGA')
    )
);

COMMENT ON TABLE  knowledge.performances                    IS '项目业绩库，是胜率预测"业绩相似度"维度和RAG检索的核心数据源';
COMMENT ON COLUMN knowledge.performances.project_scale      IS '项目规模分级：SMALL<100万，MEDIUM 100~500万，LARGE 500~5000万，MEGA>5000万';
COMMENT ON COLUMN knowledge.performances.tech_stack         IS '技术栈数组，用于技术契合度语义匹配，如{Java,K8s,PostgreSQL}';
COMMENT ON COLUMN knowledge.performances.completion_year    IS '完成年份计算列，用于时效性过滤（近5年业绩权重更高）';
COMMENT ON COLUMN knowledge.performances.project_summary    IS '核心内容字段，500字以内的结构化项目概述，由此生成知识库向量';

CREATE TRIGGER trg_performances_updated_at
    BEFORE UPDATE ON knowledge.performances
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.personnel — 人员库
-- ============================================================
CREATE TABLE knowledge.personnel (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        REFERENCES auth.users(id) ON DELETE SET NULL,  -- 若为内部员工则关联

    -- 基本信息（敏感字段加密）
    real_name           VARCHAR(64)  NOT NULL,
    id_number_enc       BYTEA,                          -- 身份证号（AES-256 加密）
    gender              CHAR(1),                        -- M/F
    birth_year          SMALLINT,                       -- 出生年份（不存具体生日）
    phone_enc           BYTEA,                          -- 手机号（AES-256 加密）

    -- 职业信息
    department          VARCHAR(128),
    job_title           VARCHAR(128)  NOT NULL,         -- 职务/岗位
    professional_title  VARCHAR(64),                    -- 职称（高工/工程师/助工等）
    title_cert_no       VARCHAR(128),                   -- 职称证书编号
    education           VARCHAR(32),                    -- 学历：BACHELOR/MASTER/DOCTOR/COLLEGE
    major               VARCHAR(128),                   -- 专业

    -- 项目经验
    work_years          SMALLINT,                       -- 工作年限
    bid_experience_years SMALLINT,                      -- 参与投标年限
    specialties         TEXT[],                         -- 专业领域标签

    -- 简历文件
    resume_file_path    VARCHAR(1024),                  -- 简历 MinIO 路径
    photo_file_path     VARCHAR(1024),                  -- 照片 MinIO 路径（标书用）

    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,   -- 是否在职

    -- 公共字段
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64) NOT NULL,
    updated_by          VARCHAR(64) NOT NULL,

    CONSTRAINT chk_personnel_gender    CHECK (gender IS NULL OR gender IN ('M', 'F')),
    CONSTRAINT chk_personnel_education CHECK (education IS NULL OR education IN (
        'COLLEGE', 'BACHELOR', 'MASTER', 'DOCTOR', 'OTHER'
    ))
);

COMMENT ON TABLE  knowledge.personnel                   IS '人员库，涵盖参与投标的内部员工和外部人员（挂靠等）';
COMMENT ON COLUMN knowledge.personnel.id_number_enc     IS '身份证号AES-256-GCM加密存储，密钥由KMS管理，禁止明文落库';
COMMENT ON COLUMN knowledge.personnel.phone_enc         IS '手机号AES-256-GCM加密存储';
COMMENT ON COLUMN knowledge.personnel.birth_year        IS '只存出生年份，避免存储完整生日泄露过多个人信息';
COMMENT ON COLUMN knowledge.personnel.specialties       IS '专业领域标签数组，用于人员配置度匹配，如{网络安全,系统集成,项目管理}';

CREATE TRIGGER trg_personnel_updated_at
    BEFORE UPDATE ON knowledge.personnel
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.personnel_certs — 人员证书表（1对多）
-- ============================================================
CREATE TABLE knowledge.personnel_certs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id       UUID        NOT NULL REFERENCES knowledge.personnel(id) ON DELETE CASCADE,

    cert_name       VARCHAR(256) NOT NULL,              -- 证书名称
    cert_no         VARCHAR(128) NOT NULL,              -- 证书编号
    cert_type       VARCHAR(64)  NOT NULL,              -- 证书类别
    issuer          VARCHAR(256) NOT NULL,              -- 颁发机构
    issue_date      DATE         NOT NULL,              -- 颁证日期
    expire_date     DATE,                               -- 到期日期
    is_expired      BOOLEAN      GENERATED ALWAYS AS (
                        expire_date IS NOT NULL AND expire_date < CURRENT_DATE
                    ) STORED,
    cert_file_path  VARCHAR(1024),                      -- 证书扫描件 MinIO 路径
    alert_days      SMALLINT NOT NULL DEFAULT 60,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64) NOT NULL,
    updated_by      VARCHAR(64) NOT NULL
);

COMMENT ON TABLE  knowledge.personnel_certs          IS '人员个人证书表，一个人可持有多项证书（职称证、注册证、技能证等）';
COMMENT ON COLUMN knowledge.personnel_certs.is_expired IS '计算列，自动判断证书是否过期，人员配置度评分时过滤过期证书';

CREATE TRIGGER trg_personnel_certs_updated_at
    BEFORE UPDATE ON knowledge.personnel_certs
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- knowledge.kb_tags — 知识库标签字典
-- ============================================================
CREATE TABLE knowledge.kb_tags (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_name    VARCHAR(64)  NOT NULL,
    tag_group   VARCHAR(32)  NOT NULL,   -- 标签分组：industry/region/tech/doc_type
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    use_count   INT          NOT NULL DEFAULT 0, -- 使用次数（冗余统计）

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(64) NOT NULL DEFAULT 'system',
    updated_by  VARCHAR(64) NOT NULL DEFAULT 'system',

    CONSTRAINT uq_kb_tags UNIQUE (tag_name, tag_group)
);

COMMENT ON TABLE  knowledge.kb_tags         IS '知识库标签字典，统一管理行业/地区/技术等标签，避免自由输入导致标签混乱';
COMMENT ON COLUMN knowledge.kb_tags.tag_group IS '标签分组：industry-行业，region-地区，tech-技术栈，doc_type-文档类型';
```

---

## 8. DDL：标书编写域（bid）

```sql
-- ============================================================
-- bid.bids — 标书主表
-- ============================================================
CREATE TABLE bid.bids (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID                    NOT NULL REFERENCES project.bid_projects(id) ON DELETE RESTRICT,

    -- 标书基本信息
    bid_title       VARCHAR(512)            NOT NULL,   -- 标书名称
    bid_version     VARCHAR(16)             NOT NULL DEFAULT 'v0.1',  -- 当前版本号
    status          public.entity_status    NOT NULL DEFAULT 'DRAFT',

    -- 标书配置（JSON 存储灵活结构）
    config          JSONB                   NOT NULL DEFAULT '{}',
    -- config 结构示例：
    -- {
    --   "page_size": "A4",
    --   "font_family": "宋体",
    --   "cover_template": "standard",
    --   "chapter_numbering": "numeric"
    -- }

    -- 进度统计（冗余，由触发器维护）
    total_sections  SMALLINT                NOT NULL DEFAULT 0,   -- 总章节数
    done_sections   SMALLINT                NOT NULL DEFAULT 0,   -- 已完成章节数
    progress_pct    NUMERIC(5, 2)           NOT NULL DEFAULT 0,   -- 完成百分比

    -- 最终导出
    export_file_path VARCHAR(1024),                               -- 最终导出文件路径
    export_version  VARCHAR(16),                                  -- 导出时的版本号
    exported_at     TIMESTAMPTZ,
    exported_by     VARCHAR(64),

    -- 审批
    submitted_at    TIMESTAMPTZ,                                  -- 提交审批时间
    approved_at     TIMESTAMPTZ,
    approved_by     VARCHAR(64),
    reject_reason   TEXT,

    -- 公共字段
    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64)             NOT NULL,
    updated_by      VARCHAR(64)             NOT NULL,

    CONSTRAINT uq_bids_project UNIQUE (project_id)  -- 一个项目只有一份标书（主版本）
);

COMMENT ON TABLE  bid.bids                  IS '标书主表，每个投标项目对应一份标书，内部通过章节版本管理内容迭代';
COMMENT ON COLUMN bid.bids.config           IS 'JSONB存储标书格式配置（页面大小、字体、封面模板等），便于扩展';
COMMENT ON COLUMN bid.bids.progress_pct     IS '完成百分比，由触发器在bid_sections更新时自动重算，供前端进度条展示';
COMMENT ON COLUMN bid.bids.bid_version      IS '语义化版本号，格式vX.Y，X=主版本（审批后递增），Y=草稿版本';

CREATE TRIGGER trg_bids_updated_at
    BEFORE UPDATE ON bid.bids
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- bid.bid_sections — 标书章节表
-- ============================================================
CREATE TABLE bid.bid_sections (
    id              UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id          UUID                NOT NULL REFERENCES bid.bids(id) ON DELETE CASCADE,
    parent_id       UUID                REFERENCES bid.bid_sections(id) ON DELETE CASCADE,  -- 支持多级目录

    -- 章节结构
    section_no      VARCHAR(32)         NOT NULL,   -- 章节编号，如 "3.2.1"
    title           VARCHAR(256)        NOT NULL,   -- 章节标题
    sort_order      INT                 NOT NULL DEFAULT 0,
    depth           SMALLINT            NOT NULL DEFAULT 1,   -- 嵌套层级（1=顶级）

    -- 章节类型（三分法路由）
    section_type    public.section_type NOT NULL DEFAULT 'FREE_NARRATIVE',

    -- 内容
    content         TEXT,                           -- 当前版本内容（最新）
    word_count      INT                 NOT NULL DEFAULT 0,
    is_done         BOOLEAN             NOT NULL DEFAULT FALSE,   -- 是否标记为完成

    -- AI 生成元数据
    last_generated_at   TIMESTAMPTZ,
    last_generated_by   VARCHAR(16),    -- 生成方式：USER/AI/TEMPLATE
    generation_task_id  UUID,           -- 关联 ai_task.ai_tasks.id
    ai_confidence       NUMERIC(5, 4),  -- 最近一次AI生成的置信度
    constraint_coverage NUMERIC(5, 4),  -- 约束覆盖率

    -- 编辑锁（协同编辑）
    locked_by       VARCHAR(64),        -- 当前锁定用户 user_id
    locked_at       TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,        -- 锁超时时间（默认30分钟）

    -- 审核
    review_status   VARCHAR(16)         NOT NULL DEFAULT 'PENDING',
    reviewer_id     VARCHAR(64),
    review_comment  TEXT,
    reviewed_at     TIMESTAMPTZ,

    -- 公共字段
    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64)         NOT NULL,
    updated_by      VARCHAR(64)         NOT NULL,

    CONSTRAINT uq_bid_sections_no UNIQUE (bid_id, section_no),
    CONSTRAINT chk_bid_sections_review_status CHECK (
        review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'SKIPPED')
    ),
    CONSTRAINT chk_bid_sections_depth CHECK (depth BETWEEN 1 AND 5)
);

COMMENT ON TABLE  bid.bid_sections                      IS '标书章节表，支持多级目录（最多5级），对应三分法路由';
COMMENT ON COLUMN bid.bid_sections.parent_id            IS '父章节ID，NULL表示顶级章节，用于构建树形目录结构';
COMMENT ON COLUMN bid.bid_sections.section_type         IS '三分法路由类型：TEMPLATE-模板填充，DATA_FILL-结构化数据，FREE_NARRATIVE-LLM生成';
COMMENT ON COLUMN bid.bid_sections.locked_by            IS '协同编辑排他锁，非NULL时其他用户只读，锁超时自动释放';
COMMENT ON COLUMN bid.bid_sections.constraint_coverage  IS 'AI生成时对招标约束的覆盖率，<0.7时前端警告提示';

CREATE TRIGGER trg_bid_sections_updated_at
    BEFORE UPDATE ON bid.bid_sections
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- bid.section_versions — 章节版本历史表（写时复制）
-- ============================================================
CREATE TABLE bid.section_versions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id      UUID        NOT NULL REFERENCES bid.bid_sections(id) ON DELETE CASCADE,

    version_no      INT         NOT NULL,           -- 版本序号（从1开始，单调递增）
    content         TEXT        NOT NULL,           -- 该版本内容快照
    word_count      INT         NOT NULL DEFAULT 0,
    change_summary  VARCHAR(512),                   -- 本次修改摘要
    change_type     VARCHAR(16) NOT NULL,           -- MANUAL/AI_GEN/REVERT
    source_version  INT,                            -- 若为回滚，记录回滚自哪个版本

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64) NOT NULL,

    CONSTRAINT uq_section_versions UNIQUE (section_id, version_no),
    CONSTRAINT chk_section_versions_change_type CHECK (
        change_type IN ('MANUAL', 'AI_GEN', 'REVERT', 'IMPORT')
    )
) PARTITION BY RANGE (created_at);  -- 按时间分区，详见第12章

COMMENT ON TABLE  bid.section_versions                IS '章节版本历史表，写时复制，支持任意版本回滚和diff对比';
COMMENT ON COLUMN bid.section_versions.version_no     IS '单调递增版本序号，同一章节内唯一，供前端时间轴展示';
COMMENT ON COLUMN bid.section_versions.change_type    IS 'MANUAL-人工编辑，AI_GEN-AI生成，REVERT-版本回滚，IMPORT-导入';

-- ============================================================
-- bid.bid_variables — 标书全局变量表
-- ============================================================
CREATE TABLE bid.bid_variables (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id          UUID        NOT NULL REFERENCES bid.bids(id) ON DELETE CASCADE,

    -- 变量定义
    var_key         VARCHAR(64)  NOT NULL,           -- 变量键名，如 CLIENT、PROJECT_NAME
    var_value       TEXT,                            -- 变量值
    display_name    VARCHAR(128) NOT NULL,           -- 界面显示名称
    var_type        VARCHAR(16)  NOT NULL DEFAULT 'TEXT',  -- TEXT/NUMBER/DATE/MONEY
    is_required     BOOLEAN      NOT NULL DEFAULT TRUE,
    is_system       BOOLEAN      NOT NULL DEFAULT FALSE,   -- 系统预置变量
    validation_rule VARCHAR(256),                   -- 正则校验规则
    placeholder     VARCHAR(256),                   -- 输入提示

    -- 公共字段
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64) NOT NULL,
    updated_by      VARCHAR(64) NOT NULL,

    CONSTRAINT uq_bid_variables UNIQUE (bid_id, var_key),
    CONSTRAINT chk_bid_variables_type CHECK (
        var_type IN ('TEXT', 'NUMBER', 'DATE', 'MONEY', 'ENUM')
    )
);

COMMENT ON TABLE  bid.bid_variables               IS '标书全局变量表，存储{{CLIENT}}等占位符的实际值，变更时级联更新所有引用位置';
COMMENT ON COLUMN bid.bid_variables.var_key       IS '变量键名，对应模板中的{{KEY}}占位符，如CLIENT/PROJECT_NAME/AMOUNT等';
COMMENT ON COLUMN bid.bid_variables.is_system     IS '系统预置变量（如CLIENT/BIDDER）不可删除，只可修改值';

CREATE TRIGGER trg_bid_variables_updated_at
    BEFORE UPDATE ON bid.bid_variables
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- bid.bid_variable_refs — 变量引用位置表
-- ============================================================
CREATE TABLE bid.bid_variable_refs (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    var_id          UUID    NOT NULL REFERENCES bid.bid_variables(id)  ON DELETE CASCADE,
    section_id      UUID    NOT NULL REFERENCES bid.bid_sections(id)   ON DELETE CASCADE,
    position        INT     NOT NULL,           -- 在 section.content 中的字符偏移量
    context_snippet VARCHAR(256)                -- 变量前后文摘要（用于定位展示）
);

COMMENT ON TABLE  bid.bid_variable_refs               IS '变量引用位置表，记录每个变量在哪些章节的哪个位置被使用，支持精确替换';
COMMENT ON COLUMN bid.bid_variable_refs.position      IS '字符位置偏移量，变量值修改时据此精确替换，避免全文正则替换的误命中';

-- ============================================================
-- bid.bid_check_reports — 一致性检查报告表
-- ============================================================
CREATE TABLE bid.bid_check_reports (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    bid_id          UUID        NOT NULL REFERENCES bid.bids(id) ON DELETE CASCADE,

    -- 报告元数据
    check_version   VARCHAR(16) NOT NULL,           -- 执行检查时标书版本号
    triggered_by    VARCHAR(16) NOT NULL DEFAULT 'MANUAL',  -- MANUAL/AUTO/PRE_EXPORT
    checked_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 汇总统计
    total_items     INT         NOT NULL DEFAULT 0,
    pass_count      INT         NOT NULL DEFAULT 0,
    warn_count      INT         NOT NULL DEFAULT 0,
    fail_count      INT         NOT NULL DEFAULT 0,
    overall_result  public.check_result NOT NULL DEFAULT 'PASS',

    -- 详细结果（JSONB 存储结构化检查项）
    check_detail    JSONB       NOT NULL DEFAULT '[]',
    -- 结构示例：
    -- [{
    --   "check_type": "AMOUNT_CONSISTENCY",
    --   "result": "FAIL",
    --   "message": "投标函金额与报价表不一致",
    --   "locations": [{"section_id": "...", "page": 12}],
    --   "suggestion": "请统一将金额修改为500万元整"
    -- }]

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64) NOT NULL
);

COMMENT ON TABLE  bid.bid_check_reports                  IS '标书一致性检查报告表，记录每次执行6类检查的结果，支持历史对比';
COMMENT ON COLUMN bid.bid_check_reports.triggered_by     IS '触发方式：MANUAL-手动触发，AUTO-定时自动，PRE_EXPORT-导出前强制触发';
COMMENT ON COLUMN bid.bid_check_reports.overall_result   IS '整体结论：PASS可导出，WARN警告可导出，FAIL存在否决项禁止导出';
COMMENT ON COLUMN bid.bid_check_reports.check_detail     IS 'JSONB数组，存储6类检查的详细结果：金额/人员/时间/响应完整性/格式/负面清单';
```

---

## 9. DDL：AI 任务与审查域（ai_task）

```sql
-- ============================================================
-- ai_task.ai_tasks — AI 异步任务总表
-- ============================================================
CREATE TABLE ai_task.ai_tasks (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 任务标识
    task_type       VARCHAR(32)     NOT NULL,       -- 任务类型
    task_status     public.task_status NOT NULL DEFAULT 'PENDING',
    priority        SMALLINT        NOT NULL DEFAULT 5,   -- 1-10，越小优先级越高

    -- 关联实体（多态外键）
    ref_type        VARCHAR(32),                   -- 关联实体类型：BID/SECTION/REVIEW/COLLUSION
    ref_id          UUID,                          -- 关联实体 ID

    -- Celery 任务信息
    celery_task_id  VARCHAR(128),                  -- Celery task_id
    worker_name     VARCHAR(128),                  -- 执行 Worker 标识
    queue_name      VARCHAR(64)     NOT NULL DEFAULT 'default',

    -- 执行信息
    input_payload   JSONB           NOT NULL DEFAULT '{}',  -- 任务输入参数
    result_payload  JSONB,                         -- 任务输出结果
    error_message   TEXT,                          -- 失败原因
    retry_count     SMALLINT        NOT NULL DEFAULT 0,
    max_retries     SMALLINT        NOT NULL DEFAULT 3,

    -- 时间追踪
    queued_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INT,                           -- 执行耗时（毫秒）

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64)     NOT NULL,

    CONSTRAINT chk_ai_tasks_type CHECK (
        task_type IN (
            'DOC_PARSE',            -- 文档解析
            'DOC_EMBED',            -- 向量化
            'SECTION_GENERATE',     -- 章节生成
            'CONSTRAINT_EXTRACT',   -- 约束提取
            'WIN_RATE_CALC',        -- 胜率计算
            'REVIEW_CHECK',         -- 审查任务
            'COLLUSION_ANALYZE',    -- 串标分析
            'CHECK_CONSISTENCY'     -- 一致性检查
        )
    )
);

COMMENT ON TABLE  ai_task.ai_tasks                  IS 'AI异步任务总表，所有耗时AI操作均通过此表追踪状态';
COMMENT ON COLUMN ai_task.ai_tasks.task_type        IS '任务类型枚举，对应各AI能力子服务';
COMMENT ON COLUMN ai_task.ai_tasks.ref_id           IS '多态关联ID，配合ref_type定位具体业务实体，不设硬外键';
COMMENT ON COLUMN ai_task.ai_tasks.duration_ms      IS '任务执行耗时毫秒，用于性能监控和LLM质量看板统计';

-- ============================================================
-- ai_task.doc_constraints — 文档约束提取结果表
-- ============================================================
CREATE TABLE ai_task.doc_constraints (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID                    NOT NULL REFERENCES project.bid_projects(id) ON DELETE CASCADE,
    doc_id          UUID                    NOT NULL REFERENCES knowledge.kb_documents(id) ON DELETE CASCADE,
    task_id         UUID                    REFERENCES ai_task.ai_tasks(id),

    -- 约束内容
    constraint_no   VARCHAR(16)             NOT NULL,   -- 编号，如 C001
    constraint_type public.constraint_type  NOT NULL,
    content         TEXT                    NOT NULL,   -- 约束条款原文
    interpretation  TEXT,                              -- AI 解读/简洁说明

    -- 定位信息
    source_page     INT,                               -- 原文所在页码
    source_section  VARCHAR(256),                      -- 原文所在章节
    source_snippet  TEXT,                              -- 原文片段（用于前端定位跳转）

    -- 评分信息（GUIDE 类型）
    score_max       NUMERIC(6, 2),                     -- 该项满分
    score_dimension VARCHAR(64),                       -- 评分维度（技术分/商务分/价格分）

    -- 否决项标识
    is_veto         BOOLEAN                 NOT NULL DEFAULT FALSE,
    veto_condition  TEXT,                              -- 废标触发条件描述

    -- 确认状态
    confidence      NUMERIC(5, 4)           NOT NULL,
    is_confirmed    BOOLEAN                 NOT NULL DEFAULT FALSE, -- 人工确认
    confirmed_by    VARCHAR(64),
    confirmed_at    TIMESTAMPTZ,
    user_note       TEXT,                              -- 人工补注说明

    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64)             NOT NULL,
    updated_by      VARCHAR(64)             NOT NULL
);

COMMENT ON TABLE  ai_task.doc_constraints              IS '招标文件约束提取结果表，存储三类约束（合规/内容/写作引导）';
COMMENT ON COLUMN ai_task.doc_constraints.constraint_no IS '约束编号，同一文档内唯一，格式Cxxx，用于章节生成时注入约束上下文';
COMMENT ON COLUMN ai_task.doc_constraints.is_veto      IS '废标条款标识，对应方案中"合规要求"的否决标识，前端显示红色警告';
COMMENT ON COLUMN ai_task.doc_constraints.source_page  IS '约束所在原文页码，前端点击可跳转PDF对应页';

CREATE TRIGGER trg_doc_constraints_updated_at
    BEFORE UPDATE ON ai_task.doc_constraints
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- ai_task.review_tasks — 投标审查任务表
-- ============================================================
CREATE TABLE ai_task.review_tasks (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID            NOT NULL REFERENCES project.bid_projects(id),
    tender_doc_id       UUID            NOT NULL REFERENCES knowledge.kb_documents(id),
    bid_doc_id          UUID            NOT NULL REFERENCES knowledge.kb_documents(id),
    ai_task_id          UUID            REFERENCES ai_task.ai_tasks(id),

    -- 状态
    status              public.task_status NOT NULL DEFAULT 'PENDING',

    -- 汇总结果
    total_requirements  INT             NOT NULL DEFAULT 0,
    compliant_count     INT             NOT NULL DEFAULT 0,
    deviated_count      INT             NOT NULL DEFAULT 0,
    missing_count       INT             NOT NULL DEFAULT 0,
    compliance_rate     NUMERIC(5, 4),  -- 整体响应率

    -- 报告
    report_file_path    VARCHAR(1024),  -- 导出报告 MinIO 路径
    report_generated_at TIMESTAMPTZ,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64)     NOT NULL,
    updated_by          VARCHAR(64)     NOT NULL
);

COMMENT ON TABLE  ai_task.review_tasks IS '投标审查任务表，每次审查为独立任务，支持对同一标书反复审查';

CREATE TRIGGER trg_review_tasks_updated_at
    BEFORE UPDATE ON ai_task.review_tasks
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- ai_task.review_items — 审查逐项结果表
-- ============================================================
CREATE TABLE ai_task.review_items (
    id              UUID                    PRIMARY KEY DEFAULT gen_random_uuid(),
    review_task_id  UUID                    NOT NULL REFERENCES ai_task.review_tasks(id) ON DELETE CASCADE,

    -- 审查项
    item_no         VARCHAR(16)             NOT NULL,   -- 编号 R001
    requirement     TEXT                    NOT NULL,   -- 招标要求原文
    req_type        public.constraint_type  NOT NULL,
    is_veto         BOOLEAN                 NOT NULL DEFAULT FALSE,

    -- 审查结论
    verdict         public.review_verdict   NOT NULL DEFAULT 'PENDING',
    evidence        TEXT,                               -- 投标文件中的响应原文
    evidence_page   INT,                               -- 响应内容所在页码
    ai_analysis     TEXT,                              -- AI 审查分析说明
    ai_confidence   NUMERIC(5, 4),

    -- 人工确认
    is_confirmed    BOOLEAN                 NOT NULL DEFAULT FALSE,
    human_verdict   public.review_verdict,              -- 人工修正的结论
    human_note      TEXT,
    confirmed_by    VARCHAR(64),
    confirmed_at    TIMESTAMPTZ,

    created_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    created_by      VARCHAR(64)             NOT NULL,
    updated_by      VARCHAR(64)             NOT NULL,

    CONSTRAINT uq_review_items UNIQUE (review_task_id, item_no)
);

COMMENT ON TABLE  ai_task.review_items               IS '审查逐项结果表，每条对应一个招标要求的审查结论';
COMMENT ON COLUMN ai_task.review_items.evidence_page IS '响应内容页码，前端点击跳转到投标文件对应PDF页，实现证据溯源';
COMMENT ON COLUMN ai_task.review_items.human_verdict IS '人工修正结论，覆盖AI判断，最终报告以人工结论为准';

CREATE TRIGGER trg_review_items_updated_at
    BEFORE UPDATE ON ai_task.review_items
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- ai_task.collusion_analysis_tasks — 串标分析任务表
-- ============================================================
CREATE TABLE ai_task.collusion_analysis_tasks (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID            REFERENCES project.bid_projects(id) ON DELETE SET NULL,
    ai_task_id          UUID            REFERENCES ai_task.ai_tasks(id),

    -- 分析文件列表（JSON 存储多个文件引用）
    input_doc_ids       UUID[]          NOT NULL,       -- 参与对比的投标文件 doc_id 数组
    bidder_names        TEXT[],                         -- 对应投标单位名称

    -- 状态
    status              public.task_status NOT NULL DEFAULT 'PENDING',

    -- 分析结果摘要
    overall_risk        public.risk_level,
    risk_score          NUMERIC(5, 2),                  -- 综合风险评分 0~100

    -- 相似度矩阵（JSONB 存储 N×N 矩阵）
    similarity_matrix   JSONB,
    -- 结构：[{"bidder_a":"A公司","bidder_b":"B公司","text_sim":0.89,"format_sim":0.92,"price_sim":0.65,"overall":0.82}]

    -- 特征分析（JSONB 详细分项）
    feature_analysis    JSONB,
    -- 各维度分析：文本/格式/元数据/报价规律

    -- 报告
    report_file_path    VARCHAR(1024),
    report_generated_at TIMESTAMPTZ,

    -- 法务确认（串标报告需免责声明）
    is_legal_reviewed   BOOLEAN         NOT NULL DEFAULT FALSE,
    legal_note          TEXT,

    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64)     NOT NULL,
    updated_by          VARCHAR(64)     NOT NULL
);

COMMENT ON TABLE  ai_task.collusion_analysis_tasks              IS '串标分析任务表，对多份投标文件进行多维度相似度分析';
COMMENT ON COLUMN ai_task.collusion_analysis_tasks.input_doc_ids IS '参与分析的投标文件ID数组，对应方案中多维度串标分析的输入';
COMMENT ON COLUMN ai_task.collusion_analysis_tasks.similarity_matrix IS 'N×N相似度矩阵JSONB，包含5个维度（文本/格式/元数据/报价/图像）的相似度分';
COMMENT ON COLUMN ai_task.collusion_analysis_tasks.is_legal_reviewed IS '串标报告定位为辅助参考，发布前须法务审阅加免责声明，此字段控制报告可见性';

CREATE TRIGGER trg_collusion_tasks_updated_at
    BEFORE UPDATE ON ai_task.collusion_analysis_tasks
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();
```

---

## 10. DDL：审计日志域（audit）

```sql
-- ============================================================
-- audit.audit_logs — 操作审计日志表（分区主表）
-- 注意：此表不设 deleted_at，所有记录永久保留（合规要求3年）
-- ============================================================
CREATE TABLE audit.audit_logs (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),

    -- 操作主体
    user_id         VARCHAR(64) NOT NULL,   -- 操作人 user_id
    user_name       VARCHAR(128),           -- 冗余存储操作人姓名（防用户删除后查询困难）
    ip_address      INET,
    user_agent      VARCHAR(512),

    -- 操作信息
    action          VARCHAR(64)  NOT NULL,  -- 操作编码，如 bid.export / user.login
    resource_type   VARCHAR(32)  NOT NULL,  -- 资源类型
    resource_id     VARCHAR(128),           -- 资源 ID
    resource_name   VARCHAR(256),           -- 冗余资源名称

    -- 请求/结果
    request_id      VARCHAR(64),            -- 全链路追踪 ID
    http_method     VARCHAR(8),
    api_path        VARCHAR(256),
    request_body    JSONB,                  -- 脱敏后的请求体
    result          VARCHAR(16)  NOT NULL,  -- SUCCESS / FAILURE / FORBIDDEN
    error_code      VARCHAR(16),
    error_message   TEXT,

    -- 时间
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 分区主键
    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

COMMENT ON TABLE  audit.audit_logs             IS '操作审计日志，按季度分区，保留周期3年，禁止任何删除操作';
COMMENT ON COLUMN audit.audit_logs.action      IS '操作编码，对应CLAUDE.md中定义的AUDIT_REQUIRED_ACTIONS列表';
COMMENT ON COLUMN audit.audit_logs.request_body IS '请求体JSON，需在记录前脱敏处理（去除密码/Token等敏感字段）';
COMMENT ON COLUMN audit.audit_logs.occurred_at IS '分区键，按此字段切分季度分区，不使用created_at避免时间漂移';

-- ============================================================
-- audit.export_logs — 文件导出记录表
-- ============================================================
CREATE TABLE audit.export_logs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(64) NOT NULL,
    user_name       VARCHAR(128),

    -- 导出信息
    export_type     VARCHAR(32) NOT NULL,   -- BID_DOC/REVIEW_REPORT/COLLUSION_REPORT
    ref_id          UUID        NOT NULL,   -- 导出的业务实体 ID
    ref_name        VARCHAR(512),           -- 业务实体名称（冗余）
    file_path       VARCHAR(1024) NOT NULL, -- MinIO 导出文件路径
    file_name       VARCHAR(256) NOT NULL,  -- 下载文件名
    file_size_bytes BIGINT,

    -- 水印信息
    watermark_text  VARCHAR(256),           -- 嵌入的水印内容
    watermark_at    TIMESTAMPTZ,

    -- 访问控制
    is_approved     BOOLEAN      NOT NULL DEFAULT FALSE,  -- 是否经过审批
    approved_by     VARCHAR(64),
    approved_at     TIMESTAMPTZ,
    download_count  INT          NOT NULL DEFAULT 0,  -- 下载次数
    last_download_at TIMESTAMPTZ,

    -- 过期
    expires_at      TIMESTAMPTZ,            -- 链接有效期（Pre-signed URL 到期时间参考）
    is_revoked      BOOLEAN      NOT NULL DEFAULT FALSE,  -- 是否撤销

    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  audit.export_logs              IS '文件导出记录表，追踪所有导出行为，支持事后追溯，水印关联';
COMMENT ON COLUMN audit.export_logs.watermark_text IS '动态水印内容格式：{用户ID}|{导出时间}|{项目编号}，嵌入PDF/Word';
COMMENT ON COLUMN audit.export_logs.is_revoked   IS '是否撤销导出权限，撤销后 Pre-signed URL 失效（需通过 MinIO Policy 实现）';

-- ============================================================
-- audit.llm_call_logs — LLM 调用日志表（分区）
-- ============================================================
CREATE TABLE audit.llm_call_logs (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    ai_task_id      UUID        REFERENCES ai_task.ai_tasks(id) ON DELETE SET NULL,

    -- 调用信息
    model_provider  VARCHAR(32) NOT NULL,   -- PRIVATE/OPENAI/ANTHROPIC
    model_name      VARCHAR(64) NOT NULL,   -- 具体模型名
    call_type       VARCHAR(32) NOT NULL,   -- GENERATE/EMBED/EXTRACT/EVALUATE

    -- Token 消耗
    prompt_tokens   INT         NOT NULL DEFAULT 0,
    completion_tokens INT       NOT NULL DEFAULT 0,
    total_tokens    INT         GENERATED ALWAYS AS (prompt_tokens + completion_tokens) STORED,

    -- 性能
    latency_ms      INT,                    -- 响应延迟（毫秒）
    is_success      BOOLEAN      NOT NULL DEFAULT TRUE,
    error_type      VARCHAR(32),            -- TIMEOUT/RATE_LIMIT/API_ERROR/CONTENT_FILTER

    -- 质量
    user_rating     SMALLINT,               -- 用户对生成结果的评分（1~5星）
    has_hallucination BOOLEAN,             -- 人工抽查是否发现幻觉

    -- 敏感性检查
    sensitive_check_passed BOOLEAN NOT NULL DEFAULT TRUE, -- 是否通过敏感数据检查
    is_external_call BOOLEAN NOT NULL DEFAULT FALSE,      -- 是否调用了外部API

    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);

COMMENT ON TABLE  audit.llm_call_logs                      IS 'LLM调用日志，用于Token消耗统计、模型质量监控和幻觉率追踪';
COMMENT ON COLUMN audit.llm_call_logs.is_external_call     IS '是否调用外部LLM API，与sensitive_check_passed联合分析安全合规性';
COMMENT ON COLUMN audit.llm_call_logs.has_hallucination    IS '人工抽查幻觉标记，每月抽样检查，计算幻觉率指标';
COMMENT ON COLUMN audit.llm_call_logs.user_rating          IS '用户对AI生成内容的满意度评分，支持模型治理中的灰度发布决策';
```

---

## 11. 索引策略

### 11.1 索引设计原则

- 每张表的主键（UUID）自动创建 B-tree 索引
- 高频查询的外键字段必须建索引（PostgreSQL 不自动为 FK 建索引）
- 软删除过滤 `deleted_at IS NULL` 使用**部分索引**，显著减少索引体积
- 状态字段（低基数）配合过滤条件使用**复合索引**
- 时间范围查询（审计日志/版本历史）使用 **BRIN 索引**
- 全文搜索使用 **GIN 索引**（配合 `pg_trgm`）
- JSON/JSONB 字段按需对特定路径建 **GIN 索引**
- 向量化状态、ES 同步状态等低基数过滤字段使用**部分索引**

### 11.2 Auth 域索引

```sql
-- auth.users
CREATE INDEX idx_users_email      ON auth.users (email)     WHERE deleted_at IS NULL;
CREATE INDEX idx_users_username   ON auth.users (username)  WHERE deleted_at IS NULL;
CREATE INDEX idx_users_is_active  ON auth.users (is_active) WHERE deleted_at IS NULL AND is_active = TRUE;

-- auth.user_roles
CREATE INDEX idx_user_roles_user_id ON auth.user_roles (user_id);
CREATE INDEX idx_user_roles_role_id ON auth.user_roles (role_id);

-- auth.refresh_tokens
CREATE INDEX idx_refresh_tokens_user_id    ON auth.refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON auth.refresh_tokens (expires_at)
    WHERE revoked_at IS NULL;
```

### 11.3 Project 域索引

```sql
-- project.bid_projects
CREATE INDEX idx_bid_projects_status      ON project.bid_projects (status)     WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_projects_tender_date ON project.bid_projects (tender_date) WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_projects_industry    ON project.bid_projects (industry)    WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_projects_region      ON project.bid_projects (region)      WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_projects_created_by  ON project.bid_projects (created_by)  WHERE deleted_at IS NULL;

-- 胜率模型批量查询（按行业+金额区间）
CREATE INDEX idx_bid_projects_industry_amount ON project.bid_projects (industry, budget_amount)
    WHERE deleted_at IS NULL;

-- project.project_members
CREATE INDEX idx_project_members_user_id   ON project.project_members (user_id);
CREATE INDEX idx_project_members_project   ON project.project_members (project_id) WHERE left_at IS NULL;

-- project.bid_records
CREATE INDEX idx_bid_records_project_id ON project.bid_records (project_id);
CREATE INDEX idx_bid_records_result     ON project.bid_records (result)      WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_records_is_reviewed ON project.bid_records (is_reviewed) WHERE deleted_at IS NULL;
```

### 11.4 Knowledge 域索引

```sql
-- knowledge.kb_documents（核心检索表）
CREATE INDEX idx_kb_docs_doc_type      ON knowledge.kb_documents (doc_type)     WHERE deleted_at IS NULL;
CREATE INDEX idx_kb_docs_parse_status  ON knowledge.kb_documents (parse_status)  WHERE deleted_at IS NULL;
CREATE INDEX idx_kb_docs_industry      ON knowledge.kb_documents (industry)      WHERE deleted_at IS NULL;
CREATE INDEX idx_kb_docs_expire_date   ON knowledge.kb_documents (expire_date)   WHERE deleted_at IS NULL AND expire_date IS NOT NULL;

-- 待 ES/Milvus 同步的文档（部分索引，索引体积极小）
CREATE INDEX idx_kb_docs_es_pending    ON knowledge.kb_documents (created_at)
    WHERE deleted_at IS NULL AND es_indexed = FALSE AND parse_status = 'SUCCESS';
CREATE INDEX idx_kb_docs_mv_pending    ON knowledge.kb_documents (created_at)
    WHERE deleted_at IS NULL AND milvus_synced = FALSE AND parse_status = 'SUCCESS';

-- 标签数组 GIN 索引（支持 @> 操作符）
CREATE INDEX idx_kb_docs_tags_gin      ON knowledge.kb_documents USING GIN (tags);
CREATE INDEX idx_kb_docs_keywords_gin  ON knowledge.kb_documents USING GIN (keywords);

-- knowledge.kb_chunks
CREATE INDEX idx_kb_chunks_doc_id      ON knowledge.kb_chunks (doc_id);
CREATE INDEX idx_kb_chunks_milvus_id   ON knowledge.kb_chunks (milvus_id) WHERE milvus_id IS NOT NULL;

-- GIN 全文检索索引（中文分词配合 pg_trgm）
CREATE INDEX idx_kb_chunks_content_trgm ON knowledge.kb_chunks USING GIN (content gin_trgm_ops);

-- knowledge.qualifications
CREATE INDEX idx_qualifications_cert_type   ON knowledge.qualifications (cert_type)   WHERE deleted_at IS NULL;
CREATE INDEX idx_qualifications_expire_date ON knowledge.qualifications (expire_date)  WHERE deleted_at IS NULL AND expire_date IS NOT NULL;
-- 即将过期证书查询（知识库健康度用）
CREATE INDEX idx_qualifications_expiring    ON knowledge.qualifications (expire_date)
    WHERE deleted_at IS NULL AND is_expired = FALSE AND expire_date < (CURRENT_DATE + INTERVAL '90 days');

-- knowledge.performances
CREATE INDEX idx_performances_industry       ON knowledge.performances (industry)         WHERE deleted_at IS NULL;
CREATE INDEX idx_performances_completion_year ON knowledge.performances (completion_year) WHERE deleted_at IS NULL;
CREATE INDEX idx_performances_scale          ON knowledge.performances (project_scale)    WHERE deleted_at IS NULL;
CREATE INDEX idx_performances_tech_stack     ON knowledge.performances USING GIN (tech_stack);

-- knowledge.personnel
CREATE INDEX idx_personnel_is_active         ON knowledge.personnel (is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_personnel_specialties_gin   ON knowledge.personnel USING GIN (specialties);

-- knowledge.personnel_certs
CREATE INDEX idx_personnel_certs_person_id   ON knowledge.personnel_certs (person_id);
CREATE INDEX idx_personnel_certs_expiring    ON knowledge.personnel_certs (expire_date)
    WHERE deleted_at IS NULL AND is_expired = FALSE AND expire_date < (CURRENT_DATE + INTERVAL '60 days');
```

### 11.5 Bid 域索引

```sql
-- bid.bids
CREATE INDEX idx_bids_project_id ON bid.bids (project_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_bids_status     ON bid.bids (status)     WHERE deleted_at IS NULL;
CREATE INDEX idx_bids_created_by ON bid.bids (created_by) WHERE deleted_at IS NULL;

-- bid.bid_sections
CREATE INDEX idx_bid_sections_bid_id    ON bid.bid_sections (bid_id)    WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_sections_parent_id ON bid.bid_sections (parent_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_sections_locked    ON bid.bid_sections (locked_by)
    WHERE deleted_at IS NULL AND locked_by IS NOT NULL;

-- bid.section_versions（高写入，按时间 BRIN）
CREATE INDEX idx_section_versions_section_id ON bid.section_versions (section_id);
CREATE INDEX idx_section_versions_created_at ON bid.section_versions USING BRIN (created_at);

-- bid.bid_variables
CREATE INDEX idx_bid_variables_bid_id  ON bid.bid_variables (bid_id);

-- bid.bid_variable_refs
CREATE INDEX idx_bid_var_refs_var_id     ON bid.bid_variable_refs (var_id);
CREATE INDEX idx_bid_var_refs_section_id ON bid.bid_variable_refs (section_id);

-- bid.bid_check_reports
CREATE INDEX idx_bid_check_reports_bid_id    ON bid.bid_check_reports (bid_id);
CREATE INDEX idx_bid_check_reports_checked_at ON bid.bid_check_reports (checked_at);

-- JSONB 索引：check_detail 中的 result 字段
CREATE INDEX idx_bid_check_detail_gin ON bid.bid_check_reports USING GIN (check_detail);
```

### 11.6 AI Task 域索引

```sql
-- ai_task.ai_tasks
CREATE INDEX idx_ai_tasks_status      ON ai_task.ai_tasks (task_status) WHERE task_status IN ('PENDING', 'RUNNING');
CREATE INDEX idx_ai_tasks_type_status ON ai_task.ai_tasks (task_type, task_status);
CREATE INDEX idx_ai_tasks_ref         ON ai_task.ai_tasks (ref_type, ref_id);
CREATE INDEX idx_ai_tasks_queued_at   ON ai_task.ai_tasks USING BRIN (queued_at);

-- ai_task.doc_constraints
CREATE INDEX idx_doc_constraints_project  ON ai_task.doc_constraints (project_id);
CREATE INDEX idx_doc_constraints_doc_id   ON ai_task.doc_constraints (doc_id);
CREATE INDEX idx_doc_constraints_type     ON ai_task.doc_constraints (constraint_type);
CREATE INDEX idx_doc_constraints_veto     ON ai_task.doc_constraints (is_veto)
    WHERE is_veto = TRUE;

-- ai_task.review_items
CREATE INDEX idx_review_items_task_id ON ai_task.review_items (review_task_id);
CREATE INDEX idx_review_items_verdict ON ai_task.review_items (verdict) WHERE verdict != 'COMPLIANT';
```

### 11.7 Audit 域索引

```sql
-- audit.audit_logs（分区子表自动继承，BRIN 适合时序数据）
CREATE INDEX idx_audit_logs_user_id     ON audit.audit_logs USING BRIN (user_id);
CREATE INDEX idx_audit_logs_action      ON audit.audit_logs (action);
CREATE INDEX idx_audit_logs_resource    ON audit.audit_logs (resource_type, resource_id);
CREATE INDEX idx_audit_logs_occurred_at ON audit.audit_logs USING BRIN (occurred_at);

-- audit.export_logs
CREATE INDEX idx_export_logs_user_id    ON audit.export_logs (user_id);
CREATE INDEX idx_export_logs_ref_id     ON audit.export_logs (ref_id);
CREATE INDEX idx_export_logs_occurred_at ON audit.export_logs USING BRIN (occurred_at);

-- audit.llm_call_logs（分区表，BRIN）
CREATE INDEX idx_llm_logs_model      ON audit.llm_call_logs (model_name);
CREATE INDEX idx_llm_logs_call_type  ON audit.llm_call_logs (call_type);
CREATE INDEX idx_llm_logs_is_success ON audit.llm_call_logs (is_success) WHERE is_success = FALSE;
CREATE INDEX idx_llm_logs_occurred   ON audit.llm_call_logs USING BRIN (occurred_at);
```

---

## 12. 分区策略

### 12.1 分区表一览

| 表名 | 分区策略 | 分区键 | 分区粒度 | 保留策略 |
|------|----------|--------|----------|----------|
| `audit.audit_logs` | RANGE | `occurred_at` | 季度 | 3年（12个分区）|
| `audit.llm_call_logs` | RANGE | `occurred_at` | 季度 | 2年（8个分区）|
| `bid.section_versions` | RANGE | `created_at` | 半年 | 永久保留 |

### 12.2 audit_logs 分区 DDL

```sql
-- 2026 年全年分区预建
CREATE TABLE audit.audit_logs_2026_q1 PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE audit.audit_logs_2026_q2 PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE TABLE audit.audit_logs_2026_q3 PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

CREATE TABLE audit.audit_logs_2026_q4 PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');

-- 2027 年分区（运维提前创建）
CREATE TABLE audit.audit_logs_2027_q1 PARTITION OF audit.audit_logs
    FOR VALUES FROM ('2027-01-01') TO ('2027-04-01');
-- ... 以此类推
```

### 12.3 llm_call_logs 分区 DDL

```sql
CREATE TABLE audit.llm_call_logs_2026_q1 PARTITION OF audit.llm_call_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE audit.llm_call_logs_2026_q2 PARTITION OF audit.llm_call_logs
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

CREATE TABLE audit.llm_call_logs_2026_q3 PARTITION OF audit.llm_call_logs
    FOR VALUES FROM ('2026-07-01') TO ('2026-10-01');

CREATE TABLE audit.llm_call_logs_2026_q4 PARTITION OF audit.llm_call_logs
    FOR VALUES FROM ('2026-10-01') TO ('2027-01-01');
```

### 12.4 section_versions 分区 DDL

```sql
CREATE TABLE bid.section_versions_2026_h1 PARTITION OF bid.section_versions
    FOR VALUES FROM ('2026-01-01') TO ('2026-07-01');

CREATE TABLE bid.section_versions_2026_h2 PARTITION OF bid.section_versions
    FOR VALUES FROM ('2026-07-01') TO ('2027-01-01');

CREATE TABLE bid.section_versions_2027_h1 PARTITION OF bid.section_versions
    FOR VALUES FROM ('2027-01-01') TO ('2027-07-01');
```

### 12.5 分区管理自动化函数

```sql
-- 自动创建下个季度分区（由 pg_cron 每季度执行）
CREATE OR REPLACE FUNCTION audit.fn_create_next_quarter_partition()
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    next_q_start DATE;
    next_q_end   DATE;
    partition_name TEXT;
BEGIN
    -- 计算下一个季度起止日期
    next_q_start := DATE_TRUNC('quarter', CURRENT_DATE + INTERVAL '3 months');
    next_q_end   := next_q_start + INTERVAL '3 months';
    partition_name := 'audit_logs_' ||
                      TO_CHAR(next_q_start, 'YYYY') || '_q' ||
                      TO_CHAR(next_q_start, 'Q');

    EXECUTE FORMAT(
        'CREATE TABLE IF NOT EXISTS audit.%I PARTITION OF audit.audit_logs
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, next_q_start, next_q_end
    );

    -- 同步创建 llm_call_logs 分区
    partition_name := 'llm_call_logs_' ||
                      TO_CHAR(next_q_start, 'YYYY') || '_q' ||
                      TO_CHAR(next_q_start, 'Q');
    EXECUTE FORMAT(
        'CREATE TABLE IF NOT EXISTS audit.%I PARTITION OF audit.llm_call_logs
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, next_q_start, next_q_end
    );

    RAISE NOTICE '分区创建完成: % ~ %', next_q_start, next_q_end;
END;
$$;

COMMENT ON FUNCTION audit.fn_create_next_quarter_partition IS
    '自动创建下季度审计日志分区，由 pg_cron 在每季度第一天前30天执行';
```

### 12.6 数据归档策略

```sql
-- 归档3年前的审计日志到冷存储（逻辑删除分区）
-- 执行前先导出分区数据到 MinIO 归档存储
CREATE OR REPLACE FUNCTION audit.fn_archive_old_partition(p_partition_name TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    -- 1. 标记分区为只读（DDL 级别保护）
    EXECUTE FORMAT('ALTER TABLE audit.%I ENABLE ROW LEVEL SECURITY', p_partition_name);
    -- 2. 从主表 DETACH（数据仍保留在分区表中，但不可通过主表查询）
    EXECUTE FORMAT(
        'ALTER TABLE audit.audit_logs DETACH PARTITION audit.%I',
        p_partition_name
    );
    RAISE NOTICE '分区 % 已归档（detach），数据保留在独立表中', p_partition_name;
END;
$$;
```

---

## 13. 视图与物化视图

```sql
-- ============================================================
-- 活跃文档视图（过滤软删除）
-- ============================================================
CREATE VIEW knowledge.v_active_documents AS
SELECT * FROM knowledge.kb_documents
WHERE deleted_at IS NULL;

-- ============================================================
-- 即将过期证书视图（知识库健康度监控用）
-- ============================================================
CREATE VIEW knowledge.v_expiring_certs AS
SELECT
    'qualification' AS cert_source,
    id, cert_name, cert_no, cert_type, expire_date,
    (expire_date - CURRENT_DATE) AS days_remaining,
    NULL::UUID AS person_id
FROM knowledge.qualifications
WHERE deleted_at IS NULL
  AND is_expired = FALSE
  AND expire_date IS NOT NULL
  AND expire_date < CURRENT_DATE + INTERVAL '90 days'

UNION ALL

SELECT
    'personnel_cert' AS cert_source,
    pc.id, pc.cert_name, pc.cert_no, pc.cert_type, pc.expire_date,
    (pc.expire_date - CURRENT_DATE) AS days_remaining,
    pc.person_id
FROM knowledge.personnel_certs pc
WHERE pc.deleted_at IS NULL
  AND pc.is_expired = FALSE
  AND pc.expire_date IS NOT NULL
  AND pc.expire_date < CURRENT_DATE + INTERVAL '60 days';

COMMENT ON VIEW knowledge.v_expiring_certs IS '即将过期证书视图，整合企业资质和人员个人证书，驱动到期提醒推送';

-- ============================================================
-- 物化视图：知识库健康度评分（每周刷新）
-- ============================================================
CREATE MATERIALIZED VIEW knowledge.mv_kb_health_score AS
WITH coverage AS (
    -- 覆盖度：各类型文档数量
    SELECT
        doc_type,
        COUNT(*) FILTER (WHERE deleted_at IS NULL) AS doc_count
    FROM knowledge.kb_documents
    WHERE deleted_at IS NULL
    GROUP BY doc_type
),
timeliness AS (
    -- 时效性：过期文档占比
    SELECT
        COUNT(*) FILTER (WHERE is_expired = TRUE)::FLOAT /
        NULLIF(COUNT(*), 0) AS expired_ratio
    FROM knowledge.kb_documents
    WHERE deleted_at IS NULL
      AND expire_date IS NOT NULL
),
activity AS (
    -- 活跃度：近30天新增文档数
    SELECT COUNT(*) AS recent_30d_count
    FROM knowledge.kb_documents
    WHERE deleted_at IS NULL
      AND created_at >= NOW() - INTERVAL '30 days'
)
SELECT
    NOW() AS calculated_at,
    COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'QUALIFICATION'), 0) AS qualification_count,
    COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'PERFORMANCE'), 0)   AS performance_count,
    COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'PERSONNEL'), 0)     AS personnel_count,
    COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'SOLUTION'), 0)      AS solution_count,
    COALESCE((SELECT expired_ratio FROM timeliness), 0) AS expired_ratio,
    COALESCE((SELECT recent_30d_count FROM activity), 0) AS recent_30d_count,
    -- 综合评分算法（0~100）
    GREATEST(0, LEAST(100,
        -- 覆盖度得分（40分）
        LEAST(40, (
            COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'PERFORMANCE'), 0) * 0.5 +
            COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'QUALIFICATION'), 0) * 0.3 +
            COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'PERSONNEL'), 0) * 0.1 +
            COALESCE((SELECT doc_count FROM coverage WHERE doc_type = 'SOLUTION'), 0) * 0.5
        )) +
        -- 时效性得分（30分，过期率越低分越高）
        30 * (1 - COALESCE((SELECT expired_ratio FROM timeliness), 0)) +
        -- 活跃度得分（30分）
        LEAST(30, COALESCE((SELECT recent_30d_count FROM activity), 0) * 3)
    )) AS health_score
WITH DATA;

CREATE UNIQUE INDEX idx_mv_kb_health ON knowledge.mv_kb_health_score (calculated_at);

COMMENT ON MATERIALIZED VIEW knowledge.mv_kb_health_score IS
    '知识库健康度评分物化视图，每周由 pg_cron 刷新，≥80分健康，60~79预警，<60告警';

-- ============================================================
-- 视图：标书编写进度看板
-- ============================================================
CREATE VIEW bid.v_bid_progress AS
SELECT
    b.id,
    b.project_id,
    p.project_name,
    p.tender_date,
    (p.tender_date - CURRENT_DATE) AS days_to_deadline,
    b.status,
    b.total_sections,
    b.done_sections,
    b.progress_pct,
    COUNT(bs.id) FILTER (WHERE bs.review_status = 'APPROVED') AS approved_sections,
    COUNT(bs.id) FILTER (WHERE bs.locked_by IS NOT NULL)       AS locked_sections,
    b.created_at,
    b.updated_at
FROM bid.bids b
JOIN project.bid_projects p ON b.project_id = p.id
LEFT JOIN bid.bid_sections bs ON bs.bid_id = b.id AND bs.deleted_at IS NULL
WHERE b.deleted_at IS NULL
  AND p.deleted_at IS NULL
GROUP BY b.id, p.project_name, p.tender_date;

-- ============================================================
-- 物化视图：LLM 调用质量统计（每日刷新）
-- ============================================================
CREATE MATERIALIZED VIEW audit.mv_llm_quality_daily AS
SELECT
    DATE_TRUNC('day', occurred_at)  AS stat_date,
    model_name,
    call_type,
    COUNT(*)                        AS total_calls,
    COUNT(*) FILTER (WHERE is_success = FALSE) AS failed_calls,
    ROUND(AVG(latency_ms))          AS avg_latency_ms,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms)) AS p99_latency_ms,
    SUM(total_tokens)               AS total_tokens,
    AVG(user_rating) FILTER (WHERE user_rating IS NOT NULL) AS avg_user_rating,
    COUNT(*) FILTER (WHERE has_hallucination = TRUE) AS hallucination_count,
    COUNT(*) FILTER (WHERE is_external_call = TRUE)  AS external_call_count
FROM audit.llm_call_logs
WHERE occurred_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', occurred_at), model_name, call_type
WITH DATA;

CREATE INDEX idx_mv_llm_quality_date ON audit.mv_llm_quality_daily (stat_date, model_name);

COMMENT ON MATERIALIZED VIEW audit.mv_llm_quality_daily IS
    'LLM调用质量日统计物化视图，用于Grafana监控看板，每日00:30刷新';
```

---

## 14. 触发器与函数

```sql
-- ============================================================
-- 触发器：标书章节更新时自动同步进度到 bid.bids
-- ============================================================
CREATE OR REPLACE FUNCTION bid.fn_sync_bid_progress()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_total INT;
    v_done  INT;
BEGIN
    -- 仅在 is_done 或 deleted_at 变化时重算
    IF (TG_OP = 'UPDATE' AND OLD.is_done = NEW.is_done AND OLD.deleted_at IS NOT DISTINCT FROM NEW.deleted_at) THEN
        RETURN NEW;
    END IF;

    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE is_done = TRUE)
    INTO v_total, v_done
    FROM bid.bid_sections
    WHERE bid_id = NEW.bid_id AND deleted_at IS NULL;

    UPDATE bid.bids
    SET total_sections = v_total,
        done_sections  = v_done,
        progress_pct   = CASE WHEN v_total = 0 THEN 0
                              ELSE ROUND((v_done::NUMERIC / v_total) * 100, 2)
                         END,
        updated_at     = NOW()
    WHERE id = NEW.bid_id;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_sync_bid_progress
    AFTER INSERT OR UPDATE OR DELETE ON bid.bid_sections
    FOR EACH ROW EXECUTE FUNCTION bid.fn_sync_bid_progress();

-- ============================================================
-- 触发器：章节内容变更时自动保存版本历史
-- ============================================================
CREATE OR REPLACE FUNCTION bid.fn_save_section_version()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_version_no INT;
BEGIN
    -- 仅在 content 字段变化时触发
    IF OLD.content IS NOT DISTINCT FROM NEW.content THEN
        RETURN NEW;
    END IF;

    SELECT COALESCE(MAX(version_no), 0) + 1
    INTO v_version_no
    FROM bid.section_versions
    WHERE section_id = NEW.id;

    INSERT INTO bid.section_versions (
        section_id, version_no, content, word_count,
        change_type, created_by
    ) VALUES (
        NEW.id,
        v_version_no,
        OLD.content,   -- 保存修改前的内容
        COALESCE(LENGTH(OLD.content) - LENGTH(REPLACE(OLD.content, ' ', '')) + 1, 0),
        CASE WHEN NEW.last_generated_by = 'AI' THEN 'AI_GEN' ELSE 'MANUAL' END,
        NEW.updated_by
    );

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_save_section_version
    BEFORE UPDATE ON bid.bid_sections
    FOR EACH ROW EXECUTE FUNCTION bid.fn_save_section_version();

-- ============================================================
-- 函数：检查编辑锁是否过期并自动释放
-- ============================================================
CREATE OR REPLACE FUNCTION bid.fn_acquire_section_lock(
    p_section_id UUID,
    p_user_id    VARCHAR(64),
    p_timeout_minutes INT DEFAULT 30
)
RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_section bid.bid_sections%ROWTYPE;
BEGIN
    SELECT * INTO v_section FROM bid.bid_sections WHERE id = p_section_id FOR UPDATE;

    -- 检查是否已被他人锁定且未过期
    IF v_section.locked_by IS NOT NULL
       AND v_section.locked_by != p_user_id
       AND v_section.lock_expires_at > NOW()
    THEN
        RETURN JSONB_BUILD_OBJECT(
            'success', FALSE,
            'locked_by', v_section.locked_by,
            'expires_at', v_section.lock_expires_at
        );
    END IF;

    -- 获取锁
    UPDATE bid.bid_sections
    SET locked_by       = p_user_id,
        locked_at       = NOW(),
        lock_expires_at = NOW() + (p_timeout_minutes || ' minutes')::INTERVAL,
        updated_at      = NOW(),
        updated_by      = p_user_id
    WHERE id = p_section_id;

    RETURN JSONB_BUILD_OBJECT(
        'success', TRUE,
        'expires_at', NOW() + (p_timeout_minutes || ' minutes')::INTERVAL
    );
END;
$$;

COMMENT ON FUNCTION bid.fn_acquire_section_lock IS
    '章节编辑锁获取函数，支持过期自动续锁和锁超时自动释放，防止多人同时编辑冲突';

-- ============================================================
-- 函数：知识库文档去重检查
-- ============================================================
CREATE OR REPLACE FUNCTION knowledge.fn_check_doc_duplicate(p_file_hash VARCHAR(64))
RETURNS JSONB LANGUAGE plpgsql AS $$
DECLARE
    v_existing knowledge.kb_documents%ROWTYPE;
BEGIN
    SELECT * INTO v_existing
    FROM knowledge.kb_documents
    WHERE file_hash = p_file_hash AND deleted_at IS NULL
    LIMIT 1;

    IF FOUND THEN
        RETURN JSONB_BUILD_OBJECT(
            'is_duplicate', TRUE,
            'existing_id', v_existing.id,
            'existing_title', v_existing.title,
            'created_at', v_existing.created_at
        );
    ELSE
        RETURN JSONB_BUILD_OBJECT('is_duplicate', FALSE);
    END IF;
END;
$$;

COMMENT ON FUNCTION knowledge.fn_check_doc_duplicate IS '上传前去重检查，相同SHA-256哈希的文件不重复入库';
```

---

## 15. 数据字典

### 15.1 枚举值说明

| 枚举名 | 值 | 中文含义 |
|--------|-----|---------|
| `entity_status` | `DRAFT` | 草稿 |
| | `IN_PROGRESS` | 进行中 |
| | `REVIEWING` | 审核中 |
| | `APPROVED` | 已审批 |
| | `SUBMITTED` | 已递交 |
| | `COMPLETED` | 已完成 |
| | `CANCELLED` | 已取消 |
| | `ARCHIVED` | 已归档 |
| `bid_result` | `WON` | 中标 |
| | `LOST` | 未中标 |
| | `INVALID` | 废标 |
| | `WITHDREW` | 撤标 |
| | `PENDING` | 待定 |
| `section_type` | `TEMPLATE` | 固定模板（变量替换） |
| | `DATA_FILL` | 结构化数据填充 |
| | `FREE_NARRATIVE` | 自由论述（LLM生成）|
| `constraint_type` | `COMPLIANCE` | 合规要求（废标条款）|
| | `CONTENT` | 内容要求（必备材料）|
| | `GUIDE` | 写作引导（评分导向）|
| `review_verdict` | `COMPLIANT` | 符合 |
| | `DEVIATED` | 偏离 |
| | `MISSING` | 缺失 |
| | `PENDING` | 待确认 |
| `check_result` | `PASS` | 通过（绿色）|
| | `WARN` | 警告（橙色）|
| | `FAIL` | 否决（红色）|
| `task_status` | `PENDING` | 等待执行 |
| | `RUNNING` | 执行中 |
| | `SUCCESS` | 成功 |
| | `FAILED` | 失败 |
| | `CANCELLED` | 已取消 |
| | `RETRYING` | 重试中 |
| `risk_level` | `HIGH` | 高风险（串标）|
| | `MEDIUM` | 中风险 |
| | `LOW` | 低风险 |

### 15.2 角色权限矩阵

| 权限编码 | SYS_ADMIN | COMP_ADMIN | PROJECT_MGR | BID_STAFF | APPROVER | READER |
|---------|:---------:|:----------:|:-----------:|:---------:|:--------:|:------:|
| `system:config` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `user:manage` | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `knowledge:manage` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `project:create` | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `bid:edit` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `bid:approve` | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| `bid:export` | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| `report:read` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### 15.3 表数量与规模预估

| Schema | 表数量 | 预计首年记录量（量级）| 主要增长驱动 |
|--------|--------|---------------------|-------------|
| `auth` | 5 | 万级 | 用户增长缓慢 |
| `project` | 3 | 百~千级 | 投标项目（100个/年）|
| `knowledge` | 6 | 万~十万级 | 知识库文档持续积累 |
| `bid` | 6 | 万级 | 章节版本历史高频写入 |
| `ai_task` | 5 | 十万级 | 每次生成/审查产生大量任务 |
| `audit` | 3 | 百万级 | 审计日志每操作写入，LLM调用频繁 |

---

## 16. 迁移管理规范

### 16.1 迁移工具

- **Python 服务**：使用 `Alembic`，迁移文件路径 `{service}/migrations/`
- **Java 服务**：使用 `Flyway`，迁移文件路径 `src/main/resources/db/migration/`
- **迁移脚本命名**：`V{version}__{描述}.sql`，如 `V001__init_auth_schema.sql`

### 16.2 迁移执行原则

```sql
-- ✅ 正确：向后兼容的迁移
-- 1. 新增列必须允许 NULL 或有默认值
ALTER TABLE bid.bids ADD COLUMN export_format VARCHAR(16) DEFAULT 'DOCX';

-- 2. 删除列分两步：先废弃（应用层停用），再下一个版本物理删除
-- Step 1: 在代码中停止读写该列（本次上线）
-- Step 2: 下版本迁移中执行
ALTER TABLE bid.bids DROP COLUMN old_column;  -- 仅在完全确认应用层不再使用后

-- 3. 修改字段类型：先新增，双写，再切换，再删旧
-- ❌ 禁止直接 ALTER COLUMN 修改类型（可能导致锁表）
ALTER TABLE bid.bids ALTER COLUMN bid_version TYPE TEXT;  -- 禁止在生产直接执行

-- ✅ 正确做法：
ALTER TABLE bid.bids ADD COLUMN bid_version_new TEXT;
UPDATE bid.bids SET bid_version_new = bid_version::TEXT WHERE bid_version_new IS NULL;
-- 完成双写验证后再删除旧列
```

### 16.3 大表 DDL 安全操作

```sql
-- 对于行数超过 100 万的表，禁止直接 ALTER TABLE（会锁表）
-- 使用 pg_repack 或分步操作

-- 添加索引：使用 CONCURRENTLY（不锁表）
CREATE INDEX CONCURRENTLY idx_new_index ON knowledge.kb_chunks (doc_id);

-- 添加约束：先以 NOT VALID 添加，再 VALIDATE（减少锁持有时间）
ALTER TABLE knowledge.kb_chunks ADD CONSTRAINT chk_new_rule
    CHECK (token_count > 0) NOT VALID;
ALTER TABLE knowledge.kb_chunks VALIDATE CONSTRAINT chk_new_rule;
```

---

*本文档为 AI 智能投标系统数据库设计文档，数据库结构变更须同步更新本文档并记录变更历史。*

*© 2026 内部保密文件，未经授权不得外传。*
