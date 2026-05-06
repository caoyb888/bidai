package com.bidai.projectservice.dto;

import com.bidai.projectservice.entity.BidProject;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public record ProjectDetail(
        UUID id,
        String name,
        String client,
        BidProject.EntityStatus status,
        LocalDate tenderDate,
        String budgetAmount,
        String industry,
        String region,
        String description,
        String tenderAgency,
        BigDecimal winRateScore,
        List<ProjectMemberDTO> members,
        String createdBy,
        Instant createdAt,
        Instant updatedAt
) {
}
