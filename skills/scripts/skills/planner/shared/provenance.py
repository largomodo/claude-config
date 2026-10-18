"""Provenance header for plan.md and plan->execute state resolution.

WHY plan.md carries a pointer: plan.json is the IR that execution needs
(plan.md is a lossy rendering), but the user copies only plan.md to its final
path. A one-line header naming the planner STATE_DIR lets a later session find
plan.json without searching /tmp.

WHY values are percent-encoded: the header is a single HTML comment of
space-separated key=value tokens; encoding keeps spaces and '-->' sequences in
paths from breaking the parse.

The absolute /tmp path is harmless to readers and can be deleted from the file;
execution then falls back to sidecars or a manual copy. STATE_DIR under /tmp
may not survive until execution, so sidecars are checked first.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote

PROVENANCE_PREFIX = "<!-- planner-state:"
_SAFE = "/:-_.T"
# Only the top of the file is scanned so plan prose that quotes a header is never mistaken for provenance.
_SCAN_LINES = 5


def render_provenance(state_dir: str, plan_id: str, created_at: str) -> str:
    """One-line HTML comment header naming the planner state directory.

    Called by the plan.md translation when the planner reaches its terminal
    pass; parse_provenance reads the result back.
    """
    fields = {"state_dir": state_dir, "plan_id": plan_id, "created_at": created_at}
    body = " ".join(f"{k}={quote(str(v), safe=_SAFE)}" for k, v in fields.items())
    return f"{PROVENANCE_PREFIX} {body} -->"


def parse_provenance(text: str) -> dict | None:
    """Return {'state_dir','plan_id','created_at'} from the leading lines, or None.

    Called by resolve_plan_state to read the header render_provenance writes.
    """
    for line in text.splitlines()[:_SCAN_LINES]:
        line = line.strip()
        if not (line.startswith(PROVENANCE_PREFIX) and line.endswith("-->")):
            continue
        inner = line[len(PROVENANCE_PREFIX):-len("-->")].split()
        values = {}
        for token in inner:
            key, sep, value = token.partition("=")
            if sep:
                values[key] = unquote(value)
        if {"state_dir", "plan_id", "created_at"} <= values.keys():
            return {k: values[k] for k in ("state_dir", "plan_id", "created_at")}
    return None


def sidecar_paths(plan_file: Path) -> tuple[Path, Path]:
    """<stem>.plan.json and <stem>.context.json beside the plan file.

    Called by resolve_plan_state to locate sidecar copies of the plan state.
    """
    plan_file = Path(plan_file)
    return (plan_file.with_name(f"{plan_file.stem}.plan.json"),
            plan_file.with_name(f"{plan_file.stem}.context.json"))


@dataclass
class PlanStateResolution:
    """Where resolve_plan_state found plan.json and context.json.

    Returned to executor step 1; source 'none' tells it to print the manual
    copy instruction.
    """
    source: str  # 'sidecar' | 'provenance' | 'none'
    plan_json: Path | None = None
    context_json: Path | None = None
    state_dir: str | None = None
    plan_id: str | None = None


def resolve_plan_state(plan_file: Path) -> PlanStateResolution:
    """Locate plan.json/context.json for a delivered plan file.

    Order: sidecars, then the provenance state_dir if it still holds plan.json.

    Called by the executor's state-resolution step when a delivered plan file is
    supplied and STATE_DIR holds no plan.json.
    """
    plan_file = Path(plan_file)
    side_plan, side_ctx = sidecar_paths(plan_file)
    if side_plan.exists():
        return PlanStateResolution(
            source="sidecar",
            plan_json=side_plan,
            context_json=side_ctx if side_ctx.exists() else None,
        )

    try:
        prov = parse_provenance(plan_file.read_text())
    except OSError:
        prov = None
    if prov:
        live = Path(prov["state_dir"])
        if (live / "plan.json").exists():
            ctx_json = live / "context.json"
            return PlanStateResolution(
                source="provenance",
                plan_json=live / "plan.json",
                context_json=ctx_json if ctx_json.exists() else None,
                state_dir=prov["state_dir"],
                plan_id=prov["plan_id"],
            )
    return PlanStateResolution(source="none")
