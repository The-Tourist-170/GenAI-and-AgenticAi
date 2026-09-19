\connect northwind;

-- 1. Create a dedicated read-only user for the AI agent
CREATE USER agent_user WITH PASSWORD 'readonly123';

-- 2. Grant connection and read permissions
GRANT CONNECT ON DATABASE northwind TO agent_user;
GRANT USAGE ON SCHEMA public TO agent_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_user;

-- 3. Lock down permissions: disallow creating any new tables/objects
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM agent_user;

-- 4. Ensure any future tables default to SELECT only
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_user;

-- 5. Force all sessions from this user into read-only transaction mode
ALTER USER agent_user SET default_transaction_read_only = on;
