-- ============================================================
-- Auth Schema 初始化
-- 对应数据库设计文档: DB-BIDAI-2026-001
-- ============================================================

CREATE SCHEMA IF NOT EXISTS auth;

-- 公共函数：自动维护 updated_at
CREATE OR REPLACE FUNCTION public.fn_update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- ============================================================
-- auth.users — 系统用户表
-- ============================================================
CREATE TABLE auth.users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64)  NOT NULL,
    display_name    VARCHAR(128) NOT NULL,
    email           VARCHAR(256) NOT NULL,
    phone_enc       BYTEA,
    department      VARCHAR(128),
    job_title       VARCHAR(128),
    avatar_url      VARCHAR(512),
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    password_hash   VARCHAR(256) NOT NULL,
    last_login_at   TIMESTAMPTZ,
    login_fail_cnt  SMALLINT     NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    mfa_enabled     BOOLEAN      NOT NULL DEFAULT FALSE,
    mfa_secret_enc  BYTEA,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    created_by      VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by      VARCHAR(64)  NOT NULL DEFAULT 'system',
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email    UNIQUE (email)
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- auth.roles — 角色表
-- ============================================================
CREATE TABLE auth.roles (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    role_code   VARCHAR(32)  NOT NULL,
    role_name   VARCHAR(64)  NOT NULL,
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ,
    created_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    CONSTRAINT uq_roles_code UNIQUE (role_code)
);

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON auth.roles
    FOR EACH ROW EXECUTE FUNCTION public.fn_update_updated_at();

-- ============================================================
-- auth.permissions — 权限点表
-- ============================================================
CREATE TABLE auth.permissions (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    perm_code   VARCHAR(64)  NOT NULL,
    perm_name   VARCHAR(128) NOT NULL,
    resource    VARCHAR(64)  NOT NULL,
    action      VARCHAR(32)  NOT NULL,
    description TEXT,
    is_system   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    updated_by  VARCHAR(64)  NOT NULL DEFAULT 'system',
    CONSTRAINT uq_permissions_code UNIQUE (perm_code)
);

-- ============================================================
-- auth.role_permissions — 角色权限关联表
-- ============================================================
CREATE TABLE auth.role_permissions (
    role_id     UUID    NOT NULL REFERENCES auth.roles(id)       ON DELETE CASCADE,
    perm_id     UUID    NOT NULL REFERENCES auth.permissions(id) ON DELETE CASCADE,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by  VARCHAR(64) NOT NULL DEFAULT 'system',
    PRIMARY KEY (role_id, perm_id)
);

-- ============================================================
-- auth.user_roles — 用户角色关联表
-- ============================================================
CREATE TABLE auth.user_roles (
    user_id     UUID    NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_id     UUID    NOT NULL REFERENCES auth.roles(id) ON DELETE RESTRICT,
    granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by  VARCHAR(64) NOT NULL DEFAULT 'system',
    expires_at  TIMESTAMPTZ,
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================
-- auth.refresh_tokens — Refresh Token 表
-- ============================================================
CREATE TABLE auth.refresh_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(256) NOT NULL,
    device_info VARCHAR(512),
    ip_address  INET,
    expires_at  TIMESTAMPTZ  NOT NULL,
    revoked_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_refresh_tokens_hash UNIQUE (token_hash)
);
