package com.bidai.authservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import com.bidai.authservice.dto.CreateUserRequest;
import com.bidai.authservice.dto.CurrentUserResponse;
import com.bidai.authservice.dto.PaginatedResponse;
import com.bidai.authservice.dto.SetUserRolesRequest;
import com.bidai.authservice.dto.UpdateUserRequest;
import com.bidai.authservice.dto.UserBriefResponse;
import com.bidai.authservice.entity.Role;
import com.bidai.authservice.entity.User;
import com.bidai.authservice.exception.BusinessException;
import com.bidai.authservice.repository.PermissionRepository;
import com.bidai.authservice.repository.RoleRepository;
import com.bidai.authservice.repository.UserRepository;
import com.bidai.authservice.repository.UserRoleRepository;
import com.bidai.authservice.security.AuthContext;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private RoleRepository roleRepository;

    @Mock
    private UserRoleRepository userRoleRepository;

    @Mock
    private PermissionRepository permissionRepository;

    @Mock
    private BCryptPasswordEncoder passwordEncoder;

    @InjectMocks
    private UserService userService;

    private static final UUID TEST_USER_ID = UUID.randomUUID();
    private static final String TEST_USERNAME = "testuser";
    private static final String TEST_EMAIL = "test@bidai.internal";

    @BeforeEach
    void setUp() {
        AuthContext.set(new AuthContext.CurrentUser(UUID.randomUUID(), "operator", List.of("SYS_ADMIN"), List.of("user:manage")));
    }

    @AfterEach
    void tearDown() {
        AuthContext.clear();
    }

    private User createTestUser() {
        User user = new User();
        user.setId(TEST_USER_ID);
        user.setUsername(TEST_USERNAME);
        user.setDisplayName("测试用户");
        user.setEmail(TEST_EMAIL);
        user.setDepartment("技术部");
        user.setIsActive(true);
        user.setPasswordHash("$2a$10$hash");
        user.setLoginFailCnt((short) 0);
        user.setCreatedAt(Instant.now());
        return user;
    }

    // ==================== listUsers tests ====================

    @Test
    void listUsers_success_shouldReturnPaginatedResponse() {
        // given
        User user = createTestUser();
        Page<User> userPage = new PageImpl<>(List.of(user), Pageable.ofSize(20), 1);
        when(userRepository.findUsers(any(), any(), any(), any(), any(Pageable.class))).thenReturn(userPage);
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit"));

        // when
        PaginatedResponse<CurrentUserResponse> result = userService.listUsers(1, 20, null, null, null, null);

        // then
        assertThat(result.items()).hasSize(1);
        assertThat(result.total()).isEqualTo(1);
        assertThat(result.page()).isEqualTo(1);
        assertThat(result.pageSize()).isEqualTo(20);
        assertThat(result.items().get(0).username()).isEqualTo(TEST_USERNAME);
    }

    @Test
    void listUsers_invalidPage_shouldThrow30006() {
        assertThatThrownBy(() -> userService.listUsers(0, 20, null, null, null, null))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(30006));
    }

    @Test
    void listUsers_invalidPageSize_shouldThrow30006() {
        assertThatThrownBy(() -> userService.listUsers(1, 0, null, null, null, null))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(30006));

        assertThatThrownBy(() -> userService.listUsers(1, 101, null, null, null, null))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(30006));
    }

    // ==================== getUser tests ====================

    @Test
    void getUser_success_shouldReturnUserDetail() {
        // given
        User user = createTestUser();
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(user));
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit"));

        // when
        CurrentUserResponse result = userService.getUser(TEST_USER_ID);

        // then
        assertThat(result.id()).isEqualTo(TEST_USER_ID.toString());
        assertThat(result.username()).isEqualTo(TEST_USERNAME);
        assertThat(result.roles()).containsExactly("BID_STAFF");
    }

    @Test
    void getUser_notFound_shouldThrow40002() {
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.getUser(TEST_USER_ID))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40002));
    }

    // ==================== createUser tests ====================

    @Test
    void createUser_success_shouldReturnUserDetail() {
        // given
        CreateUserRequest request = new CreateUserRequest(
                "newuser", "新用户", "new@bidai.internal", "Password@123", "技术部", List.of("BID_STAFF")
        );
        when(userRepository.existsByUsername("newuser")).thenReturn(false);
        when(userRepository.existsByEmail("new@bidai.internal")).thenReturn(false);
        when(passwordEncoder.encode("Password@123")).thenReturn("encoded_password");
        when(userRepository.save(any(User.class))).thenAnswer(i -> {
            User u = i.getArgument(0);
            u.setId(UUID.randomUUID());
            return u;
        });

        Role role = new Role();
        role.setId(UUID.randomUUID());
        role.setRoleCode("BID_STAFF");
        when(roleRepository.findByRoleCode("BID_STAFF")).thenReturn(Optional.of(role));
        when(userRoleRepository.save(any())).thenAnswer(i -> i.getArgument(0));
        when(roleRepository.findRoleCodesByUserId(any())).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(any())).thenReturn(List.of("bid:edit"));

        // when
        CurrentUserResponse result = userService.createUser(request);

        // then
        assertThat(result.username()).isEqualTo("newuser");
        assertThat(result.displayName()).isEqualTo("新用户");
        verify(userRoleRepository).save(any());
    }

    @Test
    void createUser_duplicateUsername_shouldThrow40001() {
        CreateUserRequest request = new CreateUserRequest(
                "newuser", "新用户", "new@bidai.internal", "Password@123", null, List.of("BID_STAFF")
        );
        when(userRepository.existsByUsername("newuser")).thenReturn(true);

        assertThatThrownBy(() -> userService.createUser(request))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40001));
    }

    @Test
    void createUser_duplicateEmail_shouldThrow40001() {
        CreateUserRequest request = new CreateUserRequest(
                "newuser", "新用户", "new@bidai.internal", "Password@123", null, List.of("BID_STAFF")
        );
        when(userRepository.existsByUsername("newuser")).thenReturn(false);
        when(userRepository.existsByEmail("new@bidai.internal")).thenReturn(true);

        assertThatThrownBy(() -> userService.createUser(request))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40001));
    }

    // ==================== updateUser tests ====================

    @Test
    void updateUser_success_shouldReturnUpdatedUser() {
        // given
        User user = createTestUser();
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(user));
        when(userRepository.save(any(User.class))).thenReturn(user);
        when(roleRepository.findRoleCodesByUserId(TEST_USER_ID)).thenReturn(List.of("BID_STAFF"));
        when(permissionRepository.findPermissionCodesByUserId(TEST_USER_ID)).thenReturn(List.of("bid:edit"));

        UpdateUserRequest request = new UpdateUserRequest("新名字", "newemail@bidai.internal", "销售部", false);

        // when
        CurrentUserResponse result = userService.updateUser(TEST_USER_ID, request);

        // then
        assertThat(result.displayName()).isEqualTo("新名字");
        assertThat(result.email()).isEqualTo("newemail@bidai.internal");
        assertThat(result.department()).isEqualTo("销售部");
        assertThat(result.isActive()).isFalse();
    }

    @Test
    void updateUser_notFound_shouldThrow40002() {
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.updateUser(TEST_USER_ID, new UpdateUserRequest(null, null, null, null)))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40002));
    }

    @Test
    void updateUser_duplicateEmail_shouldThrow40001() {
        User user = createTestUser();
        user.setEmail("old@bidai.internal");
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(user));
        when(userRepository.existsByEmail("new@bidai.internal")).thenReturn(true);

        UpdateUserRequest request = new UpdateUserRequest(null, "new@bidai.internal", null, null);

        assertThatThrownBy(() -> userService.updateUser(TEST_USER_ID, request))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40001));
    }

    // ==================== deleteUser tests ====================

    @Test
    void deleteUser_success_shouldSoftDelete() {
        User user = createTestUser();
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.of(user));
        when(userRepository.save(any(User.class))).thenReturn(user);

        userService.deleteUser(TEST_USER_ID);

        assertThat(user.getDeletedAt()).isNotNull();
    }

    @Test
    void deleteUser_notFound_shouldThrow40002() {
        when(userRepository.findById(TEST_USER_ID)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.deleteUser(TEST_USER_ID))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40002));
    }

    // ==================== setUserRoles tests ====================

    @Test
    void setUserRoles_success_shouldReplaceRoles() {
        when(userRepository.existsById(TEST_USER_ID)).thenReturn(true);

        Role role1 = new Role();
        role1.setId(UUID.randomUUID());
        role1.setRoleCode("PROJECT_MGR");
        when(roleRepository.findByRoleCode("PROJECT_MGR")).thenReturn(Optional.of(role1));

        SetUserRolesRequest request = new SetUserRolesRequest(List.of("PROJECT_MGR"));

        userService.setUserRoles(TEST_USER_ID, request);

        verify(userRoleRepository).deleteByUserId(TEST_USER_ID);
        verify(userRoleRepository).save(any());
    }

    @Test
    void setUserRoles_userNotFound_shouldThrow40002() {
        when(userRepository.existsById(TEST_USER_ID)).thenReturn(false);

        assertThatThrownBy(() -> userService.setUserRoles(TEST_USER_ID, new SetUserRolesRequest(List.of("BID_STAFF"))))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40002));
    }

    @Test
    void setUserRoles_roleNotFound_shouldThrow40002() {
        when(userRepository.existsById(TEST_USER_ID)).thenReturn(true);
        when(roleRepository.findByRoleCode("UNKNOWN")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> userService.setUserRoles(TEST_USER_ID, new SetUserRolesRequest(List.of("UNKNOWN"))))
                .isInstanceOf(BusinessException.class)
                .satisfies(ex -> assertThat(((BusinessException) ex).getCode()).isEqualTo(40002));
    }

    // ==================== getUsersBatch tests ====================

    @Test
    void getUsersBatch_success_shouldReturnUserBriefList() {
        User user = createTestUser();
        when(userRepository.findAllById(List.of(TEST_USER_ID))).thenReturn(List.of(user));

        List<UserBriefResponse> result = userService.getUsersBatch(List.of(TEST_USER_ID));

        assertThat(result).hasSize(1);
        assertThat(result.get(0).id()).isEqualTo(TEST_USER_ID);
        assertThat(result.get(0).username()).isEqualTo(TEST_USERNAME);
        assertThat(result.get(0).displayName()).isEqualTo("测试用户");
    }

    @Test
    void getUsersBatch_emptyIds_shouldReturnEmptyList() {
        List<UserBriefResponse> result = userService.getUsersBatch(List.of());
        assertThat(result).isEmpty();
    }

    @Test
    void getUsersBatch_nullIds_shouldReturnEmptyList() {
        List<UserBriefResponse> result = userService.getUsersBatch(null);
        assertThat(result).isEmpty();
    }
}
