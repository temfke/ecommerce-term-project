package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ShipmentResponse;
import com.ecommerce.backend.enums.ShipmentStatus;
import com.ecommerce.backend.service.ShipmentService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/shipments")
@RequiredArgsConstructor
public class ShipmentController {

    private final ShipmentService shipmentService;

    @PostMapping
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<ShipmentResponse> createShipment(@RequestBody Map<String, Object> body) {
        Long orderId = Long.valueOf(body.get("orderId").toString());
        String carrier = (String) body.getOrDefault("carrier", "Standard");
        String mode = (String) body.getOrDefault("modeOfShipment", "Ground");
        String warehouse = (String) body.getOrDefault("warehouseBlock", "A");
        String destination = (String) body.getOrDefault("destination", "");
        return ResponseEntity.ok(shipmentService.createShipment(orderId, carrier, mode, warehouse, destination));
    }

    @GetMapping("/order/{orderId}")
    public ResponseEntity<ShipmentResponse> getShipmentByOrder(@PathVariable Long orderId) {
        return ResponseEntity.ok(shipmentService.getShipmentByOrderId(orderId));
    }

    @GetMapping
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<List<ShipmentResponse>> getAllShipments(
            @RequestParam(required = false) ShipmentStatus status) {
        if (status != null) {
            return ResponseEntity.ok(shipmentService.getShipmentsByStatus(status));
        }
        return ResponseEntity.ok(shipmentService.getAllShipments());
    }

    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<ShipmentResponse> updateStatus(
            @PathVariable Long id,
            @RequestParam ShipmentStatus status) {
        return ResponseEntity.ok(shipmentService.updateShipmentStatus(id, status));
    }
}
