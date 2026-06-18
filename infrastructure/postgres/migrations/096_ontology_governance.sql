-- =====================================================================
-- 096_ontology_governance.sql
--
-- P2.2 + P2.3 of orchestration hardening: ontology lifecycle FSM +
-- edge taxonomy governance (per anh's review §4: "Edge taxonomy
-- governance" + "Lifecycle FSM strict constraints").
--
-- Two tables:
--   lifecycle_state_transitions   strict FSM rules for customer/asset
--                                  lifecycle moves (lead → customer → ...)
--   ontology_edge_types           authoritative edge type registry
--                                  (no free-form edges)
--
-- Both seeded with the v0 strict graph. Adding a new edge type or
-- lifecycle transition = DB migration (deliberate friction prevents
-- ontology drift).
-- =====================================================================

BEGIN;

-- ─── lifecycle_state_transitions ─────────────────────────────────────
-- Whitelist of allowed lifecycle state moves per entity_type. App
-- code MUST validate against this table before UPDATE.

CREATE TABLE IF NOT EXISTS lifecycle_state_transitions (
    transition_id     UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type       VARCHAR(64)     NOT NULL,
    from_state        VARCHAR(64)     NOT NULL,
    to_state          VARCHAR(64)     NOT NULL,
    requires_event    VARCHAR(128),
    requires_role     VARCHAR(32),
    is_recovery       BOOLEAN         NOT NULL DEFAULT FALSE,
    description       TEXT            NOT NULL DEFAULT '',
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, from_state, to_state)
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_transitions_by_type
    ON lifecycle_state_transitions(entity_type, from_state);

-- Seed: customer lifecycle (Stage 5 ontology FSM mention in PIPELINE_UNIFIED §5)
INSERT INTO lifecycle_state_transitions
    (entity_type, from_state, to_state, requires_event, requires_role, is_recovery, description)
VALUES
    ('customer', 'lead',           'active_customer', 'first_purchase', NULL, FALSE,
     'Lead converts on first paying transaction.'),
    ('customer', 'active_customer','at_risk',         'risk_signal',     NULL, FALSE,
     'Health score drop or churn signal lands.'),
    ('customer', 'at_risk',        'active_customer', 'recovery_signal', NULL, FALSE,
     'Intervention worked + signals back to healthy.'),
    ('customer', 'at_risk',        'churned',         'churn_confirmed', NULL, FALSE,
     'Customer cancelled or NPS hit -10 floor.'),
    ('customer', 'active_customer','churned',         'cancellation',    NULL, FALSE,
     'Direct cancellation skipping at_risk stage.'),
    ('customer', 'churned',        'lead',            'win_back',        'MANAGER', TRUE,
     'Win-back campaign — MANAGER approval + win_back event required.'),
    -- Asset lifecycle (Stage 5 mention)
    ('asset', 'draft',     'published',    'publish_action',  'EDITOR', FALSE, ''),
    ('asset', 'published', 'archived',     'archive_action',  'EDITOR', FALSE, ''),
    ('asset', 'archived',  'published',    'unarchive_action', 'OWNER', TRUE,
     'Unarchive requires OWNER role + explicit unarchive event.')
ON CONFLICT (entity_type, from_state, to_state) DO NOTHING;


-- ─── ontology_edge_types ─────────────────────────────────────────────
-- Authoritative edge registry. Neo4j adapter MUST validate against
-- this before inserting any edge — free-form edges blocked.

CREATE TABLE IF NOT EXISTS ontology_edge_types (
    edge_type_key     VARCHAR(64)     PRIMARY KEY,
    source_primitive  VARCHAR(32)     NOT NULL
                        CHECK (source_primitive IN (
                          'customer','transaction','product','location',
                          'time','channel','outcome'
                        )),
    target_primitive  VARCHAR(32)     NOT NULL
                        CHECK (target_primitive IN (
                          'customer','transaction','product','location',
                          'time','channel','outcome'
                        )),
    cardinality       VARCHAR(16)     NOT NULL DEFAULT 'many_to_many'
                        CHECK (cardinality IN ('one_to_one','one_to_many',
                                                'many_to_one','many_to_many')),
    retention_days    INT             NOT NULL DEFAULT 730,
    governance_owner  VARCHAR(64)     NOT NULL DEFAULT 'platform',
    description       TEXT            NOT NULL DEFAULT '',
    deprecated_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ontology_edge_active
    ON ontology_edge_types(source_primitive, target_primitive)
    WHERE deprecated_at IS NULL;

-- Seed: v0 governance-approved edge taxonomy.
-- Naming convention: SOURCE_VERB_TARGET.
-- Frozen — adding a new edge type = explicit migration + ADR.
INSERT INTO ontology_edge_types
    (edge_type_key, source_primitive, target_primitive, cardinality, governance_owner, description)
VALUES
    ('CUSTOMER_PURCHASED_PRODUCT',     'customer', 'product',     'many_to_many', 'platform',
     'Customer bought product (any transaction).'),
    ('CUSTOMER_CONTACTED_SUPPORT',     'customer', 'outcome',     'many_to_many', 'cs',
     'Customer opened a support ticket — outcome holds the resolution state.'),
    ('CUSTOMER_REGISTERED_AT_LOCATION','customer', 'location',    'many_to_one',  'platform',
     'Primary location for the customer (billing or signup).'),
    ('CUSTOMER_PREFERS_CHANNEL',       'customer', 'channel',     'many_to_many', 'marketing',
     'Inferred channel preference (Slack/email/Zalo/etc.).'),
    ('TRANSACTION_OCCURRED_AT_TIME',   'transaction','time',      'many_to_one',  'platform',
     'Anchor a transaction event to a Time primitive (snapshot).'),
    ('TRANSACTION_FOR_CUSTOMER',       'transaction','customer',  'many_to_one',  'platform',
     'Inverse of CUSTOMER_PURCHASED_PRODUCT — owner of the transaction.'),
    ('TRANSACTION_INVOLVES_PRODUCT',   'transaction','product',   'many_to_many', 'platform',
     'Line-item association.'),
    ('TRANSACTION_VIA_CHANNEL',        'transaction','channel',   'many_to_one',  'platform',
     'Acquisition or fulfillment channel for the transaction.'),
    ('PRODUCT_SOLD_AT_LOCATION',       'product',  'location',    'many_to_many', 'warehouse',
     'Distribution availability.'),
    ('OUTCOME_RELATES_TO_CUSTOMER',    'outcome',  'customer',    'many_to_one',  'platform',
     'Service outcome record anchored to its customer.'),
    ('OUTCOME_AT_TIME',                'outcome',  'time',        'many_to_one',  'platform',
     'When the outcome was recorded.')
ON CONFLICT (edge_type_key) DO NOTHING;


-- RLS — these are governance tables, readable by all tenants (not
-- tenant-scoped data, just the schema rules).
-- We deliberately do NOT enable RLS — both tables are read-mostly
-- platform config + the seed values are not sensitive.

COMMIT;
