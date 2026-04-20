package com.ecommerce.backend.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class PaymentConfirmResponse {
    private String status;
    private OrderResponse order;
}
