-- =========================================
--  TEMİZ KURULUM
-- =========================================
DROP SCHEMA IF EXISTS yemek_kuyrugu CASCADE;

-- =========================================
--  ŞEMA OLUŞTUR
-- =========================================
CREATE SCHEMA yemek_kuyrugu;
SET search_path TO yemek_kuyrugu;

-- =========================================
--  ENUM TİPLERİ
-- =========================================

CREATE TYPE user_role AS ENUM ('USER', 'RESTAURANT');

CREATE TYPE order_status AS ENUM (
    'PAYMENT_SUCCESS',
    'CONFIRMED',
    'CANCELLED',
    'REJECTED'
);

-- =========================================
--  TABLOLAR
-- =========================================

CREATE TABLE restaurants (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    address         TEXT,
    phone           VARCHAR(50),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    password        VARCHAR(255) NOT NULL,
    role            user_role NOT NULL,
    restaurant_id   INTEGER REFERENCES restaurants(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE orders (
    id              VARCHAR(64) PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id   INTEGER NOT NULL REFERENCES restaurants(id) ON DELETE CASCADE,

    amount          NUMERIC(10,2) NOT NULL,
    items           JSONB NOT NULL,

    status          order_status NOT NULL,
    transaction_id  VARCHAR(64),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status_history  JSONB NOT NULL DEFAULT '[]'::JSONB
);

CREATE TABLE session_tokens (
    token       UUID PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ
);

-- =========================================
--  İNDEKSLER
-- =========================================

CREATE INDEX idx_orders_user_id
    ON orders(user_id);

CREATE INDEX idx_orders_restaurant_id
    ON orders(restaurant_id);

CREATE INDEX idx_orders_status
    ON orders(status);

CREATE INDEX idx_users_role
    ON users(role);

CREATE INDEX idx_users_restaurant_id
    ON users(restaurant_id);

-- =========================================
--  ÖRNEK VERİLER
-- =========================================

INSERT INTO restaurants (name, address, phone)
VALUES ('Kimo Burger', 'Merkez Mah. 123. Sokak No:5', '0532 000 00 00');

INSERT INTO users (username, password, role)
VALUES ('ali', '1234', 'USER');

INSERT INTO users (username, password, role, restaurant_id)
VALUES ('kimo_owner', '1234', 'RESTAURANT', 1);
