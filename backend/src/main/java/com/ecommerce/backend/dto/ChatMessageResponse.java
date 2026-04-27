package com.ecommerce.backend.dto;

import com.ecommerce.backend.entity.ChatMessage;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Slf4j
public class ChatMessageResponse {
    private Long id;
    private String role;
    private String content;
    /** Re-hydrated ChatResponse for assistant turns; null for user turns. */
    private ChatResponse payload;
    private LocalDateTime createdAt;

    public static ChatMessageResponse from(ChatMessage m, ObjectMapper mapper) {
        ChatResponse payload = null;
        if (m.getPayloadJson() != null && !m.getPayloadJson().isBlank()) {
            try {
                payload = mapper.readValue(m.getPayloadJson(), ChatResponse.class);
            } catch (Exception e) {
                log.warn("Could not deserialize chat message payload {}: {}", m.getId(), e.getMessage());
            }
        }
        return ChatMessageResponse.builder()
                .id(m.getId())
                .role(m.getRole())
                .content(m.getContent())
                .payload(payload)
                .createdAt(m.getCreatedAt())
                .build();
    }
}
