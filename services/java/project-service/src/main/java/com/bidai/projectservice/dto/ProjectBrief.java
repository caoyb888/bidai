package com.bidai.projectservice.dto;

import com.bidai.projectservice.entity.BidProject;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;

public record ProjectBrief(
        UUID id,
        String name,
        String client,
        BidProject.EntityStatus status,
        LocalDate tenderDate,
        String budgetAmount,
        String industry,
        BigDecimal winRateScore
) {
}
