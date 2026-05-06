package com.bidai.projectservice.repository;

import com.bidai.projectservice.entity.ProjectMember;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ProjectMemberRepository extends JpaRepository<ProjectMember, UUID> {

    List<ProjectMember> findByProjectIdAndLeftAtIsNull(UUID projectId);

    Optional<ProjectMember> findByProjectIdAndUserIdAndLeftAtIsNull(UUID projectId, UUID userId);

    void deleteByProjectId(UUID projectId);

    boolean existsByProjectIdAndUserIdAndLeftAtIsNull(UUID projectId, UUID userId);
}
