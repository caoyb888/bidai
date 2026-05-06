package com.bidai.authservice.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Token 刷新请求 DTO
 */
public record RefreshRequest(
        @NotBlank(message = "refresh_token 不能为空")
        String refreshToken
) {
}
