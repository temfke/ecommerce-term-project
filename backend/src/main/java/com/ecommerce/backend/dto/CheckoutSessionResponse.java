package com.ecommerce.backend.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class CheckoutSessionResponse {
    private String sessionId;
    private String url;
}
