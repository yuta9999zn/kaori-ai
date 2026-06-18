package com.kaorisystem.gateway.filter;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.reactivestreams.Publisher;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.http.server.reactive.ServerHttpResponseDecorator;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Set;
import java.util.concurrent.atomic.AtomicReference;

/**
 * K-13 — Idempotency-Key middleware.
 *
 * Per CLAUDE.md K-13 / TARGET_ARCHITECTURE_1M.md §5.2: every mutating
 * call under /api/v1/** must carry an {@code Idempotency-Key} header.
 * The first request flows through normally; the response status,
 * content-type and body are cached in Redis for 24 hours keyed on
 * {@code sha256(idempotency_key + ":" + tenant_id + ":" + method +
 * ":" + path)}. Subsequent requests with the same key replay the
 * cached response without touching the downstream service.
 *
 * <h3>Scope</h3>
 *
 * <ul>
 *   <li>Applies only to <b>POST / PUT / PATCH / DELETE</b> under {@code /api/v1/**}.</li>
 *   <li>Skips {@code /auth/**} (login flow has no tenant context yet).</li>
 *   <li>Skips GET / HEAD / OPTIONS (idempotent by HTTP semantics).</li>
 * </ul>
 *
 * <h3>Caching policy</h3>
 *
 * <ul>
 *   <li>2xx + 4xx responses are cached. 5xx is treated as transient and
 *       <i>not</i> cached — the next retry should reach the service so a
 *       transient outage doesn't get pinned for 24 h.</li>
 *   <li>Cache value is a JSON envelope: {@code {status, contentType, bodyB64}}.
 *       Base64 keeps binary or non-UTF-8 payloads intact across the Redis
 *       string round-trip.</li>
 * </ul>
 *
 * <h3>Filter chain ordering</h3>
 *
 * Runs at order {@code -50} — after {@link JwtAuthFilter} ({@code -200})
 * has injected {@code X-Enterprise-ID} (so we can scope the cache key
 * by tenant) and after {@link RateLimitFilter} ({@code -100}) (so a
 * legitimate retry storm still counts against budget).
 *
 * <h3>Defence-in-depth body fingerprint</h3>
 *
 * Out of scope for this MVP. The cache key already binds tenant +
 * method + path + key, so a client reusing an Idempotency-Key for a
 * <i>different</i> resource path or HTTP method gets a fresh cache
 * slot. Reusing the same key for the same path with a different body
 * still replays the original response — that's the documented
 * trade-off Stripe / GitHub / etc. all make. Body-hash 409 is tracked
 * as a follow-up.
 */
@Component
@Slf4j
public class IdempotencyFilter implements GlobalFilter, Ordered {

    public static final String HDR_IDEMPOTENCY_KEY  = "Idempotency-Key";
    public static final String HDR_REPLAY_MARKER    = "Idempotent-Replay";
    public static final String HDR_ENTERPRISE_ID    = "X-Enterprise-ID";

    private static final String CACHE_KEY_PREFIX = "idem:";
    private static final Duration CACHE_TTL = Duration.ofHours(24);
    private static final Set<HttpMethod> MUTATING = Set.of(
            HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE);

    private final ReactiveStringRedisTemplate redis;
    private final ObjectMapper json;

    public IdempotencyFilter(ReactiveStringRedisTemplate redis, ObjectMapper json) {
        this.redis = redis;
        this.json  = json;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        if (!shouldApply(exchange)) {
            return chain.filter(exchange);
        }

        String idemKey = exchange.getRequest().getHeaders().getFirst(HDR_IDEMPOTENCY_KEY);
        if (idemKey == null || idemKey.isBlank()) {
            return rejectMissingHeader(exchange);
        }

        String tenantId = headerOrAnon(exchange, HDR_ENTERPRISE_ID);
        String method = exchange.getRequest().getMethod().name();
        String path   = exchange.getRequest().getPath().value();
        String cacheKey = CACHE_KEY_PREFIX + sha256(
                idemKey + ":" + tenantId + ":" + method + ":" + path);

        // Try cache first; on miss, capture the downstream response and persist.
        //
        // Subtle reactive plumbing: replayCached returns Mono<Boolean> —
        //   TRUE  = cache hit successfully replayed → suppress fallthrough
        //   empty = malformed cache entry, treat as miss → fall through
        // processAndCache returns Mono<Void> which we likewise tag so the
        // outer Mono always emits a value (otherwise the post-replay
        // "completed-empty" Mono<Void> would be indistinguishable from a
        // genuine cache miss and switchIfEmpty would fire the chain twice).
        return redis.opsForValue().get(cacheKey)
                .flatMap(cached -> replayCached(exchange, cached))
                .switchIfEmpty(Mono.defer(
                        () -> processAndCache(exchange, chain, cacheKey).thenReturn(Boolean.FALSE)))
                .then();
    }

