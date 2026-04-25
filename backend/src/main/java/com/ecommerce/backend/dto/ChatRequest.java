package com.ecommerce.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.List;

@Data
public class ChatRequest {

    @NotBlank
    @Size(max = 1000)
    private String question;

    private List<ChatTurn> history;

    @Data
    public static class ChatTurn {
        private String role;
        private String content;
    }
}
