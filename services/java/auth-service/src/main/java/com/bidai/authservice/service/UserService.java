package com.bidai.authservice.service;

import com.bidai.authservice.dto.CreateUserRequest;
import com.bidai.authservice.dto.CurrentUserResponse;
import com.bidai.authservice.dto.PaginatedResponse;
import com.bidai.authservice.dto.UserBriefResponse;
import com.bidai.authservice.dto.SetUserRolesRequest;
import com.bidai.authservice.dto.UpdateUserRequest;
import com.bidai.authservice.entity.Role;
import com.bidai.authservice.entity.User;
import com.bidai.authservice.entity.UserRole;
import com.bidai.authservice.exception.AuthenticationException;
import com.bidai.authservice.exception.BusinessException;
import com.bidai.authservice.repository.PermissionRepository;
import com.bidai.authservice.repository.RoleRepository;
import com.bidai.authservice.repository.UserRepository;
import com.bidai.authservice.repository.UserRoleRepository;
import com.bidai.authservice.security.AuthContext;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 用户管理服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final UserRoleRepository userRoleRepository;
    private final PermissionRepository permissionRepository;
    private final BCryptPasswordEncoder passwordEncoder;

    @Transactional(readOnly = true)
    public PaginatedResponse<CurrentUserResponse> listUsers(
            int page, int pageSize, String role, String department, Boolean isActive, String keyword) {

        if (page < 1) {
            throw new BusinessException(30006, "分页参数非法：page 必须大于等于 1");
        }
        if (pageSize < 1 || pageSize > 100) {
            throw new BusinessException(30006, "分页参数非法：page_size 必须在 1~100 之间");
        }

        Pageable pageable = PageRequest.of(page - 1, pageSize);
        Page<User> userPage = userRepository.findUsers(role, department, isActive, keyword, pageable);

        List<CurrentUserResponse> items = userPage.getContent().stream()
                .map(this::buildUserDetail)
                .toList();

        return new PaginatedResponse<>(
                items,
                userPage.getTotalElements(),
                page,
                pageSize,
                userPage.getTotalPages()
        );
    }

    @Transactional(readOnly = true)
    public CurrentUserResponse getUser(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(40002, "用户不存在"));
        return buildUserDetail(user);
    }

    @Transactional
    public CurrentUserResponse createUser(CreateUserRequest request) {
        if (userRepository.existsByUsername(request.username())) {
            throw new BusinessException(40001, "用户名已存在");
        }
        if (userRepository.existsByEmail(request.email())) {
            throw new BusinessException(40001, "邮箱已存在");
        }

        User user = new User();
        user.setUsername(request.username());
        user.setDisplayName(request.realName());
        user.setEmail(request.email());
        user.setPasswordHash(passwordEncoder.encode(request.password()));
        user.setDepartment(request.department());
        user.setIsActive(true);
        user.setLoginFailCnt((short) 0);

        String operator = AuthContext.currentUsername();
        if (operator == null) {
            operator = "system";
        }
        user.setCreatedBy(operator);
        user.setUpdatedBy(operator);

        userRepository.save(user);

        assignRoles(user.getId(), request.roles(), operator);

        log.info("User created: id={}, username={}, operator={}", user.getId(), user.getUsername(), operator);
        return buildUserDetail(user);
    }

    @Transactional
    public CurrentUserResponse updateUser(UUID userId, UpdateUserRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(40002, "用户不存在"));

        if (request.realName() != null) {
            user.setDisplayName(request.realName());
        }
        if (request.email() != null) {
            if (!request.email().equals(user.getEmail()) && userRepository.existsByEmail(request.email())) {
                throw new BusinessException(40001, "邮箱已存在");
            }
            user.setEmail(request.email());
        }
        if (request.department() != null) {
            user.setDepartment(request.department());
        }
        if (request.isActive() != null) {
            user.setIsActive(request.isActive());
        }

        String operator = AuthContext.currentUsername();
        if (operator != null) {
            user.setUpdatedBy(operator);
        }

        userRepository.save(user);

        log.info("User updated: id={}, operator={}", userId, operator);
        return buildUserDetail(user);
    }

    @Transactional
    public void deleteUser(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(40002, "用户不存在"));

        user.setDeletedAt(Instant.now());
        String operator = AuthContext.currentUsername();
        if (operator != null) {
            user.setUpdatedBy(operator);
        }
        userRepository.save(user);

        log.info("User deleted (soft): id={}, operator={}", userId, operator);
    }

    @Transactional
    public void setUserRoles(UUID userId, SetUserRolesRequest request) {
        if (!userRepository.existsById(userId)) {
            throw new BusinessException(40002, "用户不存在");
        }

        String operator = AuthContext.currentUsername();
        if (operator == null) {
            operator = "system";
        }

        assignRoles(userId, request.roles(), operator);
        log.info("User roles updated: id={}, roles={}, operator={}", userId, request.roles(), operator);
    }

    private void assignRoles(UUID userId, List<String> roleCodes, String grantedBy) {
        userRoleRepository.deleteByUserId(userId);

        for (String roleCode : roleCodes) {
            Role role = roleRepository.findByRoleCode(roleCode)
                    .orElseThrow(() -> new BusinessException(40002, "角色不存在: " + roleCode));

            UserRole userRole = new UserRole();
            userRole.setUserId(userId);
            userRole.setRoleId(role.getId());
            userRole.setGrantedBy(grantedBy);
            userRoleRepository.save(userRole);
        }
    }

    @Transactional(readOnly = true)
    public List<UserBriefResponse> getUsersBatch(List<UUID> ids) {
        if (ids == null || ids.isEmpty()) {
            return List.of();
        }
        List<User> users = userRepository.findAllById(ids);
        return users.stream()
                .map(user -> new UserBriefResponse(
                        user.getId(),
                        user.getUsername(),
                        user.getDisplayName()
                ))
                .toList();
    }

    private CurrentUserResponse buildUserDetail(User user) {
        List<String> roles = roleRepository.findRoleCodesByUserId(user.getId());
        List<String> permissions = permissionRepository.findPermissionCodesByUserId(user.getId());

        return new CurrentUserResponse(
                user.getId().toString(),
                user.getUsername(),
                user.getDisplayName(),
                user.getDisplayName(),
                user.getDepartment(),
                user.getEmail(),
                user.getIsActive(),
                user.getLastLoginAt(),
                user.getCreatedAt(),
                roles,
                permissions
        );
    }
}
