package com.bidai.projectservice.client;

import com.bidai.projectservice.dto.ApiResponse;
import com.bidai.projectservice.security.AuthContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.List;
import java.util.UUID;

@Slf4j
@Component
@RequiredArgsConstructor
public class AuthServiceClient {

    private final RestTemplate restTemplate;

    @Value("${app.auth-service.url:http://localhost:8081}")
    private String authServiceUrl;

    public List<UserBrief> getUsersBatch(List<UUID> ids) {
        if (ids == null || ids.isEmpty()) {
            return List.of();
        }

        String url = authServiceUrl + "/api/v1/users/batch";
        HttpHeaders headers = new HttpHeaders();
        headers.set("Content-Type", "application/json");
        headers.set("Authorization", "Bearer " + getCurrentToken());

        HttpEntity<List<UUID>> request = new HttpEntity<>(ids, headers);

        try {
            ResponseEntity<ApiResponse<List<UserBrief>>> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    request,
                    new ParameterizedTypeReference<>() {}
            );

            if (response.getBody() != null && response.getBody().getData() != null) {
                return response.getBody().getData();
            }
            return List.of();
        } catch (Exception e) {
            log.warn("Failed to fetch user info from auth-service: {}", e.getMessage());
            return List.of();
        }
    }

    private String getCurrentToken() {
        String token = AuthContext.currentToken();
        return token != null ? token : "";
    }

    public record UserBrief(
            UUID id,
            String username,
            String displayName
    ) {
    }
}
