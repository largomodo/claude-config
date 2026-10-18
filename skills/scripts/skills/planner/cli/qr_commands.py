"""QR state manipulation commands as plain functions.

Each public function with 'ctx' as first param is auto-discovered as RPC method.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


VALID_STATUSES = frozenset({"PASS", "FAIL"})
# A FAIL must carry a finding and a PASS must not, so a failure always explains itself and a pass never keeps a stale reason.
REQUIRES_FINDING = frozenset({"FAIL"})
FORBIDS_FINDING = frozenset({"PASS"})

# Verdict rule: within one iteration a verdict only moves toward FAIL.
#   always accepted: TODO->PASS, TODO->FAIL, PASS->FAIL, FAIL->FAIL, PASS->PASS (no-op)
#   accepted only in a later iteration than the stamp: FAIL->PASS
# A verify agent that recorded PASS early must be able to correct it when a
# later item in its walkthrough exposes a defect; a FAIL must not be softened
# without a fix cycle (new iteration) in between.
# The downgrade is for items in the agent's own --qr-item list only: parallel
# verify agents hold disjoint item sets, and rewriting another agent's item
# would race with that agent's recording. The prompt text in
# qr_verify_base.py enforces the list; this function checks the transition only.
# An item with no stamp counts as the current iteration: an unstamped FAIL may
# have been written in this iteration, and treating it as older would allow a
# FAIL->PASS with no fix cycle in between. increment_qr_iteration stamps such
# items, so they become releasable after exactly one increment.
BLOCKED_UPGRADE_FROM = "FAIL"
BLOCKED_UPGRADE_TO = "PASS"


def check_transition(current_status: str, new_status: str,
                     item_iteration: int | None,
                     current_iteration: int) -> None:
    """Raise ValueError when the verdict change is a same-iteration upgrade.

    Only FAIL->PASS is ever refused, and only when the FAIL was written in the
    current iteration (stamp missing or >= current_iteration).

    Called by qr_commands.update_item and, through it, by the cli/qr.py
    update-item command, before any status write. One implementation serves both
    entry points: two copies of the rule would drift, and the stricter one would
    silently decide which verdicts agents can record.
    """
    if current_status != BLOCKED_UPGRADE_FROM or new_status != BLOCKED_UPGRADE_TO:
        return
    if item_iteration is None or item_iteration >= current_iteration:
        raise ValueError(
            f"Cannot change FAIL to PASS within iteration {current_iteration}: "
            f"a FAIL verdict is released only after a fix cycle starts a new "
            f"iteration. PASS->FAIL is accepted at any time."
        )


@dataclass
class QRContext:
    """Context passed to all QR commands."""
    state_dir: Path
    phase: str

    def qr_path(self) -> Path:
        return self.state_dir / f"qr-{self.phase}.json"


def _load_qr_state_locked(fd) -> dict:
    """Load QR state from file descriptor (assumes lock held)."""
    fd.seek(0)
    content = fd.read()
    if not content:
        return {"phase": "", "items": []}
    return json.loads(content)


def _save_qr_state_atomic(ctx: QRContext, qr_state: dict) -> None:
    """Write QR state atomically via tempfile + rename."""
    qr_path = ctx.qr_path()
    fd, tmp_path = tempfile.mkstemp(
        dir=str(ctx.state_dir),
        prefix=f"qr-{ctx.phase}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(qr_state, f, indent=2)
        os.rename(tmp_path, qr_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _find_item(qr_state: dict, item_id: str) -> tuple[int, dict | None]:
    """Find item by ID. Returns (index, item) or (-1, None)."""
    for i, item in enumerate(qr_state.get("items", [])):
        if item.get("id") == item_id:
            return i, item
    return -1, None


def _validate_update(status: str, finding: str | None) -> str:
    """Normalize status and enforce the finding rules; returns upper-cased status."""
    status = status.upper()

    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be PASS or FAIL.")

    if status in REQUIRES_FINDING and not finding:
        raise ValueError(f"Status {status} requires finding to explain what failed.")

    if status in FORBIDS_FINDING and finding:
        raise ValueError(f"Status {status} forbids finding. PASS means no issues found.")

    return status


def update_item(ctx: QRContext, item_id: str, status: str,
                finding: str = None, severity: str = None) -> dict:
    """Update QR item status with file locking."""
    status = _validate_update(status, finding)

    qr_path = ctx.qr_path()
    if not qr_path.exists():
        raise FileNotFoundError(f"QR state file not found: {qr_path}")

    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        qr_state = _load_qr_state_locked(f)

        idx, item = _find_item(qr_state, item_id)
        if idx < 0:
            raise ValueError(f"Item {item_id} not found in qr-{ctx.phase}.json")

        current_status = item.get("status", "TODO")
        # Re-recording an identical PASS is a no-op below, so agents that confirm twice do not bump versions.
        current_iteration = qr_state.get("iteration", 1)
        check_transition(current_status, status, item.get("iteration"),
                         current_iteration)

        if current_status == "PASS" and status == "PASS":
            return {"id": item_id, "version": item.get("version", 1),
                    "operation": "unchanged"}

        item["version"] = item.get("version", 1) + 1
        item["status"] = status
        item["iteration"] = current_iteration
        if finding:
            item["finding"] = finding
        elif "finding" in item and status == "PASS":
            del item["finding"]
        if severity:
            item["severity"] = severity

        qr_state["items"][idx] = item
        _save_qr_state_atomic(ctx, qr_state)

    return {"id": item_id, "version": item["version"], "operation": "updated"}


def get_item(ctx: QRContext, item_id: str) -> dict:
    """Get QR item by ID."""
    qr_path = ctx.qr_path()
    if not qr_path.exists():
        raise FileNotFoundError(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    _, item = _find_item(qr_state, item_id)
    if item is None:
        raise ValueError(f"Item {item_id} not found")

    return item


def list_items(ctx: QRContext, status: str = None) -> list[dict]:
    """List QR items, optionally filtered by status."""
    qr_path = ctx.qr_path()
    if not qr_path.exists():
        raise FileNotFoundError(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    items = []
    for item in qr_state.get("items", []):
        item_status = item.get("status", "TODO")
        if status and item_status != status.upper():
            continue
        items.append({
            "id": item.get("id"),
            "status": item_status,
            "finding": item.get("finding"),
        })

    return items


def summary(ctx: QRContext) -> dict:
    """Get summary of QR state (counts by status)."""
    qr_path = ctx.qr_path()
    if not qr_path.exists():
        raise FileNotFoundError(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    counts = {"TODO": 0, "PASS": 0, "FAIL": 0}
    for item in qr_state.get("items", []):
        status = item.get("status", "TODO")
        counts[status] = counts.get(status, 0) + 1

    return {
        "phase": ctx.phase,
        "total": sum(counts.values()),
        "counts": counts,
    }


def assign_group(ctx: QRContext, item_id: str, group_id: str) -> dict:
    """Assign QR item to a group."""
    valid_prefixes = ('umbrella', 'parent-', 'component-', 'concern-', 'affinity-')
    if not (group_id == 'umbrella' or any(group_id.startswith(p) for p in valid_prefixes[1:])):
        raise ValueError(
            f"Invalid group_id '{group_id}'. "
            f"Must be 'umbrella' or start with: parent-, component-, concern-, affinity-"
        )

    qr_path = ctx.qr_path()
    if not qr_path.exists():
        raise FileNotFoundError(f"QR state file not found: {qr_path}")

    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        qr_state = _load_qr_state_locked(f)

        idx, item = _find_item(qr_state, item_id)
        if idx < 0:
            raise ValueError(f"Item {item_id} not found in qr-{ctx.phase}.json")

        item["group_id"] = group_id
        qr_state["items"][idx] = item
        _save_qr_state_atomic(ctx, qr_state)

    return {"id": item_id, "version": item.get("version", 1), "operation": "updated"}
