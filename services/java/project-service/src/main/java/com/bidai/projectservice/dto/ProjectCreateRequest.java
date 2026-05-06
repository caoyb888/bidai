package com.bidai.projectservice.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.LocalDate;

public record ProjectCreateRequest(
        @NotBlank(message = "项目名称不能为空")
        @Size(max = 512, message = "项目名称不超过512字符")
        String name,

        @NotBlank(message = "客户名称不能为空")
        @Size(max = 256, message = "客户名称不超过256字符")
        String client,

        @Size(max = 64, message = "行业分类不超过64字符")
        String industry,

        @Size(max = 64, message = "地区不超过64字符")
        String region,

        @NotNull(message = "开标日期不能为空")
        LocalDate tenderDate,

        String budgetAmount,

        @Size(max = 256, message = "招标代理机构不超过256字符")
        String tenderAgency,

        String description,

        @NotNull(message = "递交截止时间不能为空")
        java.time.Instant deadline
) {
}
