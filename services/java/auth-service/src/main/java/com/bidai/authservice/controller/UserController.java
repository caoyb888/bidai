package com.bidai.authservice.controller;

import com.bidai.authservice.annotation.RequirePermission;
import com.bidai.authservice.dto.ApiResponse;
import com.bidai.authservice.dto.CreateUserRequest;
import com.bidai.authservice.dto.CurrentUserResponse;
import com.bidai.authservice.dto.PaginatedResponse;
import com.bidai.authservice.dto.SetUserRolesRequest;
import com.bidai.authservice.dto.UpdateUserRequest;
import com.bidai.authservice.dto.UserBriefResponse;
import com.bidai.authservice.service.UserService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 用户管理控制器
 */
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;

    @GetMapping
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<PaginatedResponse<CurrentUserResponse>>> listUsers(
            @RequestParam(defaultValue = "1") @Min(1) int page,
            @RequestParam(defaultValue = "20", name = "page_size") @Min(1) @Max(100) int pageSize,
            @RequestParam(required = false) String role,
            @RequestParam(required = false) String department,
            @RequestParam(required = false, name = "is_active") Boolean isActive,
            @RequestParam(required = false) String keyword) {

        PaginatedResponse<CurrentUserResponse> response = userService.listUsers(
                page, pageSize, role, department, isActive, keyword);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/{id}")
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<CurrentUserResponse>> getUser(
            @PathVariable("id") UUID userId) {

        CurrentUserResponse response = userService.getUser(userId);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PostMapping
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<CurrentUserResponse>> createUser(
            @RequestBody @Valid CreateUserRequest request) {

        CurrentUserResponse response = userService.createUser(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    @PutMapping("/{id}")
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<CurrentUserResponse>> updateUser(
            @PathVariable("id") UUID userId,
            @RequestBody @Valid UpdateUserRequest request) {

        CurrentUserResponse response = userService.updateUser(userId, request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @DeleteMapping("/{id}")
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<Void>> deleteUser(
            @PathVariable("id") UUID userId) {

        userService.deleteUser(userId);
        return ResponseEntity.status(HttpStatus.NO_CONTENT).body(ApiResponse.success());
    }

    @PutMapping("/{id}/roles")
    @RequirePermission("user:manage")
    public ResponseEntity<ApiResponse<Void>> setUserRoles(
            @PathVariable("id") UUID userId,
            @RequestBody @Valid SetUserRolesRequest request) {

        userService.setUserRoles(userId, request);
        return ResponseEntity.ok(ApiResponse.success());
    }

    /**
     * 批量查询用户简要信息
     * 供内部服务（如 project-service）调用，只需有效 JWT（已登录）即可访问
     */
    @PostMapping("/batch")
    public ResponseEntity<ApiResponse<List<UserBriefResponse>>> getUsersBatch(
            @RequestBody List<UUID> ids) {

        List<UserBriefResponse> response = userService.getUsersBatch(ids);
        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
