package com.bidai.projectservice.security;

import java.util.List;
import java.util.UUID;

public class AuthContext {

    private static final ThreadLocal<CurrentUser> HOLDER = new ThreadLocal<>();
    private static final ThreadLocal<String> TOKEN_HOLDER = new ThreadLocal<>();

    public record CurrentUser(
            UUID userId,
            String username,
            List<String> roles,
            List<String> permissions
    ) {
    }

    public static void set(CurrentUser user) {
        HOLDER.set(user);
    }

    public static void setToken(String token) {
        TOKEN_HOLDER.set(token);
    }

    public static CurrentUser get() {
        return HOLDER.get();
    }

    public static void clear() {
        HOLDER.remove();
        TOKEN_HOLDER.remove();
    }

    public static String currentToken() {
        return TOKEN_HOLDER.get();
    }

    public static boolean hasPermission(String permission) {
        CurrentUser user = get();
        return user != null && user.permissions() != null && user.permissions().contains(permission);
    }

    public static UUID currentUserId() {
        CurrentUser user = get();
        return user != null ? user.userId() : null;
    }

    public static String currentUsername() {
        CurrentUser user = get();
        return user != null ? user.username() : null;
    }
}
