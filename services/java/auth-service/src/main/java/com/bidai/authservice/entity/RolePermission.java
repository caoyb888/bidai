package com.bidai.authservice.entity;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.Setter;

/**
 * 角色权限关联实体
 * 对应数据库表: auth.role_permissions
 */
@Entity
@Table(name = "role_permissions", schema = "auth")
@IdClass(RolePermissionId.class)
@Getter
@Setter
public class RolePermission {

    @Id
    @Column(name = "role_id", nullable = false)
    private UUID roleId;

    @Id
    @Column(name = "perm_id", nullable = false)
    private UUID permId;

    @Column(name = "granted_at", nullable = false)
    private Instant grantedAt;

    @Column(name = "granted_by", nullable = false, length = 64)
    private String grantedBy;

    @PrePersist
    protected void onCreate() {
        if (grantedAt == null) {
            grantedAt = Instant.now();
        }
    }
}
