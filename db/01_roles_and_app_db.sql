-- 1. Create two seperate login users with passwords
CREATE ROLE agent_readonly LOGIN PASSWORD :'ro_password';
CREATE ROLE agent_app      LOGIN PASSWORD :'app_password';

-- 2. Lock down the pagila database
REVOKE ALL ON DATABASE pagila FROM PUBLIC;
GRANT CONNECT ON DATABASE pagila TO agent_readonly;

-- 3. Lock down the schema
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO agent_readonly;

-- 4. The real security barrier: SELECT ONLY
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_readonly;

-- 5. Safety backups (Defense-in-depth)
ALTER ROLE agent_readonly SET statement_timeout = '5s';
ALTER ROLE agent_readonly SET default_transaction_read_only = on;

-- 6. Create the separate application database
CREATE DATABASE agent_app OWNER agent_app;
REVOKE ALL ON DATABASE agent_app FROM PUBLIC;