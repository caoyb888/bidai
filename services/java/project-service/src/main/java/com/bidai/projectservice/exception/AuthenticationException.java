package com.bidai.projectservice.exception;

import lombok.Getter;

@Getter
public class AuthenticationException extends RuntimeException {

    private final int code;

    public AuthenticationException(int code, String message) {
        super(message);
        this.code = code;
    }
}
