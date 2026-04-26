package com.ecommerce.backend.dto;

import com.ecommerce.backend.entity.ChatAudit;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatAuditResponse {
    private Long id;
    private Long userId;
    private String userEmail;
    private String role;
    private String question;
    private String status;
    private String blockedBy;
    private String guardrailTrigger;
    private String sqlPreview;
    private Integer rowCount;
    private Integer executionMs;
    private boolean rateLimited;
    private LocalDateTime createdAt;

    public static ChatAuditResponse from(ChatAudit a) {
        return ChatAuditResponse.builder()
                .id(a.getId())
                .userId(a.getUserId())
                .userEmail(a.getUserEmail())
                .role(a.getRole())
                .question(a.getQuestion())
                .status(a.getStatus())
                .blockedBy(a.getBlockedBy())
                .guardrailTrigger(a.getGuardrailTrigger())
                .sqlPreview(a.getSqlPreview())
                .rowCount(a.getRowCount())
                .executionMs(a.getExecutionMs())
                .rateLimited(a.isRateLimited())
                .createdAt(a.getCreatedAt())
                .build();
    }
}
