package com.bidai.projectservice.dto;

import com.bidai.projectservice.entity.BidProject;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record ProjectUpdateRequest(
        @Size(max = 512, message = "项目名称不超过512字符")
        String name,

        @Size(max = 256, message = "客户名称不超过256字符")
        String client,

        @Size(max = 64, message = "行业分类不超过64字符")
        String industry,

        @Size(max = 64, message = "地区不超过64字符")
        String region,

        LocalDate tenderDate,

        String budgetAmount,

        BidProject.EntityStatus status,

        @Size(max = 256, message = "招标代理机构不超过256字符")
        String tenderAgency,

        String description
) {
}
