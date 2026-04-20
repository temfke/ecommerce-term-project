package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.ReviewVote;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface ReviewVoteRepository extends JpaRepository<ReviewVote, Long> {
    Optional<ReviewVote> findByUserIdAndReviewId(Long userId, Long reviewId);

    long countByReviewIdAndHelpful(Long reviewId, boolean helpful);

    long countByReviewId(Long reviewId);

    List<ReviewVote> findByUserIdAndReviewIdIn(Long userId, Collection<Long> reviewIds);

    void deleteByReviewId(Long reviewId);
}
