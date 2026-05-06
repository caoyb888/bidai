package com.bidai.authservice.entity;

import java.io.Serializable;
import java.util.UUID;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

/**
 * 角色权限关联复合主键
 */
@Getter
@Setter
@EqualsAndHashCode
public class RolePermissionId implements Serializable {

    private UUID roleId;
    private UUID permId;

    public RolePermissionId() {
    }

    public RolePermissionId(UUID roleId, UUID permId) {
        this.roleId = roleId;
        this.permId = permId;
    }
}
