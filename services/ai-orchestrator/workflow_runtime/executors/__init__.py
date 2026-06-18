"""
Built-in node executors. Importing this package registers all bundled
executors with workflow_runtime.node_executor.REGISTRY.

To add a new executor:
  1. Add file in this package.
  2. Subclass NodeExecutor with node_type_key + side_effect_class +
     async execute().
  3. Append to register_builtin_executors() below.
"""
from __future__ import annotations

from ..node_executor import REGISTRY
from .pure import (
    AggregateExecutor, IfElseExecutor, LoopEndExecutor, LoopForeachExecutor,
    NoopExecutor, SwitchExecutor,
)
from .data import ReadEmailExecutor, ReadTableExecutor, UpdateRecordExecutor
from .external import SendEmailExecutor
from .approval import ApprovalGateExecutor, ReadFormSubmissionExecutor
from .contract import ContractNodeExecutor
from .ai import (
    CallForecastingExecutor,
    CallInsightEngineExecutor,
    CallRecommendationEngineExecutor,
    CallRiskDetectionExecutor,
    ClassifyTextExecutor,
    ExtractEntitiesExecutor,
    GenerateNarrativeExecutor,
    RagQueryExecutor,
)
from .output import (
    CreateTaskExecutor,
    DisplayDashboardExecutor,
    PublishAlertExecutor,
    PublishInsightExecutor,
    SaveToDatabaseExecutor,
)
from .action import (
    CallApiExecutor,
    GenerateReportExecutor,
    TriggerWorkflowExecutor,
)
from .validate_exec import ValidateExecutor
from .utility import (
    FilterExecutor,
    JoinExecutor,
    LogExecutor,
    ReadWebhookExecutor,
    ScheduledTriggerExecutor,
    SendChatMessageExecutor,
    SplitExecutor,
    TransformExecutor,
)
from .wave5 import (
    DeduplicateExecutor,
    EnrichExecutor,
    ExportFileExecutor,
    MergeExecutor,
    ReadApiExecutor,
    ReadCalendarExecutor,
    ReadChatExecutor,
    ReadFileUploadExecutor,
    SendSmsExecutor,
    SortExecutor,
    WaitForConditionExecutor,
)


def register_builtin_executors() -> None:
    """Idempotent — safe to call twice (REGISTRY.register logs a warning
    on duplicate but doesn't raise)."""
    for executor in (
        # Wave 1 (commit 1): 6 pure/data/external executors
        IfElseExecutor(),
        SwitchExecutor(),
        AggregateExecutor(),
        NoopExecutor(),
        LoopForeachExecutor(),
        LoopEndExecutor(),
        ReadTableExecutor(),
        UpdateRecordExecutor(),
        SendEmailExecutor(),
        # Wave 2a (commit 2): approval pause/resume + form ingest
        ApprovalGateExecutor(),
        ContractNodeExecutor(),
        ReadFormSubmissionExecutor(),
        # Wave 2b (commit 5): 8 AI node wrappers
        ClassifyTextExecutor(),
        GenerateNarrativeExecutor(),
        RagQueryExecutor(),
        CallInsightEngineExecutor(),
        CallRiskDetectionExecutor(),
        CallForecastingExecutor(),
        ExtractEntitiesExecutor(),
        CallRecommendationEngineExecutor(),
        # Wave 3 (commit 6): 10 output/action/validation/data nodes
        PublishInsightExecutor(),
        PublishAlertExecutor(),
        CreateTaskExecutor(),
        DisplayDashboardExecutor(),
        SaveToDatabaseExecutor(),
        CallApiExecutor(),
        TriggerWorkflowExecutor(),
        GenerateReportExecutor(),
        ValidateExecutor(),
        ReadEmailExecutor(),
        # Wave 4 (commit 7): 8 utility nodes — closes full 25/25 templates
        ScheduledTriggerExecutor(),
        FilterExecutor(),
        TransformExecutor(),
        SplitExecutor(),
        JoinExecutor(),
        LogExecutor(),
        SendChatMessageExecutor(),
        ReadWebhookExecutor(),
        # Wave 5 (commit 8): 11 final nodes — closes 45/45 catalog coverage
        SortExecutor(),
        MergeExecutor(),
        DeduplicateExecutor(),
        EnrichExecutor(),
        WaitForConditionExecutor(),
        ReadApiExecutor(),
        ReadCalendarExecutor(),
        ReadChatExecutor(),
        ReadFileUploadExecutor(),
        SendSmsExecutor(),
        ExportFileExecutor(),
    ):
        REGISTRY.register(executor)


register_builtin_executors()

__all__ = [
    "register_builtin_executors",
    # Wave 1
    "IfElseExecutor",
    "SwitchExecutor",
    "AggregateExecutor",
    "NoopExecutor",
    "ReadTableExecutor",
    "UpdateRecordExecutor",
    "SendEmailExecutor",
    # Wave 2a
    "ApprovalGateExecutor",
    "ContractNodeExecutor",
    "ReadFormSubmissionExecutor",
    # Wave 2b
    "ClassifyTextExecutor",
    "GenerateNarrativeExecutor",
    "RagQueryExecutor",
    "CallInsightEngineExecutor",
    "CallRiskDetectionExecutor",
    "CallForecastingExecutor",
    "ExtractEntitiesExecutor",
    "CallRecommendationEngineExecutor",
    # Wave 3
    "PublishInsightExecutor",
    "PublishAlertExecutor",
    "CreateTaskExecutor",
    "DisplayDashboardExecutor",
    "SaveToDatabaseExecutor",
    "CallApiExecutor",
    "TriggerWorkflowExecutor",
    "GenerateReportExecutor",
    "ValidateExecutor",
    "ReadEmailExecutor",
    # Wave 4
    "ScheduledTriggerExecutor",
    "FilterExecutor",
    "TransformExecutor",
    "SplitExecutor",
    "JoinExecutor",
    "LogExecutor",
    "SendChatMessageExecutor",
    "ReadWebhookExecutor",
    # Wave 5
    "SortExecutor",
    "MergeExecutor",
    "DeduplicateExecutor",
    "EnrichExecutor",
    "WaitForConditionExecutor",
    "ReadApiExecutor",
    "ReadCalendarExecutor",
    "ReadChatExecutor",
    "ReadFileUploadExecutor",
    "SendSmsExecutor",
    "ExportFileExecutor",
]
