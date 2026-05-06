package com.bidai.authservice.dto;

import java.util.UUID;

/**
 * 用户简要信息响应 DTO
 * 用于内部服务间批量查询用户信息
 */
public record UserBriefResponse(
        UUID id,
        String username,
        String displayName
) {
}
