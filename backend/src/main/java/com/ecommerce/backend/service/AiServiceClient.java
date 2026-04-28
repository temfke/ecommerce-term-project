package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.User;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;

@Component
public class AiServiceClient {

    private final HttpClient http = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    private final ObjectMapper mapper = new ObjectMapper();

    @Value("${chat.ai-service.url:}")
    private String aiServiceUrl;

    @Value("${chat.ai-service.internal-key:}")
    private String internalKey;

    public boolean isEnabled() {
        return aiServiceUrl != null && !aiServiceUrl.isBlank();
    }

    public ChatResponse ask(ChatRequest req, User user, Long scopedStoreId) throws Exception {
        AiPayload payload = new AiPayload(
                req.getQuestion(),
                user.getId(),
                user.getRole().name(),
                scopedStoreId,
                user.getFirstName(),
                req.getHistory() == null ? List.of() : req.getHistory().stream()
                        .map(t -> new AiTurn(t.getRole(), t.getContent()))
                        .toList()
        );

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(aiServiceUrl.replaceAll("/+$", "") + "/chat/ask"))
                // Budget: DB query cap (25s) + 2 LLM calls (SQL gen + narrative),
                // each up to ~10s on a cold path. 60s leaves headroom without
                // letting a genuinely stuck request hang the UI forever.
                .timeout(Duration.ofSeconds(60))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(payload)));

        if (internalKey != null && !internalKey.isBlank()) {
            builder.header("X-Internal-Key", internalKey);
        }

        HttpResponse<String> response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
        if (response.statusCode() / 100 != 2) {
            throw new IllegalStateException("AI service returned HTTP " + response.statusCode() + ": " + response.body());
        }
        return mapper.readValue(response.body(), AiChatResponseEnvelope.class).toChatResponse();
    }

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    private static class AiPayload {
        private String question;
        @JsonProperty("user_id") private Long userId;
        private String role;
        @JsonProperty("store_owner_id") private Long storeOwnerId;
        @JsonProperty("first_name") private String firstName;
        private List<AiTurn> history;
    }

    @Data
    @AllArgsConstructor
    @NoArgsConstructor
    private static class AiTurn {
        private String role;
        private String content;
    }

    /** Envelope using snake_case to match the Python pydantic schema. */
    @Data
    @NoArgsConstructor
    public static class AiChatResponseEnvelope {
        private String status;
        private String narrative;
        private String title;
        private List<String> bullets;
        private String insight;
        @JsonProperty("sql_preview") private String sqlPreview;
        private List<AiDataRow> rows;
        @JsonProperty("chart_type") private String chartType;
        private AiTable table;
        private AiGuardrail guardrail;

        public ChatResponse toChatResponse() {
            return ChatResponse.builder()
                    .status(ChatResponse.Status.valueOf(status))
                    .narrative(narrative)
                    .title(title)
                    .bullets(bullets)
                    .insight(insight)
                    .sqlPreview(sqlPreview)
                    .rows(rows == null ? null : rows.stream()
                            .map(r -> ChatResponse.DataRow.builder().label(r.label).value(r.value).build())
                            .toList())
                    .chartType(chartType == null ? null : ChatResponse.ChartType.valueOf(chartType))
                    .table(table == null ? null : ChatResponse.TableData.builder()
                            .columns(table.columns)
                            .rows(table.rows)
                            .build())
                    .guardrail(guardrail == null ? null : ChatResponse.Guardrail.builder()
                            .type(guardrail.type)
                            .trigger(guardrail.trigger)
                            .action(guardrail.action)
                            .build())
                    .build();
        }
    }

    @Data
    @NoArgsConstructor
    public static class AiDataRow {
        private String label;
        private Double value;
    }

    @Data
    @NoArgsConstructor
    public static class AiTable {
        private List<String> columns;
        private List<List<Object>> rows;
    }

    @Data
    @NoArgsConstructor
    public static class AiGuardrail {
        private String type;
        private String trigger;
        private String action;
    }
}
