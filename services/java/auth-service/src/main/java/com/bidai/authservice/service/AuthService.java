package com.bidai.authservice.service;

import com.bidai.authservice.config.JwtProperties;
import com.bidai.authservice.config.SecurityProperties;
import com.bidai.authservice.dto.CurrentUserResponse;
import com.bidai.authservice.dto.LoginRequest;
import com.bidai.authservice.dto.LoginResponse;
import com.bidai.authservice.dto.RefreshRequest;
import com.bidai.authservice.dto.RefreshResponse;
import com.bidai.authservice.dto.TokenPair;
import com.bidai.authservice.entity.RefreshToken;
import com.bidai.authservice.entity.User;
import com.bidai.authservice.exception.AuthenticationException;
import com.bidai.authservice.repository.PermissionRepository;
import com.bidai.authservice.repository.RefreshTokenRepository;
import com.bidai.authservice.repository.RoleRepository;
import com.bidai.authservice.repository.UserRepository;
import com.bidai.authservice.security.JwtTokenProvider;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final RoleRepository roleRepository;
    private final PermissionRepository permissionRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final JwtTokenProvider jwtTokenProvider;
    private final BCryptPasswordEncoder passwordEncoder;
    private final JwtProperties jwtProperties;
    private final SecurityProperties securityProperties;

    @Transactional
    public LoginResponse login(LoginRequest request, String clientIp, String deviceInfo) {
        User user = userRepository.findActiveByUsername(request.username())
                .orElseThrow(() -> new AuthenticationException(20008, "用户名或密码错误"));

        // 检查账号是否被锁定
        if (user.getLockedUntil() != null && user.getLockedUntil().isAfter(Instant.now())) {
            long remainingMinutes = ChronoUnit.MINUTES.between(Instant.now(), user.getLockedUntil());
            throw new AuthenticationException(20007,
                    "账号已被锁定，请" + remainingMinutes + "分钟后重试或联系管理员");
        }

        // 自动解锁（如果锁定时间已过）
        if (user.getLockedUntil() != null && user.getLockedUntil().isBefore(Instant.now())) {
            user.setLockedUntil(null);
            user.setLoginFailCnt((short) 0);
            userRepository.save(user);
        }

        // 校验密码
        if (!passwordEncoder.matches(request.password(), user.getPasswordHash())) {
            handleLoginFailure(user);
            throw new AuthenticationException(20008, "用户名或密码错误");
        }

        // 登录成功：重置失败次数、更新最后登录时间
        handleLoginSuccess(user);

        // 查询用户角色和权限
        List<String> roles = roleRepository.findRoleCodesByUserId(user.getId());
        List<String> permissions = permissionRepository.findPermissionCodesByUserId(user.getId());

        // 生成 Token
        TokenPair tokenPair = generateTokenPair(user, roles, permissions);

        // 保存 Refresh Token
        saveRefreshToken(user.getId(), tokenPair.refreshToken(), clientIp, deviceInfo);

        log.info("User login successful: username={}, ip={}", user.getUsername(), clientIp);

        return new LoginResponse(
                tokenPair.accessToken(),
                tokenPair.refreshToken(),
                "Bearer",
                tokenPair.accessExpiresInSeconds(),
                new LoginResponse.UserInfo(
                        user.getId().toString(),
                        user.getUsername(),
                        user.getDisplayName(),
                        user.getEmail(),
                        roles,
                        permissions
                )
        );
    }

    private void handleLoginFailure(User user) {
        short newFailCount = (short) (user.getLoginFailCnt() + 1);
        user.setLoginFailCnt(newFailCount);

        if (newFailCount >= securityProperties.getMaxLoginFailures()) {
            Instant lockUntil = Instant.now().plus(securityProperties.getLockDurationMinutes(), ChronoUnit.MINUTES);
            user.setLockedUntil(lockUntil);
            log.warn("Account locked due to too many failed attempts: username={}, lockUntil={}",
                    user.getUsername(), lockUntil);
        }

        userRepository.save(user);
    }

    private void handleLoginSuccess(User user) {
        user.setLoginFailCnt((short) 0);
        user.setLockedUntil(null);
        user.setLastLoginAt(Instant.now());
        userRepository.save(user);
    }

    private TokenPair generateTokenPair(User user, List<String> roles, List<String> permissions) {
        String accessToken = jwtTokenProvider.generateAccessToken(
                user.getId(), user.getUsername(), roles, permissions);
        String refreshToken = jwtTokenProvider.generateRefreshToken(user.getId());

        long accessExpiresInSeconds = jwtProperties.getAccessExpirationHours() * 60 * 60;
        long refreshExpiresInSeconds = jwtProperties.getRefreshExpirationDays() * 24 * 60 * 60;

        return new TokenPair(accessToken, refreshToken, accessExpiresInSeconds, refreshExpiresInSeconds);
    }

    private void saveRefreshToken(UUID userId, String refreshToken, String clientIp, String deviceInfo) {
        String tokenHash = hashRefreshToken(refreshToken);

        RefreshToken token = new RefreshToken();
        token.setUserId(userId);
        token.setTokenHash(tokenHash);
        token.setIpAddress(clientIp);
        token.setDeviceInfo(deviceInfo);
        token.setExpiresAt(Instant.now().plus(30, ChronoUnit.DAYS));

        refreshTokenRepository.save(token);
    }

    @Transactional
    public RefreshResponse refreshToken(RefreshRequest request, String clientIp, String deviceInfo) {
        // 1. 验证 JWT 格式和签名
        if (!jwtTokenProvider.validateToken(request.refreshToken())) {
            throw new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录");
        }

        // 2. 校验 token 类型为 refresh
        var claims = jwtTokenProvider.parseToken(request.refreshToken());
        if (!"refresh".equals(claims.get("type", String.class))) {
            throw new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录");
        }

        // 3. 查找数据库记录
        String tokenHash = hashRefreshToken(request.refreshToken());
        RefreshToken storedToken = refreshTokenRepository.findByTokenHash(tokenHash)
                .orElseThrow(() -> new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录"));

        // 4. 检查是否已吊销或过期
        if (storedToken.getRevokedAt() != null || storedToken.getExpiresAt().isBefore(Instant.now())) {
            throw new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录");
        }

        // 5. 获取用户信息
        UUID userId = UUID.fromString(claims.getSubject());
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录"));

        if (!Boolean.TRUE.equals(user.getIsActive())) {
            throw new AuthenticationException(20003, "refresh_token 无效或已吊销，请重新登录");
        }

        // 6. 吊销旧的 refresh_token
        storedToken.setRevokedAt(Instant.now());
        refreshTokenRepository.save(storedToken);

        // 7. 查询角色权限并生成新 Token
        List<String> roles = roleRepository.findRoleCodesByUserId(userId);
        List<String> permissions = permissionRepository.findPermissionCodesByUserId(userId);
        TokenPair tokenPair = generateTokenPair(user, roles, permissions);

        // 8. 保存新的 refresh_token
        saveRefreshToken(userId, tokenPair.refreshToken(), clientIp, deviceInfo);

        log.info("Token refreshed: userId={}, ip={}", userId, clientIp);

        return new RefreshResponse(
                tokenPair.accessToken(),
                tokenPair.refreshToken(),
                "Bearer",
                tokenPair.accessExpiresInSeconds()
        );
    }

    @Transactional
    public void logout(String accessToken) {
        if (!jwtTokenProvider.validateToken(accessToken)) {
            return; // token 已过期，无需处理
        }

        UUID userId = jwtTokenProvider.getUserIdFromToken(accessToken);

        // 吊销该用户所有未过期的 refresh_token
        List<RefreshToken> activeTokens = refreshTokenRepository.findAllActiveByUserId(userId);
        Instant now = Instant.now();
        for (RefreshToken token : activeTokens) {
            token.setRevokedAt(now);
        }
        refreshTokenRepository.saveAll(activeTokens);

        log.info("User logout: userId={}, revokedTokens={}", userId, activeTokens.size());
    }

    @Transactional(readOnly = true)
    public CurrentUserResponse getCurrentUser(String accessToken) {
        UUID userId = jwtTokenProvider.getUserIdFromToken(accessToken);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new AuthenticationException(20001, "Token 无效或已过期"));

        List<String> roles = roleRepository.findRoleCodesByUserId(userId);
        List<String> permissions = permissionRepository.findPermissionCodesByUserId(userId);

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

    private String hashRefreshToken(String refreshToken) {
        try {
            java.security.MessageDigest digest = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(refreshToken.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(hash);
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 algorithm not available", e);
        }
    }
}
