package com.bidai.authservice.dto;

import java.util.List;

/**
 * 用户登录响应 DTO
 */
public record LoginResponse(
        String accessToken,
        String refreshToken,
        String tokenType,
        Long expiresIn,
        UserInfo user
) {

    public record UserInfo(
            String id,
            String username,
            String displayName,
            String email,
            List<String> roles,
            List<String> permissions
    ) {
    }
}
