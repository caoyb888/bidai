package com.bidai.authservice.dto;

/**
 * Token 对（内部使用）
 */
public record TokenPair(
        String accessToken,
        String refreshToken,
        long accessExpiresInSeconds,
        long refreshExpiresInSeconds
) {
}
