"""Saatleri Turkiye saatine (Europe/Istanbul) cevirme."""
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    TR = ZoneInfo("Europe/Istanbul")
except Exception:                      # zaman dilimi verisi yoksa sabit UTC+3
    from datetime import timedelta
    TR = timezone(timedelta(hours=3))


def now_tr() -> datetime:
    return datetime.now(TR)


def to_tr(iso: str):
    """ISO metni Turkiye saatine cevirir; olmazsa None."""
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TR)


def fmt_tr(iso: str) -> str:
    dt = to_tr(iso)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else (str(iso)[:16].replace("T", " ") if iso else "")
