package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.Role;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@Builder
public class UserResponse {
    private Long id;
    private String email;
    private String firstName;
    private String lastName;
    private Role role;
    private String gender;
    private String phone;
    private boolean enabled;
    private LocalDateTime createdAt;
}
