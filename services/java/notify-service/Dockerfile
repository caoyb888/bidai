# ============================================================
# Java 服务多阶段构建 Dockerfile
# ============================================================

# ------------------ Stage 1: Build ------------------
FROM gradle:8.5-jdk21-alpine AS builder

WORKDIR /app

COPY build.gradle settings.gradle gradlew ./
COPY gradle ./gradle
COPY src ./src

RUN ./gradlew bootJar --no-daemon

# ------------------ Stage 2: Runtime ------------------
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY --from=builder /app/build/libs/*.jar app.jar

EXPOSE 8084

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:8084/actuator/health | grep -q '"status":"UP"' || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
