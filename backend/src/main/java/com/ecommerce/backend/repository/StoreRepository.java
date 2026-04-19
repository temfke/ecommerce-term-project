package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Store;
import com.ecommerce.backend.enums.StoreStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface StoreRepository extends JpaRepository<Store, Long> {
    List<Store> findByOwnerId(Long ownerId);
    List<Store> findByStatus(StoreStatus status);
    long countByStatus(StoreStatus status);
}
