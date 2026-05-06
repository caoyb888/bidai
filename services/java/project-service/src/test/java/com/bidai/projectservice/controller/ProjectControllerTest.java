package com.bidai.projectservice.controller;

import com.bidai.projectservice.config.JwtProperties;
import com.bidai.projectservice.dto.*;
import com.bidai.projectservice.entity.BidProject;
import com.bidai.projectservice.entity.ProjectMember;
import com.bidai.projectservice.security.JwtTokenProvider;
import com.bidai.projectservice.service.ProjectService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.FilterType;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(controllers = ProjectController.class, excludeFilters = {
        @ComponentScan.Filter(type = FilterType.ASSIGNABLE_TYPE, classes = com.bidai.projectservice.config.WebConfig.class)
})
class ProjectControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ProjectService projectService;

    @MockBean
    private JwtTokenProvider jwtTokenProvider;

    @MockBean
    private JwtProperties jwtProperties;

    private final UUID testProjectId = UUID.randomUUID();

    @Test
    void getProject_shouldReturn200() throws Exception {
        ProjectDetail detail = new ProjectDetail(
                testProjectId, "测试项目", "测试客户",
                BidProject.EntityStatus.DRAFT,
                LocalDate.of(2026, 6, 15),
                "5000000", "IT", "北京",
                null, null, null,
                List.of(), "testuser",
                Instant.now(), Instant.now()
        );
        when(projectService.getProject(testProjectId)).thenReturn(detail);

        mockMvc.perform(get("/api/v1/projects/{id}", testProjectId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.name").value("测试项目"));
    }

    @Test
    void listProjects_shouldReturn200() throws Exception {
        PaginatedResponse<ProjectBrief> response = new PaginatedResponse<>(
                List.of(new ProjectBrief(testProjectId, "测试项目", "测试客户",
                        BidProject.EntityStatus.DRAFT, LocalDate.of(2026, 6, 15),
                        "5000000", "IT", null)),
                1, 1, 20, 1
        );
        when(projectService.listProjects(anyInt(), anyInt(), any(), any(), any(), any(), any(), anyBoolean()))
                .thenReturn(response);

        mockMvc.perform(get("/api/v1/projects"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.items[0].name").value("测试项目"));
    }

    @Test
    void createProject_shouldReturn201() throws Exception {
        ProjectDetail detail = new ProjectDetail(
                testProjectId, "新项目", "新客户",
                BidProject.EntityStatus.DRAFT,
                LocalDate.of(2026, 7, 1),
                null, "建筑", "上海",
                null, null, null,
                List.of(), "testuser",
                Instant.now(), Instant.now()
        );
        when(projectService.createProject(any())).thenReturn(detail);

        mockMvc.perform(post("/api/v1/projects")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "name": "新项目",
                                    "client": "新客户",
                                    "industry": "建筑",
                                    "region": "上海",
                                    "tenderDate": "2026-07-01",
                                    "deadline": "2026-07-15T10:00:00Z"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.name").value("新项目"));
    }

    @Test
    void updateProject_shouldReturn200() throws Exception {
        ProjectDetail detail = new ProjectDetail(
                testProjectId, "更新后", "客户A",
                BidProject.EntityStatus.IN_PROGRESS,
                LocalDate.of(2026, 8, 1),
                null, "IT", "北京",
                null, null, null,
                List.of(), "testuser",
                Instant.now(), Instant.now()
        );
        when(projectService.updateProject(any(), any())).thenReturn(detail);

        mockMvc.perform(put("/api/v1/projects/{id}", testProjectId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "name": "更新后",
                                    "status": "IN_PROGRESS"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.name").value("更新后"));
    }

    @Test
    void deleteProject_shouldReturn204() throws Exception {
        mockMvc.perform(delete("/api/v1/projects/{id}", testProjectId))
                .andExpect(status().isNoContent());
    }

    @Test
    void getProjectMembers_shouldReturn200() throws Exception {
        when(projectService.getProjectMembers(testProjectId)).thenReturn(List.of(
                new ProjectMemberDTO(UUID.randomUUID(), "user1", "张三",
                        ProjectMember.ProjectRole.LEADER, Instant.now())
        ));

        mockMvc.perform(get("/api/v1/projects/{id}/members", testProjectId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].projectRole").value("LEADER"));
    }

    @Test
    void setProjectMembers_shouldReturn200() throws Exception {
        when(projectService.setProjectMembers(any(), any())).thenReturn(List.of());

        mockMvc.perform(put("/api/v1/projects/{id}/members", testProjectId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                    "members": [
                                        {"userId": "550e8400-e29b-41d4-a716-446655440000", "role": "LEADER"}
                                    ]
                                }
                                """))
                .andExpect(status().isOk());
    }
}
