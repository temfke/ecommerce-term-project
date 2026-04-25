package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.User;
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

    @PostMapping("/ask")
    public ResponseEntity<ChatResponse> ask(
            @Valid @RequestBody ChatRequest request,
            @AuthenticationPrincipal User currentUser) {
        return ResponseEntity.ok(chatService.handle(request, currentUser));
    }
}
