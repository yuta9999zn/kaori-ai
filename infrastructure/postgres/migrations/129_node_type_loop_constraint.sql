-- 129_node_type_loop_constraint.sql
-- #7 Loop/for-each — widen workflow_nodes.chk_node_type (mig 060) to allow the
-- two loop control node types. Pairs with mig 128 (catalog rows) + the pydantic
-- node_type pattern in routers/workflow_builder.py.

ALTER TABLE workflow_nodes DROP CONSTRAINT IF EXISTS chk_node_type;
ALTER TABLE workflow_nodes ADD CONSTRAINT chk_node_type CHECK (
  node_type::text = ANY (ARRAY[
    'step','decision_if_else','decision_switch','approval_gate',
    'wait_event','sla_timer','parallel_split','parallel_join',
    'subworkflow','notification','loop_foreach','loop_end'
  ]::text[])
);
