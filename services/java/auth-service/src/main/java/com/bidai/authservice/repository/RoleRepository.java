package com.bidai.authservice.repository;

import com.bidai.authservice.entity.Role;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface RoleRepository extends JpaRepository<Role, UUID> {

    Optional<Role> findByRoleCode(String roleCode);

    @Query("""
            SELECT r.roleCode FROM Role r
            JOIN UserRole ur ON r.id = ur.roleId
            WHERE ur.userId = :userId
            AND r.deletedAt IS NULL
            AND (ur.expiresAt IS NULL OR ur.expiresAt > CURRENT_TIMESTAMP)
            """)
    List<String> findRoleCodesByUserId(@Param("userId") UUID userId);
}
