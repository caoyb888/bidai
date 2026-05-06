package com.bidai.authservice.security;

import com.bidai.authservice.annotation.RequirePermission;
import com.bidai.authservice.exception.AuthenticationException;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.AnnotationUtils;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 权限拦截器
 * 1. 验证 JWT Token 有效性
 * 2. 将当前用户信息写入 AuthContext（ThreadLocal）
 * 3. 检查方法上的 @RequirePermission 注解
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PermissionInterceptor implements HandlerInterceptor {

    private final JwtTokenProvider jwtTokenProvider;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (!(handler instanceof HandlerMethod handlerMethod)) {
            return true;
        }

        String token = extractBearerToken(request);
        if (token == null || token.isBlank()) {
            throw new AuthenticationException(20001, "缺少 Authorization Header");
        }

        Claims claims;
        try {
            if (!jwtTokenProvider.validateToken(token)) {
                throw new AuthenticationException(20001, "Token 无效或已过期");
            }
            claims = jwtTokenProvider.parseToken(token);
        } catch (Exception e) {
            log.debug("JWT validation failed: {}", e.getMessage());
            throw new AuthenticationException(20001, "Token 无效或已过期");
        }

        UUID userId = UUID.fromString(claims.getSubject());
        String username = claims.get("username", String.class);
        @SuppressWarnings("unchecked")
        List<String> roles = claims.get("roles", List.class);
        @SuppressWarnings("unchecked")
        List<String> permissions = claims.get("permissions", List.class);

        AuthContext.set(new AuthContext.CurrentUser(userId, username, roles, permissions));

        RequirePermission requirePermission = handlerMethod.getMethodAnnotation(RequirePermission.class);
        if (requirePermission == null) {
            requirePermission = AnnotationUtils.findAnnotation(handlerMethod.getBeanType(), RequirePermission.class);
        }

        if (requirePermission != null) {
            String requiredPerm = requirePermission.value();
            if (permissions == null || !permissions.contains(requiredPerm)) {
                log.warn("Permission denied: user={}, required={}", username, requiredPerm);
                throw new AuthenticationException(20004, "权限不足，无法执行此操作");
            }
        }

        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response,
                                Object handler, Exception ex) {
        AuthContext.clear();
    }

    private String extractBearerToken(HttpServletRequest request) {
        String authHeader = request.getHeader("Authorization");
        if (authHeader != null && authHeader.startsWith("Bearer ")) {
            return authHeader.substring(7);
        }
        return authHeader;
    }
}
