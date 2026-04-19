package com.ecommerce.backend.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ReviewRequest {
    @NotNull
    private Long productId;
    @NotNull @Min(1) @Max(5)
    private Integer starRating;
    private String reviewBody;
}
