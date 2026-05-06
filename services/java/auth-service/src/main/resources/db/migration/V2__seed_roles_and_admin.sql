-- ============================================================
-- 初始化 6 种系统内置角色
-- ============================================================
INSERT INTO auth.roles (role_code, role_name, description, is_system, sort_order, created_by, updated_by) VALUES
    ('SYS_ADMIN',    '超级管理员', '系统最高权限，管理所有配置和用户', TRUE, 10, 'system', 'system'),
    ('COMP_ADMIN',   '公司管理员', '管理本公司用户和知识库',           TRUE, 20, 'system', 'system'),
    ('PROJECT_MGR',  '项目经理',   '创建和管理投标项目，审批导出',     TRUE, 30, 'system', 'system'),
    ('BID_STAFF',    '投标专员',   '编写标书，使用AI辅助功能',         TRUE, 40, 'system', 'system'),
    ('APPROVER',     '审批人',     '审批标书，查阅审查报告',           TRUE, 50, 'system', 'system'),
    ('READER',       '只读查阅',   '仅查阅报告，无编辑权限',           TRUE, 60, 'system', 'system')
ON CONFLICT (role_code) DO NOTHING;

-- ============================================================
-- 初始化基础权限点
-- ============================================================
INSERT INTO auth.permissions (perm_code, perm_name, resource, action, description, is_system, created_by, updated_by) VALUES
    ('user:manage',      '用户管理',       'user',      'manage',   '创建、编辑、删除用户及分配角色', TRUE, 'system', 'system'),
    ('project:create',   '项目创建',       'project',   'create',   '创建和管理投标项目',            TRUE, 'system', 'system'),
    ('project:read',     '项目查看',       'project',   'read',     '查看投标项目列表和详情',         TRUE, 'system', 'system'),
    ('bid:edit',         '标书编辑',       'bid',       'edit',     '编写和编辑标书内容',            TRUE, 'system', 'system'),
    ('bid:export',       '标书导出',       'bid',       'export',   '导出标书文件',                  TRUE, 'system', 'system'),
    ('report:read',      '报告查看',       'report',    'read',     '查看审查报告和分析结果',         TRUE, 'system', 'system'),
    ('knowledge:manage', '知识库管理',     'knowledge', 'manage',   '上传、删除知识库文档',           TRUE, 'system', 'system'),
    ('system:config',    '系统配置',       'system',    'config',   '修改系统全局配置',              TRUE, 'system', 'system')
ON CONFLICT (perm_code) DO NOTHING;

-- ============================================================
-- 角色权限关联（简化的权限矩阵）
-- ============================================================
-- SYS_ADMIN: 全部权限
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'SYS_ADMIN'
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- COMP_ADMIN: user:manage, knowledge:manage, project:read, report:read
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'COMP_ADMIN'
  AND p.perm_code IN ('user:manage', 'knowledge:manage', 'project:read', 'report:read')
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- PROJECT_MGR: project:create, project:read, bid:export, report:read
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'PROJECT_MGR'
  AND p.perm_code IN ('project:create', 'project:read', 'bid:export', 'report:read')
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- BID_STAFF: bid:edit, project:read, bid:export
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'BID_STAFF'
  AND p.perm_code IN ('bid:edit', 'project:read', 'bid:export')
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- APPROVER: report:read, project:read
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'APPROVER'
  AND p.perm_code IN ('report:read', 'project:read')
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- READER: report:read, project:read
INSERT INTO auth.role_permissions (role_id, perm_id, granted_by)
SELECT r.id, p.id, 'system'
FROM auth.roles r, auth.permissions p
WHERE r.role_code = 'READER'
  AND p.perm_code IN ('report:read', 'project:read')
ON CONFLICT (role_id, perm_id) DO NOTHING;

-- ============================================================
-- ============================================================
-- 预置系统管理员账号
-- 密码: Admin@123 (bcrypt 哈希)
-- ============================================================
INSERT INTO auth.users (
    username, display_name, email, is_active, password_hash,
    created_by, updated_by
) VALUES (
    'admin', '系统管理员', 'admin@bidai.internal', TRUE,
    '$2b$12$8EFpUyWddfmyWcEfshbi7eyj5DromaFLzQ.q39BZzP.K5cSfx/93K',
    'system', 'system'
)
ON CONFLICT (username) DO NOTHING;

-- 为管理员分配 SYS_ADMIN 角色
INSERT INTO auth.user_roles (user_id, role_id, granted_by)
SELECT u.id, r.id, 'system'
FROM auth.users u, auth.roles r
WHERE u.username = 'admin' AND r.role_code = 'SYS_ADMIN'
ON CONFLICT (user_id, role_id) DO NOTHING;
