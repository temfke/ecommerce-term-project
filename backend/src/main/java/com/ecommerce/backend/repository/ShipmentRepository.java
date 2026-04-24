package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Shipment;
import com.ecommerce.backend.enums.ShipmentStatus;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;

public interface ShipmentRepository extends JpaRepository<Shipment, Long> {
    Optional<Shipment> findByOrderId(Long orderId);
    List<Shipment> findByStatus(ShipmentStatus status);
    long countByStatus(ShipmentStatus status);

    @Query("SELECT s FROM Shipment s LEFT JOIN FETCH s.order o LEFT JOIN FETCH o.user ORDER BY s.createdAt DESC")
    List<Shipment> findAllPaged(Pageable pageable);

    @Query("SELECT s FROM Shipment s LEFT JOIN FETCH s.order o LEFT JOIN FETCH o.user WHERE s.status = :status ORDER BY s.createdAt DESC")
    List<Shipment> findByStatusPaged(ShipmentStatus status, Pageable pageable);

    @Query("SELECT s FROM Shipment s LEFT JOIN FETCH s.order o LEFT JOIN FETCH o.user WHERE o.store.owner.id = :ownerId ORDER BY s.createdAt DESC")
    List<Shipment> findByStoreOwnerIdPaged(Long ownerId, Pageable pageable);

    @Query("SELECT s FROM Shipment s LEFT JOIN FETCH s.order o LEFT JOIN FETCH o.user WHERE o.store.owner.id = :ownerId AND s.status = :status ORDER BY s.createdAt DESC")
    List<Shipment> findByStoreOwnerIdAndStatusPaged(Long ownerId, ShipmentStatus status, Pageable pageable);
}
