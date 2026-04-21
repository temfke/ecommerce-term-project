package com.ecommerce.backend.config;

import lombok.RequiredArgsConstructor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class EmailVerificationMigration implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(EmailVerificationMigration.class);

    private final JdbcTemplate jdbc;

    @Override
    public void run(String... args) {
        try {
            int updated = jdbc.update(
                    "UPDATE users SET email_verified = TRUE " +
                    "WHERE email_verified = FALSE AND email_verification_token IS NULL"
            );
            if (updated > 0) {
                log.info("Auto-verified {} legacy users without a pending verification token", updated);
            }
        } catch (Exception ex) {
            log.warn("Skipping email verification migration: {}", ex.getMessage());
        }
    }
}
