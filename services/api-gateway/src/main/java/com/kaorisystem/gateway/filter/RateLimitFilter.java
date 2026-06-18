package com.kaorisystem.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.data.domain.Range;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.time.Instant;

@Component
@Slf4j
public class RateLimitFilter implements GlobalFilter, Ordered {

    private final ReactiveStringRedisTemplate redis;
    private final int jwtPerMinute;
    private final int ipPerMinute;

    public RateLimitFilter(
            ReactiveStringRedisTemplate redis,
            @Value("${kaori.rate-limit.jwt-per-minute:60}") int jwtPerMinute,
            @Value("${kaori.rate-limit.ip-per-minute:300}") int ipPerMinute) {
        this.redis = redis;
        this.jwtPerMinute = jwtPerMinute;
        this.ipPerMinute = ipPerMinute;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String userId = exchange.getRequest().getHeaders().getFirst("X-User-ID");
        String ip = getClientIp(exchange);
        long nowMs = Instant.now().toEpochMilli();
        long windowStart = nowMs - 60_000L;

        // Sliding window using Redis sorted set
        String key = userId != null
                ? "ratelimit:jwt:" + userId
                : "ratelimit:ip:" + ip;
        int limit = userId != null ? jwtPerMinute : ipPerMinute;

        return redis.opsForZSet()
                // Add current request timestamp
                .add(key, String.valueOf(nowMs), nowMs)
                .then(redis.opsForZSet().removeRangeByScore(key, Range.closed(0.0, (double) windowStart)))
                .then(redis.opsForZSet().size(key))
                .flatMap(count -> {
                    redis.expire(key, Duration.ofSeconds(70)).subscribe();

                    if (count > limit) {
                        exchange.getResponse().setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
                        exchange.getResponse().getHeaders().set("Retry-After", "60");
                        return exchange.getResponse().setComplete();
                    }
                    return chain.filter(exchange);
                });
    }

    private String getClientIp(ServerWebExchange exchange) {
        String forwarded = exchange.getRequest().getHeaders().getFirst("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        var remoteAddr = exchange.getRequest().getRemoteAddress();
        return remoteAddr != null ? remoteAddr.getAddress().getHostAddress() : "unknown";
    }

    @Override
    public int getOrder() {
        return -100;
    }
}
