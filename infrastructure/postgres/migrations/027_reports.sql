-- Migration 027: F-038 Reports — auto LLM-generated reports.
--
-- (Note: 47-reports-hub.tsx and 48-report-auto.tsx template comments
-- mis-quote this feature as "F-053". F-053 is actually Performance
-- Tracking on the P4 personal portal; the correct ID for Reports is
-- F-038 per docs/BACKLOG.md line 117. Template comments will be
-- patched when those pages are wired to this backend in a follow-up
-- PR.)
--
-- Why this exists
-- ===============
-- Phase 1 had Insight + Decision Log + Pipeline result, but no
-- multi-section published report. F-038 closes that — a "monthly
-- summary" report (the seeded built-in template) joins gold_features
-- + analysis_runs into a structured JSON document the FE can render
-- as PDF / HTML / CSV.
--
-- Two tables:
--   * report_templates  — system-wide and per-tenant templates. Each
--                         carries a system prompt + a JSONSchema for
--                         the expected LLM output (used with the
--                         output_schema layer from PR #112 / Issue #3).
--   * reports           — one row per generated report instance.
--                         Status machine: queued → running → ready
--                         (terminal) | failed (terminal). content_json
--                         holds the validated LLM output.
--
-- RLS
-- ===
-- Both tables are tenant-scoped per K-1, with the standard
-- ``tenant_isolation`` policy + sibling ``admin_bypass`` policy
-- (matches the pattern from migration 025). Built-in templates have
-- ``enterprise_id IS NULL`` and are visible to every tenant via the
-- additional ``built_in_visible`` policy below.
--
-- Reversibility
-- =============
--   DROP TABLE reports;
--   DROP TABLE report_templates;
-- ============================================================

BEGIN;

-- ============================================================
-- 1. report_templates
-- ============================================================
CREATE TABLE IF NOT EXISTS report_templates (
    template_id      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),

    -- NULL for built-in templates shipped with the platform; non-NULL
    -- for tenant-customised templates. The built_in_visible policy
    -- below makes the NULL rows readable cross-tenant.
    enterprise_id    UUID         REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,

    name             VARCHAR(120) NOT NULL,
    description      TEXT,

    -- LLM system prompt for the generation call. Templated with
    -- {{enterprise_name}}, {{period}}, etc. via Jinja-style
    -- substitution at call time (the service handles rendering).
    system_prompt    TEXT         NOT NULL,

    -- JSONSchema (Draft 2020-12) for the expected LLM output. Passed
    -- verbatim to llm-gateway as ``output_schema`` so the validator
    -- + repair layer from PR #112 / Issue #3 enforces the shape.
    output_schema    JSONB        NOT NULL,

    is_built_in      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- A built-in template MUST have enterprise_id NULL; a tenant
    -- template MUST have enterprise_id set. Constraint catches the
    -- accident at INSERT time instead of after a confused listing.
    CONSTRAINT report_templates_built_in_xor_tenant CHECK (
        (is_built_in = TRUE  AND enterprise_id IS NULL)
     OR (is_built_in = FALSE AND enterprise_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_report_templates_tenant
    ON report_templates(enterprise_id, created_at DESC)
    WHERE enterprise_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_report_templates_built_in
    ON report_templates(template_id)
    WHERE is_built_in = TRUE;

ALTER TABLE report_templates ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    -- Per-tenant view (matches the standard pattern from migration 005).
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'report_templates' AND policyname = 'tenant_report_templates'
    ) THEN
        CREATE POLICY tenant_report_templates ON report_templates
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    -- Built-in templates visible to everyone. Permissive — ORs with
    -- tenant_report_templates so a tenant sees built-ins + their own.
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'report_templates' AND policyname = 'built_in_visible'
    ) THEN
        CREATE POLICY built_in_visible ON report_templates
            USING (is_built_in = TRUE);
    END IF;

    -- Cross-tenant aggregation path (matches migration 025).
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'report_templates' AND policyname = 'admin_bypass_report_templates'
    ) THEN
        CREATE POLICY admin_bypass_report_templates ON report_templates
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON report_templates TO kaori_app;

