from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, EmailStr


class TemplateType(str, Enum):
    INVITE = "invite"
    RESET_PASSWORD = "reset-password"
    QUOTA_ALERT = "quota-alert"
    REPORT_READY = "report-ready"  # F-038 — fired by ai-orchestrator after a report run reaches status='ready'
    WORKFLOW_FREEFORM = "workflow-freeform"  # workflow send_email node — context={subject, body, cc}


class SendRequest(BaseModel):
    to: EmailStr
    template: TemplateType
    context: dict[str, Any] = {}
    # invite:         { invited_by, enterprise_name, invite_url, role }
    # reset-password: { full_name, reset_url }
    # quota-alert:    { enterprise_name, usage_pct, quota_limit, used, plan, upgrade_url }


class SendResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
