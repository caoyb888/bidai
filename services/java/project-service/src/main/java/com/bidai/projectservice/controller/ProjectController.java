package com.bidai.projectservice.controller;

import com.bidai.projectservice.annotation.RequirePermission;
import com.bidai.projectservice.dto.*;
import com.bidai.projectservice.entity.BidProject;
import com.bidai.projectservice.service.ProjectService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/projects")
@RequiredArgsConstructor
public class ProjectController {

    private final ProjectService projectService;

    @GetMapping
    public ResponseEntity<ApiResponse<PaginatedResponse<ProjectBrief>>> listProjects(
            @RequestParam(defaultValue = "1") @Min(1) int page,
            @RequestParam(defaultValue = "20", name = "page_size") @Min(1) @Max(100) int pageSize,
            @RequestParam(required = false) BidProject.EntityStatus status,
            @RequestParam(required = false) String industry,
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false, name = "tender_date_from") String tenderDateFrom,
            @RequestParam(required = false, name = "tender_date_to") String tenderDateTo,
            @RequestParam(defaultValue = "false", name = "my_projects_only") boolean myProjectsOnly) {

        PaginatedResponse<ProjectBrief> response = projectService.listProjects(
                page, pageSize, status, industry, keyword, tenderDateFrom, tenderDateTo, myProjectsOnly);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<ProjectDetail>> getProject(
            @PathVariable("id") UUID projectId) {

        ProjectDetail response = projectService.getProject(projectId);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PostMapping
    @RequirePermission("project:create")
    public ResponseEntity<ApiResponse<ProjectDetail>> createProject(
            @RequestBody @Valid ProjectCreateRequest request) {

        ProjectDetail response = projectService.createProject(request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(response));
    }

    @PutMapping("/{id}")
    @RequirePermission("project:create")
    public ResponseEntity<ApiResponse<ProjectDetail>> updateProject(
            @PathVariable("id") UUID projectId,
            @RequestBody @Valid ProjectUpdateRequest request) {

        ProjectDetail response = projectService.updateProject(projectId, request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @DeleteMapping("/{id}")
    @RequirePermission("project:create")
    public ResponseEntity<ApiResponse<Void>> deleteProject(
            @PathVariable("id") UUID projectId) {

        projectService.deleteProject(projectId);
        return ResponseEntity.status(HttpStatus.NO_CONTENT).body(ApiResponse.success());
    }

    @GetMapping("/{id}/members")
    @RequirePermission("project:read")
    public ResponseEntity<ApiResponse<List<ProjectMemberDTO>>> getProjectMembers(
            @PathVariable("id") UUID projectId) {

        List<ProjectMemberDTO> response = projectService.getProjectMembers(projectId);
        return ResponseEntity.ok(ApiResponse.success(response));
    }

    @PutMapping("/{id}/members")
    @RequirePermission("project:create")
    public ResponseEntity<ApiResponse<List<ProjectMemberDTO>>> setProjectMembers(
            @PathVariable("id") UUID projectId,
            @RequestBody @Valid SetProjectMembersRequest request) {

        List<ProjectMemberDTO> response = projectService.setProjectMembers(projectId, request);
        return ResponseEntity.ok(ApiResponse.success(response));
    }
}
