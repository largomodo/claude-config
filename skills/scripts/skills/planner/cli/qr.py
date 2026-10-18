"""CLI for atomic QR state mutation with file locking.

Usage: python3 -m skills.planner.cli.qr --state-dir <dir> --qr-phase <phase> <command> [args]

Commands:
  update-item <id> --status <PASS|FAIL> [--finding <text>] [--severity <MUST|SHOULD|COULD>]

Parallel verify agents write to the same qr-{phase}.json file simultaneously.
Without coordination, race conditions corrupt the file:
  Agent A reads {items: [todo, todo]}
  Agent B reads {items: [todo, todo]}
  Agent A writes {items: [pass, todo]}  <- lost update
  Agent B writes {items: [todo, pass]}

This CLI serializes access via file locking and prevents corruption.

This works by:
1. fcntl.flock(LOCK_EX) blocks until exclusive lock acquired
2. Read qr-{phase}.json inside critical section
3. Mutate single item in memory
4. Write to tempfile, os.rename() for atomicity
5. Release lock on file descriptor close

Invariants:
- Lock holder is sole writer; readers may see stale data but never partial writes
- os.rename() is atomic on POSIX; no reader sees half-written JSON
- Verdicts move toward FAIL within an iteration: PASS->FAIL is accepted,
  FAIL->PASS is refused until a later iteration (see qr_commands.check_transition)
- FAIL requires --finding; prevents silent status changes
- Every accepted write stamps the item with the file's iteration; the stamp lets a later iteration release a FAIL
"""

from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path

from .output import EntityResult, print_entity_result
from . import qr_commands
from .dispatch import discover_methods, batch as batch_dispatch, list_methods


# Valid severity values (per conventions/severity.md)
VALID_SEVERITIES = frozenset({"MUST", "SHOULD", "COULD"})


def error_exit(msg: str, code: int = 1):
    """Print error in XML format and exit."""
    print(f"""<qr_cli_error>
  <message>{msg}</message>
</qr_cli_error>""")
    sys.exit(code)


def get_qr_path(state_dir: str, phase: str) -> Path:
    """Get path to qr-{phase}.json file."""
    return Path(state_dir) / f"qr-{phase}.json"


def load_qr_state_locked(fd) -> dict:
    """Load QR state from file descriptor (assumes lock held)."""
    fd.seek(0)
    content = fd.read()
    if not content:
        return {"phase": "", "items": []}
    return json.loads(content)


