"""
OBS-021 — Capacity planning forecast (P2-S18).

Pure compute: takes resource usage history, projects N days forward
via simple linear regression on the trailing window, computes the
date when projected usage crosses the limit.

Phase 1.5 deliberately uses simple linear regression (slope + intercept
+ R² confidence). Phase 2 swap to Prophet / ARIMA when seasonal
patterns matter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, Optional


@dataclass(frozen=True)
class ResourceUsageHistory:
    """One resource's time-series + capacity ceiling."""
    resource:           str       # 'cpu' / 'memory' / 'storage_gb' / 'connections'
    capacity_limit:     float     # the hard ceiling (e.g. 1000 GB storage cap)
    points:             tuple[tuple[datetime, float], ...]    # (ts, usage_value)


@dataclass(frozen=True)
class CapacityForecast:
    """Projection output."""
    resource:                 str
    current_usage:            float
    capacity_limit:           float
    usage_pct_now:            float
    slope_per_day:            float
    projected_usage_horizon:  float           # at horizon_days
    projected_date_to_limit:  Optional[datetime]  # None if trend flat/down
    r_squared:                float           # 0..1 confidence in linear fit
    recommendation:           str             # human-readable next step
    horizon_days:             int


def forecast_capacity_linear(
    history: ResourceUsageHistory,
    *,
    horizon_days: int = 30,
    min_points: int = 7,
) -> CapacityForecast:
    """Simple linear regression on (day_offset, value).

    Returns CapacityForecast with slope, projected usage at horizon,
    and projected_date_to_limit if slope > 0.

    `min_points=7` enforced — fewer than a week of data isn't enough
    to extract a trend; we return slope=0 + recommendation to wait.
    """
    pts = list(history.points)
    if not pts:
        raise ValueError("ResourceUsageHistory.points must be non-empty")

    if len(pts) < min_points:
        current = pts[-1][1]
        return CapacityForecast(
            resource=history.resource,
            current_usage=current,
            capacity_limit=history.capacity_limit,
            usage_pct_now=_pct(current, history.capacity_limit),
            slope_per_day=0.0,
            projected_usage_horizon=current,
            projected_date_to_limit=None,
            r_squared=0.0,
            recommendation=(
                f"Cần ít nhất {min_points} ngày lịch sử để dự báo "
                f"(hiện có {len(pts)} ngày). Đợi thêm dữ liệu."
            ),
            horizon_days=horizon_days,
        )

    # Convert to (day_offset_from_first_point, value)
    t0 = pts[0][0]
    x_y = [((p[0] - t0).total_seconds() / 86400.0, p[1]) for p in pts]
    n = len(x_y)
    mean_x = sum(x for x, _ in x_y) / n
    mean_y = sum(y for _, y in x_y) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in x_y)
    var_x = sum((x - mean_x) ** 2 for x, _ in x_y)
    if var_x == 0:
        slope = 0.0
        intercept = mean_y
    else:
        slope = cov / var_x
        intercept = mean_y - slope * mean_x

    # R² — how well does the linear fit explain variance?
    ss_total = sum((y - mean_y) ** 2 for _, y in x_y)
    ss_residual = sum(
        (y - (intercept + slope * x)) ** 2 for x, y in x_y
    )
    if ss_total == 0:
        r2 = 1.0    # perfectly flat — perfect fit (degenerate)
    else:
        r2 = max(0.0, min(1.0, 1.0 - ss_residual / ss_total))

    # Project at horizon_days from LAST data point
    last_x = x_y[-1][0]
    proj_x = last_x + horizon_days
    proj_usage = intercept + slope * proj_x

    # When does usage cross the limit?
    proj_date_to_limit: Optional[datetime] = None
    if slope > 0:
        # limit = intercept + slope * x_limit → x_limit = (limit - intercept) / slope
        x_limit = (history.capacity_limit - intercept) / slope
        if x_limit > last_x:
            days_offset = x_limit
            proj_date_to_limit = t0 + timedelta(days=days_offset)
        else:
            # Limit already exceeded by trend — flag immediately
            proj_date_to_limit = pts[-1][0]

    current = pts[-1][1]
    recommendation = _recommendation(
        current=current,
        limit=history.capacity_limit,
        slope=slope,
        proj=proj_usage,
        proj_date=proj_date_to_limit,
        horizon_days=horizon_days,
        r2=r2,
    )

    return CapacityForecast(
        resource=history.resource,
        current_usage=current,
        capacity_limit=history.capacity_limit,
        usage_pct_now=_pct(current, history.capacity_limit),
        slope_per_day=slope,
        projected_usage_horizon=proj_usage,
        projected_date_to_limit=proj_date_to_limit,
        r_squared=r2,
        recommendation=recommendation,
        horizon_days=horizon_days,
    )


def _pct(value: float, limit: float) -> float:
    if limit == 0:
        return 0.0
    return (value / limit) * 100.0


def _recommendation(*, current, limit, slope, proj, proj_date, horizon_days, r2) -> str:
    """Vietnamese business-language recommendation."""
    pct = _pct(current, limit)
    if slope <= 0:
        return f"Tải trọng ổn định/giảm. Hiện đang dùng {pct:.1f}% capacity. Không cần action."
    if proj_date is None:
        return f"Slope dương nhưng chưa chạm giới hạn trong {horizon_days} ngày tới. Theo dõi."
    days_to_limit = (proj_date - datetime.now(proj_date.tzinfo)).days
    if days_to_limit <= 0:
        return f"⚠️ CRITICAL: trend đã vượt giới hạn. Scale gấp."
    if days_to_limit <= 30:
        return (
            f"⚠️ CRITICAL: dự báo cạn capacity trong {days_to_limit} ngày "
            f"(R²={r2:.2f}). Scale ngay."
        )
    if days_to_limit <= 90:
        return (
            f"WARNING: dự báo cạn capacity trong {days_to_limit} ngày "
            f"(R²={r2:.2f}). Lên kế hoạch scale."
        )
    return (
        f"OK: dự báo cạn capacity trong {days_to_limit} ngày "
        f"(R²={r2:.2f}). Theo dõi định kỳ."
    )
