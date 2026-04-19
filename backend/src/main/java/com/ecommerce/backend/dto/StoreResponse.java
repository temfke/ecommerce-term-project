package com.ecommerce.backend.dto;

import com.ecommerce.backend.enums.StoreStatus;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@Builder
public class StoreResponse {
    private Long id;
    private String name;
    private String description;
    private String logoUrl;
    private StoreStatus status;
    private Long ownerId;
    private String ownerName;
    private LocalDateTime createdAt;
}
