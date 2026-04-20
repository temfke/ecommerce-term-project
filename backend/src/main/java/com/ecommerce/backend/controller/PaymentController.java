package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.CheckoutSessionRequest;
import com.ecommerce.backend.dto.CheckoutSessionResponse;
import com.ecommerce.backend.dto.PaymentConfirmResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.PaymentService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/payments")
@RequiredArgsConstructor
public class PaymentController {

    private final PaymentService paymentService;

    @PostMapping("/checkout-session")
    public ResponseEntity<CheckoutSessionResponse> createCheckoutSession(
            @Valid @RequestBody CheckoutSessionRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(paymentService.createCheckoutSession(request, currentUser));
    }

    @GetMapping("/confirm")
    public ResponseEntity<PaymentConfirmResponse> confirm(
            @RequestParam("session_id") String sessionId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(paymentService.confirm(sessionId, currentUser));
    }
}
