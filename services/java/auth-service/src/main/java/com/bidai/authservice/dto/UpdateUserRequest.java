package com.bidai.authservice.dto;

import jakarta.validation.constraints.Email;

/**
 * 更新用户请求 DTO
 */
public record UpdateUserRequest(
        String realName,

        @Email(message = "邮箱格式不正确")
        String email,

        String department,

        Boolean isActive
) {
}
