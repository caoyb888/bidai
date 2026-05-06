package com.bidai.authservice.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import java.util.List;

/**
 * 创建用户请求 DTO
 */
public record CreateUserRequest(
        @NotBlank(message = "用户名不能为空")
        @Size(min = 3, max = 32, message = "用户名长度必须在 3~32 之间")
        String username,

        @NotBlank(message = "姓名不能为空")
        String realName,

        @NotBlank(message = "邮箱不能为空")
        @Email(message = "邮箱格式不正确")
        String email,

        @NotBlank(message = "密码不能为空")
        @Size(min = 8, message = "密码长度至少 8 位")
        String password,

        String department,

        @NotEmpty(message = "角色不能为空")
        List<@NotBlank(message = "角色编码不能为空") String> roles
) {
}
