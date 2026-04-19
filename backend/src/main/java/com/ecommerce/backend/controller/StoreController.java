package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.StoreRequest;
import com.ecommerce.backend.dto.StoreResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.StoreStatus;
import com.ecommerce.backend.service.StoreService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/stores")
@RequiredArgsConstructor
public class StoreController {

    private final StoreService storeService;

    @GetMapping
    public ResponseEntity<List<StoreResponse>> getAllStores() {
        return ResponseEntity.ok(storeService.getAllStores());
    }

    @GetMapping("/{id}")
    public ResponseEntity<StoreResponse> getStoreById(@PathVariable Long id) {
        return ResponseEntity.ok(storeService.getStoreById(id));
    }

    @GetMapping("/my")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<List<StoreResponse>> getMyStores(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(storeService.getStoresByOwner(currentUser.getId()));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<StoreResponse> createStore(
            @Valid @RequestBody StoreRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(storeService.createStore(request, currentUser));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<StoreResponse> updateStore(
            @PathVariable Long id,
            @Valid @RequestBody StoreRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(storeService.updateStore(id, request, currentUser));
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<StoreResponse> updateStoreStatus(
            @PathVariable Long id,
            @RequestParam StoreStatus status) {
        return ResponseEntity.ok(storeService.updateStoreStatus(id, status));
    }
}
