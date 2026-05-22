CREATE OR REPLACE FUNCTION validate_promotion_for_order(
    p_order_id UUID,
    p_promotion_id UUID,
    p_order_promotion_id UUID DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    promo_row promotion%ROWTYPE;
    usage_count INTEGER;
    ticket_count INTEGER;
    invalid_event_title TEXT;
    invalid_event_date DATE;
BEGIN
    SELECT *
    INTO promo_row
    FROM promotion
    WHERE promotion_id = p_promotion_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'ERROR: Promotion dengan ID % tidak ditemukan.', p_promotion_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM "order"
        WHERE order_id = p_order_id
    ) THEN
        RAISE EXCEPTION 'ERROR: Order dengan ID % tidak ditemukan.', p_order_id;
    END IF;

    SELECT COUNT(*)
    INTO usage_count
    FROM order_promotion
    WHERE promotion_id = p_promotion_id
      AND (
          p_order_promotion_id IS NULL
          OR order_promotion_id <> p_order_promotion_id
      );

    IF usage_count >= promo_row.usage_limit THEN
        RAISE EXCEPTION 'ERROR: Promotion "%" telah mencapai batas maksimum penggunaan.', promo_row.promo_code;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM order_promotion
        WHERE order_id = p_order_id
          AND promotion_id = p_promotion_id
          AND (
              p_order_promotion_id IS NULL
              OR order_promotion_id <> p_order_promotion_id
          )
    ) THEN
        RAISE EXCEPTION 'ERROR: Promotion "%" sudah digunakan pada order ini.', promo_row.promo_code;
    END IF;

    SELECT COUNT(*)
    INTO ticket_count
    FROM ticket
    WHERE torder_id = p_order_id;

    IF ticket_count = 0 THEN
        RAISE EXCEPTION 'ERROR: Order belum memiliki tiket sehingga promotion belum bisa divalidasi.';
    END IF;

    SELECT e.event_title, e.event_datetime::date
    INTO invalid_event_title, invalid_event_date
    FROM ticket t
    JOIN ticket_category tc ON tc.category_id = t.tcategory_id
    JOIN event e ON e.event_id = tc.tevent_id
    WHERE t.torder_id = p_order_id
      AND (
          e.event_datetime::date < promo_row.start_date
          OR e.event_datetime::date > promo_row.end_date
      )
    ORDER BY e.event_datetime
    LIMIT 1;

    IF invalid_event_date IS NOT NULL THEN
        RAISE EXCEPTION
            'ERROR: Promotion "%" tidak berlaku untuk event "%" pada tanggal %.',
            promo_row.promo_code,
            invalid_event_title,
            invalid_event_date;
    END IF;
END;
$$ LANGUAGE plpgsql;


CREATE OR REPLACE FUNCTION trg_order_promotion_validate_fn()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM validate_promotion_for_order(
        NEW.order_id,
        NEW.promotion_id,
        NEW.order_promotion_id
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_promotion_validate ON order_promotion;

CREATE TRIGGER trg_order_promotion_validate
BEFORE INSERT OR UPDATE ON order_promotion
FOR EACH ROW
EXECUTE FUNCTION trg_order_promotion_validate_fn();


CREATE OR REPLACE FUNCTION trg_ticket_validate_existing_promotion_fn()
RETURNS TRIGGER AS $$
DECLARE
    promo_row RECORD;
    target_event_title TEXT;
    target_event_date DATE;
BEGIN
    SELECT e.event_title, e.event_datetime::date
    INTO target_event_title, target_event_date
    FROM ticket_category tc
    JOIN event e ON e.event_id = tc.tevent_id
    WHERE tc.category_id = NEW.tcategory_id;

    IF target_event_date IS NULL THEN
        RAISE EXCEPTION 'ERROR: Event untuk kategori tiket tidak ditemukan.';
    END IF;

    FOR promo_row IN
        SELECT p.promo_code, p.start_date, p.end_date
        FROM order_promotion op
        JOIN promotion p ON p.promotion_id = op.promotion_id
        WHERE op.order_id = NEW.torder_id
    LOOP
        IF target_event_date < promo_row.start_date
           OR target_event_date > promo_row.end_date THEN
            RAISE EXCEPTION
                'ERROR: Promotion "%" tidak berlaku untuk event "%" pada tanggal %.',
                promo_row.promo_code,
                target_event_title,
                target_event_date;
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ticket_validate_existing_promotion ON ticket;

CREATE TRIGGER trg_ticket_validate_existing_promotion
BEFORE INSERT OR UPDATE OF tcategory_id, torder_id ON ticket
FOR EACH ROW
EXECUTE FUNCTION trg_ticket_validate_existing_promotion_fn();