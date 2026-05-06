package com.bidai.authservice.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;

/**
 * 设置用户角色请求 DTO
 */
public record SetUserRolesRequest(
        @NotEmpty(message = "角色不能为空")
        List<@NotBlank(message = "角色编码不能为空") String> roles
) {
}
