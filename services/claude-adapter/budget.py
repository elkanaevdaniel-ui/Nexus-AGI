import json, os, time
from datetime import date
from pathlib import Path
BUDGET_FILE = Path(__file__).parent / "budget_state.json"
DAILY_LIMIT = 5.00
MONTHLY_LIMIT = 20.00
PER_RUN_LIMIT = 1.00
SESSION_CALL_LIMIT = 10
INPUT_COST_PER_1K = 0.003
OUTPUT_COST_PER_1K = 0.015
_session_calls = 0
def _load():
    if BUDGET_FILE.exists():
        try: return json.loads(BUDGET_FILE.read_text())
        except: pass
    return {"daily": {}, "monthly": {}}
def _save(s):
    try: BUDGET_FILE.write_text(json.dumps(s, indent=2))
    except: pass
def estimate_cost(pt, ct):
    return (pt/1000)*INPUT_COST_PER_1K + (ct/1000)*OUTPUT_COST_PER_1K
def check_budget():
    global _session_calls
    if _session_calls >= SESSION_CALL_LIMIT:
        return False, f"Session limit ({SESSION_CALL_LIMIT})"
    s = _load()
    t, m = date.today().isoformat(), date.today().strftime("%Y-%m")
    d = s.get("daily",{}).get(t, 0.0)
    mo = s.get("monthly",{}).get(m, 0.0)
    if d >= DAILY_LIMIT: return False, f"Daily ${d:.2f}/${DAILY_LIMIT}"
    if mo >= MONTHLY_LIMIT: return False, f"Monthly ${mo:.2f}/${MONTHLY_LIMIT}"
    return True, "OK"
def record_usage(pt, ct):
    global _session_calls
    cost = min(estimate_cost(pt, ct), PER_RUN_LIMIT)
    _session_calls += 1
    s = _load()
    t, m = date.today().isoformat(), date.today().strftime("%Y-%m")
    s.setdefault("daily",{})[t] = s.get("daily",{}).get(t,0.0) + cost
    s.setdefault("monthly",{})[m] = s.get("monthly",{}).get(m,0.0) + cost
    _save(s)
    return cost, f"${cost:.4f} (day:${s['daily'][t]:.2f} mo:${s['monthly'][m]:.2f} sess:{_session_calls})"
def get_status():
    s = _load()
    t, m = date.today().isoformat(), date.today().strftime("%Y-%m")
    return {"daily": s.get("daily",{}).get(t,0.0), "daily_limit": DAILY_LIMIT,
            "monthly": s.get("monthly",{}).get(m,0.0), "monthly_limit": MONTHLY_LIMIT,
            "session": _session_calls, "session_limit": SESSION_CALL_LIMIT}
