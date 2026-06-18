-- 127_approval_gate_chain_binding.sql
-- ADR-0037 follow-up — wire the workflow approval_gate node to the multi-level
-- approval-chain system (migs 121-123). The runtime executor
-- (workflow_runtime/executors/approval.py) ALREADY consumes
-- config.approval_chain_id; this migration just declares the field in the node
-- catalog so the builder/validation know it is a first-class config key, and
-- ships a ui_schema so the FE renders a chain-picker + role-select.
--
-- Before: approval_gate config required {approver_role, timeout_action} and had
-- no way to reference a chain → the "Duyệt & Phân quyền" chains were unreachable
-- from a workflow step (the empty-permission gap anh hit during the
-- "Giải quyết khiếu nại" test).
--
-- After: required = {timeout_action} only; either approval_chain_id (preferred,
-- multi-level + SLA + escalation) OR approver_role (single-role fallback) must be
-- set — the one-of rule is enforced at run-readiness (routers/workflow_builder.py
-- _check_approval_gates), not by JSON Schema, so the catalog stays declarative.

UPDATE node_type_catalog SET
  config_schema_json = jsonb_build_object(
    'type', 'object',
    'required', jsonb_build_array('timeout_action'),
    'properties', jsonb_build_object(
      'approval_chain_id', jsonb_build_object(
        'type', 'string', 'format', 'uuid',
        'description', 'Chuỗi duyệt nhiều cấp (approval_chains). Ưu tiên hơn approver_role.'),
      'approver_role', jsonb_build_object(
        'type', 'string',
        'description', 'Vai trò duyệt đơn — fallback khi không gắn chuỗi.'),
      'message', jsonb_build_object('type', 'string'),
      'timeout_action', jsonb_build_object(
        'enum', jsonb_build_array('approve', 'reject', 'escalate'))
    )
  ),
  ui_schema_json = jsonb_build_object(
    'approval_chain_id', jsonb_build_object(
      'ui:widget', 'approval-chain-picker', 'ui:title', 'Chuỗi duyệt'),
    'approver_role', jsonb_build_object(
      'ui:widget', 'role-select', 'ui:title', 'Vai trò duyệt (fallback)'),
    'ui:order', jsonb_build_array(
      'approval_chain_id', 'approver_role', 'timeout_action', 'message')
  )
WHERE node_type_key = 'approval_gate';
