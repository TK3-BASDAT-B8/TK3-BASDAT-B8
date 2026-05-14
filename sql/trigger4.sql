CREATE OR REPLACE FUNCTION trg_order_promotion_validate_fn()
RETURNS TRIGGER AS $$
DECLARE
    promo_row promotion%ROWTYPE;
    usage_count INTEGER;
    event_date DATE;
BEGIN
    SELECT * INTO promo_row
    FROM promotion
    WHERE promotion_id = NEW.promotion_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Promotion dengan ID % tidak ditemukan.', NEW.promotion_id;
    END IF;

    SELECT COUNT(*) INTO usage_count
    FROM order_promotion
    WHERE promotion_id = NEW.promotion_id;

    IF usage_count >= promo_row.usage_limit THEN
        RAISE EXCEPTION 'Promotion "%" telah mencapai batas maksimum penggunaan.', promo_row.promo_code;
    END IF;

    SELECT e.event_datetime::date INTO event_date
    FROM ticket t
    JOIN ticket_category tc ON tc.category_id = t.tcategory_id
    JOIN event e ON e.event_id = tc.tevent_id
    WHERE t.torder_id = NEW.order_id
    ORDER BY e.event_datetime
    LIMIT 1;

    IF event_date IS NOT NULL AND (event_date < promo_row.start_date OR event_date > promo_row.end_date) THEN
        RAISE EXCEPTION 'Promotion "%" tidak berlaku untuk tanggal event ini.', promo_row.promo_code;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_promotion_validate ON order_promotion;
CREATE TRIGGER trg_order_promotion_validate
BEFORE INSERT ON order_promotion
FOR EACH ROW EXECUTE FUNCTION trg_order_promotion_validate_fn();
