package com.bidai.authservice.dto;

import java.util.List;

/**
 * 分页列表响应 DTO
 */
public record PaginatedResponse<T>(
        List<T> items,
        long total,
        int page,
        int pageSize,
        int totalPages
) {
}
