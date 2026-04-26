package com.ecommerce.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatResponse {

    public enum Status { ANSWER, GREETING, OUT_OF_SCOPE, BLOCKED }
    public enum ChartType { BAR, LINE, NONE }

    private Status status;
    private String narrative;

    private String sqlPreview;
    private List<DataRow> rows;
    private ChartType chartType;
    private TableData table;

    private Guardrail guardrail;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TableData {
        private List<String> columns;
        private List<List<Object>> rows;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class DataRow {
        private String label;
        private Double value;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Guardrail {
        private String type;
        private String trigger;
        private String action;
    }
}
