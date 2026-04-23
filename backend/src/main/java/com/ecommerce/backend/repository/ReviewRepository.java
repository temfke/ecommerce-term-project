package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Review;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ReviewRepository extends JpaRepository<Review, Long> {

    @Query("SELECT r FROM Review r WHERE r.product.id = :productId")
    List<Review> findByProductId(@Param("productId") Long productId);

    @Query("SELECT r FROM Review r WHERE r.product.id = :productId ORDER BY r.createdAt DESC")
    List<Review> findRecentByProductId(@Param("productId") Long productId, Pageable pageable);

    @Query("SELECT r FROM Review r WHERE r.user.id = :userId")
    List<Review> findByUserId(@Param("userId") Long userId);

    @Query("SELECT r FROM Review r WHERE r.product.id = :productId AND r.user.id = :userId ORDER BY r.createdAt DESC")
    List<Review> findByProductIdAndUserIdOrderByCreatedAtDesc(@Param("productId") Long productId, @Param("userId") Long userId);

    @Query("SELECT AVG(r.starRating) FROM Review r WHERE r.product.id = :productId")
    Double getAverageRatingByProductId(@Param("productId") Long productId);

    @Query("SELECT AVG(r.starRating) FROM Review r WHERE r.product.store.id = :storeId")
    Double getAverageRatingByStoreId(@Param("storeId") Long storeId);

    @Query("SELECT COUNT(r) FROM Review r WHERE r.product.id = :productId")
    long countByProductId(@Param("productId") Long productId);

    @Query("SELECT r FROM Review r WHERE r.product.store.id = :storeId")
    List<Review> findByStoreId(@Param("storeId") Long storeId);

    @Query("SELECT r FROM Review r WHERE r.product.store.owner.id = :ownerId ORDER BY r.createdAt DESC")
    List<Review> findByStoreOwnerId(@Param("ownerId") Long ownerId);

    @Query("SELECT r FROM Review r ORDER BY r.createdAt DESC")
    List<Review> findAllOrderedByCreatedAt();
}
