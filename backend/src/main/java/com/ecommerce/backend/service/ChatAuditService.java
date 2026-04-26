package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ChatAuditResponse;
import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.ChatAudit;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.repository.ChatAuditRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class ChatAuditService {

    private final ChatAuditRepository repo;

    public void record(
            User user,
            ChatRequest request,
            ChatResponse response,
            int executionMs,
            boolean rateLimited
    ) {
        try {
            ChatAudit audit = ChatAudit.builder()
                    .userId(user.getId())
                    .userEmail(user.getEmail())
                    .role(user.getRole().name())
                    .question(truncate(request.getQuestion(), 1000))
                    .status(response.getStatus() == null ? "UNKNOWN" : response.getStatus().name())
                    .blockedBy(response.getGuardrail() == null ? null : truncate(response.getGuardrail().getType(), 64))
                    .guardrailTrigger(response.getGuardrail() == null ? null : truncate(response.getGuardrail().getTrigger(), 256))
                    .sqlPreview(response.getSqlPreview())
                    .rowCount(response.getRows() == null ? null : response.getRows().size())
                    .executionMs(executionMs)
                    .rateLimited(rateLimited)
                    .build();
            repo.save(audit);
        } catch (Exception e) {
            // Audit must never break the chat flow.
            log.warn("Failed to write chat audit entry: {}", e.getMessage());
        }
    }

    public List<ChatAuditResponse> list(String status, Long userId, int limit, int offset) {
        int safeLimit = Math.max(1, Math.min(limit, 500));
        int safeOffset = Math.max(0, offset);
        int page = safeOffset / safeLimit;
        int leadingSkip = safeOffset % safeLimit;

        PageRequest pageRequest = PageRequest.of(page, safeLimit + leadingSkip);
        List<ChatAudit> raw;
        if (status != null && !status.isBlank()) {
            raw = repo.findByStatusPaged(status, pageRequest);
        } else if (userId != null) {
            raw = repo.findByUserIdPaged(userId, pageRequest);
        } else {
            raw = repo.findAllPaged(pageRequest);
        }
        return raw.stream()
                .skip(leadingSkip)
                .limit(safeLimit)
                .map(ChatAuditResponse::from)
                .toList();
    }

    private String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() <= max ? s : s.substring(0, max);
    }
}
