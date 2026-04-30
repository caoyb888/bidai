-- ============================================================
-- AI 智能投标系统 · PostgreSQL 初始化脚本
-- 在容器首次启动时自动执行（docker-entrypoint-initdb.d）
-- ============================================================

-- ----------------------------------------------------------
-- 1. 启用必要扩展
-- ----------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid(), 加密函数
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- 中文模糊搜索支持
CREATE EXTENSION IF NOT EXISTS "btree_gin";   -- GIN 索引支持 B-tree 操作符
CREATE EXTENSION IF NOT EXISTS "unaccent";    -- 文本标准化

COMMENT ON EXTENSION "pgcrypto"  IS 'UUID 生成与加密函数';
COMMENT ON EXTENSION "pg_trgm"   IS '三元组匹配，支持中文模糊搜索';
COMMENT ON EXTENSION "btree_gin" IS 'GIN 索引的 B-tree 操作符支持';
COMMENT ON EXTENSION "unaccent"  IS '去重音符号，用于文本标准化';

-- ----------------------------------------------------------
-- 2. 创建业务域 Schema（按数据库设计文档要求）
-- ----------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS project;
CREATE SCHEMA IF NOT EXISTS knowledge;
CREATE SCHEMA IF NOT EXISTS bid;
CREATE SCHEMA IF NOT EXISTS ai_task;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA auth      IS '用户、角色、权限';
COMMENT ON SCHEMA project   IS '投标项目、项目成员、投标记录';
COMMENT ON SCHEMA knowledge IS '企业知识库（文档、分块、资质、业绩、人员）';
COMMENT ON SCHEMA bid       IS '标书编写（标书、章节、变量、检查报告）';
COMMENT ON SCHEMA ai_task   IS 'AI 任务队列、审查、串标分析、约束提取';
COMMENT ON SCHEMA audit     IS '审计日志、导出记录、LLM 调用日志';

-- ----------------------------------------------------------
-- 3. 设置默认搜索路径（便于开发调试）
-- ----------------------------------------------------------
ALTER DATABASE bidai SET search_path = auth, project, knowledge, bid, ai_task, audit, public;

-- ----------------------------------------------------------
-- 4. 公共函数：自动维护 updated_at
-- ----------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.fn_update_updated_at() IS '自动维护所有业务表的 updated_at 字段';

-- ----------------------------------------------------------
-- 5. 初始化完成标记（便于外部脚本判断）
-- ----------------------------------------------------------
DO $$
BEGIN
    RAISE NOTICE 'BidAI PostgreSQL initialization completed successfully.';
END $$;
