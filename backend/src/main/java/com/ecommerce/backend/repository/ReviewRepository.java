package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Review;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;

public interface ReviewRepository extends JpaRepository<Review, Long> {
    List<Review> findByProductId(Long productId);
    List<Review> findFirst50ByProductIdOrderByCreatedAtDesc(Long productId);
    List<Review> findByUserId(Long userId);

    @Query("SELECT r FROM Review r WHERE r.product.id = :productId AND r.user.id = :userId ORDER BY r.createdAt DESC")
    List<Review> findByProductIdAndUserIdOrderByCreatedAtDesc(Long productId, Long userId);

    @Query("SELECT AVG(r.starRating) FROM Review r WHERE r.product.id = :productId")
    Double getAverageRatingByProductId(Long productId);

    @Query("SELECT AVG(r.starRating) FROM Review r WHERE r.product.store.id = :storeId")
    Double getAverageRatingByStoreId(Long storeId);

    long countByProductId(Long productId);

    @Query("SELECT r FROM Review r WHERE r.product.store.id = :storeId")
    List<Review> findByStoreId(Long storeId);
}
