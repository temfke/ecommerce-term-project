package com.ecommerce.backend.service;

import org.springframework.stereotype.Component;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Sliding-window rate limiter — caps each user at N requests per WINDOW_MS.
 *
 *  Per-process, in-memory. Adequate for a single-instance backend; would need
 *  Redis or a token bucket service if the backend ever scales horizontally.
 */
@Component
public class ChatRateLimiter {

    private static final int MAX_REQUESTS = 10;
    private static final long WINDOW_MS = 60_000;

    private final Map<Long, Deque<Long>> requestsByUser = new ConcurrentHashMap<>();

    /** True if the request is allowed (and recorded), false if the user is over budget. */
    public boolean tryAcquire(Long userId) {
        long now = System.currentTimeMillis();
        Deque<Long> deque = requestsByUser.computeIfAbsent(userId, k -> new ArrayDeque<>());
        synchronized (deque) {
            while (!deque.isEmpty() && deque.peekFirst() < now - WINDOW_MS) {
                deque.pollFirst();
            }
            if (deque.size() >= MAX_REQUESTS) {
                return false;
            }
            deque.addLast(now);
            return true;
        }
    }
}
