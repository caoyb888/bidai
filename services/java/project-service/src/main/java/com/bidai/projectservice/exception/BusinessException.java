package com.bidai.projectservice.exception;

import lombok.Getter;

/**
 * 业务异常基类
 * 错误码规范：
 * 1xxxx - 系统错误
 * 2xxxx - 认证/权限错误
 * 3xxxx - 输入参数错误
 * 4xxxx - 业务逻辑错误
 * 5xxxx - AI 服务错误
 */
@Getter
public class BusinessException extends RuntimeException {

    private final int code;

    public BusinessException(int code, String message) {
        super(message);
        this.code = code;
    }

    public BusinessException(int code, String message, Throwable cause) {
        super(message, cause);
        this.code = code;
    }
}
