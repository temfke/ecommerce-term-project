package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Order;
import com.ecommerce.backend.enums.OrderStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public interface OrderRepository extends JpaRepository<Order, Long> {
    List<Order> findByUserId(Long userId);
    List<Order> findByStoreId(Long storeId);
    List<Order> findByStoreIdAndStatus(Long storeId, OrderStatus status);
    List<Order> findByUserIdAndStatus(Long userId, OrderStatus status);
    long countByStoreId(Long storeId);
    long countByStatus(OrderStatus status);

    @Query("SELECT COALESCE(SUM(o.grandTotal), 0) FROM Order o WHERE o.store.id = :storeId AND o.status <> 'CANCELLED'")
    BigDecimal getTotalRevenueByStoreId(Long storeId);

    @Query("SELECT COALESCE(SUM(o.grandTotal), 0) FROM Order o WHERE o.status <> 'CANCELLED'")
    BigDecimal getTotalRevenue();

    List<Order> findByCreatedAtBetween(LocalDateTime start, LocalDateTime end);
    List<Order> findByStoreIdAndCreatedAtBetween(Long storeId, LocalDateTime start, LocalDateTime end);

    @Query("SELECT o FROM Order o WHERE o.store.owner.id = :ownerId ORDER BY o.createdAt DESC")
    List<Order> findByStoreOwnerId(Long ownerId);

    @Query("SELECT o FROM Order o ORDER BY o.createdAt DESC")
    List<Order> findAllOrderedByCreatedAt();

    @Query("SELECT DISTINCT o FROM Order o LEFT JOIN FETCH o.items i LEFT JOIN FETCH i.product LEFT JOIN FETCH o.user LEFT JOIN FETCH o.store ORDER BY o.createdAt DESC")
    List<Order> findAllPaged(Pageable pageable);

    @Query("SELECT DISTINCT o FROM Order o LEFT JOIN FETCH o.items i LEFT JOIN FETCH i.product LEFT JOIN FETCH o.user LEFT JOIN FETCH o.store WHERE o.store.owner.id = :ownerId ORDER BY o.createdAt DESC")
    List<Order> findByStoreOwnerIdPaged(Long ownerId, Pageable pageable);

    @Query("SELECT DISTINCT o FROM Order o LEFT JOIN FETCH o.items i LEFT JOIN FETCH i.product LEFT JOIN FETCH o.user LEFT JOIN FETCH o.store WHERE o.user.id = :userId ORDER BY o.createdAt DESC")
    List<Order> findByUserIdPaged(Long userId, Pageable pageable);
}
