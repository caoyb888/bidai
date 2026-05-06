#!/usr/bin/env bash
# ============================================================
# K8s 开发环境一键部署脚本
# Story: S0-007
# 用法：./scripts/deploy-k8s-dev.sh [--dry-run]
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
K8S_BASE="$PROJECT_ROOT/infra/k8s/base"
K8S_DEV="$PROJECT_ROOT/infra/k8s/dev"
NAMESPACE="bid-ai-dev"
DRY_RUN=""

if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN="--dry-run=client"
  echo "🧪 Dry-run mode enabled (no changes will be applied)"
fi

echo "🚀 Deploying BidAI development environment to K8s..."
echo "   Namespace: $NAMESPACE"
echo ""

# 检查依赖
if ! command -v kubectl &> /dev/null; then
  echo "❌ kubectl is not installed. Please install kubectl first."
  exit 1
fi

# 检查 Secret 是否已配置
if [[ ! -f "$K8S_BASE/02-secrets.yaml" ]]; then
  echo "⚠️  Secret file not found: infra/k8s/base/02-secrets.yaml"
  echo "   Please copy 02-secrets-template.yaml → 02-secrets.yaml"
  echo "   and replace <PLACEHOLDER> values with real secrets."
  echo ""
  echo "   Or use: ./scripts/generate-k8s-secrets.sh"
  exit 1
fi

# 检查 Secret 中是否还有占位符
if grep -q '<PLACEHOLDER>' "$K8S_BASE/02-secrets.yaml"; then
  echo "⚠️  02-secrets.yaml still contains <PLACEHOLDER> values."
  echo "   Please replace all placeholders with real secrets before deploying."
  exit 1
fi

# 1. 部署 Namespace
echo "📦 Step 1/4: Creating namespace..."
kubectl apply $DRY_RUN -f "$K8S_BASE/00-namespace.yaml"

# 2. 部署 ConfigMap
echo "📦 Step 2/4: Applying ConfigMap..."
kubectl apply $DRY_RUN -f "$K8S_BASE/01-shared-configmap.yaml"

# 3. 部署 Secret
echo "📦 Step 3/4: Applying Secret..."
kubectl apply $DRY_RUN -f "$K8S_BASE/02-secrets.yaml"

# 4. 部署所有服务
echo "📦 Step 4/4: Applying Deployments and Services..."
for f in "$K8S_DEV"/*.yaml; do
  echo "   → $(basename "$f")"
  kubectl apply $DRY_RUN -f "$f"
done

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   kubectl get pods -n $NAMESPACE"
echo "   kubectl get svc -n $NAMESPACE"
echo "   kubectl logs -f deployment/auth-service -n $NAMESPACE"
echo ""

if [[ -n "$DRY_RUN" ]]; then
  echo "🧪 This was a dry-run. No actual changes were made."
fi
