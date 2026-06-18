"""Process Mining engine — discover workflows from event logs.

Phase 1 v4 P1-S7 contract surface:
  * EventLog dataclass (consumes ingestion.NormalizedEvent stream)
  * case_inference.infer_cases — group events by inferred case_id
  * heuristic_miner.HeuristicMiner — baseline algorithm (bigram counter)

Connectors live in services/data-pipeline/ingestion/connectors/{postgres_cdc,
excel_filesystem, zalo_metadata}/ (skeleton P1-S3, full impl Phase 1.5+).

Phase 2 P2-S20 extracts this whole subpackage to services/process-mining/.
"""

from .anomalies import (
    BypassEvent,
    BypassRiskScore,
    ConformanceCheck,
    ReworkLoop,
    TokenReplayResult,
    analyze_conformance,
    detect_approval_bypass,
    detect_rework_loops,
    score_bypass_risk,
    token_replay,
)
from .case_inference import infer_cases
from .fuzzy_miner import FuzzyEdge, FuzzyMiner, FuzzyResult
from .heuristic_miner import HeuristicMiner, MinedWorkflow
from .inductive_miner import InductiveMiner, InductiveResult, ProcessTreeNode
from .types import Event, EventLog, ProcessVariant

__all__ = [
    # Types
    "Event", "EventLog", "ProcessVariant",
    # Algorithms
    "HeuristicMiner", "MinedWorkflow",
    "InductiveMiner", "InductiveResult", "ProcessTreeNode",
    "FuzzyMiner", "FuzzyResult", "FuzzyEdge",
    # Anomaly detectors
    "BypassEvent", "BypassRiskScore", "ConformanceCheck",
    "ReworkLoop", "TokenReplayResult",
    "analyze_conformance", "detect_approval_bypass",
    "detect_rework_loops", "score_bypass_risk", "token_replay",
    # Case inference
    "infer_cases",
]
