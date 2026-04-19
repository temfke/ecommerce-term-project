package com.ecommerce.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;

@Data
@AllArgsConstructor
@Builder
public class DashboardStats {
    private BigDecimal totalRevenue;
    private long totalOrders;
    private long totalCustomers;
    private Double avgRating;
    private long totalProducts;
    private long pendingOrders;
    private long shippedOrders;
    private long deliveredOrders;
}
