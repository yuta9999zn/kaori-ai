-- 128_node_catalog_loop.sql
-- #7 Loop/for-each — register the two control nodes that bound a loop region:
--   loop_foreach : "Với mỗi X" — iterates config.items; the BODY is the chain of
--                  steps up to the matching loop_end, run once per item.
--   loop_end     : closes the loop region (marker; the runner resumes the main
--                  flow from its successor after all iterations).
-- side_effect = pure (orchestration only). Category 'decision' (control-flow),
-- matching how if_else/switch live in the catalog. The runner executor wiring is
-- Phase B; this migration just makes the node types valid + builder-pickable.

INSERT INTO node_type_catalog (
    node_type_key, category, side_effect_class, default_retry_policy,
    config_schema_json, cost_band, description_vi, sort_order
) VALUES
('loop_foreach', 'decision', 'pure',
 '{"max_attempts": 1, "backoff_seconds": 0, "backoff_factor": 1.0, "jitter": false}'::jsonb,
 '{"type":"object","required":["items"],"properties":{"items":{"type":"string","description":"Tham chiếu danh sách để lặp, vd $.input.hoa_don hoặc $.upstream.rows"},"item_var":{"type":"string","default":"item","description":"Tên biến cho mỗi phần tử trong thân vòng lặp"},"max_iterations":{"type":"integer","description":"Trần số vòng (an toàn)"}}}'::jsonb,
 'low', 'Vòng lặp — với mỗi phần tử trong danh sách, chạy chuỗi bước trong thân tới loop_end.', 36),
('loop_end', 'decision', 'pure',
 '{"max_attempts": 1, "backoff_seconds": 0, "backoff_factor": 1.0, "jitter": false}'::jsonb,
 '{"type":"object","properties":{}}'::jsonb,
 'low', 'Kết thúc vòng lặp — đóng vùng thân; runner chạy tiếp luồng chính sau khi lặp xong.', 37)
ON CONFLICT (node_type_key) DO NOTHING;
