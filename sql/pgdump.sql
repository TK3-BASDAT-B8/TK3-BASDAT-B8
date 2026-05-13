-- TikTakTuk DDL sesuai pgdump.sql yang diberikan
-- Run: psql -d tiktaktuk -f sql/ddl.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS user_account (
    user_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    username  VARCHAR(100)  UNIQUE NOT NULL,
    password  VARCHAR(255)  NOT NULL
);

CREATE TABLE IF NOT EXISTS role (
    role_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    role_name VARCHAR(50)  UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS account_role (
    role_id UUID REFERENCES role(role_id) ON DELETE CASCADE,
    user_id UUID REFERENCES user_account(user_id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, user_id)
);

CREATE TABLE IF NOT EXISTS customer (
    customer_id  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name    VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    user_id      UUID         UNIQUE NOT NULL REFERENCES user_account(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS organizer (
    organizer_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_name VARCHAR(100) NOT NULL,
    contact_email  VARCHAR(100),
    user_id        UUID         UNIQUE NOT NULL REFERENCES user_account(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS venue (
    venue_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_name VARCHAR(100) NOT NULL,
    capacity   INTEGER      NOT NULL CHECK (capacity > 0),
    address    TEXT         NOT NULL,
    city       VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS seat (
    seat_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    section     VARCHAR(50) NOT NULL,
    seat_number VARCHAR(10) NOT NULL,
    row_number  VARCHAR(10) NOT NULL,
    venue_id    UUID        NOT NULL REFERENCES venue(venue_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event (
    event_id       UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    event_datetime TIMESTAMP    NOT NULL,
    event_title    VARCHAR(200) NOT NULL,
    venue_id       UUID         NOT NULL REFERENCES venue(venue_id),
    organizer_id   UUID         NOT NULL REFERENCES organizer(organizer_id)
);

CREATE TABLE IF NOT EXISTS artist (
    artist_id UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name      VARCHAR(100) NOT NULL,
    genre     VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS event_artist (
    event_id  UUID REFERENCES event(event_id) ON DELETE CASCADE,
    artist_id UUID REFERENCES artist(artist_id) ON DELETE CASCADE,
    role      VARCHAR(100),
    PRIMARY KEY (event_id, artist_id)
);

CREATE TABLE IF NOT EXISTS ticket_category (
    category_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    category_name VARCHAR(50)   NOT NULL,
    quota         INTEGER       NOT NULL CHECK (quota > 0),
    price         NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    tevent_id     UUID          NOT NULL REFERENCES event(event_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "order" (
    order_id       UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_date     TIMESTAMP     NOT NULL,
    payment_status VARCHAR(20)   NOT NULL CHECK (payment_status IN ('Pending', 'Paid', 'Cancelled')),
    total_amount   NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    customer_id    UUID          NOT NULL REFERENCES customer(customer_id)
);

CREATE TABLE IF NOT EXISTS promotion (
    promotion_id   UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    promo_code     VARCHAR(50)   UNIQUE NOT NULL,
    discount_type  VARCHAR(20)   NOT NULL CHECK (discount_type IN ('NOMINAL', 'PERCENTAGE')),
    discount_value NUMERIC(12,2) NOT NULL CHECK (discount_value > 0),
    start_date     DATE          NOT NULL,
    end_date       DATE          NOT NULL,
    usage_limit    INTEGER       NOT NULL CHECK (usage_limit > 0)
);

CREATE TABLE IF NOT EXISTS order_promotion (
    order_promotion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    promotion_id       UUID NOT NULL REFERENCES promotion(promotion_id),
    order_id           UUID NOT NULL REFERENCES "order"(order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ticket (
    ticket_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_code VARCHAR(100) UNIQUE NOT NULL,
    tcategory_id UUID        NOT NULL REFERENCES ticket_category(category_id),
    torder_id   UUID         NOT NULL REFERENCES "order"(order_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS has_relationship (
    seat_id   UUID REFERENCES seat(seat_id) ON DELETE CASCADE,
    ticket_id UUID REFERENCES ticket(ticket_id) ON DELETE CASCADE,
    PRIMARY KEY (seat_id, ticket_id)
);
