package com.bidai.authservice.dto;

/**
 * Token 刷新响应 DTO
 */
public record RefreshResponse(
        String accessToken,
        String refreshToken,
        String tokenType,
        Long expiresIn
) {
}
