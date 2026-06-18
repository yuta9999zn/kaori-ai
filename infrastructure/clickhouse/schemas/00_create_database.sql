-- Bootstrap — create the kaori_silver database before any table DDL.
-- The 00_ prefix ensures it runs first under ClickHouse's
-- /docker-entrypoint-initdb.d/ lexicographic order.

CREATE DATABASE IF NOT EXISTS kaori_silver
    COMMENT 'Kaori Silver tier — cleaned + typed + PII-masked event store. ADR-0012 polyglot persistence.';
