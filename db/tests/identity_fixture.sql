-- TEST ONLY. Never run against the identity team's database.
CREATE SCHEMA identity;
CREATE TABLE identity.users (id uuid PRIMARY KEY);
COMMENT ON SCHEMA identity IS 'Isolated Core DB test fixture; not USERS/RBAC implementation';
