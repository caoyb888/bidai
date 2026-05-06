package com.bidai.authservice.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * 用户登录请求 DTO
 */
public record LoginRequest(
        @NotBlank(message = "用户名不能为空")
        String username,

        @NotBlank(message = "密码不能为空")
        String password
) {
}
