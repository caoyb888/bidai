package com.bidai.projectservice.service;

import com.bidai.projectservice.client.AuthServiceClient;
import com.bidai.projectservice.client.AuthServiceClient.UserBrief;
import com.bidai.projectservice.dto.*;
import com.bidai.projectservice.entity.BidProject;
import com.bidai.projectservice.entity.ProjectMember;
import com.bidai.projectservice.exception.AuthenticationException;
import com.bidai.projectservice.exception.BusinessException;
import com.bidai.projectservice.repository.ProjectMemberRepository;
import com.bidai.projectservice.repository.ProjectRepository;
import com.bidai.projectservice.security.AuthContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.*;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ProjectServiceTest {

    @Mock
    private ProjectRepository projectRepository;

    @Mock
    private ProjectMemberRepository projectMemberRepository;

    @Mock
    private AuthServiceClient authServiceClient;

    @InjectMocks
    private ProjectService projectService;

    private final UUID testUserId = UUID.randomUUID();
    private final UUID testProjectId = UUID.randomUUID();

    @BeforeEach
    void setUp() {
        AuthContext.set(new AuthContext.CurrentUser(testUserId, "testuser", List.of("PROJECT_MGR"), List.of("project:create", "project:read")));
    }

    @AfterEach
    void tearDown() {
        AuthContext.clear();
    }

    private void mockCurrentUserAsMember() {
        when(projectMemberRepository.existsByProjectIdAndUserIdAndLeftAtIsNull(testProjectId, testUserId))
                .thenReturn(true);
    }

    @Test
    void createProject_shouldSucceed_whenNoConflict() {
        ProjectCreateRequest request = new ProjectCreateRequest(
                "测试项目", "测试客户", "IT", "北京",
                LocalDate.of(2026, 6, 15), "5000000", null, null, Instant.now().plusSeconds(86400)
        );

        when(projectRepository.existsByProjectNameAndClientNameAndDeletedAtIsNull("测试项目", "测试客户"))
                .thenReturn(false);
        when(projectRepository.save(any(BidProject.class))).thenAnswer(inv -> {
            BidProject p = inv.getArgument(0);
            p.setId(testProjectId);
            return p;
        });
        when(projectMemberRepository.save(any(ProjectMember.class))).thenAnswer(inv -> inv.getArgument(0));
        when(authServiceClient.getUsersBatch(anyList())).thenReturn(List.of(
                new UserBrief(testUserId, "testuser", "测试用户")
        ));

        ProjectDetail result = projectService.createProject(request);

        assertNotNull(result);
        assertEquals("测试项目", result.name());
        assertEquals("测试客户", result.client());
        verify(projectRepository).save(any(BidProject.class));
        verify(projectMemberRepository).save(any(ProjectMember.class));
    }

    @Test
    void createProject_shouldThrow_whenDuplicateNameAndClient() {
        ProjectCreateRequest request = new ProjectCreateRequest(
                "测试项目", "测试客户", "IT", "北京",
                LocalDate.of(2026, 6, 15), null, null, null, Instant.now()
        );

        when(projectRepository.existsByProjectNameAndClientNameAndDeletedAtIsNull("测试项目", "测试客户"))
                .thenReturn(true);

        BusinessException ex = assertThrows(BusinessException.class, () -> projectService.createProject(request));
        assertEquals(40001, ex.getCode());
        assertTrue(ex.getMessage().contains("同名项目"));
    }

    @Test
    void getProject_shouldReturnDetail_whenExists() {
        BidProject project = createTestProject();
        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        when(projectMemberRepository.findByProjectIdAndLeftAtIsNull(testProjectId)).thenReturn(List.of());
        when(authServiceClient.getUsersBatch(anyList())).thenReturn(List.of());

        ProjectDetail result = projectService.getProject(testProjectId);

        assertNotNull(result);
        assertEquals(testProjectId, result.id());
        assertEquals("测试项目", result.name());
    }

    @Test
    void getProject_shouldThrow_whenNotFound() {
        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.empty());

        BusinessException ex = assertThrows(BusinessException.class, () -> projectService.getProject(testProjectId));
        assertEquals(40002, ex.getCode());
    }

    @Test
    void updateProject_shouldThrow_whenArchived() {
        BidProject project = createTestProject();
        project.setStatus(BidProject.EntityStatus.ARCHIVED);
        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));

        ProjectUpdateRequest request = new ProjectUpdateRequest(
                "新名称", null, null, null, null, null, null, null, null
        );

        BusinessException ex = assertThrows(BusinessException.class,
                () -> projectService.updateProject(testProjectId, request));
        assertEquals(40003, ex.getCode());
        assertTrue(ex.getMessage().contains("归档"));
    }

    @Test
    void deleteProject_shouldSoftDelete() {
        BidProject project = createTestProject();
        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        when(projectRepository.save(any(BidProject.class))).thenAnswer(inv -> inv.getArgument(0));

        projectService.deleteProject(testProjectId);

        assertNotNull(project.getDeletedAt());
        verify(projectRepository).save(project);
    }

    @Test
    void listProjects_shouldReturnPaginatedResults() {
        BidProject project = createTestProject();
        Page<BidProject> page = new PageImpl<>(List.of(project), PageRequest.of(0, 20), 1);
        when(projectRepository.findProjects(any(), any(), any(), any(), any(), anyBoolean(), any(), any()))
                .thenReturn(page);

        PaginatedResponse<ProjectBrief> result = projectService.listProjects(
                1, 20, null, null, null, null, null, false);

        assertEquals(1, result.items().size());
        assertEquals(1, result.total());
    }

    @Test
    void getProjectMembers_shouldReturnMembers_whenProjectExists() {
        BidProject project = createTestProject();
        UUID memberId = UUID.randomUUID();
        ProjectMember member = new ProjectMember();
        member.setProjectId(testProjectId);
        member.setUserId(memberId);
        member.setRole(ProjectMember.ProjectRole.LEADER);
        member.setJoinedAt(Instant.now());

        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        mockCurrentUserAsMember();
        when(projectMemberRepository.findByProjectIdAndLeftAtIsNull(testProjectId)).thenReturn(List.of(member));
        when(authServiceClient.getUsersBatch(List.of(memberId)))
                .thenReturn(List.of(new UserBrief(memberId, "leader1", "负责人1")));

        List<ProjectMemberDTO> result = projectService.getProjectMembers(testProjectId);

        assertEquals(1, result.size());
        assertEquals(memberId, result.get(0).userId());
        assertEquals("leader1", result.get(0).username());
        assertEquals("负责人1", result.get(0).realName());
        assertEquals(ProjectMember.ProjectRole.LEADER, result.get(0).projectRole());
    }

    @Test
    void getProjectMembers_shouldThrow_whenNotProjectMember() {
        BidProject project = createTestProject();
        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        when(projectMemberRepository.existsByProjectIdAndUserIdAndLeftAtIsNull(testProjectId, testUserId))
                .thenReturn(false);

        AuthenticationException ex = assertThrows(AuthenticationException.class,
                () -> projectService.getProjectMembers(testProjectId));
        assertEquals(20005, ex.getCode());
    }

    @Test
    void setProjectMembers_shouldReplaceExisting() {
        BidProject project = createTestProject();
        UUID user1 = UUID.randomUUID();
        UUID user2 = UUID.randomUUID();

        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        mockCurrentUserAsMember();
        when(projectMemberRepository.findByProjectIdAndLeftAtIsNull(testProjectId))
                .thenReturn(List.of());
        when(projectMemberRepository.save(any(ProjectMember.class))).thenAnswer(inv -> inv.getArgument(0));
        when(authServiceClient.getUsersBatch(anyList())).thenReturn(List.of());

        SetProjectMembersRequest request = new SetProjectMembersRequest(List.of(
                new SetProjectMembersRequest.MemberItem(user1, ProjectMember.ProjectRole.LEADER),
                new SetProjectMembersRequest.MemberItem(user2, ProjectMember.ProjectRole.WRITER)
        ));

        projectService.setProjectMembers(testProjectId, request);

        verify(projectMemberRepository, atLeastOnce()).save(any(ProjectMember.class));
    }

    @Test
    void setProjectMembers_shouldThrow_whenDuplicateUserId() {
        BidProject project = createTestProject();
        UUID user1 = UUID.randomUUID();

        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        mockCurrentUserAsMember();

        SetProjectMembersRequest request = new SetProjectMembersRequest(List.of(
                new SetProjectMembersRequest.MemberItem(user1, ProjectMember.ProjectRole.LEADER),
                new SetProjectMembersRequest.MemberItem(user1, ProjectMember.ProjectRole.WRITER)
        ));

        BusinessException ex = assertThrows(BusinessException.class,
                () -> projectService.setProjectMembers(testProjectId, request));
        assertEquals(30003, ex.getCode());
        assertTrue(ex.getMessage().contains("重复"));
    }

    @Test
    void setProjectMembers_shouldThrow_whenNoLeader() {
        BidProject project = createTestProject();
        UUID user1 = UUID.randomUUID();

        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        mockCurrentUserAsMember();

        SetProjectMembersRequest request = new SetProjectMembersRequest(List.of(
                new SetProjectMembersRequest.MemberItem(user1, ProjectMember.ProjectRole.WRITER)
        ));

        BusinessException ex = assertThrows(BusinessException.class,
                () -> projectService.setProjectMembers(testProjectId, request));
        assertEquals(30003, ex.getCode());
        assertTrue(ex.getMessage().contains("LEADER"));
    }

    @Test
    void setProjectMembers_shouldThrow_whenNotProjectMember() {
        BidProject project = createTestProject();
        UUID user1 = UUID.randomUUID();

        when(projectRepository.findByIdAndDeletedAtIsNull(testProjectId)).thenReturn(Optional.of(project));
        when(projectMemberRepository.existsByProjectIdAndUserIdAndLeftAtIsNull(testProjectId, testUserId))
                .thenReturn(false);

        SetProjectMembersRequest request = new SetProjectMembersRequest(List.of(
                new SetProjectMembersRequest.MemberItem(user1, ProjectMember.ProjectRole.LEADER)
        ));

        AuthenticationException ex = assertThrows(AuthenticationException.class,
                () -> projectService.setProjectMembers(testProjectId, request));
        assertEquals(20005, ex.getCode());
    }

    @Test
    void listProjects_shouldThrow_whenInvalidPage() {
        BusinessException ex = assertThrows(BusinessException.class,
                () -> projectService.listProjects(0, 20, null, null, null, null, null, false));
        assertEquals(30006, ex.getCode());
    }

    private BidProject createTestProject() {
        BidProject p = new BidProject();
        p.setId(testProjectId);
        p.setProjectNo("BID-2026-0001");
        p.setProjectName("测试项目");
        p.setClientName("测试客户");
        p.setIndustry("IT");
        p.setRegion("北京");
        p.setTenderDate(LocalDate.of(2026, 6, 15));
        p.setDeadline(Instant.now().plusSeconds(86400));
        p.setStatus(BidProject.EntityStatus.DRAFT);
        p.setCreatedBy("testuser");
        p.setUpdatedBy("testuser");
        return p;
    }
}
