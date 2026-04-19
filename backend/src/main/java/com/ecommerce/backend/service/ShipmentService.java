package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ShipmentResponse;
import com.ecommerce.backend.entity.Order;
import com.ecommerce.backend.entity.Shipment;
import com.ecommerce.backend.enums.ShipmentStatus;
import com.ecommerce.backend.exception.BadRequestException;
import com.ecommerce.backend.exception.ResourceNotFoundException;
import com.ecommerce.backend.repository.OrderRepository;
import com.ecommerce.backend.repository.ShipmentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ShipmentService {

    private final ShipmentRepository shipmentRepository;
    private final OrderRepository orderRepository;

    public ShipmentResponse createShipment(Long orderId, String carrier, String modeOfShipment,
                                           String warehouseBlock, String destination) {
        Order order = orderRepository.findById(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Order not found"));

        if (shipmentRepository.findByOrderId(orderId).isPresent()) {
            throw new BadRequestException("Shipment already exists for this order");
        }

        Shipment shipment = Shipment.builder()
                .order(order)
                .trackingId("TRK-" + UUID.randomUUID().toString().substring(0, 8).toUpperCase())
                .carrier(carrier)
                .modeOfShipment(modeOfShipment)
                .warehouseBlock(warehouseBlock)
                .destination(destination)
                .status(ShipmentStatus.PROCESSING)
                .estimatedDelivery(LocalDateTime.now().plusDays(5))
                .build();

        return toResponse(shipmentRepository.save(shipment));
    }

    public ShipmentResponse updateShipmentStatus(Long id, ShipmentStatus status) {
        Shipment shipment = shipmentRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Shipment not found"));

        shipment.setStatus(status);
        if (status == ShipmentStatus.IN_TRANSIT) {
            shipment.setShippedAt(LocalDateTime.now());
        } else if (status == ShipmentStatus.DELIVERED) {
            shipment.setDeliveredAt(LocalDateTime.now());
        }

        return toResponse(shipmentRepository.save(shipment));
    }

    public ShipmentResponse getShipmentByOrderId(Long orderId) {
        return toResponse(shipmentRepository.findByOrderId(orderId)
                .orElseThrow(() -> new ResourceNotFoundException("Shipment not found for this order")));
    }

    public List<ShipmentResponse> getAllShipments() {
        return shipmentRepository.findAll().stream().map(this::toResponse).toList();
    }

    public List<ShipmentResponse> getShipmentsByStatus(ShipmentStatus status) {
        return shipmentRepository.findByStatus(status).stream().map(this::toResponse).toList();
    }

    private ShipmentResponse toResponse(Shipment shipment) {
        return ShipmentResponse.builder()
                .id(shipment.getId())
                .orderId(shipment.getOrder().getId())
                .trackingId(shipment.getTrackingId())
                .carrier(shipment.getCarrier())
                .warehouseBlock(shipment.getWarehouseBlock())
                .modeOfShipment(shipment.getModeOfShipment())
                .destination(shipment.getDestination())
                .status(shipment.getStatus())
                .customerName(shipment.getOrder().getUser().getFirstName() + " " + shipment.getOrder().getUser().getLastName())
                .estimatedDelivery(shipment.getEstimatedDelivery())
                .shippedAt(shipment.getShippedAt())
                .deliveredAt(shipment.getDeliveredAt())
                .createdAt(shipment.getCreatedAt())
                .build();
    }
}
