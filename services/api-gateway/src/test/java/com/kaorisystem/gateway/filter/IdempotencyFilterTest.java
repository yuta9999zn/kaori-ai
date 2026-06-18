package com.kaorisystem.gateway.filter;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.data.redis.core.ReactiveValueOperations;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.http.server.reactive.MockServerHttpResponse;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for IdempotencyFilter (K-13).
 *
 * Mocks {@link ReactiveStringRedisTemplate}; spins a {@link MockServerWebExchange}
 * with a stub chain that simulates a downstream service writing a response.
 *
 * <p>The chain stub mimics what {@code chain.filter(exchange)} would do in
 * production: it writes a body to {@code exchange.getResponse()} so the
 * filter's response decorator gets exercised end-to-end.
 */
@DisplayName("IdempotencyFilter — K-13 idempotent retries")
class IdempotencyFilterTest {

    private ReactiveStringRedisTemplate redis;
    private ReactiveValueOperations<String, String> valueOps;
    private ObjectMapper json;
    private IdempotencyFilter filter;

    private AtomicReference<ServerWebExchange> chainSawExchange;
    private GatewayFilterChain forwardingChain;

    @BeforeEach
    @SuppressWarnings("unchecked")
    void setUp() {
        redis = mock(ReactiveStringRedisTemplate.class);
        valueOps = mock(ReactiveValueOperations.class);
        given(redis.opsForValue()).willReturn(valueOps);
        // default: no cache hit anywhere
        given(valueOps.get(anyString())).willReturn(Mono.empty());
        // default: cache writes succeed
        given(valueOps.set(anyString(), anyString(), any(Duration.class)))
                .willReturn(Mono.just(true));

        json = new ObjectMapper();
        filter = new IdempotencyFilter(redis, json);

        chainSawExchange = new AtomicReference<>();
        // Default chain: simulate the downstream writing a 201 + body.
        forwardingChain = exchange -> {
            chainSawExchange.set(exchange);
            return writeDownstreamResponse(exchange, HttpStatus.CREATED,
                    MediaType.APPLICATION_JSON, "{\"data\":{\"id\":\"abc\"}}");
        };
    }

    // ─── Order ──────────────────────────────────────────────────────────

    @Test
    @DisplayName("filter order is -50 (after JwtAuthFilter -200 and RateLimitFilter -100)")
    void orderIsAfterAuthAndRateLimit() {
        assertThat(filter.getOrder()).isEqualTo(-50);
    }

    // ─── Bypass paths ───────────────────────────────────────────────────

    @Test
    @DisplayName("GET requests bypass the filter (no Redis interaction, chain runs)")
    void getRequestBypasses() {
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.get("/api/v1/analytics/runs")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        assertThat(chainSawExchange.get()).isNotNull();
        verify(valueOps, never()).get(anyString());
    }

    @Test
    @DisplayName("paths outside /api/v1/** bypass (e.g. /auth/login)")
    void nonApiPathBypasses() {
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/auth/login"));

        filter.filter(exchange, forwardingChain).block();

        assertThat(chainSawExchange.get()).isNotNull();
        verify(valueOps, never()).get(anyString());
    }

    @Test
    @DisplayName("/api/v1/auth/* explicitly bypasses (login flow has no tenant context)")
    void apiV1AuthPathBypasses() {
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/auth/anything")
                        .header("Idempotency-Key", "should-be-ignored"));

        filter.filter(exchange, forwardingChain).block();

