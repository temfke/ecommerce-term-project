package com.ecommerce.backend.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class StoreRequest {
    @NotBlank
    private String name;
    private String description;
    private String logoUrl;
}
