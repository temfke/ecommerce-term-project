package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ReviewRequest;
import com.ecommerce.backend.dto.ReviewResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.ReviewService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/reviews")
@RequiredArgsConstructor
public class ReviewController {

    private final ReviewService reviewService;

    @PostMapping
    public ResponseEntity<ReviewResponse> createReview(
            @Valid @RequestBody ReviewRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.createReview(request, currentUser));
    }

    @GetMapping("/product/{productId}")
    public ResponseEntity<List<ReviewResponse>> getReviewsByProduct(
            @PathVariable Long productId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.getReviewsByProduct(productId, currentUser));
    }

    @GetMapping("/product/{productId}/summary")
    public ResponseEntity<java.util.Map<String, Object>> getProductRatingSummary(@PathVariable Long productId) {
        return ResponseEntity.ok(reviewService.getProductRatingSummary(productId));
    }

    @GetMapping("/product/{productId}/mine")
    public ResponseEntity<List<ReviewResponse>> getMyReviewsForProduct(
            @PathVariable Long productId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.getMyReviewsForProduct(productId, currentUser));
    }

    @GetMapping("/my")
    public ResponseEntity<List<ReviewResponse>> getMyReviews(@AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.getReviewsByUser(currentUser.getId()));
    }

    @GetMapping
    public ResponseEntity<List<ReviewResponse>> getReviews(
            @AuthenticationPrincipal User currentUser,
            @RequestParam(required = false, defaultValue = "200") int limit,
            @RequestParam(required = false, defaultValue = "0") int offset) {
        return ResponseEntity.ok(reviewService.getReviewsForCurrentUserPaged(currentUser, limit, offset));
    }

    @GetMapping("/store/{storeId}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<List<ReviewResponse>> getReviewsByStore(
            @PathVariable Long storeId,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.getReviewsByStore(storeId, currentUser));
    }

    @PostMapping("/{id}/vote")
    public ResponseEntity<ReviewResponse> voteOnReview(
            @PathVariable Long id,
            @RequestParam String type,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(reviewService.vote(id, type, currentUser));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteReview(
            @PathVariable Long id,
            @AuthenticationPrincipal User currentUser) {
        reviewService.deleteReview(id, currentUser);
        return ResponseEntity.noContent().build();
    }
}
