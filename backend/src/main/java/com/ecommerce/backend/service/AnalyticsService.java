package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.DashboardStats;
import com.ecommerce.backend.enums.OrderStatus;
import com.ecommerce.backend.enums.Role;
import com.ecommerce.backend.repository.OrderRepository;
import com.ecommerce.backend.repository.ProductRepository;
import com.ecommerce.backend.repository.ReviewRepository;
import com.ecommerce.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

@Service
@RequiredArgsConstructor
public class AnalyticsService {

    private final OrderRepository orderRepository;
    private final UserRepository userRepository;
    private final ProductRepository productRepository;
    private final ReviewRepository reviewRepository;
    public DashboardStats getAdminDashboardStats() {
        BigDecimal totalRevenue = orderRepository.getTotalRevenue();
        long totalOrders = orderRepository.count();
        long totalCustomers = userRepository.countByRole(Role.INDIVIDUAL);
        long totalProducts = productRepository.count();
        long pendingOrders = orderRepository.countByStatus(OrderStatus.PENDING);
        long shippedOrders = orderRepository.countByStatus(OrderStatus.SHIPPED);
        long deliveredOrders = orderRepository.countByStatus(OrderStatus.DELIVERED);

        return DashboardStats.builder()
                .totalRevenue(totalRevenue)
                .totalOrders(totalOrders)
                .totalCustomers(totalCustomers)
                .totalProducts(totalProducts)
                .pendingOrders(pendingOrders)
                .shippedOrders(shippedOrders)
                .deliveredOrders(deliveredOrders)
                .build();
    }

    public DashboardStats getCorporateDashboardStats(Long storeId) {
        BigDecimal totalRevenue = orderRepository.getTotalRevenueByStoreId(storeId);
        long totalOrders = orderRepository.countByStoreId(storeId);
        long totalProducts = productRepository.countByStoreId(storeId);
        Double avgRating = reviewRepository.getAverageRatingByStoreId(storeId);

        return DashboardStats.builder()
                .totalRevenue(totalRevenue)
                .totalOrders(totalOrders)
                .totalProducts(totalProducts)
                .avgRating(avgRating)
                .build();
    }
}
