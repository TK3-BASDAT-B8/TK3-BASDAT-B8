CREATE OR REPLACE FUNCTION trg_venue_no_duplicate_fn()
RETURNS TRIGGER AS $$
DECLARE
    existing_id UUID;
BEGIN
    SELECT venue_id INTO existing_id
    FROM venue
    WHERE LOWER(venue_name) = LOWER(NEW.venue_name)
      AND LOWER(city) = LOWER(NEW.city)
      AND venue_id <> NEW.venue_id
    LIMIT 1;

    IF existing_id IS NOT NULL THEN
        RAISE EXCEPTION 'Venue "%" di kota "%" sudah terdaftar dengan ID %.', NEW.venue_name, NEW.city, existing_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_venue_no_duplicate ON venue;
CREATE TRIGGER trg_venue_no_duplicate
BEFORE INSERT OR UPDATE ON venue
FOR EACH ROW EXECUTE FUNCTION trg_venue_no_duplicate_fn();

CREATE OR REPLACE FUNCTION trg_venue_no_delete_active_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM event e
        WHERE e.venue_id = OLD.venue_id
          AND e.event_datetime >= NOW()
    ) THEN
        RAISE EXCEPTION 'Venue "%" masih memiliki event aktif sehingga tidak dapat dihapus.', OLD.venue_name;
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_venue_no_delete_active ON venue;
CREATE TRIGGER trg_venue_no_delete_active
BEFORE DELETE ON venue
FOR EACH ROW EXECUTE FUNCTION trg_venue_no_delete_active_fn();
