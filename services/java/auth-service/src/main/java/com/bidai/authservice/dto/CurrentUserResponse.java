package com.bidai.authservice.dto;

import java.time.Instant;
import java.util.List;

/**
 * 当前登录用户信息响应 DTO
 * 对应 API Spec: UserDetail
 */
public record CurrentUserResponse(
        String id,
        String username,
        String realName,
        String displayName,
        String department,
        String email,
        Boolean isActive,
        Instant lastLoginAt,
        Instant createdAt,
        List<String> roles,
        List<String> permissions
) {
}
