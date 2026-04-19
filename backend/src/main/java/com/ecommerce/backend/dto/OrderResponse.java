package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.OrderStatus;
import com.ecommerce.backend.enums.PaymentMethod;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

@Data
@AllArgsConstructor
@Builder
public class OrderResponse {
    private Long id;
    private Long userId;
    private String customerName;
    private String customerEmail;
    private Long storeId;
    private String storeName;
    private OrderStatus status;
    private BigDecimal grandTotal;
    private PaymentMethod paymentMethod;
    private String shippingAddress;
    private List<OrderItemResponse> items;
    private LocalDateTime createdAt;
}
