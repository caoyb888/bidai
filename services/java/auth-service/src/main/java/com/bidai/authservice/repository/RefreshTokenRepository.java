package com.bidai.authservice.repository;

import com.bidai.authservice.entity.RefreshToken;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface RefreshTokenRepository extends JpaRepository<RefreshToken, UUID> {

    Optional<RefreshToken> findByTokenHash(String tokenHash);

    @Query("""
            SELECT rt FROM RefreshToken rt
            WHERE rt.userId = :userId
            AND rt.revokedAt IS NULL
            AND rt.expiresAt > CURRENT_TIMESTAMP
            """)
    List<RefreshToken> findAllActiveByUserId(@Param("userId") UUID userId);
}
