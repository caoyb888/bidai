# ============================================================
# Elasticsearch 8.x + IK 中文分词器
# 用于 AI 智能投标系统全文检索
# ============================================================

FROM elasticsearch:8.11.0

# 安装 Elasticsearch Analysis IK 插件（版本必须与 ES 一致）
RUN bin/elasticsearch-plugin install --batch \
    https://get.infini.cloud/elasticsearch/analysis-ik/8.11.0

# 声明端口
EXPOSE 9200 9300
