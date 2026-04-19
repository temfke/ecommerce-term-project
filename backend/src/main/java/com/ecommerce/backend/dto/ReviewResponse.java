package com.ecommerce.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@AllArgsConstructor
@Builder
public class ReviewResponse {
    private Long id;
    private Long userId;
    private String userName;
    private Long productId;
    private String productName;
    private Integer starRating;
    private String reviewBody;
    private String sentiment;
    private Integer helpfulVotes;
    private Integer totalVotes;
    private LocalDateTime createdAt;
}
