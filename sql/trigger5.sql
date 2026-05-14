CREATE OR REPLACE FUNCTION trg_seat_no_delete_if_assigned_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM has_relationship WHERE seat_id = OLD.seat_id) THEN
        RAISE EXCEPTION 'Kursi % - Baris % No. % tidak dapat dihapus karena sudah terisi.', OLD.section, OLD.row_number, OLD.seat_number;
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_seat_no_delete_if_assigned ON seat;
CREATE TRIGGER trg_seat_no_delete_if_assigned
BEFORE DELETE ON seat
FOR EACH ROW EXECUTE FUNCTION trg_seat_no_delete_if_assigned_fn();

CREATE OR REPLACE FUNCTION trg_ticket_check_quota_fn()
RETURNS TRIGGER AS $$
DECLARE
    quota_limit INTEGER;
    sold_count INTEGER;
    category_label TEXT;
BEGIN
    SELECT quota, category_name
    INTO quota_limit, category_label
    FROM ticket_category
    WHERE category_id = NEW.tcategory_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Kategori tiket tidak ditemukan.';
    END IF;

    SELECT COUNT(*) INTO sold_count
    FROM ticket
    WHERE tcategory_id = NEW.tcategory_id;

    IF sold_count >= quota_limit THEN
        RAISE EXCEPTION 'Kuota kategori tiket "%" sudah penuh. Tidak dapat membuat tiket baru.', category_label;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ticket_check_quota ON ticket;
CREATE TRIGGER trg_ticket_check_quota
BEFORE INSERT ON ticket
FOR EACH ROW EXECUTE FUNCTION trg_ticket_check_quota_fn();