def save_qr_state_atomic(state_dir: str, phase: str, qr_state: dict):
    """Write QR state atomically via tempfile + rename.

    tempfile in same directory ensures same filesystem (rename can't cross mounts).
    os.rename() is atomic on POSIX filesystems.
    """
    qr_path = get_qr_path(state_dir, phase)

    # Create tempfile in same directory as target
    fd, tmp_path = tempfile.mkstemp(
        dir=state_dir,
        prefix=f"qr-{phase}.",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(qr_state, f, indent=2)
        # Atomic rename
        os.rename(tmp_path, qr_path)
    except Exception:
        # Clean up on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def find_item(qr_state: dict, item_id: str) -> tuple[int, dict | None]:
    """Find item by ID. Returns (index, item) or (-1, None) if not found."""
    for i, item in enumerate(qr_state.get("items", [])):
        if item.get("id") == item_id:
            return i, item
    return -1, None


def _parse_update_args(args: list[str]) -> tuple[str, str | None, str | None, str | None]:
    """Parse update-item args into (item_id, status, finding, severity)."""
    item_id = args[0]
    status = finding = severity = None
    i = 1
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status = args[i + 1].upper()
            i += 2
        elif args[i] == "--finding" and i + 1 < len(args):
            finding = args[i + 1]
            i += 2
        elif args[i] == "--severity" and i + 1 < len(args):
            severity = args[i + 1].upper()
            if severity not in VALID_SEVERITIES:
                error_exit(f"Invalid severity: {severity}. Must be MUST, SHOULD, or COULD")
            i += 2
        else:
            i += 1
    return item_id, status, finding, severity


def cmd_update_item(state_dir: str, phase: str, args: list[str]):
    """Update a single QR item status.

    Delegates the locked read-modify-write, status/finding validation and
    transition rule to qr_commands.update_item so the CLI and the batch RPC
    path cannot drift; this function only parses flags and maps errors to
    the CLI's XML exit.
    """
    if not args:
        error_exit("Usage: update-item <id> --status <PASS|FAIL> [--finding <text>] [--severity <MUST|SHOULD|COULD>]")

    item_id, status, finding, severity = _parse_update_args(args)
    if not status:
        error_exit("--status required (PASS or FAIL)")

    ctx = qr_commands.QRContext(state_dir=Path(state_dir), phase=phase)
    try:
        result = qr_commands.update_item(ctx, item_id, status, finding, severity)
    except (ValueError, FileNotFoundError) as e:
        error_exit(str(e))

    print_entity_result(EntityResult(
        id=result["id"],
        version=result["version"],
        operation=result["operation"],
    ))


def cmd_get_item(state_dir: str, phase: str, args: list[str]):
    """Get a single QR item by ID. For debugging/inspection."""
    if not args:
        error_exit("Usage: get-item <id>")

    item_id = args[0]
    qr_path = get_qr_path(state_dir, phase)

    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    _, item = find_item(qr_state, item_id)
    if item is None:
        error_exit(f"Item {item_id} not found")

    print(json.dumps(item, indent=2))


def cmd_list_items(state_dir: str, phase: str, args: list[str]):
    """List all QR items with their status."""
    status_filter = None

    i = 0
    while i < len(args):
        if args[i] == "--status" and i + 1 < len(args):
            status_filter = args[i + 1].upper()
            i += 2
        else:
            i += 1

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    for item in qr_state.get("items", []):
        item_status = item.get("status", "TODO")
        if status_filter and item_status != status_filter:
            continue
        finding_str = f" | {item.get('finding', '')}" if item.get("finding") else ""
        print(f"{item.get('id')}\t{item_status}{finding_str}")


def cmd_summary(state_dir: str, phase: str, args: list[str]):
    """Print summary of QR state (counts by status)."""
    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    with open(qr_path) as f:
        qr_state = json.load(f)

    counts = {"TODO": 0, "PASS": 0, "FAIL": 0}
    for item in qr_state.get("items", []):
        status = item.get("status", "TODO")
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    print(f"Phase: {phase}")
    print(f"Total: {total}")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


def cmd_assign_group(state_dir: str, phase: str, args: list[str]):
    """Assign QR item to a group.

    Usage: assign-group <item_id> --group-id <group_id>

    Atomic update with file locking. Group assignment is idempotent.
    Does not increment version (grouping is metadata, not verification).
    """
    if not args:
        error_exit("Usage: assign-group <item_id> --group-id <group_id>")

    item_id = args[0]
    group_id = None

    i = 1
    while i < len(args):
        if args[i] == "--group-id" and i + 1 < len(args):
            group_id = args[i + 1]
            i += 2
        else:
            i += 1

    if not group_id:
        error_exit("--group-id required")

    qr_path = get_qr_path(state_dir, phase)
    if not qr_path.exists():
        error_exit(f"QR state file not found: {qr_path}")

    valid_prefixes = ('umbrella', 'parent-', 'component-', 'concern-', 'affinity-')
    if not (group_id == 'umbrella' or any(group_id.startswith(p) for p in valid_prefixes[1:])):
        error_exit(f"Invalid group_id '{group_id}'. Must be 'umbrella' or start with: parent-, component-, concern-, affinity-")

    with open(qr_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        qr_state = load_qr_state_locked(f)

        idx, item = find_item(qr_state, item_id)
        if idx < 0:
            error_exit(f"Item {item_id} not found in qr-{phase}.json")

        item["group_id"] = group_id
        qr_state["items"][idx] = item
        save_qr_state_atomic(state_dir, phase, qr_state)

    print_entity_result(EntityResult(
        id=item_id,
        version=item.get("version", 1),
        operation="updated"
    ))


COMMANDS = {
    "update-item": cmd_update_item,
    "get-item": cmd_get_item,
    "list-items": cmd_list_items,
    "summary": cmd_summary,
    "assign-group": cmd_assign_group,
}


def cli(args: list[str] = None):
    """Main CLI entrypoint."""
    if args is None:
        args = sys.argv[1:]

    if not args:
        print("Usage: python3 -m skills.planner.cli.qr --state-dir <dir> --qr-phase <phase> <command> [args]")
        print("")
        print("Global options:")
        print("  --state-dir <dir>   State directory (required)")
        print("  --qr-phase <phase>  QR phase name (required)")
        print("")
        print("Commands:")
        print("  update-item <id> --status <PASS|FAIL> [--finding <text>]")
        print("  get-item <id>")
        print("  list-items [--status <status>]")
        print("  summary")
        sys.exit(0)

    # Parse global options
    state_dir = None
    phase = None
    remaining_args = []

    i = 0
    while i < len(args):
        if args[i] == "--state-dir" and i + 1 < len(args):
            state_dir = args[i + 1]
            i += 2
        elif args[i] == "--qr-phase" and i + 1 < len(args):
            phase = args[i + 1]
            i += 2
        else:
            remaining_args.append(args[i])
            i += 1

    if not state_dir:
        error_exit("--state-dir required")
    if not phase:
        error_exit("--qr-phase required")

    if not remaining_args:
        error_exit("Command required")

    cmd = remaining_args[0]
    cmd_args = remaining_args[1:]

    # Handle batch command
    if cmd == "batch":
        methods = discover_methods(qr_commands)
        ctx = qr_commands.QRContext(state_dir=Path(state_dir), phase=phase)

        if cmd_args:
            requests = json.loads(cmd_args[0])
        else:
            requests = json.load(sys.stdin)

        results = batch_dispatch(methods, requests, ctx)
        print(json.dumps(results, indent=2))
        return

    # Handle list-methods command
    if cmd == "list-methods":
        methods = discover_methods(qr_commands)
        print(json.dumps(list_methods(methods), indent=2))
        return

    if cmd not in COMMANDS:
        error_exit(f"Unknown command: {cmd}")

    COMMANDS[cmd](state_dir, phase, cmd_args)


def main():
    cli()


if __name__ == "__main__":
    main()
