-- Read-only MySQL user for the chatbot's executor.
-- The sanitizer is the primary defense (blocks UPDATE/DELETE/sensitive columns
-- before we ever reach the DB). This user is the second layer: even if the
-- sanitizer misses something, MySQL itself rejects writes.
--
-- Run as root: mysql -u root -p ecommerce_db < setup-readonly-user.sql
-- (or paste into MySQL Workbench)

CREATE USER IF NOT EXISTS 'chatbot_ro'@'localhost' IDENTIFIED BY 'admin';

-- SELECT only, on the analytical tables. No DROP/INSERT/UPDATE/DELETE.
-- 'users' is included because most queries join through it; the sanitizer
-- still blocks password_hash / email_verification_* columns at the SQL level.
GRANT SELECT ON ecommerce_db.users              TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.stores             TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.products           TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.categories         TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.orders             TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.order_items        TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.shipments          TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.reviews            TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.customer_profiles  TO 'chatbot_ro'@'localhost';
GRANT SELECT ON ecommerce_db.addresses          TO 'chatbot_ro'@'localhost';

FLUSH PRIVILEGES;

-- Sanity-check the grants (run manually):
-- SHOW GRANTS FOR 'chatbot_ro'@'localhost';