package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.AddressRequest;
import com.ecommerce.backend.dto.AddressResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.AddressService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/addresses")
@RequiredArgsConstructor
public class AddressController {

    private final AddressService addressService;

    @GetMapping
    public ResponseEntity<List<AddressResponse>> list(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(addressService.listForUser(currentUser));
    }

    @PostMapping
    public ResponseEntity<AddressResponse> create(
            @Valid @RequestBody AddressRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(addressService.create(request, currentUser));
    }

    @PutMapping("/{id}")
    public ResponseEntity<AddressResponse> update(
            @PathVariable Long id,
            @Valid @RequestBody AddressRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(addressService.update(id, request, currentUser));
    }

    @PatchMapping("/{id}/default")
    public ResponseEntity<AddressResponse> setDefault(
            @PathVariable Long id,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(addressService.setDefault(id, currentUser));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @PathVariable Long id,
            @AuthenticationPrincipal User currentUser) {
        addressService.delete(id, currentUser);
        return ResponseEntity.noContent().build();
    }
}