-- ============================================================
-- 2. reports
-- ============================================================
CREATE TABLE IF NOT EXISTS reports (
    report_id        UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID         NOT NULL REFERENCES enterprises(enterprise_id) ON DELETE CASCADE,
    template_id      UUID         NOT NULL REFERENCES report_templates(template_id) ON DELETE RESTRICT,

    -- Caller-supplied parameters (period, dataset filter, recipients,
    -- etc.). Treated as opaque JSONB; the template's system prompt
    -- decides how to use them.
    params           JSONB        NOT NULL DEFAULT '{}'::jsonb,

    -- pii surface for the report list view (no need to re-derive from
    -- params on every list query).
    title            VARCHAR(200) NOT NULL,
    owner_email      VARCHAR(320) NOT NULL,

    -- State machine. Terminal states (ready / failed) never transition.
    -- 'failed' rows keep last_error so the FE can show "regenerate?".
    status           VARCHAR(20)  NOT NULL DEFAULT 'queued'
                                    CHECK (status IN ('queued', 'running', 'ready', 'failed')),

    -- Validated LLM output (matches the template's output_schema). NULL
    -- until status='ready'.
    content_json     JSONB,

    -- Free-text narrative summary the model writes alongside the
    -- structured payload. Useful as the email body / first paragraph
    -- of the report. NULL until status='ready'.
    narrative        TEXT,

    last_error       TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);

-- Hot path: the FE list endpoint is "show me my recent reports".
CREATE INDEX IF NOT EXISTS idx_reports_tenant_created
    ON reports(enterprise_id, created_at DESC);

-- Background workers and ops dashboards filter by status.
CREATE INDEX IF NOT EXISTS idx_reports_pending
    ON reports(created_at)
    WHERE status IN ('queued', 'running');

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'reports' AND policyname = 'tenant_reports'
    ) THEN
        CREATE POLICY tenant_reports ON reports
            USING (enterprise_id = current_setting('app.enterprise_id', true)::UUID);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'reports' AND policyname = 'admin_bypass_reports'
    ) THEN
        CREATE POLICY admin_bypass_reports ON reports
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON reports TO kaori_app;

-- ============================================================
-- 3. Built-in template seed: monthly_summary
-- ============================================================
-- One built-in template ships with the platform so a fresh tenant
-- has something to generate on day 1. The output_schema mirrors the
-- minimum the FE needs to render the report (top KPIs, trend
-- highlights, top risks, recommendations).
INSERT INTO report_templates
    (template_id, enterprise_id, name, description, system_prompt,
     output_schema, is_built_in)
VALUES (
    '00000000-0000-0000-0000-000000000001',  -- stable id so service code can reference
    NULL,
    'Báo cáo tổng hợp tháng',
    'Tổng quan KPIs, xu hướng nổi bật, rủi ro cao nhất, và khuyến nghị '
    'hành động dựa trên dữ liệu phân tích trong kỳ. Dùng làm báo cáo '
    'gửi ban lãnh đạo hàng tháng.',
    -- system prompt — placeholders ({{enterprise_name}}, {{period}})
    -- substituted by the service at call time.
    'Bạn là trợ lý phân tích dữ liệu của {{enterprise_name}}. Dựa trên '
    'tóm tắt các phân tích đã chạy trong kỳ {{period}} (cung cấp ở phần '
    'người dùng), hãy tạo báo cáo tổng hợp tháng theo đúng schema JSON '
    'được cung cấp. Yêu cầu: '
    '(1) Mọi số liệu phải dẫn nguồn từ dữ liệu thực, không bịa. '
    '(2) Khuyến nghị phải hành động được, không chung chung. '
    '(3) Trả về CHỈ JSON object hợp schema, không markdown, không giải thích.',
    -- output_schema — the LLM gateway validates against this and
    -- repairs once if the model misses the shape.
    '{
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "additionalProperties": false,
      "required": ["kpi_overview", "trends", "top_risks", "recommendations"],
      "properties": {
        "kpi_overview": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["label", "value", "trend"],
            "properties": {
              "label": {"type": "string"},
              "value": {"type": "string"},
              "trend": {"type": "string", "enum": ["up", "down", "flat"]}
            }
          }
        },
        "trends": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["title", "summary"],
            "properties": {
              "title":   {"type": "string"},
              "summary": {"type": "string"}
            }
          }
        },
        "top_risks": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["risk", "severity"],
            "properties": {
              "risk":     {"type": "string"},
              "severity": {"type": "string", "enum": ["low", "medium", "high"]}
            }
          }
        },
        "recommendations": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["action", "owner_role", "deadline_relative"],
            "properties": {
              "action":            {"type": "string"},
              "owner_role":        {"type": "string"},
              "deadline_relative": {"type": "string"}
            }
          }
        }
      }
    }'::jsonb,
    TRUE
)
ON CONFLICT (template_id) DO NOTHING;

COMMIT;
