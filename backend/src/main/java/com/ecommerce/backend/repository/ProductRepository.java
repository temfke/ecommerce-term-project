package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Product;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface ProductRepository extends JpaRepository<Product, Long> {
    List<Product> findByStoreId(Long storeId);
    List<Product> findByStoreIdAndActiveTrue(Long storeId);
    List<Product> findByCategoryId(Long categoryId);
    List<Product> findFirst100ByActiveTrueOrderByIdDesc();
    List<Product> findFirst100ByNameContainingIgnoreCaseAndActiveTrueOrderByIdDesc(String name);

    @Query("SELECT p FROM Product p WHERE p.active = true AND p.stockQuantity < :threshold")
    List<Product> findLowStockProducts(int threshold);

    long countByStoreId(Long storeId);

    @Query("SELECT p FROM Product p " +
           "WHERE p.active = true " +
           "AND (:search IS NULL OR LOWER(p.name) LIKE LOWER(CONCAT('%', :search, '%'))) " +
           "AND (:categoryId IS NULL OR p.category.id = :categoryId) " +
           "AND (:storeId IS NULL OR p.store.id = :storeId)")
    Page<Product> filterProducts(
            @Param("search") String search,
            @Param("categoryId") Long categoryId,
            @Param("storeId") Long storeId,
            Pageable pageable);
}
