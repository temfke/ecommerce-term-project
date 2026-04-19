package com.ecommerce.backend.repository;

import com.ecommerce.backend.entity.Shipment;
import com.ecommerce.backend.enums.ShipmentStatus;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface ShipmentRepository extends JpaRepository<Shipment, Long> {
    Optional<Shipment> findByOrderId(Long orderId);
    List<Shipment> findByStatus(ShipmentStatus status);
    long countByStatus(ShipmentStatus status);
}
