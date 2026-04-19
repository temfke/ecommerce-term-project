package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.Role;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class RegisterRequest {
    @NotBlank
    private String firstName;
    @NotBlank
    private String lastName;
    @NotBlank @Email
    private String email;
    @NotBlank @Size(min = 6, message = "Password must be at least 6 characters")
    private String password;
    private Role role;
    private String gender;
    private String phone;
}
