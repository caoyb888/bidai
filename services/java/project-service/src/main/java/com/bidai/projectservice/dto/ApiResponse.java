package com.bidai.projectservice.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import java.util.UUID;
import lombok.Builder;
import lombok.Getter;

/**
 * 统一 API 响应包装
 * 对应 API Spec: {code, message, data, request_id}
 */
@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {

    private final int code;
    private final String message;
    private final T data;
    private final String requestId;

    public static <T> ApiResponse<T> success(T data) {
        return ApiResponse.<T>builder()
                .code(200)
                .message("success")
                .data(data)
                .requestId(generateRequestId())
                .build();
    }

    public static <T> ApiResponse<T> success() {
        return success(null);
    }

    public static <T> ApiResponse<T> error(int code, String message) {
        return ApiResponse.<T>builder()
                .code(code)
                .message(message)
                .requestId(generateRequestId())
                .build();
    }

    public static ApiResponse<ErrorDetail> error(int code, String message, String detail) {
        return ApiResponse.<ErrorDetail>builder()
                .code(code)
                .message(message)
                .data(new ErrorDetail(detail))
                .requestId(generateRequestId())
                .build();
    }

    private static String generateRequestId() {
        return "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }

    @Getter
    @Builder
    public static class ErrorDetail {
        private final String detail;

        public ErrorDetail(String detail) {
            this.detail = detail;
        }
    }
}
