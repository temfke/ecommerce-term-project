package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.Role;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

@Data
@AllArgsConstructor
@Builder
public class AuthResponse {
    private String accessToken;
    private String refreshToken;
    private Long userId;
    private String email;
    private String firstName;
    private String lastName;
    private Role role;
    private boolean emailVerified;
    private String emailVerificationToken;
}
