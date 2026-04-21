package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.*;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    public ResponseEntity<AuthResponse> register(@Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.ok(authService.register(request));
    }

    @PostMapping("/login")
    public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(authService.login(request));
    }

    @PostMapping("/refresh")
    public ResponseEntity<AuthResponse> refresh(@Valid @RequestBody RefreshTokenRequest request) {
        return ResponseEntity.ok(authService.refreshToken(request));
    }

    @PostMapping("/verify")
    public ResponseEntity<AuthResponse> verify(
            @Valid @RequestBody VerifyEmailRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(authService.verifyEmail(request.getToken(), currentUser));
    }

    @PostMapping("/resend-verification")
    public ResponseEntity<AuthResponse> resendVerification(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(authService.resendVerification(currentUser));
    }
}
