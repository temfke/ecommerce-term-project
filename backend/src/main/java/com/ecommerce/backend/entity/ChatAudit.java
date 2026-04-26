package com.ecommerce.backend.entity;

import jakarta.persistence.*;
import lombok.*;

import java.time.LocalDateTime;

@Entity
@Table(name = "chat_audit", indexes = {
        @Index(name = "idx_chat_audit_user", columnList = "user_id, created_at"),
        @Index(name = "idx_chat_audit_status", columnList = "status, created_at"),
        @Index(name = "idx_chat_audit_created", columnList = "created_at"),
})
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ChatAudit {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "user_email", length = 320)
    private String userEmail;

    @Column(nullable = false, length = 16)
    private String role;

    @Column(nullable = false, length = 1000)
    private String question;

    @Column(nullable = false, length = 16)
    private String status;

    @Column(name = "blocked_by", length = 64)
    private String blockedBy;

    @Column(name = "guardrail_trigger", length = 256)
    private String guardrailTrigger;

    @Column(name = "sql_preview", columnDefinition = "TEXT")
    private String sqlPreview;

    @Column(name = "row_count")
    private Integer rowCount;

    @Column(name = "execution_ms")
    private Integer executionMs;

    @Column(name = "rate_limited", nullable = false)
    private boolean rateLimited;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }
}
