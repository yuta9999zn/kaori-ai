"""
Intervention engine — AI-INT-022 (P15-S10 D4) Vietnamese context adapter.

Per BACKLOG_V4 line 747 + S10 plan D4. The engine resolves which channel
+ which approval shape an intervention takes for a given (tenant, user)
based on locale + tenant settings.

Two Vietnamese-specific concerns:

  1. Channel routing — Vietnamese SME pilots use Zalo OA when configured;
     fall back to Telegram (P15-S9 D5 REL-011) otherwise. International
     tenants default to email (notification-service SMTP path) until a
     locale-specific channel adapter exists.

  2. Hierarchical decision factor — Vietnamese workflow culture often
     requires manager sign-off before automated actions execute. When
     `tenant_settings.requires_manager_approval = true`, the engine
     wraps the intervention in a Telegram-approval-gate workflow node
     (REL-011 already wired) instead of dispatching directly.

Phase 1.5 ships the resolver as a pure function. The actual dispatch
happens inside the Temporal workflow (workflow_runtime/workflows/
intervention_followup.py) which calls this resolver to build its
side-effect activity inputs. Splitting keeps the resolver testable
without Temporal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class InterventionMisconfigError(ValueError):
    """Raised when tenant intervention settings are internally inconsistent
    in a way that would silently bypass an audit gate (K-6 spirit).

    The canonical case is `requires_manager_approval=True` with no
    `telegram_chat_id` bound — there is no channel through which the
    approval can be requested, so auto-firing would defeat the gate the
    tenant explicitly configured. Fail-closed: surface the misconfig to
    operators (Temporal workflow failure → PagerDuty) rather than
    dispatch and lose the audit trail.
    """


class InterventionChannel(str, Enum):
    """Per-locale channel choice. The activity that dispatches reads
    this enum to pick the right adapter (Zalo / Telegram / email).
    """
    ZALO = "zalo"
    TELEGRAM = "telegram"
    EMAIL = "email"


class ApprovalGate(str, Enum):
    """Whether the intervention auto-fires or waits on manager sign-off."""
    AUTO = "auto"                      # fire immediately
    MANAGER_APPROVAL = "manager_approval"  # wait for Telegram approval (REL-011)


@dataclass(frozen=True)
class InterventionPlan:
    """Resolver output. The Temporal workflow consumes this to:
      - pick the channel adapter (Zalo / Telegram / email)
      - decide whether to schedule the manager_approval gate node
        before the dispatch activity
    """
    channel: InterventionChannel
    gate: ApprovalGate
    locale: str                        # 'vi' / 'en' — for templating
    rationale: str                     # human-readable reason — for audit + debug


@dataclass(frozen=True)
class TenantInterventionSettings:
    """Subset of tenant_settings the resolver cares about. Loaded by
    the calling activity from the tenant's row; passed in here so the
    resolver doesn't query the DB itself (keeps it pure).
    """
    locale: str = "vi"                 # 'vi' or 'en'
    zalo_oa_configured: bool = False   # True when secret/tenant/.../zalo_oa exists
    requires_manager_approval: bool = False
    telegram_chat_id: Optional[str] = None  # None = no Telegram bound


def resolve_intervention_plan(
    settings: TenantInterventionSettings,
) -> InterventionPlan:
    """Pure resolver: tenant settings → channel + gate decision.

    Decision tree (per S10 plan D4):

      Channel
      -------
      locale=='vi' AND zalo_oa_configured=True  → ZALO
      locale=='vi' AND telegram_chat_id != None → TELEGRAM (S9 D5 path)
      locale=='vi' AND no Vietnamese channel    → EMAIL (graceful fallback)
      locale=='en' (international)              → EMAIL

      Gate
      ----
      requires_manager_approval=True            → MANAGER_APPROVAL
      otherwise                                 → AUTO

    Manager approval requires Telegram regardless of intervention channel
    (REL-011 only supports Telegram in Phase 1.5; Zalo approval ships
    when the customer Zalo OA path settles per S9 D4c blocker). If
    `requires_manager_approval=True` AND no `telegram_chat_id`, the
    resolver raises `InterventionMisconfigError` — fail-closed so the
    audit gate the tenant configured is never silently bypassed (K-6
    spirit). The workflow surfaces the error as a Temporal failure for
    operator triage; the intervention can be retried after Telegram bind.
    """
    locale = (settings.locale or "vi").lower()

    # ---- Channel ----
    if locale == "vi":
        if settings.zalo_oa_configured:
            channel = InterventionChannel.ZALO
            ch_reason = "Vietnamese tenant + Zalo OA configured"
        elif settings.telegram_chat_id:
            channel = InterventionChannel.TELEGRAM
            ch_reason = "Vietnamese tenant + Telegram bound (S9 D5 REL-011 path)"
        else:
            channel = InterventionChannel.EMAIL
            ch_reason = "Vietnamese tenant but no Zalo OA + no Telegram → email fallback"
    else:
        channel = InterventionChannel.EMAIL
        ch_reason = f"locale={locale!r} → email (no locale-specific adapter wired)"

    # ---- Gate ----
    if settings.requires_manager_approval:
        if not settings.telegram_chat_id:
            # Fail-closed: tenant configured an audit gate but no channel to ask.
            # K-6 says every automated decision needs an audit trail; silently
            # auto-firing bypasses the gate the tenant opted into. The action can
            # be retried later — the missed audit trail cannot.
            raise InterventionMisconfigError(
                "tenant requires manager approval but no telegram_chat_id "
                "is bound; refuse to dispatch (would bypass audit gate). "
                "Bind Telegram via REL-011 or unset requires_manager_approval."
            )
        gate = ApprovalGate.MANAGER_APPROVAL
        gate_reason = "tenant requires manager approval; Telegram bound for REL-011 gate"
    else:
        gate = ApprovalGate.AUTO
        gate_reason = "no approval requirement"

    return InterventionPlan(
        channel=channel,
        gate=gate,
        locale=locale,
        rationale=f"channel: {ch_reason}; gate: {gate_reason}",
    )
