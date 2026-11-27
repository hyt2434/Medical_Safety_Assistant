-- Optional single-database deployment. Public Auth tables remain in place.
-- No passwords, grants, sessions or retained Core history are rewritten.
CREATE OR REPLACE FUNCTION identity.register_auth_user() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO identity.users(id) VALUES (NEW.user_id) ON CONFLICT(id) DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER register_core_identity
AFTER INSERT ON public.users
FOR EACH ROW EXECUTE FUNCTION identity.register_auth_user();

INSERT INTO identity.users(id)
SELECT user_id FROM public.users
ON CONFLICT(id) DO NOTHING;
