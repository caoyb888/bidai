package com.bidai.authservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import com.bidai.authservice.config.JwtProperties;
import com.bidai.authservice.config.SecurityProperties;
import com.bidai.authservice.dto.CurrentUserResponse;
import com.bidai.authservice.dto.LoginRequest;
import com.bidai.authservice.dto.LoginResponse;
import com.bidai.authservice.dto.RefreshRequest;
import com.bidai.authservice.dto.RefreshResponse;
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
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private PermissionRepository permissionRepository;

    @Mock
    private RefreshTokenRepository refreshTokenRepository;

    @Mock
    private JwtTokenProvider jwtTokenProvider;

    @Mock
    private BCryptPasswordEncoder passwordEncoder;

    @Mock
    private JwtProperties jwtProperties;

    @Mock
    private SecurityProperties securityProperties;

    @InjectMocks
    private AuthService authService;

    private static final String TEST_USERNAME = "testuser";
    private static final String TEST_PASSWORD = "Test@123";
    private static final String HASHED_PASSWORD = "$2a$10$hashedpassword";
    private static final UUID TEST_USER_ID = UUID.randomUUID();
    private static final String CLIENT_IP = "192.168.1.1";
    private static final String DEVICE_INFO = "Mozilla/5.0";

    private User activeUser;

    @BeforeEach
    void setUp() {
        activeUser = new User();
        activeUser.setId(TEST_USER_ID);
        activeUser.setUsername(TEST_USERNAME);
        activeUser.setDisplayName("测试用户");
        activeUser.setEmail("test@bidai.internal");
        activeUser.setPasswordHash(HASHED_PASSWORD);
        activeUser.setIsActive(true);
        activeUser.setLoginFailCnt((short) 0);
        activeUser.setLockedUntil(null);
    }

    @Test
    void login_success_shouldReturnTokenPairAndUserInfo() {
        // given
        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);
        when(jwtProperties.getAccessExpirationHours()).thenReturn(8L);
        when(jwtProperties.getRefreshExpirationDays()).thenReturn(30L);
        when(jwtTokenProvider.generateAccessToken(any(), anyString(), any(), any())).thenReturn("access_token_123");
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn("refresh_token_456");
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit"));
        when(userRepository.save(any(User.class))).thenReturn(activeUser);
        when(refreshTokenRepository.save(any(RefreshToken.class))).thenAnswer(i -> i.getArgument(0));

        // when
        LoginResponse response = authService.login(request, CLIENT_IP, DEVICE_INFO);

        // then
        assertThat(response.accessToken()).isEqualTo("access_token_123");
        assertThat(response.refreshToken()).isEqualTo("refresh_token_456");
        assertThat(response.tokenType()).isEqualTo("Bearer");
        assertThat(response.user().username()).isEqualTo(TEST_USERNAME);
        assertThat(response.user().roles()).containsExactly("BID_STAFF");
        assertThat(response.user().permissions()).containsExactly("bid:edit");

        // verify fail count reset
        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertThat(savedUser.getLoginFailCnt()).isEqualTo((short) 0);
        assertThat(savedUser.getLockedUntil()).isNull();
        assertThat(savedUser.getLastLoginAt()).isNotNull();
    }

    @Test
    void login_userNotFound_shouldThrowAuthenticationException20008() {
        // given
        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.login(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20008);
                    assertThat(ae.getMessage()).isEqualTo("用户名或密码错误");
                });
    }

    @Test
    void login_accountLocked_shouldThrowAuthenticationException20007() {
        // given
        Instant lockUntil = Instant.now().plus(30, ChronoUnit.MINUTES);
        activeUser.setLockedUntil(lockUntil);
        activeUser.setLoginFailCnt((short) 5);

        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        // when & then
        assertThatThrownBy(() -> authService.login(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20007);
                    assertThat(ae.getMessage()).contains("账号已被锁定");
                });
    }

    @Test
    void login_accountAutoUnlocked_shouldLoginSuccessfully() {
        // given
        Instant pastLockUntil = Instant.now().minus(1, ChronoUnit.MINUTES);
        activeUser.setLockedUntil(pastLockUntil);
        activeUser.setLoginFailCnt((short) 5);

        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);
        when(jwtProperties.getAccessExpirationHours()).thenReturn(8L);
        when(jwtProperties.getRefreshExpirationDays()).thenReturn(30L);
        when(jwtTokenProvider.generateAccessToken(any(), anyString(), any(), any())).thenReturn("access_token");
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn("refresh_token");
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(userRepository.save(any(User.class))).thenReturn(activeUser);
        when(refreshTokenRepository.save(any(RefreshToken.class))).thenAnswer(i -> i.getArgument(0));

        // when
        LoginResponse response = authService.login(request, CLIENT_IP, DEVICE_INFO);

        // then
        assertThat(response).isNotNull();
        verify(userRepository, times(2)).save(any(User.class));
    }

    @Test
    void login_accountAutoUnlocked_shouldResetLockAndLoginSuccessfully() {
        // given
        Instant pastLockUntil = Instant.now().minus(1, ChronoUnit.MINUTES);
        activeUser.setLockedUntil(pastLockUntil);
        activeUser.setLoginFailCnt((short) 5);

        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);
        when(jwtProperties.getAccessExpirationHours()).thenReturn(8L);
        when(jwtProperties.getRefreshExpirationDays()).thenReturn(30L);
        when(jwtTokenProvider.generateAccessToken(any(), anyString(), any(), any())).thenReturn("access_token");
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn("refresh_token");
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(userRepository.save(any(User.class))).thenReturn(activeUser);
        when(refreshTokenRepository.save(any(RefreshToken.class))).thenAnswer(i -> i.getArgument(0));

        // when
        LoginResponse response = authService.login(request, CLIENT_IP, DEVICE_INFO);

        // then
        assertThat(response).isNotNull();
        verify(userRepository, times(2)).save(any(User.class));
    }

    @Test
    void login_wrongPassword_shouldIncrementFailCount() {
        // given
        LoginRequest request = new LoginRequest(TEST_USERNAME, "wrong_password");
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches("wrong_password", HASHED_PASSWORD)).thenReturn(false);
        when(userRepository.save(any(User.class))).thenReturn(activeUser);

        // when & then
        assertThatThrownBy(() -> authService.login(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20008);
                });

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(userCaptor.capture());
        assertThat(userCaptor.getValue().getLoginFailCnt()).isEqualTo((short) 1);
    }

    @Test
    void login_wrongPassword_maxFailures_shouldLockAccount() {
        // given
        activeUser.setLoginFailCnt((short) 4);
        LoginRequest request = new LoginRequest(TEST_USERNAME, "wrong_password");
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches("wrong_password", HASHED_PASSWORD)).thenReturn(false);
        when(securityProperties.getMaxLoginFailures()).thenReturn(5);
        when(securityProperties.getLockDurationMinutes()).thenReturn(30L);
        when(userRepository.save(any(User.class))).thenReturn(activeUser);

        // when & then
        assertThatThrownBy(() -> authService.login(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20008);
                });

        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertThat(savedUser.getLoginFailCnt()).isEqualTo((short) 5);
        assertThat(savedUser.getLockedUntil()).isNotNull();
        assertThat(savedUser.getLockedUntil()).isAfter(Instant.now());
    }

    @Test
    void login_success_shouldResetFailCountAndLastLoginAt() {
        // given
        activeUser.setLoginFailCnt((short) 3);
        LoginRequest request = new LoginRequest(TEST_USERNAME, TEST_PASSWORD);
        when(userRepository.findActiveByUsername(TEST_USERNAME)).thenReturn(Optional.of(activeUser));
        when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);
        when(jwtProperties.getAccessExpirationHours()).thenReturn(8L);
        when(jwtProperties.getRefreshExpirationDays()).thenReturn(30L);
        when(jwtTokenProvider.generateAccessToken(any(), anyString(), any(), any())).thenReturn("access");
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn("refresh");
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of());
        when(userRepository.save(any(User.class))).thenReturn(activeUser);
        when(refreshTokenRepository.save(any(RefreshToken.class))).thenAnswer(i -> i.getArgument(0));

        // when
        authService.login(request, CLIENT_IP, DEVICE_INFO);

        // then
        ArgumentCaptor<User> userCaptor = ArgumentCaptor.forClass(User.class);
        verify(userRepository).save(userCaptor.capture());
        User savedUser = userCaptor.getValue();
        assertThat(savedUser.getLoginFailCnt()).isEqualTo((short) 0);
        assertThat(savedUser.getLastLoginAt()).isNotNull();
    }

    // ==================== refreshToken tests ====================

    @Test
    void refreshToken_success_shouldReturnNewTokenPairAndRevokeOld() {
        // given
        String oldRefreshToken = "old_refresh_jwt";
        String newAccessToken = "new_access_123";
        String newRefreshToken = "new_refresh_456";

        RefreshRequest request = new RefreshRequest(oldRefreshToken);
        RefreshToken storedToken = new RefreshToken();
        storedToken.setId(UUID.randomUUID());
        storedToken.setUserId(TEST_USER_ID);
        storedToken.setTokenHash("old_hash");
        storedToken.setExpiresAt(Instant.now().plus(1, ChronoUnit.DAYS));
        storedToken.setRevokedAt(null);

        io.jsonwebtoken.Claims claims = mock(io.jsonwebtoken.Claims.class);
        when(claims.getSubject()).thenReturn(TEST_USER_ID.toString());
        when(claims.get("type", String.class)).thenReturn("refresh");

        when(jwtTokenProvider.validateToken(oldRefreshToken)).thenReturn(true);
        when(jwtTokenProvider.parseToken(oldRefreshToken)).thenReturn(claims);
        when(refreshTokenRepository.findByTokenHash(anyString())).thenReturn(Optional.of(storedToken));
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(activeUser));
        when(jwtProperties.getAccessExpirationHours()).thenReturn(8L);
        when(jwtProperties.getRefreshExpirationDays()).thenReturn(30L);
        when(jwtTokenProvider.generateAccessToken(any(), anyString(), any(), any())).thenReturn(newAccessToken);
        when(jwtTokenProvider.generateRefreshToken(any())).thenReturn(newRefreshToken);
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit"));
        when(refreshTokenRepository.save(any(RefreshToken.class))).thenAnswer(i -> i.getArgument(0));

        // when
        RefreshResponse response = authService.refreshToken(request, CLIENT_IP, DEVICE_INFO);

        // then
        assertThat(response.accessToken()).isEqualTo(newAccessToken);
        assertThat(response.refreshToken()).isEqualTo(newRefreshToken);
        assertThat(response.tokenType()).isEqualTo("Bearer");

        // verify old token revoked
        assertThat(storedToken.getRevokedAt()).isNotNull();
        verify(refreshTokenRepository).save(storedToken);
    }

    @Test
    void refreshToken_invalidJwt_shouldThrow20003() {
        // given
        RefreshRequest request = new RefreshRequest("invalid_token");
        when(jwtTokenProvider.validateToken("invalid_token")).thenReturn(false);

        // when & then
        assertThatThrownBy(() -> authService.refreshToken(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20003);
                });
    }

    @Test
    void refreshToken_wrongTokenType_shouldThrow20003() {
        // given
        RefreshRequest request = new RefreshRequest("access_token_jwt");
        io.jsonwebtoken.Claims claims = mock(io.jsonwebtoken.Claims.class);
        when(claims.get("type", String.class)).thenReturn("access");

        when(jwtTokenProvider.validateToken("access_token_jwt")).thenReturn(true);
        when(jwtTokenProvider.parseToken("access_token_jwt")).thenReturn(claims);

        // when & then
        assertThatThrownBy(() -> authService.refreshToken(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20003);
                });
    }

    @Test
    void refreshToken_tokenNotFound_shouldThrow20003() {
        // given
        RefreshRequest request = new RefreshRequest("unknown_token");
        io.jsonwebtoken.Claims claims = mock(io.jsonwebtoken.Claims.class);
        when(claims.get("type", String.class)).thenReturn("refresh");

        when(jwtTokenProvider.validateToken("unknown_token")).thenReturn(true);
        when(jwtTokenProvider.parseToken("unknown_token")).thenReturn(claims);
        when(refreshTokenRepository.findByTokenHash(anyString())).thenReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.refreshToken(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20003);
                });
    }

    @Test
    void refreshToken_tokenRevoked_shouldThrow20003() {
        // given
        RefreshRequest request = new RefreshRequest("revoked_token");
        RefreshToken storedToken = new RefreshToken();
        storedToken.setTokenHash("revoked_hash");
        storedToken.setRevokedAt(Instant.now());
        storedToken.setExpiresAt(Instant.now().plus(1, ChronoUnit.DAYS));

        io.jsonwebtoken.Claims claims = mock(io.jsonwebtoken.Claims.class);
        when(claims.get("type", String.class)).thenReturn("refresh");

        when(jwtTokenProvider.validateToken("revoked_token")).thenReturn(true);
        when(jwtTokenProvider.parseToken("revoked_token")).thenReturn(claims);
        when(refreshTokenRepository.findByTokenHash(anyString())).thenReturn(Optional.of(storedToken));

        // when & then
        assertThatThrownBy(() -> authService.refreshToken(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20003);
                });
    }

    @Test
    void refreshToken_userInactive_shouldThrow20003() {
        // given
        RefreshRequest request = new RefreshRequest("valid_token");
        activeUser.setIsActive(false);

        RefreshToken storedToken = new RefreshToken();
        storedToken.setUserId(TEST_USER_ID);
        storedToken.setTokenHash("hash");
        storedToken.setExpiresAt(Instant.now().plus(1, ChronoUnit.DAYS));
        storedToken.setRevokedAt(null);

        io.jsonwebtoken.Claims claims = mock(io.jsonwebtoken.Claims.class);
        when(claims.getSubject()).thenReturn(TEST_USER_ID.toString());
        when(claims.get("type", String.class)).thenReturn("refresh");

        when(jwtTokenProvider.validateToken("valid_token")).thenReturn(true);
        when(jwtTokenProvider.parseToken("valid_token")).thenReturn(claims);
        when(refreshTokenRepository.findByTokenHash(anyString())).thenReturn(Optional.of(storedToken));
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(activeUser));

        // when & then
        assertThatThrownBy(() -> authService.refreshToken(request, CLIENT_IP, DEVICE_INFO))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20003);
                });
    }

    // ==================== logout tests ====================

    @Test
    void logout_success_shouldRevokeAllActiveTokens() {
        // given
        String accessToken = "valid_access_token";
        RefreshToken token1 = new RefreshToken();
        token1.setId(UUID.randomUUID());
        token1.setRevokedAt(null);
        RefreshToken token2 = new RefreshToken();
        token2.setId(UUID.randomUUID());
        token2.setRevokedAt(null);

        when(jwtTokenProvider.validateToken(accessToken)).thenReturn(true);
        when(jwtTokenProvider.getUserIdFromToken(accessToken)).thenReturn(TEST_USER_ID);
        when(refreshTokenRepository.findAllActiveByUserId(TEST_USER_ID)).thenReturn(List.of(token1, token2));
        when(refreshTokenRepository.saveAll(anyList())).thenAnswer(i -> i.getArgument(0));

        // when
        authService.logout(accessToken);

        // then
        assertThat(token1.getRevokedAt()).isNotNull();
        assertThat(token2.getRevokedAt()).isNotNull();
        verify(refreshTokenRepository).saveAll(anyList());
    }

    @Test
    void logout_invalidToken_shouldDoNothing() {
        // given
        String expiredToken = "expired_token";
        when(jwtTokenProvider.validateToken(expiredToken)).thenReturn(false);

        // when
        authService.logout(expiredToken);

        // then
        verify(refreshTokenRepository, never()).findAllActiveByUserId(any());
        verify(refreshTokenRepository, never()).saveAll(anyList());
    }

    // ==================== getCurrentUser tests ====================

    @Test
    void getCurrentUser_success_shouldReturnUserDetail() {
        // given
        String accessToken = "valid_access_token";
        Instant createdAt = Instant.now().minus(7, ChronoUnit.DAYS);
        Instant lastLoginAt = Instant.now().minus(1, ChronoUnit.HOURS);

        activeUser.setDepartment("技术部");
        activeUser.setCreatedAt(createdAt);
        activeUser.setLastLoginAt(lastLoginAt);

        when(jwtTokenProvider.getUserIdFromToken(accessToken)).thenReturn(TEST_USER_ID);
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(activeUser));
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF", "SYS_ADMIN"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit", "user:manage"));

        // when
        CurrentUserResponse response = authService.getCurrentUser(accessToken);

        // then
        assertThat(response.id()).isEqualTo(TEST_USER_ID.toString());
        assertThat(response.username()).isEqualTo(TEST_USERNAME);
        assertThat(response.displayName()).isEqualTo("测试用户");
        assertThat(response.email()).isEqualTo("test@bidai.internal");
        assertThat(response.isActive()).isTrue();
        assertThat(response.department()).isEqualTo("技术部");
        assertThat(response.lastLoginAt()).isEqualTo(lastLoginAt);
        assertThat(response.createdAt()).isEqualTo(createdAt);
        assertThat(response.roles()).containsExactly("BID_STAFF", "SYS_ADMIN");
        assertThat(response.permissions()).containsExactly("bid:edit", "user:manage");
    }

    @Test
    void getCurrentUser_userNotFound_shouldThrow20001() {
        // given
        String accessToken = "valid_access_token";
        when(jwtTokenProvider.getUserIdFromToken(accessToken)).thenReturn(TEST_USER_ID);
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> authService.getCurrentUser(accessToken))
                .isInstanceOf(AuthenticationException.class)
                .satisfies(ex -> {
                    AuthenticationException ae = (AuthenticationException) ex;
                    assertThat(ae.getCode()).isEqualTo(20001);
                    assertThat(ae.getMessage()).isEqualTo("Token 无效或已过期");
                });
    }
}
