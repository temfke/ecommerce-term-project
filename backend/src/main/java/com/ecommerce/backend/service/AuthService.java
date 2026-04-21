package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.*;
import com.ecommerce.backend.entity.CustomerProfile;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.Role;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.repository.CustomerProfileRepository;
import com.ecommerce.backend.repository.UserRepository;
import com.ecommerce.backend.security.JwtTokenProvider;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.HexFormat;

@Service
@RequiredArgsConstructor
public class AuthService {

    private static final Logger log = LoggerFactory.getLogger(AuthService.class);
    private static final SecureRandom RNG = new SecureRandom();
    private static final long VERIFICATION_TTL_HOURS = 24;

    private final UserRepository userRepository;
    private final CustomerProfileRepository customerProfileRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final AuthenticationManager authenticationManager;

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new BadRequestException("Email already in use");
        }

        Role role = request.getRole() != null ? request.getRole() : Role.INDIVIDUAL;
        String token = generateVerificationToken();

        User user = User.builder()
                .firstName(request.getFirstName())
                .lastName(request.getLastName())
                .email(request.getEmail())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .role(role)
                .gender(request.getGender())
                .phone(request.getPhone())
                .emailVerified(false)
                .emailVerificationToken(token)
                .emailVerificationExpiresAt(LocalDateTime.now().plusHours(VERIFICATION_TTL_HOURS))
                .build();

        user = userRepository.save(user);

        if (role == Role.INDIVIDUAL) {
            CustomerProfile profile = CustomerProfile.builder()
                    .user(user)
                    .totalSpend(BigDecimal.ZERO)
                    .itemsPurchased(0)
                    .priorPurchases(0)
                    .membershipType("Bronze")
                    .build();
            customerProfileRepository.save(profile);
        }

        log.info("EMAIL VERIFICATION token for {}: {}", user.getEmail(), token);

        String accessToken = jwtTokenProvider.generateAccessToken(user);
        String refreshToken = jwtTokenProvider.generateRefreshToken(user);

        return AuthResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .userId(user.getId())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .role(user.getRole())
                .emailVerified(user.isEmailVerified())
                .emailVerificationToken(token)
                .build();
    }

    public AuthResponse login(LoginRequest request) {
        authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(request.getEmail(), request.getPassword())
        );

        User user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new BadRequestException("Invalid credentials"));

        String accessToken = jwtTokenProvider.generateAccessToken(user);
        String refreshToken = jwtTokenProvider.generateRefreshToken(user);

        return AuthResponse.builder()
                .accessToken(accessToken)
                .refreshToken(refreshToken)
                .userId(user.getId())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .role(user.getRole())
                .emailVerified(user.isEmailVerified())
                .build();
    }

    public AuthResponse refreshToken(RefreshTokenRequest request) {
        String email = jwtTokenProvider.extractUsername(request.getRefreshToken());
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new BadRequestException("Invalid refresh token"));

        if (!jwtTokenProvider.isTokenValid(request.getRefreshToken(), user)) {
            throw new BadRequestException("Invalid or expired refresh token");
        }

        String accessToken = jwtTokenProvider.generateAccessToken(user);

        return AuthResponse.builder()
                .accessToken(accessToken)
                .refreshToken(request.getRefreshToken())
                .userId(user.getId())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .role(user.getRole())
                .emailVerified(user.isEmailVerified())
                .build();
    }

    @Transactional
    public AuthResponse verifyEmail(String token, User currentUser) {
        if (token == null || token.isBlank()) {
            throw new BadRequestException("Verification token is required");
        }
        User user = userRepository.findById(currentUser.getId())
                .orElseThrow(() -> new BadRequestException("Authenticated user no longer exists"));

        if (user.isEmailVerified()) {
            return buildAuthResponse(user, null);
        }
        if (user.getEmailVerificationToken() == null
                || !user.getEmailVerificationToken().equals(token.trim())) {
            throw new BadRequestException("Invalid verification token");
        }
        if (user.getEmailVerificationExpiresAt() != null
                && user.getEmailVerificationExpiresAt().isBefore(LocalDateTime.now())) {
            throw new BadRequestException("Verification token has expired — request a new one");
        }

        user.setEmailVerified(true);
        user.setEmailVerificationToken(null);
        user.setEmailVerificationExpiresAt(null);
        userRepository.save(user);
        log.info("Email verified for user {}", user.getEmail());

        return buildAuthResponse(user, null);
    }

    @Transactional
    public AuthResponse resendVerification(User currentUser) {
        User user = userRepository.findById(currentUser.getId())
                .orElseThrow(() -> new BadRequestException("Authenticated user no longer exists"));
        if (user.isEmailVerified()) {
            throw new BadRequestException("Email is already verified");
        }
        String token = generateVerificationToken();
        user.setEmailVerificationToken(token);
        user.setEmailVerificationExpiresAt(LocalDateTime.now().plusHours(VERIFICATION_TTL_HOURS));
        userRepository.save(user);
        log.info("EMAIL VERIFICATION resend for {}: {}", user.getEmail(), token);
        return buildAuthResponse(user, token);
    }

    private AuthResponse buildAuthResponse(User user, String verificationToken) {
        return AuthResponse.builder()
                .accessToken(jwtTokenProvider.generateAccessToken(user))
                .refreshToken(jwtTokenProvider.generateRefreshToken(user))
                .userId(user.getId())
                .email(user.getEmail())
                .firstName(user.getFirstName())
                .lastName(user.getLastName())
                .role(user.getRole())
                .emailVerified(user.isEmailVerified())
                .emailVerificationToken(verificationToken)
                .build();
    }

    private String generateVerificationToken() {
        byte[] bytes = new byte[24];
        RNG.nextBytes(bytes);
        return HexFormat.of().formatHex(bytes);
    }
}
