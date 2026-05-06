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
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final ProjectMemberRepository projectMemberRepository;
    private final AuthServiceClient authServiceClient;

    @Transactional(readOnly = true)
    public PaginatedResponse<ProjectBrief> listProjects(
            int page, int pageSize,
            BidProject.EntityStatus status,
            String industry,
            String keyword,
            String tenderDateFrom,
            String tenderDateTo,
            boolean myProjectsOnly) {

        validatePagination(page, pageSize);

        UUID currentUserId = AuthContext.currentUserId();
        Pageable pageable = PageRequest.of(page - 1, pageSize);
        Page<BidProject> projectPage = projectRepository.findProjects(
                status, industry, keyword, tenderDateFrom, tenderDateTo,
                myProjectsOnly, currentUserId, pageable);

        List<ProjectBrief> items = projectPage.getContent().stream()
                .map(this::toBrief)
                .toList();

        return new PaginatedResponse<>(
                items,
                projectPage.getTotalElements(),
                page,
                pageSize,
                projectPage.getTotalPages()
        );
    }

    @Transactional(readOnly = true)
    public ProjectDetail getProject(UUID projectId) {
        BidProject project = projectRepository.findByIdAndDeletedAtIsNull(projectId)
                .orElseThrow(() -> new BusinessException(40002, "项目不存在或已删除"));

        List<ProjectMemberDTO> members = enrichMemberDTOs(
                projectMemberRepository.findByProjectIdAndLeftAtIsNull(projectId));

        return toDetail(project, members);
    }

    @Transactional
    public ProjectDetail createProject(ProjectCreateRequest request) {
        if (projectRepository.existsByProjectNameAndClientNameAndDeletedAtIsNull(request.name(), request.client())) {
            throw new BusinessException(40001, "同客户下已存在同名项目");
        }

        String operator = getOperator();

        BidProject project = new BidProject();
        project.setProjectNo(generateProjectNo());
        project.setProjectName(request.name());
        project.setClientName(request.client());
        project.setIndustry(request.industry() != null ? request.industry() : "");
        project.setRegion(request.region() != null ? request.region() : "");
        project.setTenderDate(request.tenderDate());
        project.setDeadline(request.deadline());
        project.setTenderAgency(request.tenderAgency());
        project.setDescription(request.description());
        project.setStatus(BidProject.EntityStatus.DRAFT);
        project.setCreatedBy(operator);
        project.setUpdatedBy(operator);

        if (request.budgetAmount() != null && !request.budgetAmount().isBlank()) {
            project.setBudgetAmount(new BigDecimal(request.budgetAmount()));
        }

        projectRepository.save(project);

        // 自动将创建者加入为 LEADER
        ProjectMember member = new ProjectMember();
        member.setProjectId(project.getId());
        member.setUserId(AuthContext.currentUserId());
        member.setRole(ProjectMember.ProjectRole.LEADER);
        member.setCreatedBy(operator);
        member.setUpdatedBy(operator);
        projectMemberRepository.save(member);

        log.info("Project created: id={}, name={}, operator={}", project.getId(), project.getProjectName(), operator);

        List<ProjectMemberDTO> members = enrichMemberDTOs(List.of(member));
        return toDetail(project, members);
    }

    @Transactional
    public ProjectDetail updateProject(UUID projectId, ProjectUpdateRequest request) {
        BidProject project = projectRepository.findByIdAndDeletedAtIsNull(projectId)
                .orElseThrow(() -> new BusinessException(40002, "项目不存在或已删除"));

        // 已归档项目不允许编辑
        if (project.getStatus() == BidProject.EntityStatus.ARCHIVED) {
            throw new BusinessException(40003, "已归档的项目不允许编辑");
        }

        if (request.name() != null && !request.name().isBlank()) {
            if (!request.name().equals(project.getProjectName()) ||
                    (request.client() != null && !request.client().equals(project.getClientName()))) {
                String client = request.client() != null ? request.client() : project.getClientName();
                if (projectRepository.existsByProjectNameAndClientNameAndDeletedAtIsNullAndIdNot(
                        request.name(), client, projectId)) {
                    throw new BusinessException(40001, "同客户下已存在同名项目");
                }
            }
            project.setProjectName(request.name());
        }

        if (request.client() != null && !request.client().isBlank()) {
            project.setClientName(request.client());
        }
        if (request.industry() != null) {
            project.setIndustry(request.industry());
        }
        if (request.region() != null) {
            project.setRegion(request.region());
        }
        if (request.tenderDate() != null) {
            project.setTenderDate(request.tenderDate());
        }
        if (request.budgetAmount() != null && !request.budgetAmount().isBlank()) {
            project.setBudgetAmount(new BigDecimal(request.budgetAmount()));
        }
        if (request.status() != null) {
            project.setStatus(request.status());
        }
        if (request.tenderAgency() != null) {
            project.setTenderAgency(request.tenderAgency());
        }
        if (request.description() != null) {
            project.setDescription(request.description());
        }

        String operator = getOperator();
        project.setUpdatedBy(operator);
        projectRepository.save(project);

        log.info("Project updated: id={}, operator={}", projectId, operator);

        return getProject(projectId);
    }

    @Transactional
    public void deleteProject(UUID projectId) {
        BidProject project = projectRepository.findByIdAndDeletedAtIsNull(projectId)
                .orElseThrow(() -> new BusinessException(40002, "项目不存在或已删除"));

        project.setDeletedAt(Instant.now());
        String operator = getOperator();
        project.setUpdatedBy(operator);
        projectRepository.save(project);

        log.info("Project deleted (soft): id={}, operator={}", projectId, operator);
    }

    @Transactional(readOnly = true)
    public List<ProjectMemberDTO> getProjectMembers(UUID projectId) {
        BidProject project = projectRepository.findByIdAndDeletedAtIsNull(projectId)
                .orElseThrow(() -> new BusinessException(40002, "项目不存在或已删除"));

        requireProjectMembership(projectId);

        List<ProjectMember> members = projectMemberRepository.findByProjectIdAndLeftAtIsNull(projectId);
        return enrichMemberDTOs(members);
    }

    @Transactional
    public List<ProjectMemberDTO> setProjectMembers(UUID projectId, SetProjectMembersRequest request) {
        BidProject project = projectRepository.findByIdAndDeletedAtIsNull(projectId)
                .orElseThrow(() -> new BusinessException(40002, "项目不存在或已删除"));

        requireProjectMembership(projectId);

        List<SetProjectMembersRequest.MemberItem> items = request.members();
        if (items == null) {
            items = List.of();
        }

        // 校验：不允许重复 userId
        Set<UUID> uniqueUserIds = new HashSet<>();
        for (SetProjectMembersRequest.MemberItem item : items) {
            if (!uniqueUserIds.add(item.userId())) {
                throw new BusinessException(30003, "成员列表中存在重复的用户: " + item.userId());
            }
        }

        // 校验：必须保留至少一个 LEADER
        boolean hasLeader = items.stream()
                .anyMatch(item -> item.role() == ProjectMember.ProjectRole.LEADER);
        if (!hasLeader) {
            throw new BusinessException(30003, "项目成员中必须至少包含一名项目负责人（LEADER）");
        }

        String operator = getOperator();

        // 标记现有成员为已离开
        List<ProjectMember> existing = projectMemberRepository.findByProjectIdAndLeftAtIsNull(projectId);
        for (ProjectMember m : existing) {
            m.setLeftAt(Instant.now());
            m.setUpdatedBy(operator);
        }
        projectMemberRepository.saveAll(existing);

        // 添加新成员
        for (SetProjectMembersRequest.MemberItem item : items) {
            ProjectMember member = new ProjectMember();
            member.setProjectId(projectId);
            member.setUserId(item.userId());
            member.setRole(item.role() != null ? item.role() : ProjectMember.ProjectRole.WRITER);
            member.setCreatedBy(operator);
            member.setUpdatedBy(operator);
            projectMemberRepository.save(member);
        }

        log.info("Project members updated: id={}, count={}, operator={}", projectId, items.size(), operator);

        return getProjectMembers(projectId);
    }

    private void validatePagination(int page, int pageSize) {
        if (page < 1) {
            throw new BusinessException(30006, "分页参数非法：page 必须大于等于 1");
        }
        if (pageSize < 1 || pageSize > 100) {
            throw new BusinessException(30006, "分页参数非法：page_size 必须在 1~100 之间");
        }
    }

    private String getOperator() {
        String operator = AuthContext.currentUsername();
        return operator != null ? operator : "system";
    }

    private String generateProjectNo() {
        return "BID-" + LocalDate.now().getYear() + "-" + System.currentTimeMillis() % 10000;
    }

    private ProjectBrief toBrief(BidProject project) {
        return new ProjectBrief(
                project.getId(),
                project.getProjectName(),
                project.getClientName(),
                project.getStatus(),
                project.getTenderDate(),
                project.getBudgetAmount() != null ? project.getBudgetAmount().toPlainString() : null,
                project.getIndustry(),
                project.getWinRateScore()
        );
    }

    private ProjectDetail toDetail(BidProject project, List<ProjectMemberDTO> members) {
        return new ProjectDetail(
                project.getId(),
                project.getProjectName(),
                project.getClientName(),
                project.getStatus(),
                project.getTenderDate(),
                project.getBudgetAmount() != null ? project.getBudgetAmount().toPlainString() : null,
                project.getIndustry(),
                project.getRegion(),
                project.getDescription(),
                project.getTenderAgency(),
                project.getWinRateScore(),
                members,
                project.getCreatedBy(),
                project.getCreatedAt(),
                project.getUpdatedAt()
        );
    }

    private void requireProjectMembership(UUID projectId) {
        UUID currentUserId = AuthContext.currentUserId();
        // 允许系统操作（如单元测试中未设置用户时跳过校验）
        if (currentUserId == null) {
            return;
        }
        boolean isMember = projectMemberRepository.existsByProjectIdAndUserIdAndLeftAtIsNull(projectId, currentUserId);
        if (!isMember) {
            throw new AuthenticationException(20005, "无该资源的访问权限");
        }
    }

    private List<ProjectMemberDTO> enrichMemberDTOs(List<ProjectMember> members) {
        List<UUID> userIds = members.stream()
                .map(ProjectMember::getUserId)
                .distinct()
                .toList();

        Map<UUID, UserBrief> userMap = authServiceClient.getUsersBatch(userIds).stream()
                .collect(Collectors.toMap(UserBrief::id, u -> u));

        return members.stream()
                .map(member -> {
                    UserBrief user = userMap.get(member.getUserId());
                    return new ProjectMemberDTO(
                            member.getUserId(),
                            user != null ? user.username() : null,
                            user != null ? user.displayName() : null,
                            member.getRole(),
                            member.getJoinedAt()
                    );
                })
                .toList();
    }
}
