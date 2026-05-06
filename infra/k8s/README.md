# K8s 开发环境配置

**Story**: S0-007 — 部署 K8s 开发命名空间，配置 ConfigMap / Secret 管理规范

---

## 目录结构

```
infra/k8s/
├── base/
│   ├── 00-namespace.yaml          # 命名空间 bid-ai-dev
│   ├── 01-shared-configmap.yaml   # 共享 ConfigMap（普通配置）
│   └── 02-secrets-template.yaml   # Secret 模板（占位符，严禁提交真实值）
│   └── 02-secrets.yaml            # 真实 Secret（由脚本生成，已加入 .gitignore）
├── dev/
│   ├── python-services.yaml       # 6 个 Python 服务 Deployment + Service
│   ├── java-services.yaml         # 4 个 Java 服务 Deployment + Service
│   └── frontend-web.yaml          # Web 前端 nginx Deployment + Service
└── monitoring/                    # Prometheus/Grafana 配置（预留）
```

---

## 配置管理规范

按 Tech Spec §14 分级管理：

| 级别 | 管理方式 | 示例 |
|------|----------|------|
| 普通配置 | K8s ConfigMap | `APP_ENV`, `LOG_LEVEL`, `ES_URL` |
| 敏感配置 | K8s Secret（Base64） | `DATABASE_PASSWORD`, `JWT_SECRET_KEY` |
| 超敏感配置 | HashiCorp Vault | 证书私钥、加密主密钥（预留） |

**红线**：任何 Secret 值不得出现在 Git 仓库中。违者按 S1 级安全事故处理。

---

## 快速部署

### 1. 生成 Secret（首次部署或密钥轮换）

```bash
export DATABASE_PASSWORD="your-db-password"
export MINIO_ACCESS_KEY="your-minio-key"
export MINIO_SECRET_KEY="your-minio-secret"
export JWT_SECRET_KEY="your-jwt-secret"
export ENCRYPTION_KEY="your-encryption-key"
export LLM_EXTERNAL_API_KEY="your-llm-api-key"

./scripts/generate-k8s-secrets.sh
```

### 2. 一键部署到 K8s

```bash
# 验证模式（不实际执行）
./scripts/deploy-k8s-dev.sh --dry-run

# 实际部署
./scripts/deploy-k8s-dev.sh
```

### 3. 手动逐文件部署

```bash
kubectl apply -f infra/k8s/base/00-namespace.yaml
kubectl apply -f infra/k8s/base/01-shared-configmap.yaml
kubectl apply -f infra/k8s/base/02-secrets.yaml   # 确保已生成真实值
kubectl apply -f infra/k8s/dev/
```

---

## 验证部署

```bash
# 查看命名空间内所有资源
kubectl get all -n bid-ai-dev

# 查看 Pod 状态
kubectl get pods -n bid-ai-dev -w

# 查看服务日志
kubectl logs -f deployment/auth-service -n bid-ai-dev
kubectl logs -f deployment/bid-parser-service -n bid-ai-dev

# 端口转发测试本地访问
kubectl port-forward svc/auth-service 8081:80 -n bid-ai-dev
kubectl port-forward svc/bid-web 8080:80 -n bid-ai-dev
```

---

## 资源限制（开发环境）

| 服务类型 | 请求内存 | 限制内存 | 请求 CPU | 限制 CPU |
|----------|----------|----------|----------|----------|
| Python 服务 | 256Mi | 512Mi | 250m | 500m |
| Java 服务 | 512Mi | 1Gi | 250m | 1000m |
| Web 前端 | 64Mi | 128Mi | 50m | 100m |

---

## 回滚操作

```bash
# 查看 Deployment 历史
kubectl rollout history deployment/auth-service -n bid-ai-dev

# 回滚到上一个版本
kubectl rollout undo deployment/auth-service -n bid-ai-dev

# 回滚到指定版本
kubectl rollout undo deployment/auth-service -n bid-ai-dev --to-revision=2
```
