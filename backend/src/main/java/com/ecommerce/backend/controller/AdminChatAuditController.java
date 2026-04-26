package com.ecommerce.backend.controller;

import com.ecommerce.backend.dto.ChatAuditResponse;
import com.ecommerce.backend.service.ChatAuditService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/admin/chat-audit")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class AdminChatAuditController {

    private final ChatAuditService auditService;

    @GetMapping
    public ResponseEntity<List<ChatAuditResponse>> list(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) Long userId,
            @RequestParam(defaultValue = "200") int limit,
            @RequestParam(defaultValue = "0") int offset
    ) {
        return ResponseEntity.ok(auditService.list(status, userId, limit, offset));
    }
}
