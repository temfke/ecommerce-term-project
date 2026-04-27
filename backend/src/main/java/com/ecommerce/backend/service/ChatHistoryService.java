package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ChatMessageResponse;
import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.ChatMessage;
import com.ecommerce.backend.repository.ChatMessageRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class ChatHistoryService {

    /** Cap on how many prior turns we feed back into the LLM as context. */
    private static final int CONTEXT_TURNS = 10;
    /** Cap on how many messages we ever load for the UI. */
    private static final int MAX_LOAD = 200;

    private final ChatMessageRepository repo;
    private final ObjectMapper mapper;

    public List<ChatMessageResponse> loadForUser(Long userId) {
        List<ChatMessage> raw = repo.findHistoryAsc(userId, PageRequest.of(0, MAX_LOAD));
        return raw.stream().map(m -> ChatMessageResponse.from(m, mapper)).toList();
    }

    public int clearForUser(Long userId) {
        return repo.deleteByUserId(userId);
    }

    /** Returns the recent turns (oldest-first) to attach as `history` on the next LLM call. */
    public List<ChatRequest.ChatTurn> recentContextTurns(Long userId) {
        List<ChatMessage> recentDesc = repo.findRecentDesc(userId, PageRequest.of(0, CONTEXT_TURNS));
        Collections.reverse(recentDesc);
        List<ChatRequest.ChatTurn> turns = new ArrayList<>(recentDesc.size());
        for (ChatMessage m : recentDesc) {
            ChatRequest.ChatTurn t = new ChatRequest.ChatTurn();
            t.setRole(m.getRole());
            t.setContent(m.getContent());
            turns.add(t);
        }
        return turns;
    }

    public void saveUserMessage(Long userId, String content) {
        try {
            repo.save(ChatMessage.builder()
                    .userId(userId)
                    .role("user")
                    .content(truncate(content, 4000))
                    .build());
        } catch (Exception e) {
            log.warn("Failed to save user chat message: {}", e.getMessage());
        }
    }

    public void saveAssistantMessage(Long userId, ChatResponse response) {
        try {
            String json = mapper.writeValueAsString(response);
            repo.save(ChatMessage.builder()
                    .userId(userId)
                    .role("assistant")
                    .content(truncate(response.getNarrative() == null ? "" : response.getNarrative(), 4000))
                    .payloadJson(json)
                    .build());
        } catch (Exception e) {
            log.warn("Failed to save assistant chat message: {}", e.getMessage());
        }
    }

    private String truncate(String s, int max) {
        if (s == null) return null;
        return s.length() <= max ? s : s.substring(0, max);
    }
}
