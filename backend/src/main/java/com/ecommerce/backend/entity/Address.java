package com.ecommerce.backend.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "addresses")
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Address {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false, length = 60)
    private String label;

    @Column(name = "line1", nullable = false, length = 200)
    private String line1;

    @Column(name = "line2", length = 200)
    private String line2;

    @Column(nullable = false, length = 100)
    private String city;

    @Column(length = 100)
    private String state;

    @Column(name = "postal_code", nullable = false, length = 30)
    private String postalCode;

    @Column(nullable = false, length = 100)
    private String country;

    @Column(name = "is_default", nullable = false)
    private boolean isDefault;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = createdAt;
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}