    @Override
    public int getOrder() {
        return -50;  // after JwtAuthFilter (-200) and RateLimitFilter (-100)
    }

    // =========================================================================
    // Decision: does this request need idempotency handling?
    // =========================================================================

    private boolean shouldApply(ServerWebExchange exchange) {
        HttpMethod method = exchange.getRequest().getMethod();
        if (!MUTATING.contains(method)) {
            return false;
        }
        String path = exchange.getRequest().getPath().value();
        if (!path.startsWith("/api/v1/")) {
            return false;
        }
        // /auth/** is public and pre-tenant; idempotency makes no sense there.
        // (Defensive — the gateway routes /auth/** without /api/v1 prefix so
        // this branch normally never matches, but keeps intent explicit.)
        if (path.startsWith("/api/v1/auth/")) {
            return false;
        }
        return true;
    }

    // =========================================================================
    // Cache miss — forward downstream, capture response, store.
    // =========================================================================

    private Mono<Void> processAndCache(ServerWebExchange exchange,
                                       GatewayFilterChain chain,
                                       String cacheKey) {
        ServerHttpResponse original = exchange.getResponse();
        AtomicReference<byte[]> capturedBody = new AtomicReference<>(new byte[0]);

        ServerHttpResponseDecorator wrapped = new ServerHttpResponseDecorator(original) {
            @Override
            public Mono<Void> writeWith(Publisher<? extends DataBuffer> body) {
                // Buffer the entire response so we can both forward it to the
                // client and store it for the next replay. Acceptable for
                // /api/v1/** where responses are JSON envelopes, typically
                // small (<100 KB). Streaming endpoints (e.g. SSE) should be
                // path-excluded if they ever land under /api/v1/**.
                return DataBufferUtils.join(Flux.from(body))
                        .flatMap(joined -> {
                            byte[] bytes = new byte[joined.readableByteCount()];
                            joined.read(bytes);
                            DataBufferUtils.release(joined);
                            capturedBody.set(bytes);
                            DataBuffer out = bufferFactory().wrap(bytes);
                            return super.writeWith(Mono.just(out));
                        });
            }

            @Override
            public Mono<Void> writeAndFlushWith(
                    Publisher<? extends Publisher<? extends DataBuffer>> body) {
                return writeWith(Flux.from(body).flatMap(p -> p));
            }
        };

        return chain.filter(exchange.mutate().response(wrapped).build())
                .then(Mono.defer(() -> cacheResponse(cacheKey, original, capturedBody.get())));
    }

    private Mono<Void> cacheResponse(String cacheKey,
                                     ServerHttpResponse response,
                                     byte[] body) {
        HttpStatusCode status = response.getStatusCode();
        int code = status != null ? status.value() : 200;

        // Don't cache transient server errors — let the next retry actually
        // try again. 4xx caches because the client error is typically stable
        // (e.g. validation failure on the same payload).
        if (code >= 500) {
            log.debug("idem.skip.5xx cacheKey={} status={}", redact(cacheKey), code);
            return Mono.empty();
        }

        String contentType = response.getHeaders().getFirst(HttpHeaders.CONTENT_TYPE);
        CachedResponse cached = new CachedResponse(
                code, contentType, Base64.getEncoder().encodeToString(body));

        try {
            String serialised = json.writeValueAsString(cached);
            return redis.opsForValue().set(cacheKey, serialised, CACHE_TTL)
                    .then()
                    .onErrorResume(e -> {
                        // Best-effort cache write — never break the response
                        // path. The client got the right answer; the next
                        // retry will just go through to the service again.
                        log.warn("idem.cache.write_failed cacheKey={} error={}",
                                redact(cacheKey), e.getMessage());
                        return Mono.empty();
                    });
        } catch (JsonProcessingException e) {
            log.warn("idem.cache.serialise_failed cacheKey={} error={}",
                    redact(cacheKey), e.getMessage());
            return Mono.empty();
        }
    }

