package com.bidai.authservice.repository;

import com.bidai.authservice.entity.Permission;
import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface PermissionRepository extends JpaRepository<Permission, UUID> {

    @Query("""
            SELECT DISTINCT p.permCode FROM Permission p
            JOIN RolePermission rp ON p.id = rp.permId
            JOIN UserRole ur ON rp.roleId = ur.roleId
            WHERE ur.userId = :userId
            """)
    List<String> findPermissionCodesByUserId(@Param("userId") UUID userId);
}
