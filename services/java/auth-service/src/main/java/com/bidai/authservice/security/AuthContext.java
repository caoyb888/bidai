package com.bidai.authservice.security;

import java.util.List;
import java.util.UUID;

/**
 * 当前登录用户上下文（基于 ThreadLocal）
 */
public class AuthContext {

    private static final ThreadLocal<CurrentUser> HOLDER = new ThreadLocal<>();

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

    public static CurrentUser get() {
        return HOLDER.get();
    }

    public static void clear() {
        HOLDER.remove();
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
