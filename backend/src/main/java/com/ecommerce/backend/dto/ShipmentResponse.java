package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.ShipmentStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@Builder
public class ShipmentResponse {
    private Long id;
    private Long orderId;
    private String trackingId;
    private String carrier;
    private String warehouseBlock;
    private String modeOfShipment;
    private String destination;
    private ShipmentStatus status;
    private String customerName;
    private LocalDateTime estimatedDelivery;
    private LocalDateTime shippedAt;
    private LocalDateTime deliveredAt;
    private LocalDateTime createdAt;
}
