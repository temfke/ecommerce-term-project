package com.ecommerce.backend.entity;

import jakarta.persistence.*;
import lombok.*;

import java.math.BigDecimal;

@Entity
@Table(name = "customer_profiles")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class CustomerProfile {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false, unique = true)
    private User user;

    private Integer age;

    private String city;

    private String country;

    private String membershipType;

    @Column(precision = 12, scale = 2)
    private BigDecimal totalSpend;

    private Integer itemsPurchased;

    @Column(precision = 3, scale = 2)
    private BigDecimal avgRating;

    private Integer priorPurchases;

    private String satisfactionLevel;
}
