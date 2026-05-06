package com.bidai.projectservice.exception;

import com.bidai.projectservice.dto.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * 全局异常处理器
 * 统一捕获并包装所有异常为 ApiResponse 格式
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(
            BusinessException e, HttpServletRequest request) {
        log.warn("BusinessException: [{}] {} - URI: {}", e.getCode(), e.getMessage(), request.getRequestURI());
        return ResponseEntity.ok(ApiResponse.error(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<ApiResponse<Void>> handleAuthenticationException(
            AuthenticationException e, HttpServletRequest request) {
        log.warn("AuthenticationException: [{}] {} - URI: {}", e.getCode(), e.getMessage(), request.getRequestURI());
        HttpStatus status = (e.getCode() >= 20004 && e.getCode() < 20010)
                ? HttpStatus.FORBIDDEN : HttpStatus.UNAUTHORIZED;
        return ResponseEntity.status(status)
                .body(ApiResponse.error(e.getCode(), e.getMessage()));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, BindException.class})
    public ResponseEntity<ApiResponse<Void>> handleValidationException(
            Exception e, HttpServletRequest request) {
        log.warn("ValidationException: {} - URI: {}", e.getMessage(), request.getRequestURI());
        String message = "请求参数校验失败";
        if (e instanceof MethodArgumentNotValidException ex) {
            message = ex.getBindingResult().getFieldErrors().stream()
                    .map(error -> error.getField() + ": " + error.getDefaultMessage())
                    .findFirst()
                    .orElse(message);
        }
        return ResponseEntity.ok(ApiResponse.error(30001, message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<ApiResponse.ErrorDetail>> handleException(
            Exception e, HttpServletRequest request) {
        log.error("Unhandled Exception: {} - URI: {}", e.getMessage(), request.getRequestURI(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error(10001, "内部服务错误", e.getMessage()));
    }
}