        assertThat(chainSawExchange.get()).isNotNull();
        verify(valueOps, never()).get(anyString());
    }

    // ─── Missing header → 400 ───────────────────────────────────────────

    @Test
    @DisplayName("POST under /api/v1/** without Idempotency-Key returns 400 application/problem+json")
    void missingHeaderRejectsWith400() {
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(exchange.getResponse().getHeaders().getFirst(HttpHeaders.CONTENT_TYPE))
                .isEqualTo("application/problem+json");
        assertThat(chainSawExchange.get()).isNull();
        verify(valueOps, never()).get(anyString());

        String body = readResponseBody(exchange);
        assertThat(body).contains("Missing Idempotency-Key").contains("status");
    }

    @Test
    @DisplayName("blank Idempotency-Key value is treated as missing")
    void blankHeaderRejected() {
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/analyze")
                        .header("Idempotency-Key", "  ")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(chainSawExchange.get()).isNull();
    }

    // ─── First request: forward + cache ────────────────────────────────

    @Test
    @DisplayName("first POST with valid header forwards downstream and caches the response")
    void firstRequestForwardsAndCaches() {
        String key = UUID.randomUUID().toString();
        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", key)
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        // chain ran (downstream invoked)
        assertThat(chainSawExchange.get()).isNotNull();
        // response forwarded to client (status + body present)
        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(readResponseBody(exchange)).contains("\"id\":\"abc\"");
        // cached in Redis with the 24h TTL
        verify(valueOps).set(anyString(), anyString(), eq(Duration.ofHours(24)));
    }

    @Test
    @DisplayName("same Idempotency-Key from two different tenants caches under different keys")
    void tenantIsolationInCacheKey() {
        String sameKey = "shared-key";

        ServerWebExchange exchA = exchangeFor(
                MockServerHttpRequest.post("/api/v1/analyze")
                        .header("Idempotency-Key", sameKey)
                        .header("X-Enterprise-ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"));
        ServerWebExchange exchB = exchangeFor(
                MockServerHttpRequest.post("/api/v1/analyze")
                        .header("Idempotency-Key", sameKey)
                        .header("X-Enterprise-ID", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"));

        AtomicReference<String> capturedKeyA = new AtomicReference<>();
        AtomicReference<String> capturedKeyB = new AtomicReference<>();
        given(valueOps.get(anyString())).willAnswer(inv -> {
            String k = inv.getArgument(0);
            // First time we see each key, record it.
            if (capturedKeyA.get() == null) capturedKeyA.set(k);
            else if (!k.equals(capturedKeyA.get()) && capturedKeyB.get() == null) capturedKeyB.set(k);
            return Mono.empty();
        });

        filter.filter(exchA, forwardingChain).block();
        filter.filter(exchB, forwardingChain).block();

        assertThat(capturedKeyA.get()).isNotNull();
        assertThat(capturedKeyB.get()).isNotNull();
        assertThat(capturedKeyA.get())
                .as("same idempotency-key + path + method but different tenant must hash differently")
                .isNotEqualTo(capturedKeyB.get());
    }

    // ─── Replay (cache hit) ────────────────────────────────────────────

    @Test
    @DisplayName("cache hit replays the cached status + content-type + body without forwarding")
    void cacheHitReplaysWithoutForwarding() throws Exception {
        IdempotencyFilter.CachedResponse cached = new IdempotencyFilter.CachedResponse(
                201,
                "application/json",
                Base64.getEncoder().encodeToString(
                        "{\"data\":{\"id\":\"original\"}}".getBytes(StandardCharsets.UTF_8)));
        given(valueOps.get(anyString())).willReturn(Mono.just(json.writeValueAsString(cached)));

        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", "retry-key")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        // chain NOT invoked
        assertThat(chainSawExchange.get()).isNull();
        // status + body match the cached envelope
        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(readResponseBody(exchange)).contains("\"id\":\"original\"");
        // X-Idempotent-Replay marker set so the client can spot the replay
        assertThat(exchange.getResponse().getHeaders().getFirst("Idempotent-Replay"))
                .isEqualTo("true");
        assertThat(exchange.getResponse().getHeaders().getContentType())
                .isEqualTo(MediaType.APPLICATION_JSON);
    }

    @Test
    @DisplayName("malformed cache entry falls through to the chain (treated as a miss)")
    void malformedCacheEntryFallsThrough() {
        given(valueOps.get(anyString())).willReturn(Mono.just("not-valid-json"));

        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", "key")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        assertThat(chainSawExchange.get()).isNotNull();
        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    // ─── 5xx not cached ─────────────────────────────────────────────────

    @Test
    @DisplayName("5xx responses are NOT cached — the next retry should reach the service")
    void fiveXxResponsesAreNotCached() {
        // chain returns 503 instead of 201
        forwardingChain = exchange -> {
            chainSawExchange.set(exchange);
            return writeDownstreamResponse(exchange, HttpStatus.SERVICE_UNAVAILABLE,
                    MediaType.APPLICATION_JSON, "{\"error\":\"transient\"}");
        };

        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", "k")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        // chain ran, response forwarded
        assertThat(chainSawExchange.get()).isNotNull();
        assertThat(exchange.getResponse().getStatusCode())
                .isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
        // BUT no cache write
        verify(valueOps, never()).set(anyString(), anyString(), any(Duration.class));
    }

    @Test
    @DisplayName("4xx responses ARE cached — client errors are stable, retries should replay them")
    void fourXxResponsesAreCached() {
        forwardingChain = exchange -> {
            chainSawExchange.set(exchange);
            return writeDownstreamResponse(exchange, HttpStatus.BAD_REQUEST,
                    MediaType.APPLICATION_JSON, "{\"error\":\"validation\"}");
        };

        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", "k")
                        .header("X-Enterprise-ID", tenant()));

        filter.filter(exchange, forwardingChain).block();

        verify(valueOps).set(anyString(), anyString(), eq(Duration.ofHours(24)));
    }

    // ─── Best-effort cache resilience ──────────────────────────────────

    @Test
    @DisplayName("Redis write failure does NOT break the response — client still gets 201")
    void redisWriteFailureDoesNotBreakResponse() {
        given(valueOps.set(anyString(), anyString(), any(Duration.class)))
                .willReturn(Mono.error(new RuntimeException("redis down")));

        ServerWebExchange exchange = exchangeFor(
                MockServerHttpRequest.post("/api/v1/upload")
                        .header("Idempotency-Key", "k")
                        .header("X-Enterprise-ID", tenant()));

        // Should NOT raise. Block().
        filter.filter(exchange, forwardingChain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.CREATED);
    }

    // ─── helpers ───────────────────────────────────────────────────────

    private static ServerWebExchange exchangeFor(MockServerHttpRequest.BaseBuilder<?> builder) {
        return MockServerWebExchange.from(builder);
    }

    private static String tenant() {
        return UUID.randomUUID().toString();
    }

    /** Stub downstream behaviour — write a fixed status + body to the response. */
    private static Mono<Void> writeDownstreamResponse(ServerWebExchange exchange,
                                                     HttpStatus status,
                                                     MediaType contentType,
                                                     String body) {
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(contentType);
        DataBuffer buf = exchange.getResponse().bufferFactory()
                .wrap(body.getBytes(StandardCharsets.UTF_8));
        return exchange.getResponse().writeWith(Mono.just(buf));
    }

    /** Read all bytes the filter wrote to the mock response. */
    private static String readResponseBody(ServerWebExchange exchange) {
        MockServerHttpResponse mock = (MockServerHttpResponse) exchange.getResponse();
        DataBuffer buf = DataBufferUtils.join(mock.getBody()).block();
        if (buf == null) return "";
        byte[] bytes = new byte[buf.readableByteCount()];
        buf.read(bytes);
        DataBufferUtils.release(buf);
        return new String(bytes, StandardCharsets.UTF_8);
    }
}
