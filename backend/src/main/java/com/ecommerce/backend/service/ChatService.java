package com.ecommerce.backend.service;

import com.ecommerce.backend.dto.ChatRequest;
import com.ecommerce.backend.dto.ChatResponse;
import com.ecommerce.backend.entity.Store;
import com.ecommerce.backend.entity.User;
import com.ecommerce.backend.enums.Role;
import com.ecommerce.backend.repository.StoreRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
@Slf4j
public class ChatService {

    private final StoreRepository storeRepository;
    private final AiServiceClient aiServiceClient;

    private static final Pattern PROMPT_INJECTION = Pattern.compile(
            "(?i)(ignore (all |your |the )?(previous|above|prior) (instructions|prompts?|rules?)" +
                    "|system override|disregard prior|act as (an? )?admin|you are now|pretend (you are|to be)" +
                    "|admin mode|reveal (your )?(system )?prompt|repeat your (system )?prompt)"
    );

    private static final Pattern SQL_INJECTION = Pattern.compile(
            "(?i)(\\bDROP\\b|\\bDELETE\\b|\\bINSERT\\b|\\bUPDATE\\b|\\bTRUNCATE\\b|\\bUNION\\b|\\b1=1\\b|--\\s|/\\*)"
    );

    private static final Pattern STORE_REF = Pattern.compile("(?i)store[ _#-]*(?:id\\s*[:=]?\\s*)?#?(\\d{2,})");
    private static final Pattern GREETING = Pattern.compile(
            "^(?i)\\s*(hi|hello|hey|greetings|good (morning|afternoon|evening)|merhaba|selam)\\b.*"
    );

    public ChatResponse handle(ChatRequest request, User currentUser) {
        String q = request.getQuestion() == null ? "" : request.getQuestion().trim();

        if (aiServiceClient.isEnabled()) {
            try {
                return aiServiceClient.ask(request, currentUser, resolveStoreOwnerScope(currentUser));
            } catch (Exception e) {
                // The AI service is the real answering path. If it's unreachable,
                // be loud about it — silently returning a hardcoded "demo" card
                // (as we used to) hides outages and shipped fake data to admins.
                log.error("AI service call failed for question='{}'", truncate(q, 120), e);
                return blocked(
                        "AI service unavailable",
                        truncate(e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage(), 200),
                        "No SQL generated",
                        "I couldn't reach the analytics engine to answer that. " +
                                "Check that the ai-service is running on the configured URL and that its database connection is healthy, then try again."
                );
            }
        }

        // Below: local keyword stubs used ONLY when ai-service is not configured
        // (chat.ai-service.url is blank). Real production traffic never gets here.

        if (PROMPT_INJECTION.matcher(q).find()) {
            return blocked("Prompt Injection",
                    firstMatch(PROMPT_INJECTION, q),
                    "Request fully rejected",
                    "This message tripped the safety filters. Attempts to alter the system prompt are blocked and logged.");
        }

        if (SQL_INJECTION.matcher(q).find()) {
            return blocked("SQL Injection Attempt",
                    firstMatch(SQL_INJECTION, q),
                    "SQL generation halted",
                    "This request contains SQL keywords that aren't allowed. The chatbot only runs read-only, system-generated queries.");
        }

        Long ownStoreScope = resolveStoreScope(currentUser);
        Matcher storeMatch = STORE_REF.matcher(q);
        if (storeMatch.find() && currentUser.getRole() != Role.ADMIN) {
            long requested = Long.parseLong(storeMatch.group(1));
            if (ownStoreScope == null || requested != ownStoreScope) {
                return ChatResponse.builder()
                        .status(ChatResponse.Status.BLOCKED)
                        .narrative("I can only query data for your own store. Cross-store access isn't permitted.")
                        .guardrail(ChatResponse.Guardrail.builder()
                                .type("Cross-store data access")
                                .trigger("store #" + requested)
                                .action("SQL generation halted")
                                .build())
                        .build();
            }
        }

        if (GREETING.matcher(q).matches()) {
            return ChatResponse.builder()
                    .status(ChatResponse.Status.GREETING)
                    .narrative("Hi " + safeFirstName(currentUser) + " — I can answer questions about your "
                            + scopeLabel(currentUser) + " data. Try one of the suggested questions below.")
                    .build();
        }

        if (isOutOfScope(q)) {
            return ChatResponse.builder()
                    .status(ChatResponse.Status.OUT_OF_SCOPE)
                    .narrative("That's outside what I can help with. I focus on your sales, products, orders, customers, shipments, and reviews.")
                    .guardrail(ChatResponse.Guardrail.builder()
                            .type("Out of scope")
                            .trigger(truncate(q, 60))
                            .action("No SQL generated")
                            .build())
                    .build();
        }

        return mockAnswer(q, currentUser);
    }

