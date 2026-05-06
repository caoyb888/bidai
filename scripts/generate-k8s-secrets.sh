#!/usr/bin/env bash
# ============================================================
# K8s Secret 生成辅助脚本
# 从环境变量读取真实密钥，生成 02-secrets.yaml
# ⚠️  生成的文件已加入 .gitignore，严禁提交到 Git！
#
# 使用方式：
#   export DATABASE_PASSWORD="xxx"
#   export MINIO_ACCESS_KEY="xxx"
#   export MINIO_SECRET_KEY="xxx"
#   export JWT_SECRET_KEY="xxx"
#   export ENCRYPTION_KEY="xxx"
#   export LLM_EXTERNAL_API_KEY="xxx"
#   ./scripts/generate-k8s-secrets.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_FILE="$PROJECT_ROOT/infra/k8s/base/02-secrets.yaml"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔐 Generating K8s Secret manifest..."
echo "   Output: $OUTPUT_FILE"
echo ""

# 检查必要的环境变量
MISSING=()
for var in DATABASE_PASSWORD MINIO_ACCESS_KEY MINIO_SECRET_KEY JWT_SECRET_KEY ENCRYPTION_KEY LLM_EXTERNAL_API_KEY; do
  if [[ -z "${!var:-}" ]]; then
    MISSING+=("$var")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo -e "${RED}❌ Missing required environment variables:${NC}"
  for var in "${MISSING[@]}"; do
    echo "   - $var"
  done
  echo ""
  echo "Please set all required variables and retry."
  exit 1
fi

# 生成 Secret YAML
cat > "$OUTPUT_FILE" <<EOF
# ============================================================
# 开发环境 Secret（由 scripts/generate-k8s-secrets.sh 自动生成）
# ⚠️  本文件已加入 .gitignore，严禁提交到 Git！
# 生成时间: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# ============================================================
apiVersion: v1
kind: Secret
metadata:
  name: bidai-shared-secrets
  namespace: bid-ai-dev
  labels:
    app: bidai-shared
type: Opaque
stringData:
  DATABASE_PASSWORD: "${DATABASE_PASSWORD}"
  MINIO_ACCESS_KEY: "${MINIO_ACCESS_KEY}"
  MINIO_SECRET_KEY: "${MINIO_SECRET_KEY}"
  JWT_SECRET_KEY: "${JWT_SECRET_KEY}"
  ENCRYPTION_KEY: "${ENCRYPTION_KEY}"
  LLM_EXTERNAL_API_KEY: "${LLM_EXTERNAL_API_KEY}"
EOF

echo -e "${GREEN}✅ Secret manifest generated successfully.${NC}"
echo ""
echo "📋 Generated file preview:"
head -12 "$OUTPUT_FILE"
echo "..."
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "   - This file is listed in .gitignore and must NOT be committed."
echo "   - Share secret values only through secure channels (e.g., Vault, 1Password)."
echo "   - Rotate secrets immediately if accidentally committed."
