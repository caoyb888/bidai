package com.bidai.authservice.exception;

/**
 * 认证异常
 * 对应错误码: 2xxxx
 */
public class AuthenticationException extends RuntimeException {

    private final int code;

    public AuthenticationException(int code, String message) {
        super(message);
        this.code = code;
    }

    public int getCode() {
        return code;
    }
}
