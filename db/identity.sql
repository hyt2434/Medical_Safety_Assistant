-- Local Core UUID registry. Auth account/role/password data stays in Auth DB.
-- Explicit installation only; existing registry structure/data is never altered.
CREATE SCHEMA IF NOT EXISTS identity;
CREATE TABLE IF NOT EXISTS identity.users (id uuid PRIMARY KEY);
