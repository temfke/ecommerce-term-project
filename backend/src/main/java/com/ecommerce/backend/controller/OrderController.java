package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.OrderRequest;
import com.ecommerce.backend.dto.OrderResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.OrderStatus;
import com.ecommerce.backend.service.OrderService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/orders")
@RequiredArgsConstructor
public class OrderController {

    private final OrderService orderService;

    @PostMapping
    public ResponseEntity<OrderResponse> createOrder(
            @Valid @RequestBody OrderRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(orderService.createOrder(request, currentUser));
    }

    @GetMapping("/my")
    public ResponseEntity<List<OrderResponse>> getMyOrders(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(orderService.getOrdersByUser(currentUser.getId()));
    }

    @GetMapping
    public ResponseEntity<List<OrderResponse>> getOrders(
            @AuthenticationPrincipal User currentUser,
            @RequestParam(required = false, defaultValue = "200") int limit,
            @RequestParam(required = false, defaultValue = "0") int offset) {
        return ResponseEntity.ok(orderService.getOrdersForCurrentUserPaged(currentUser, limit, offset));
    }

    @GetMapping("/{id}")
    public ResponseEntity<OrderResponse> getOrderById(
            @PathVariable Long id,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(orderService.getOrderById(id, currentUser));
    }

    @GetMapping("/store/{storeId}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<List<OrderResponse>> getOrdersByStore(@PathVariable Long storeId) {
        return ResponseEntity.ok(orderService.getOrdersByStore(storeId));
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<OrderResponse> updateOrderStatus(
            @PathVariable Long id,
            @RequestParam OrderStatus status,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(orderService.updateOrderStatus(id, status, currentUser));
    }
}