    // =========================================================================
    // Cache hit — replay stored response without touching downstream.
    // =========================================================================

    /**
     * Replays a cached response onto the exchange. Returns:
     * <ul>
     *   <li>{@code Mono.just(true)}  — successful replay, caller should NOT fall through</li>
     *   <li>{@code Mono.empty()}    — cache entry was malformed; caller SHOULD fall through
     *                                 to the cache-miss path so the next successful
     *                                 response overwrites the bad entry</li>
     * </ul>
     */
    private Mono<Boolean> replayCached(ServerWebExchange exchange, String serialised) {
        CachedResponse cached;
        try {
            cached = json.readValue(serialised, CachedResponse.class);
        } catch (JsonProcessingException e) {
            log.warn("idem.cache.parse_failed error={}", e.getMessage());
            return Mono.empty();
        }

        ServerHttpResponse resp = exchange.getResponse();
        resp.setStatusCode(HttpStatus.valueOf(cached.status));
        resp.getHeaders().add(HDR_REPLAY_MARKER, "true");
        if (cached.contentType != null && !cached.contentType.isBlank()) {
            try {
                resp.getHeaders().setContentType(MediaType.parseMediaType(cached.contentType));
            } catch (Exception ignored) {
                // bad content-type in cache — skip the header, keep going
            }
        }

        byte[] body = Base64.getDecoder().decode(cached.bodyB64);
        DataBuffer buf = resp.bufferFactory().wrap(body);
        return resp.writeWith(Mono.just(buf)).thenReturn(Boolean.TRUE);
    }

    // =========================================================================
    // 400 response when Idempotency-Key is missing on a mutation.
    // =========================================================================

    private Mono<Void> rejectMissingHeader(ServerWebExchange exchange) {
        ServerHttpResponse resp = exchange.getResponse();
        resp.setStatusCode(HttpStatus.BAD_REQUEST);
        resp.getHeaders().setContentType(MediaType.parseMediaType("application/problem+json"));

        String body = "{\"type\":\"/docs/errors/missing-idempotency-key\","
                + "\"title\":\"Missing Idempotency-Key header\","
                + "\"status\":400,"
                + "\"detail\":\"POST/PUT/PATCH/DELETE requests under /api/v1/ must "
                + "include an Idempotency-Key header (any unique non-empty string, "
                + "typically a UUID v4).\"}";
        DataBuffer buf = resp.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
        return resp.writeWith(Mono.just(buf));
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static String headerOrAnon(ServerWebExchange exchange, String name) {
        String v = exchange.getRequest().getHeaders().getFirst(name);
        return (v == null || v.isBlank()) ? "anonymous" : v;
    }

    private static String sha256(String input) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    /** Trim a cache key for log output — keeps logs readable + avoids leaking the full key. */
    private static String redact(String cacheKey) {
        if (cacheKey == null || cacheKey.length() < 16) return cacheKey;
        return cacheKey.substring(0, 16) + "…";
    }

    /** JSON envelope for the cached response. */
    public static final class CachedResponse {
        public final int status;
        public final String contentType;
        public final String bodyB64;

        @JsonCreator
        public CachedResponse(
                @JsonProperty("status") int status,
                @JsonProperty("contentType") String contentType,
                @JsonProperty("bodyB64") String bodyB64) {
            this.status = status;
            this.contentType = contentType;
            this.bodyB64 = bodyB64;
        }
    }
}
