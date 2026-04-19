package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ReviewRequest;
import com.ecommerce.backend.dto.ReviewResponse;
import com.ecommerce.backend.entity.Product;
import com.ecommerce.backend.entity.Review;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.ProductRepository;
import com.ecommerce.backend.repository.ReviewRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ReviewService {

    private final ReviewRepository reviewRepository;
    private final ProductRepository productRepository;

    public ReviewResponse createReview(ReviewRequest request, User currentUser) {
        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new ResourceNotFoundException("Product not found"));

        Review review = Review.builder()
                .user(currentUser)
                .product(product)
                .starRating(request.getStarRating())
                .reviewBody(request.getReviewBody())
                .build();

        return toResponse(reviewRepository.save(review));
    }

    public List<ReviewResponse> getReviewsByProduct(Long productId) {
        return reviewRepository.findFirst50ByProductIdOrderByCreatedAtDesc(productId)
                .stream().map(this::toResponse).toList();
    }

    public java.util.Map<String, Object> getProductRatingSummary(Long productId) {
        long count = reviewRepository.countByProductId(productId);
        Double avg = count > 0 ? reviewRepository.getAverageRatingByProductId(productId) : null;
        return java.util.Map.of(
                "count", count,
                "averageRating", avg == null ? 0.0 : Math.round(avg * 10.0) / 10.0
        );
    }

    public List<ReviewResponse> getReviewsByUser(Long userId) {
        return reviewRepository.findByUserId(userId).stream().map(this::toResponse).toList();
    }

    public List<ReviewResponse> getReviewsByStore(Long storeId) {
        return reviewRepository.findByStoreId(storeId).stream().map(this::toResponse).toList();
    }

    public List<ReviewResponse> getAllReviews() {
        return reviewRepository.findAll().stream().map(this::toResponse).toList();
    }

    public void deleteReview(Long id) {
        if (!reviewRepository.existsById(id)) {
            throw new ResourceNotFoundException("Review not found");
        }
        reviewRepository.deleteById(id);
    }

    private ReviewResponse toResponse(Review review) {
        return ReviewResponse.builder()
                .id(review.getId())
                .userId(review.getUser().getId())
                .userName(review.getUser().getFirstName() + " " + review.getUser().getLastName())
                .productId(review.getProduct().getId())
                .productName(review.getProduct().getName())
                .starRating(review.getStarRating())
                .reviewBody(review.getReviewBody())
                .sentiment(review.getSentiment())
                .helpfulVotes(review.getHelpfulVotes())
                .totalVotes(review.getTotalVotes())
                .createdAt(review.getCreatedAt())
                .build();
    }
}
