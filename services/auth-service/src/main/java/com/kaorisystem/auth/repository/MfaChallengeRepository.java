package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.MfaChallenge;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

public interface MfaChallengeRepository extends JpaRepository<MfaChallenge, UUID> {

    /** Verify path looks up by SHA-256 hex of the presented JWT. */
    Optional<MfaChallenge> findByChallengeTokenHash(String challengeTokenHash);

    /**
     * Optimistic one-time-use guard — flips {@code used_at} only if the row is
     * still unused. Returning 0 means "already used or already attempts-locked",
     * which the verify path treats as a replay/closed challenge. Pairs with the
     * row-level {@code attempts} bump done in service code.
     */
    @Modifying
    @Query("UPDATE MfaChallenge c SET c.usedAt = :now "
         + "WHERE c.challengeId = :challengeId AND c.usedAt IS NULL")
    int markUsedIfPending(
            @Param("challengeId") UUID challengeId,
            @Param("now")         Instant now);

    /**
     * Bumps the attempts counter, returning the new value via a follow-up read
     * by the caller. Caller is responsible for setting {@code used_at} once the
     * counter trips (one-time-use guard).
     */
    @Modifying
    @Query("UPDATE MfaChallenge c SET c.attempts = c.attempts + 1 "
         + "WHERE c.challengeId = :challengeId AND c.usedAt IS NULL")
    int incrementAttempts(@Param("challengeId") UUID challengeId);
}
