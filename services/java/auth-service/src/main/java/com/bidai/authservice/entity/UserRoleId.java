package com.bidai.authservice.entity;

import java.io.Serializable;
import java.util.UUID;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.Setter;

/**
 * 用户角色关联复合主键
 */
@Getter
@Setter
@EqualsAndHashCode
public class UserRoleId implements Serializable {

    private UUID userId;
    private UUID roleId;

    public UserRoleId() {
    }

    public UserRoleId(UUID userId, UUID roleId) {
        this.userId = userId;
        this.roleId = roleId;
    }
}
