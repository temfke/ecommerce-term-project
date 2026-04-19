package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.DashboardStats;
import com.ecommerce.backend.service.AnalyticsService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/analytics")
@RequiredArgsConstructor
public class AnalyticsController {

    private final AnalyticsService analyticsService;

    @GetMapping("/admin/dashboard")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<DashboardStats> getAdminDashboard() {
        return ResponseEntity.ok(analyticsService.getAdminDashboardStats());
    }

    @GetMapping("/corporate/dashboard/{storeId}")
    @PreAuthorize("hasAnyRole('CORPORATE', 'ADMIN')")
    public ResponseEntity<DashboardStats> getCorporateDashboard(@PathVariable Long storeId) {
        return ResponseEntity.ok(analyticsService.getCorporateDashboardStats(storeId));
    }
}
