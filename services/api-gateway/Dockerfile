# Stage 1: Build
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn dependency:go-offline -q
COPY src ./src
RUN mvn package -DskipTests -q

# Stage 2: Runtime
FROM eclipse-temurin:25-jre-alpine
WORKDIR /app
COPY --from=build /build/target/api-gateway-*.jar app.jar
EXPOSE 8080

# B3 PR #9 — bounded heap + container-friendly GC. Same shape +
# rationale as auth-service/Dockerfile. Gateway runs Spring Cloud
# Gateway (reactive) — a smaller -Xmx is fine because each request
# allocates less than the imperative auth-service path.
ENV JAVA_OPTS="-Xmx400m -XX:+UseG1GC"
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
