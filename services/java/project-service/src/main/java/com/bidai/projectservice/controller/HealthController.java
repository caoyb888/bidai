package com.bidai.projectservice.controller;

import com.bidai.projectservice.dto.ApiResponse;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 健康检查控制器
 * 验收标准：/actuator/health 返回 UP
 */
@RestController
public class HealthController {

    @GetMapping("/api/v1/health")
    public ApiResponse<Map<String, String>> health() {
        return ApiResponse.success(Map.of("service", "project-service", "status", "UP"));
    }
}
