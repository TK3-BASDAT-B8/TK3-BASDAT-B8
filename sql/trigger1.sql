CREATE OR REPLACE FUNCTION trg_user_account_validate_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.username !~ '^[A-Za-z0-9]+$' THEN
        RAISE EXCEPTION 'Username "%" hanya boleh mengandung huruf dan angka tanpa simbol atau spasi.', NEW.username;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM user_account ua
        WHERE LOWER(ua.username) = LOWER(NEW.username)
          AND ua.user_id <> NEW.user_id
    ) THEN
        RAISE EXCEPTION 'Username "%" sudah terdaftar, gunakan username lain.', NEW.username;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_user_account_validate ON user_account;
CREATE TRIGGER trg_user_account_validate
BEFORE INSERT OR UPDATE ON user_account
FOR EACH ROW EXECUTE FUNCTION trg_user_account_validate_fn();
