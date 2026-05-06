# project-service

AI 智能投标系统 — 权限与用户服务

## 技术栈

- Spring Boot 3.2
- Java 21
- Gradle 8.x
- Spring Data JPA
- PostgreSQL

## 开发命令

```bash
# 编译
./gradlew build

# 运行测试
./gradlew test

# 启动服务
./gradlew bootRun

# 生成 JAR
./gradlew bootJar
```

## 接口

- `GET /actuator/health` — 健康检查
- `GET /api/v1/health` — 业务健康检查
