package com.bidai.projectservice.dto;

import com.bidai.projectservice.entity.ProjectMember;
import java.time.Instant;
import java.util.UUID;

public record ProjectMemberDTO(
        UUID userId,
        String username,
        String realName,
        ProjectMember.ProjectRole projectRole,
        Instant joinedAt
) {
}
