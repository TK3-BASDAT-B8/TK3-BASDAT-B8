CREATE OR REPLACE FUNCTION trg_event_artist_validate_fn()
RETURNS TRIGGER AS $$
DECLARE
    artist_name TEXT;
    event_title TEXT;
BEGIN
    SELECT name INTO artist_name FROM artist WHERE artist_id = NEW.artist_id;
    IF artist_name IS NULL THEN
        RAISE EXCEPTION 'Artist dengan ID % tidak ditemukan.', NEW.artist_id;
    END IF;

    SELECT e.event_title INTO event_title FROM event e WHERE e.event_id = NEW.event_id;
    IF event_title IS NULL THEN
        RAISE EXCEPTION 'Event dengan ID % tidak ditemukan.', NEW.event_id;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM event_artist ea
        WHERE ea.event_id = NEW.event_id
          AND ea.artist_id = NEW.artist_id
    ) THEN
        RAISE EXCEPTION 'Artist "%" sudah terdaftar pada event "%".', artist_name, event_title;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_event_artist_validate ON event_artist;
CREATE TRIGGER trg_event_artist_validate
BEFORE INSERT ON event_artist
FOR EACH ROW EXECUTE FUNCTION trg_event_artist_validate_fn();

CREATE OR REPLACE FUNCTION get_remaining_quota_by_event(p_event_id UUID)
RETURNS TABLE (
    category_id UUID,
    category_name VARCHAR,
    quota INTEGER,
    sold BIGINT,
    remaining BIGINT
) AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM event WHERE event_id = p_event_id) THEN
        RAISE EXCEPTION 'Event dengan ID % tidak ditemukan.', p_event_id;
    END IF;

    RETURN QUERY
    SELECT tc.category_id,
           tc.category_name,
           tc.quota,
           COUNT(t.ticket_id) AS sold,
           tc.quota - COUNT(t.ticket_id) AS remaining
    FROM ticket_category tc
    LEFT JOIN ticket t ON t.tcategory_id = tc.category_id
    WHERE tc.tevent_id = p_event_id
    GROUP BY tc.category_id, tc.category_name, tc.quota
    ORDER BY tc.category_name ASC;
END;
$$ LANGUAGE plpgsql;
