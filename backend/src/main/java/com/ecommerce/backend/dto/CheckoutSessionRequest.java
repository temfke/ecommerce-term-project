package com.ecommerce.backend.dto;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.List;

@Data
public class CheckoutSessionRequest {
    @NotNull
    private Long storeId;

    @NotEmpty
    private List<OrderItemRequest> items;

    private String shippingAddress;
}
