"""Generate BPMN for 'Thu mua nong san tu HTX' v2 — run inside ai-orchestrator container.

Usage: docker exec kaorisystem-ai-orchestrator-1 python /tmp/gen_bpmn.py > bpmn.xml
"""
try:
    from ai_orchestrator.workflow_runtime.bpmn_mapper import (
        MappedNode, MappedEdge, build_bpmn_xml)
except ImportError:  # PYTHONPATH variant
    from workflow_runtime.bpmn_mapper import (  # type: ignore
        MappedNode, MappedEdge, build_bpmn_xml)


def task(cid, title, key, bpmn="bpmn:ServiceTask"):
    return MappedNode(client_id=cid, bpmn_type=bpmn, title=title,
                      node_type=key, structural_type="step", executable=True,
                      kaori_node_type=key)


N = [
    MappedNode(client_id="Start_1", bpmn_type="bpmn:StartEvent", title="Nhận đơn chào bán",
               node_type="noop", structural_type="step", executable=True, is_trigger=True),
    task("Task_ReadForm",   "Đọc đơn chào bán từ HTX",            "read_form_submission"),
    task("Task_Validate",   "Kiểm tra dữ liệu đơn",               "validate"),
    task("Task_Extract",    "Bóc tách lô hàng (AI)",              "extract_entities"),
    task("Task_Rag",        "Đối chiếu QĐ-01 + SOP kiểm QA (KB)", "rag_query"),
    task("Task_Risk",       "Chấm điểm rủi ro lô hàng (AI)",      "call_insight_engine"),
    MappedNode(client_id="GW_Value", bpmn_type="bpmn:ExclusiveGateway",
               title="Giá trị > 50 triệu?", node_type="if_else",
               structural_type="decision_if_else", executable=True),
    task("Task_AutoLog",    "Dưới ngưỡng — ghi nhận tự duyệt",    "log"),
    task("Task_Approval",   "Giám đốc phê duyệt (QĐ-01)",         "approval_gate", "bpmn:UserTask"),
    task("Task_Contract",   "Lập hợp đồng thu mua (e-sign)",      "contract", "bpmn:UserTask"),
    task("Task_CreateTask", "Lệnh nhập kho + kiểm QA (SOP-02)",   "create_task"),
    task("Task_Narrative",  "Ghi lý do quyết định (AI)",          "generate_narrative"),
    task("Task_Insight",    "Đăng quyết định lên feed",           "publish_insight"),
    task("Task_Email",      "Thông báo HTX",                      "send_email", "bpmn:SendTask"),
    MappedNode(client_id="End_1", bpmn_type="bpmn:EndEvent", title="Hoàn tất",
               node_type="noop", structural_type="step", executable=True, is_throw=True),
]


def flow(i, s, t, cond=None, label=None, default=False):
    return MappedEdge(client_id=f"Flow_{i}", source_client_id=s, target_client_id=t,
                      condition=cond, label=label, is_default=default)


E = [
    flow(1,  "Start_1",        "Task_ReadForm"),
    flow(2,  "Task_ReadForm",  "Task_Validate"),
    flow(3,  "Task_Validate",  "Task_Extract"),
    flow(4,  "Task_Extract",   "Task_Rag"),
    flow(5,  "Task_Rag",       "Task_Risk"),
    flow(6,  "Task_Risk",      "GW_Value"),
    flow(7,  "GW_Value",       "Task_Approval", cond="${thanh_tien > 50000000}", label="Trên 50 triệu"),
    flow(8,  "GW_Value",       "Task_AutoLog",  label="Từ 50 triệu trở xuống", default=True),
    flow(9,  "Task_Approval",  "Task_Contract"),
    flow(10, "Task_AutoLog",   "Task_Contract"),
    flow(11, "Task_Contract",  "Task_CreateTask"),
    flow(12, "Task_CreateTask","Task_Narrative"),
    flow(13, "Task_Narrative", "Task_Insight"),
    flow(14, "Task_Insight",   "Task_Email"),
    flow(15, "Task_Email",     "End_1"),
]

LANES = [
    ("Phòng Thu mua", ["Start_1", "Task_ReadForm", "Task_Validate", "Task_AutoLog",
                       "Task_CreateTask", "Task_Email", "End_1"]),
    ("Kaori AI",      ["Task_Extract", "Task_Rag", "Task_Risk", "GW_Value",
                       "Task_Narrative", "Task_Insight"]),
    ("Ban Giám đốc",  ["Task_Approval", "Task_Contract"]),
]

xml = build_bpmn_xml(N, E, process_id="Process_thu_mua_htx",
                     process_name="Thu mua nông sản từ HTX", lanes=LANES)
print(xml)
