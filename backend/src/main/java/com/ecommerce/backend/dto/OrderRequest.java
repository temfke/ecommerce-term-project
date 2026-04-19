package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.PaymentMethod;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class OrderRequest {
    @NotNull
    private Long storeId;
    @NotNull
    private List<OrderItemRequest> items;
    private PaymentMethod paymentMethod;
    private String shippingAddress;
}
