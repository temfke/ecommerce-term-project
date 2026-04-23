package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ReviewRequest;
import com.ecommerce.backend.dto.ReviewResponse;
import com.ecommerce.backend.entity.Product;
import com.ecommerce.backend.entity.Review;
import com.ecommerce.backend.entity.ReviewVote;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.ProductRepository;
import com.ecommerce.backend.repository.ReviewRepository;
import com.ecommerce.backend.repository.ReviewVoteRepository;
import com.ecommerce.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collection;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class ReviewService {

    private static final Logger log = LoggerFactory.getLogger(ReviewService.class);

    private final ReviewRepository reviewRepository;
    private final ProductRepository productRepository;
    private final ReviewVoteRepository reviewVoteRepository;
    private final UserRepository userRepository;

    @Transactional
    public ReviewResponse createReview(ReviewRequest request, User currentUser) {
        if (currentUser == null || currentUser.getId() == null) {
            throw new BadRequestException("Authentication required to post a review");
        }
        if (request.getStarRating() == null || request.getStarRating() < 1 || request.getStarRating() > 5) {
            throw new BadRequestException("Star rating must be between 1 and 5");
        }

        User managedUser = userRepository.findById(currentUser.getId())
                .orElseThrow(() -> new BadRequestException("Authenticated user no longer exists"));
        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new ResourceNotFoundException("Product not found"));

        String body = request.getReviewBody();
        if (body != null) {
            body = body.trim();
            if (body.isEmpty()) body = null;
        }

        Review review = Review.builder()
                .user(managedUser)
                .product(product)
                .starRating(request.getStarRating())
                .reviewBody(body)
                .helpfulVotes(0)
                .totalVotes(0)
                .build();

        Review saved = reviewRepository.saveAndFlush(review);
        log.info("Saved review id={} userId={} productId={} stars={} bodyLen={}",
                saved.getId(), managedUser.getId(), product.getId(),
                saved.getStarRating(), body == null ? 0 : body.length());
        return toResponse(saved, Collections.emptyMap());
    }

    public List<ReviewResponse> getReviewsByProduct(Long productId, User currentUser) {
        List<Review> reviews = reviewRepository.findRecentByProductId(productId, PageRequest.of(0, 50));
        return mapWithVotes(reviews, currentUser);
    }

    public List<ReviewResponse> getMyReviewsForProduct(Long productId, User currentUser) {
        if (currentUser == null) return Collections.emptyList();
        List<Review> reviews = reviewRepository.findByProductIdAndUserIdOrderByCreatedAtDesc(productId, currentUser.getId());
        return mapWithVotes(reviews, currentUser);
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
        User stub = new User();
        stub.setId(userId);
        return mapWithVotes(reviewRepository.findByUserId(userId), stub);
    }

    public List<ReviewResponse> getReviewsByStore(Long storeId, User currentUser) {
        return mapWithVotes(reviewRepository.findByStoreId(storeId), currentUser);
    }

    public List<ReviewResponse> getAllReviews() {
        return reviewRepository.findAllOrderedByCreatedAt().stream()
                .map(r -> toResponse(r, Collections.emptyMap()))
                .toList();
    }

    public List<ReviewResponse> getReviewsForStoreOwner(Long ownerId) {
        return reviewRepository.findByStoreOwnerId(ownerId).stream()
                .map(r -> toResponse(r, Collections.emptyMap()))
                .toList();
    }

    public List<ReviewResponse> getReviewsForCurrentUser(User currentUser) {
        return switch (currentUser.getRole()) {
            case ADMIN -> getAllReviews();
            case CORPORATE -> getReviewsForStoreOwner(currentUser.getId());
            default -> getReviewsByUser(currentUser.getId());
        };
    }

    @Transactional
    public void deleteReview(Long id) {
        if (!reviewRepository.existsById(id)) {
            throw new ResourceNotFoundException("Review not found");
        }
        reviewVoteRepository.deleteByReviewId(id);
        reviewRepository.deleteById(id);
    }

    @Transactional
    public void deleteReview(Long id, User currentUser) {
        Review review = reviewRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Review not found"));
        boolean isOwner = review.getUser() != null
                && currentUser != null
                && review.getUser().getId().equals(currentUser.getId());
        boolean isAdmin = currentUser != null && "ADMIN".equals(currentUser.getRole().name());
        if (!isOwner && !isAdmin) {
            throw new BadRequestException("You can only delete your own reviews");
        }
        reviewVoteRepository.deleteByReviewId(id);
        reviewRepository.deleteById(id);
    }

    @Transactional
    public ReviewResponse vote(Long reviewId, String type, User currentUser) {
        Review review = reviewRepository.findById(reviewId)
                .orElseThrow(() -> new ResourceNotFoundException("Review not found"));

        if (review.getUser() != null && review.getUser().getId().equals(currentUser.getId())) {
            throw new BadRequestException("You cannot vote on your own review");
        }

        boolean helpful;
        if ("HELPFUL".equalsIgnoreCase(type)) {
            helpful = true;
        } else if ("NOT_HELPFUL".equalsIgnoreCase(type)) {
            helpful = false;
        } else {
            throw new BadRequestException("Invalid vote type. Use HELPFUL or NOT_HELPFUL");
        }

        int helpfulDelta = 0;
        int totalDelta = 0;

        Optional<ReviewVote> existing = reviewVoteRepository.findByUserIdAndReviewId(currentUser.getId(), reviewId);
        if (existing.isPresent()) {
            ReviewVote v = existing.get();
            if (v.isHelpful() == helpful) {
                reviewVoteRepository.delete(v);
                if (helpful) helpfulDelta = -1;
                totalDelta = -1;
            } else {
                v.setHelpful(helpful);
                reviewVoteRepository.save(v);
                helpfulDelta = helpful ? 1 : -1;
            }
        } else {
            ReviewVote v = ReviewVote.builder()
                    .user(currentUser)
                    .review(review)
                    .helpful(helpful)
                    .build();
            reviewVoteRepository.save(v);
            if (helpful) helpfulDelta = 1;
            totalDelta = 1;
        }

        int currentHelpful = review.getHelpfulVotes() == null ? 0 : review.getHelpfulVotes();
        int currentTotal = review.getTotalVotes() == null ? 0 : review.getTotalVotes();
        review.setHelpfulVotes(Math.max(0, currentHelpful + helpfulDelta));
        review.setTotalVotes(Math.max(0, currentTotal + totalDelta));
        Review saved = reviewRepository.save(review);

        Map<Long, String> myVotes = loadMyVotes(currentUser, List.of(reviewId));
        return toResponse(saved, myVotes);
    }

    private List<ReviewResponse> mapWithVotes(List<Review> reviews, User currentUser) {
        if (reviews.isEmpty()) return Collections.emptyList();
        Map<Long, String> myVotes = loadMyVotes(currentUser, reviews.stream().map(Review::getId).toList());
        List<ReviewResponse> out = new java.util.ArrayList<>(reviews.size());
        for (Review r : reviews) {
            out.add(toResponse(r, myVotes));
        }
        return out;
    }

    private Map<Long, String> loadMyVotes(User currentUser, Collection<Long> reviewIds) {
        if (currentUser == null || currentUser.getId() == null || reviewIds.isEmpty()) {
            return Collections.emptyMap();
        }
        try {
            List<ReviewVote> votes = reviewVoteRepository.findByUserIdAndReviewIdIn(currentUser.getId(), reviewIds);
            Map<Long, String> map = new HashMap<>();
            for (ReviewVote v : votes) {
                map.put(v.getReview().getId(), v.isHelpful() ? "HELPFUL" : "NOT_HELPFUL");
            }
            return map;
        } catch (Exception ex) {
            log.warn("Failed to load review votes for user {}: {}", currentUser.getId(), ex.getMessage());
            return Collections.emptyMap();
        }
    }

    private ReviewResponse toResponse(Review review, Map<Long, String> myVotes) {
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
                .myVote(myVotes.get(review.getId()))
                .createdAt(review.getCreatedAt())
                .build();
    }
}
