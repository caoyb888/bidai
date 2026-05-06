-- ============================================================
-- project schema initialization
-- ============================================================
CREATE SCHEMA IF NOT EXISTS project;

-- ============================================================
-- project.bid_projects — 投标项目主表
-- ============================================================
CREATE TABLE project.bid_projects (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_no          VARCHAR(64)     NOT NULL,
    project_name        VARCHAR(512)    NOT NULL,
    client_name         VARCHAR(256)    NOT NULL,
    client_contact      VARCHAR(128),
    industry            VARCHAR(64)     NOT NULL,
    region              VARCHAR(64)     NOT NULL,
    project_category    VARCHAR(64),
    budget_amount       NUMERIC(18, 2),
    bid_amount          NUMERIC(18, 2),
    release_date        DATE,
    tender_date         DATE            NOT NULL,
    deadline            TIMESTAMPTZ     NOT NULL,
    evaluation_method   VARCHAR(32),
    tech_score_weight   NUMERIC(5, 2),
    price_score_weight  NUMERIC(5, 2),
    business_score_weight NUMERIC(5, 2),
    win_rate_score      NUMERIC(5, 2),
    win_rate_grade      CHAR(1),
    win_rate_calc_at    TIMESTAMPTZ,
    status              VARCHAR(32)     NOT NULL DEFAULT 'DRAFT',
    is_participate      BOOLEAN         NOT NULL DEFAULT TRUE,
    not_participate_reason TEXT,
    description         TEXT,
    tender_agency       VARCHAR(256),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64)     NOT NULL,
    updated_by          VARCHAR(64)     NOT NULL,

    CONSTRAINT uq_bid_projects_no UNIQUE (project_no)
);

CREATE INDEX idx_bid_projects_deleted_at ON project.bid_projects(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_bid_projects_status ON project.bid_projects(status);
CREATE INDEX idx_bid_projects_industry ON project.bid_projects(industry);

COMMENT ON TABLE  project.bid_projects                   IS '投标项目主表，每条记录对应一次参与的招标项目';
COMMENT ON COLUMN project.bid_projects.project_no        IS '项目编号，格式建议：BID-YYYY-NNNN';
COMMENT ON COLUMN project.bid_projects.industry          IS '行业分类：IT/建筑/医疗/教育/交通/能源等';
COMMENT ON COLUMN project.bid_projects.tender_date       IS '开标日期，是项目时间轴的核心节点';
COMMENT ON COLUMN project.bid_projects.deleted_at        IS '软删除时间戳，非NULL表示已归档/删除';

-- ============================================================
-- project.project_members — 项目成员表
-- ============================================================
CREATE TABLE project.project_members (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID        NOT NULL REFERENCES project.bid_projects(id) ON DELETE CASCADE,
    user_id     UUID        NOT NULL,
    role        VARCHAR(32) NOT NULL DEFAULT 'MEMBER',
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    left_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by  VARCHAR(64) NOT NULL,
    updated_by  VARCHAR(64) NOT NULL,

    CONSTRAINT uq_project_members UNIQUE (project_id, user_id)
);

CREATE INDEX idx_project_members_project_id ON project.project_members(project_id) WHERE left_at IS NULL;

COMMENT ON TABLE  project.project_members      IS '项目成员表，记录参与每个项目的人员及其角色';
COMMENT ON COLUMN project.project_members.role IS '项目内职责：LEADER-项目负责人，WRITER-编写人员，REVIEWER-审核人员，OBSERVER-只读观察';

-- ============================================================
-- project.bid_records — 投标结果记录表（预留）
-- ============================================================
CREATE TABLE project.bid_records (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID            NOT NULL REFERENCES project.bid_projects(id) ON DELETE CASCADE,
    result              VARCHAR(32)     NOT NULL DEFAULT 'PENDING',
    final_bid_amount    NUMERIC(18, 2),
    winning_amount      NUMERIC(18, 2),
    winning_company     VARCHAR(256),
    tech_score          NUMERIC(6, 2),
    business_score      NUMERIC(6, 2),
    price_score         NUMERIC(6, 2),
    total_score         NUMERIC(6, 2),
    rank                SMALLINT,
    fail_reason         VARCHAR(32),
    fail_reason_detail  TEXT,
    is_reviewed         BOOLEAN NOT NULL DEFAULT FALSE,
    review_notes        TEXT,
    quality_content_ids UUID[],
    result_announced_at DATE,
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at          TIMESTAMPTZ,
    created_by          VARCHAR(64) NOT NULL,
    updated_by          VARCHAR(64) NOT NULL,

    CONSTRAINT uq_bid_records_project UNIQUE (project_id)
);
