package com.ecommerce.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@Builder
public class ProductResponse {
    private Long id;
    private String name;
    private String description;
    private String sku;
    private BigDecimal unitPrice;
    private Integer stockQuantity;
    private String imageUrl;
    private boolean active;
    private Long storeId;
    private String storeName;
    private Long categoryId;
    private String categoryName;
    private LocalDateTime createdAt;
}
