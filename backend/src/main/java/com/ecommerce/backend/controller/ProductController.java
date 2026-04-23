package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ProductRequest;
import com.ecommerce.backend.dto.ProductResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.ProductService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/products")
@RequiredArgsConstructor
public class ProductController {

    private final ProductService productService;

    @GetMapping
    public ResponseEntity<List<ProductResponse>> getAllProducts(
            @RequestParam(required = false) String search,
            @RequestParam(required = false) Long categoryId,
            @RequestParam(required = false) Long storeId,
            @RequestParam(required = false, defaultValue = "id") String sortBy,
            @RequestParam(required = false, defaultValue = "desc") String sortDir,
            @RequestParam(required = false, defaultValue = "100") int limit,
            @RequestParam(required = false, defaultValue = "0") int offset) {
        return ResponseEntity.ok(productService.filterAndSortProducts(
                search, categoryId, storeId, sortBy, sortDir, limit, offset));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ProductResponse> getProductById(@PathVariable Long id) {
        return ResponseEntity.ok(productService.getProductById(id));
    }

    @GetMapping("/store/{storeId}")
    public ResponseEntity<List<ProductResponse>> getProductsByStore(@PathVariable Long storeId) {
        return ResponseEntity.ok(productService.getProductsByStore(storeId));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<ProductResponse> createProduct(
            @Valid @RequestBody ProductRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(productService.createProduct(request, currentUser));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<ProductResponse> updateProduct(
            @PathVariable Long id,
            @Valid @RequestBody ProductRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(productService.updateProduct(id, request, currentUser));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<Void> deleteProduct(
            @PathVariable Long id,
            @AuthenticationPrincipal User currentUser) {
        productService.deleteProduct(id, currentUser);
        return ResponseEntity.noContent().build();
    }
}
