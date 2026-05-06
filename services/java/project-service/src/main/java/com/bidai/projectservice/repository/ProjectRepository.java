package com.bidai.projectservice.repository;

import com.bidai.projectservice.entity.BidProject;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface ProjectRepository extends JpaRepository<BidProject, UUID> {

    boolean existsByProjectNameAndClientNameAndDeletedAtIsNull(String projectName, String clientName);

    boolean existsByProjectNameAndClientNameAndDeletedAtIsNullAndIdNot(
            String projectName, String clientName, UUID id);

    Optional<BidProject> findByIdAndDeletedAtIsNull(UUID id);

    @Query("""
            SELECT p FROM BidProject p
            WHERE p.deletedAt IS NULL
              AND (:status IS NULL OR p.status = :status)
              AND (:industry IS NULL OR p.industry = :industry)
              AND (:keyword IS NULL OR p.projectName LIKE %:keyword% OR p.clientName LIKE %:keyword%)
              AND (:tenderDateFrom IS NULL OR p.tenderDate >= :tenderDateFrom)
              AND (:tenderDateTo IS NULL OR p.tenderDate <= :tenderDateTo)
              AND (
                  :myProjectsOnly = false
                  OR EXISTS (
                      SELECT 1 FROM ProjectMember pm
                      WHERE pm.projectId = p.id
                        AND pm.userId = :currentUserId
                        AND pm.leftAt IS NULL
                  )
              )
            ORDER BY p.createdAt DESC
            """)
    Page<BidProject> findProjects(
            @Param("status") BidProject.EntityStatus status,
            @Param("industry") String industry,
            @Param("keyword") String keyword,
            @Param("tenderDateFrom") String tenderDateFrom,
            @Param("tenderDateTo") String tenderDateTo,
            @Param("myProjectsOnly") boolean myProjectsOnly,
            @Param("currentUserId") UUID currentUserId,
            Pageable pageable);
}
