package com.bidai.projectservice.dto;

import com.bidai.projectservice.entity.ProjectMember;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import java.util.UUID;

public record SetProjectMembersRequest(
        @Valid
        List<MemberItem> members
) {

    public record MemberItem(
            @NotNull(message = "用户ID不能为空")
            UUID userId,

            ProjectMember.ProjectRole role
    ) {
    }
}
