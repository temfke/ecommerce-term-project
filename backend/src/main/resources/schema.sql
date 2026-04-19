-- ============================================================
-- E-Commerce Analytics Platform - Database Schema
-- Matches the Recommended Schema from the project document
-- ============================================================

CREATE DATABASE IF NOT EXISTS ecommerce_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE ecommerce_db;

-- ============================================================
-- 1. USERS (id, email, password_hash, role_type, gender)
--    Source: DS1 CustomerID, DS2 Demographics, DS3 Gender, DS6 CustomerID
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT          AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    first_name      VARCHAR(100)    NOT NULL,
    last_name       VARCHAR(100)    NOT NULL,
    role            ENUM('ADMIN', 'CORPORATE', 'INDIVIDUAL') NOT NULL,
    gender          VARCHAR(20),
    phone           VARCHAR(30),
    enabled         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_users_email (email),
    INDEX idx_users_role (role)
) ENGINE=InnoDB;

-- ============================================================
-- 2. CATEGORIES (id, name, parent_id)
--    Source: DS4 Category, DS5 CategoryName, DS6 ProductCategory
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id              BIGINT          AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    description     VARCHAR(500),
    parent_id       BIGINT,

    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES categories(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- 3. STORES (id, owner_id, name, status)
--    Source: derived from DS4 SalesChannel, DS5 store grouping
-- ============================================================
CREATE TABLE IF NOT EXISTS stores (
    id              BIGINT          AUTO_INCREMENT PRIMARY KEY,
    owner_id        BIGINT          NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    description     TEXT,
    logo_url        VARCHAR(500),
    status          ENUM('PENDING_APPROVAL', 'OPEN', 'CLOSED', 'SUSPENDED') NOT NULL DEFAULT 'PENDING_APPROVAL',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_stores_owner (owner_id),
    INDEX idx_stores_status (status),
    CONSTRAINT fk_store_owner FOREIGN KEY (owner_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 4. CUSTOMER_PROFILES (id, user_id, age, city, membership_type)
--    Source: DS2 full (Gender, Age, City, MembershipType, TotalSpend,
--            ItemsPurchased, AvgRating, SatisfactionLevel)
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_profiles (
    id                  BIGINT          AUTO_INCREMENT PRIMARY KEY,
    user_id             BIGINT          NOT NULL UNIQUE,
    age                 INT,
    city                VARCHAR(100),
    country             VARCHAR(100),
    membership_type     VARCHAR(50),
    total_spend         DECIMAL(12,2),
    items_purchased     INT,
    avg_rating          DECIMAL(3,2),
    prior_purchases     INT,
    satisfaction_level  VARCHAR(50),

    CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 5. PRODUCTS (id, store_id, category_id, sku, name, unit_price)
--    Source: DS1 (StockCode, Description, UnitPrice),
--            DS3 CostOfProduct, DS4/DS5 SKU, DS6 ProductTitle
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id              BIGINT          AUTO_INCREMENT PRIMARY KEY,
    store_id        BIGINT          NOT NULL,
    category_id     BIGINT,
    sku             VARCHAR(50)     NOT NULL UNIQUE,
    name            VARCHAR(300)    NOT NULL,
    description     TEXT,
    unit_price      DECIMAL(10,2)   NOT NULL,
    stock_quantity  INT             NOT NULL DEFAULT 0,
    image_url       VARCHAR(500),
    active          BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_products_store (store_id),
    INDEX idx_products_category (category_id),
    INDEX idx_products_sku (sku),
    CONSTRAINT fk_product_store FOREIGN KEY (store_id) REFERENCES stores(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_product_category FOREIGN KEY (category_id) REFERENCES categories(id)
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- 6. ORDERS (id, user_id, store_id, status, grand_total)
--    Source: DS1 (InvoiceNo, InvoiceDate, CustomerID),
--            DS4 (OrderID, Status, Fulfilment, SalesChannel),
--            DS5 (ItemID, Status, GrandTotal, PaymentMethod)
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    id                  BIGINT          AUTO_INCREMENT PRIMARY KEY,
    user_id             BIGINT          NOT NULL,
    store_id            BIGINT          NOT NULL,
    status              ENUM('PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED') NOT NULL DEFAULT 'PENDING',
    grand_total         DECIMAL(12,2)   NOT NULL,
    payment_method      ENUM('CREDIT_CARD', 'DEBIT_CARD', 'PAYPAL', 'BANK_TRANSFER', 'CASH_ON_DELIVERY'),
    shipping_address    TEXT,
    sales_channel       VARCHAR(100),
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_orders_user (user_id),
    INDEX idx_orders_store (store_id),
    INDEX idx_orders_status (status),
    CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_order_store FOREIGN KEY (store_id) REFERENCES stores(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 7. ORDER_ITEMS (id, order_id, product_id, quantity, price)
--    Source: DS1 (Quantity, UnitPrice per line),
--            DS5 (QtyOrdered, Price)
-- ============================================================
CREATE TABLE IF NOT EXISTS order_items (
    id                  BIGINT          AUTO_INCREMENT PRIMARY KEY,
    order_id            BIGINT          NOT NULL,
    product_id          BIGINT          NOT NULL,
    quantity            INT             NOT NULL,
    price               DECIMAL(10,2)   NOT NULL,
    discount_applied    DECIMAL(5,2),

    INDEX idx_oi_order (order_id),
    INDEX idx_oi_product (product_id),
    CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_oi_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 8. SHIPMENTS (id, order_id, warehouse, mode, status)
--    Source: DS3 full (WarehouseBlock, ModeOfShipment),
--            DS4 ShipServiceLevel
-- ============================================================
CREATE TABLE IF NOT EXISTS shipments (
    id                  BIGINT          AUTO_INCREMENT PRIMARY KEY,
    order_id            BIGINT          NOT NULL UNIQUE,
    tracking_id         VARCHAR(100),
    carrier             VARCHAR(100),
    warehouse_block     VARCHAR(50),
    mode_of_shipment    VARCHAR(50),
    destination         VARCHAR(300),
    status              ENUM('PENDING', 'PROCESSING', 'IN_TRANSIT', 'DELIVERED', 'RETURNED') NOT NULL DEFAULT 'PENDING',
    estimated_delivery  DATETIME,
    shipped_at          DATETIME,
    delivered_at        DATETIME,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_shipments_status (status),
    CONSTRAINT fk_shipment_order FOREIGN KEY (order_id) REFERENCES orders(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 9. REVIEWS (id, user_id, product_id, star_rating, sentiment)
--    Source: DS6 full (Marketplace, ReviewID, ProductID,
--            StarRating, HelpfulVotes, TotalVotes)
-- ============================================================
CREATE TABLE IF NOT EXISTS reviews (
    id              BIGINT          AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT          NOT NULL,
    product_id      BIGINT          NOT NULL,
    star_rating     INT             NOT NULL CHECK (star_rating BETWEEN 1 AND 5),
    review_body     TEXT,
    sentiment       VARCHAR(20),
    helpful_votes   INT             DEFAULT 0,
    total_votes     INT             DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_reviews_product (product_id),
    INDEX idx_reviews_user (user_id),
    CONSTRAINT fk_review_user FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_review_product FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE
) ENGINE=InnoDB;
