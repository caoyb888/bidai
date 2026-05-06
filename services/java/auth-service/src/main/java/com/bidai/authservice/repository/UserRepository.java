package com.bidai.authservice.repository;

import com.bidai.authservice.entity.User;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    Optional<User> findByUsername(String username);

    @Query("SELECT u FROM User u WHERE u.username = :username AND u.deletedAt IS NULL")
    Optional<User> findActiveByUsername(@Param("username") String username);

    boolean existsByUsername(String username);

    boolean existsByEmail(String email);

    @Query(value = """
            SELECT DISTINCT u FROM User u
            LEFT JOIN com.bidai.authservice.entity.UserRole ur ON u.id = ur.userId
            LEFT JOIN com.bidai.authservice.entity.Role r ON ur.roleId = r.id
            WHERE (:role IS NULL OR r.roleCode = :role)
            AND (:department IS NULL OR u.department = :department)
            AND (:isActive IS NULL OR u.isActive = :isActive)
            AND (:keyword IS NULL OR u.username LIKE %:keyword% OR u.displayName LIKE %:keyword%)
            """,
            countQuery = """
            SELECT COUNT(DISTINCT u) FROM User u
            LEFT JOIN com.bidai.authservice.entity.UserRole ur ON u.id = ur.userId
            LEFT JOIN com.bidai.authservice.entity.Role r ON ur.roleId = r.id
            WHERE (:role IS NULL OR r.roleCode = :role)
            AND (:department IS NULL OR u.department = :department)
            AND (:isActive IS NULL OR u.isActive = :isActive)
            AND (:keyword IS NULL OR u.username LIKE %:keyword% OR u.displayName LIKE %:keyword%)
            """)
    Page<User> findUsers(
            @Param("role") String role,
            @Param("department") String department,
            @Param("isActive") Boolean isActive,
            @Param("keyword") String keyword,
            Pageable pageable);
}
