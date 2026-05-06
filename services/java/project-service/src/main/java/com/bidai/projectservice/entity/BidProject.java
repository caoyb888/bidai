package com.bidai.projectservice.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

@Entity
@Table(name = "bid_projects", schema = "project")
@Getter
@Setter
public class BidProject {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "project_no", nullable = false, unique = true, length = 64)
    private String projectNo;

    @Column(name = "project_name", nullable = false, length = 512)
    private String projectName;

    @Column(name = "client_name", nullable = false, length = 256)
    private String clientName;

    @Column(name = "client_contact", length = 128)
    private String clientContact;

    @Column(name = "industry", nullable = false, length = 64)
    private String industry;

    @Column(name = "region", nullable = false, length = 64)
    private String region;

    @Column(name = "project_category", length = 64)
    private String projectCategory;

    @Column(name = "budget_amount", precision = 18, scale = 2)
    private BigDecimal budgetAmount;

    @Column(name = "bid_amount", precision = 18, scale = 2)
    private BigDecimal bidAmount;

    @Column(name = "release_date")
    private LocalDate releaseDate;

    @Column(name = "tender_date", nullable = false)
    private LocalDate tenderDate;

    @Column(name = "deadline", nullable = false)
    private Instant deadline;

    @Column(name = "evaluation_method", length = 32)
    private String evaluationMethod;

    @Column(name = "tech_score_weight", precision = 5, scale = 2)
    private BigDecimal techScoreWeight;

    @Column(name = "price_score_weight", precision = 5, scale = 2)
    private BigDecimal priceScoreWeight;

    @Column(name = "business_score_weight", precision = 5, scale = 2)
    private BigDecimal businessScoreWeight;

    @Column(name = "win_rate_score", precision = 5, scale = 2)
    private BigDecimal winRateScore;

    @Column(name = "win_rate_grade", length = 1)
    private String winRateGrade;

    @Column(name = "win_rate_calc_at")
    private Instant winRateCalcAt;

    @Column(name = "status", nullable = false, length = 32)
    @Enumerated(EnumType.STRING)
    private EntityStatus status = EntityStatus.DRAFT;

    @Column(name = "is_participate", nullable = false)
    private Boolean isParticipate = true;

    @Column(name = "not_participate_reason", columnDefinition = "TEXT")
    private String notParticipateReason;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "tender_agency", length = 256)
    private String tenderAgency;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @Column(name = "deleted_at")
    private Instant deletedAt;

    @Column(name = "created_by", nullable = false, length = 64)
    private String createdBy;

    @Column(name = "updated_by", nullable = false, length = 64)
    private String updatedBy;

    public enum EntityStatus {
        DRAFT, IN_PROGRESS, REVIEWING, APPROVED, SUBMITTED, COMPLETED, CANCELLED, ARCHIVED
    }
}
