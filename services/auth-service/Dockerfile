# Pre-built JAR — Maven `package` is run on the host so the
# infrastructure/postgres/migrations resource (referenced by
# pom.xml at ${project.basedir}/../../infrastructure/...) resolves
# correctly. The previous multi-stage build copied only
# services/auth-service into the build context, so Flyway started
# with `Unable to resolve location classpath:db/migration`.
#
# Workflow on the host:
#   cd services/auth-service && mvn package -DskipTests
#   docker compose build auth-service
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY target/auth-service-1.0.0.jar app.jar
EXPOSE 8091

# B3 PR #9 — bounded heap + container-friendly GC.
#   * -Xmx400m gives us a deterministic upper bound that pairs with the
#     mem_limit in docker-compose.yml; without it the JVM defaults to
#     ~1/4 of host RAM which OOM-kills the container on small hosts
#     (the pilot laptop sits at 16 GB → JVM would otherwise reserve 4 GB).
#   * G1GC has the best latency profile for our 400 MB heap and the
#     concurrent collector keeps p99 from spiking under load.
# JAVA_OPTS is overridable via docker-compose env so an operator can
# bump it for higher-memory deployments without rebuilding the image.
ENV JAVA_OPTS="-Xmx400m -XX:+UseG1GC"
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
