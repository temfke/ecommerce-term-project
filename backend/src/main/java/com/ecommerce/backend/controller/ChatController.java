package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.service.ChatAuditService;
import com.ecommerce.backend.service.ChatRateLimiter;
import com.ecommerce.backend.service.ChatService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;
    private final ChatRateLimiter rateLimiter;
    private final ChatAuditService auditService;

    @PostMapping("/ask")
    public ResponseEntity<ChatResponse> ask(
            @Valid @RequestBody ChatRequest request,
            @AuthenticationPrincipal User currentUser) {

        if (!rateLimiter.tryAcquire(currentUser.getId())) {
            ChatResponse limited = ChatResponse.builder()
                    .status(ChatResponse.Status.BLOCKED)
                    .narrative("You're sending questions a bit too fast — please wait a moment before trying again.")
                    .guardrail(ChatResponse.Guardrail.builder()
                            .type("Rate limit exceeded")
                            .trigger("10 requests per minute")
                            .action("Request throttled")
                            .build())
                    .build();
            auditService.record(currentUser, request, limited, 0, true);
            return ResponseEntity.status(429).body(limited);
        }

        long started = System.nanoTime();
        ChatResponse response = chatService.handle(request, currentUser);
        int elapsedMs = (int) ((System.nanoTime() - started) / 1_000_000);
        auditService.record(currentUser, request, response, elapsedMs, false);
        return ResponseEntity.ok(response);
    }
}