    private ChatResponse mockAnswer(String q, User user) {
        String lower = q.toLowerCase();
        boolean wantsTrend = lower.contains("trend") || lower.contains("revenue")
                || lower.contains("over time") || lower.contains("week") || lower.contains("month");

        if (wantsTrend) {
            return ChatResponse.builder()
                    .status(ChatResponse.Status.ANSWER)
                    .narrative("Here's the weekly revenue trend for your " + scopeLabel(user) + " over the last 7 days. "
                            + "(Demo response — real query execution arrives in step 3.)")
                    .sqlPreview("SELECT DATE(o.created_at) AS day, SUM(oi.unit_price * oi.quantity) AS revenue\n"
                            + "FROM orders o JOIN order_items oi ON oi.order_id = o.id\n"
                            + "WHERE o.created_at >= NOW() - INTERVAL 7 DAY\n"
                            + "GROUP BY day ORDER BY day;")
                    .chartType(ChatResponse.ChartType.LINE)
                    .rows(List.of(
                            row("Mon", 4200d), row("Tue", 5100d), row("Wed", 4850d),
                            row("Thu", 6200d), row("Fri", 7100d), row("Sat", 8400d), row("Sun", 7600d)
                    ))
                    .build();
        }

        return ChatResponse.builder()
                .status(ChatResponse.Status.ANSWER)
                .narrative("Top-selling products in your " + scopeLabel(user) + " this month. "
                        + "(Demo response — real query execution arrives in step 3.)")
                .sqlPreview("SELECT p.name, SUM(oi.quantity) AS units\n"
                        + "FROM order_items oi JOIN products p ON p.id = oi.product_id\n"
                        + "JOIN orders o ON o.id = oi.order_id\n"
                        + "WHERE MONTH(o.created_at) = MONTH(NOW())\n"
                        + "GROUP BY p.id ORDER BY units DESC LIMIT 5;")
                .chartType(ChatResponse.ChartType.BAR)
                .rows(List.of(
                        row("Wireless Earbuds", 284d),
                        row("Smart Watch", 217d),
                        row("Bluetooth Speaker", 196d),
                        row("Mechanical Keyboard", 178d),
                        row("USB-C Hub", 143d)
                ))
                .build();
    }

    private boolean isOutOfScope(String q) {
        String lower = q.toLowerCase();
        String[] offTopic = {
                "weather", "stock price", "bitcoin", "joke", "poem", "recipe",
                "translate", "write code", "capital of", "who is", "who are you"
        };
        for (String s : offTopic) if (lower.contains(s)) return true;
        return false;
    }

    private ChatResponse blocked(String type, String trigger, String action, String narrative) {
        return ChatResponse.builder()
                .status(ChatResponse.Status.BLOCKED)
                .narrative(narrative)
                .guardrail(ChatResponse.Guardrail.builder()
                        .type(type)
                        .trigger(trigger)
                        .action(action)
                        .build())
                .build();
    }

    private ChatResponse.DataRow row(String label, double value) {
        return ChatResponse.DataRow.builder().label(label).value(value).build();
    }

    private String firstMatch(Pattern p, String s) {
        Matcher m = p.matcher(s);
        return m.find() ? "\"" + m.group(0) + "\"" : "(matched)";
    }

    private Long resolveStoreScope(User user) {
        if (user == null || user.getRole() != Role.CORPORATE) return null;
        List<Store> stores = storeRepository.findByOwnerId(user.getId());
        if (stores.isEmpty()) return null;
        return stores.get(0).getId();
    }

    private Long resolveStoreOwnerScope(User user) {
        if (user == null || user.getRole() != Role.CORPORATE) return null;
        return user.getId();
    }

    private String scopeLabel(User user) {
        if (user == null) return "account";
        return switch (user.getRole()) {
            case ADMIN -> "platform";
            case CORPORATE -> "store";
            case INDIVIDUAL -> "account";
        };
    }

    private String safeFirstName(User user) {
        if (user == null || user.getFirstName() == null) return "there";
        return user.getFirstName();
    }

    private String truncate(String s, int n) {
        if (s == null) return "";
        return s.length() <= n ? s : s.substring(0, n) + "…";
    }
}
