"""Plan file scope for QR fix mode.

WHY: a fix agent that sees only the failed findings edits whatever fixes them,
including files no milestone owns; the next QR round then exists only to
revert those edits. This module renders the plan's per-milestone file lists
and compares git-status snapshots taken before and after the fix.

WHY two snapshots, not one: the target repository may already hold
uncommitted work when the fix agent starts. Classifying every dirty path would
mark that work OUT OF SCOPE and the revert rule would destroy it. Only paths
that are new since the baseline snapshot are the fix agent's doing, so only
those are classified.

WHY the union: a milestone's file list can omit a path that one of its
intents or changes names. Scope is the union of files, intent and change
paths, so the list shown to the agent is not visibly narrower than the plan
and stays bounded by paths the plan itself mentions.

WHY the agent names the root: plan paths are relative to the target
repository, which is not the scripts directory this module runs from and may
not be the agent's cwd. The script cannot know it, so the instructions tell the
agent to take the git toplevel of the directory where the paths resolve and to
use that root for both snapshots.

Usage: python3 -m skills.planner.shared.plan_scope --state-dir S --phase P [--docs]
"""

import argparse
import json
import posixpath
from pathlib import Path


def _load_plan(state_dir: str) -> dict | None:
    """Parsed plan.json from state_dir, or None when it is missing or invalid.

    Called by the scope renderers and the check; None makes them degrade to an
    empty block or an UNAVAILABLE notice because fix mode must still run.
    """
    path = Path(state_dir) / "plan.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def plan_scope_paths(plan: dict) -> dict[str, list[str]]:
    """Map 'M-xxx <name>' to the sorted union of its files, intent and change paths.

    Union rather than Milestone.files alone: a milestone's file list can omit a
    path that one of its intents or changes names, and an agent shown a list
    that is visibly too narrow stops trusting it. The union stays bounded by the
    plan: it holds only paths the plan itself mentions. It is wider than
    Milestone.files; that width is accepted to keep the list credible.

    Called by format_plan_file_scope and _all_scoped to build the per-milestone scope.
    """
    scope: dict[str, list[str]] = {}
    for ms in plan.get("milestones", []):
        paths = set(ms.get("files") or [])
        paths.update(c["file"] for c in ms.get("code_intents", []) if c.get("file"))
        paths.update(c["file"] for c in ms.get("code_changes", []) if c.get("file"))
        scope[f"{ms.get('id', '?')} {ms.get('name', '')}".rstrip()] = sorted(paths)
    return scope


def _companions(plan: dict, scope: dict[str, list[str]]) -> list[str]:
    """CLAUDE.md and README.md paths beside every scoped file, plus plan README entries.

    Called for docs-phase fix mode, where index and README updates accompany
    code files and are not listed in any milestone.
    """
    dirs = {posixpath.dirname(p) for paths in scope.values() for p in paths}
    found = set()
    for d in dirs:
        for name in ("CLAUDE.md", "README.md"):
            found.add(posixpath.join(d, name) if d else name)
    # readme_entries[].path names a directory whose README.md the plan owns
    found.update(posixpath.join(r["path"], "README.md")
                 for r in plan.get("readme_entries", []) if r.get("path"))
    return sorted(found)


def _all_scoped(plan: dict, include_doc_companions: bool) -> set[str]:
    """Flat set of every path the scope check treats as in scope.

    Called by format_scope_check; include_doc_companions adds the documentation
    companions for docs-phase fixes.
    """
    scope = plan_scope_paths(plan)
    allowed = {p for paths in scope.values() for p in paths}
    if include_doc_companions:
        allowed.update(_companions(plan, scope))
    return allowed


def format_plan_file_scope(state_dir: str, include_doc_companions: bool = False) -> str:
    """Render the PLAN FILE SCOPE block, or '' when plan.json is unavailable.

    Called by the fix-mode step-1 guidance of exec_implement_qr_fix and
    exec_docs_qr_fix; the docs script sets include_doc_companions.
    """
    plan = _load_plan(state_dir)
    if plan is None:
        return ""
    scope = plan_scope_paths(plan)
    lines = [
        "PLAN FILE SCOPE:",
        "Paths are relative to the target repository root (the directory where",
        "they resolve, not the scripts directory). An edit outside this list needs",
        "a finding that names the file.",
    ]
    for header, paths in scope.items():
        lines.append(f"  {header}")
        lines.extend(f"    {p}" for p in paths)
    if include_doc_companions:
        lines.append("DOCUMENTATION COMPANIONS:")
        lines.extend(f"    {p}" for p in _companions(plan, scope))
    return "\n".join(lines)


def baseline_commands(state_dir: str, phase: str) -> list[str]:
    """Step 1 instruction lines that snapshot git status before any edit.

    WHY -uall: the default status output collapses a new untracked directory to
    a single 'dir/' entry, which would hide the files inside it from the scope
    comparison.

    Called by fix-mode step 1 of the code and docs fix scripts.
    """
    return [
        "SCOPE BASELINE (do this BEFORE any edit):",
        "  1. Choose ROOT = git toplevel of the directory where the PLAN FILE SCOPE",
        "     paths resolve (git -C <that directory> rev-parse --show-toplevel).",
        f"  2. git -C ROOT status --porcelain -uall > {state_dir}/scope-baseline-{phase}.txt",
    ]


def parse_porcelain(text: str) -> set[str]:
    """Paths named by `git status --porcelain` lines (renames keep the new path).

    A trailing-slash entry is an untracked directory collapsed by git; it is
    kept as written and classified by _is_in_scope.

    Called by format_scope_check for both the baseline and the current snapshot.
    """
    paths = set()
    for line in text.splitlines():
        if len(line) < 4:
            continue
        entry = line[3:]
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if len(entry) >= 2 and entry[0] == '"' and entry[-1] == '"':
            entry = entry[1:-1]
        paths.add(entry)
    return paths


def _is_in_scope(path: str, allowed: set[str]) -> bool:
    """True when path is allowed, or is a collapsed untracked directory holding one.

    Called once per new path by format_scope_check.
    """
    if path in allowed:
        return True
    # Collapsed untracked directory: in scope when it holds any planned path,
    # so the revert rule can never delete planned files inside it.
    return path.endswith("/") and any(a.startswith(path) for a in allowed)


def scope_check_commands(state_dir: str, phase: str, docs: bool = False,
                         header: str = "SCOPE CHECK:") -> list[str]:
    """Step 3 instruction lines shared by the code and docs fix scripts.

    WHY shared: both fix scripts must give the same revert rule, and a
    divergent copy would let one revert paths the other keeps. docs=True adds
    --docs so the check counts documentation companions as in scope: docs-phase
    fixes update CLAUDE.md and README.md files beside code, and no milestone
    lists them, so without --docs the revert rule would delete valid doc edits.

    Called by fix-mode step 3 of exec_implement_qr_fix and exec_docs_qr_fix.
    """
    docs_flag = " --docs" if docs else ""
    return [
        header,
        f"  1. git -C ROOT status --porcelain -uall > {state_dir}/scope-current-{phase}.txt",
        "     (same ROOT as the baseline)",
        f"  2. python3 -m skills.planner.shared.plan_scope --state-dir {state_dir} --phase {phase}{docs_flag} --root ROOT",
        "  3. Revert only the OUT OF SCOPE paths it lists that no fixed finding",
        "     names: `git checkout -- <path>` if tracked, delete if untracked.",
        "     Leave every other path alone.",
        "  4. If the report prints an UNAVAILABLE notice, say so in your",
        "     response instead of reverting.",
    ]


def format_scope_check(state_dir: str, phase: str,
                       include_doc_companions: bool = False,
                       root: str | None = None) -> str:
    """Classify paths changed since the baseline snapshot against the plan scope.

    When root is given and no scoped path exists under it, ROOT was chosen
    wrongly and every path would classify as OUT OF SCOPE; the report refuses
    instead. The check is existence-based, so a fix that deletes or renames
    every scoped file also yields UNAVAILABLE: a false positive that fails
    safe (nothing is reverted; the notice is reported).

    Called by this module's command-line entry point, which fix-mode step 3 runs.
    """
    base_path = Path(state_dir) / f"scope-baseline-{phase}.txt"
    cur_path = Path(state_dir) / f"scope-current-{phase}.txt"
    for p in (base_path, cur_path):
        if not p.exists():
            return (f"SCOPE CHECK UNAVAILABLE: {p.name} is missing. "
                    f"Do not revert anything; state this in your response.")
    plan = _load_plan(state_dir)
    if plan is None:
        return "SCOPE CHECK UNAVAILABLE: plan.json is missing or invalid."

    allowed = _all_scoped(plan, include_doc_companions)
    if root is not None and not any((Path(root) / p).exists() for p in allowed):
        return (f"SCOPE CHECK UNAVAILABLE: no PLAN FILE SCOPE path exists under {root}. "
                f"ROOT is probably wrong; redo the snapshots with the right git "
                f"toplevel. Do not revert anything; state this in your response.")
    new_paths = sorted(parse_porcelain(cur_path.read_text())
                       - parse_porcelain(base_path.read_text()))
    lines = ["SCOPE CHECK:"]
    for p in new_paths:
        lines.append(f"  {'IN SCOPE' if _is_in_scope(p, allowed) else 'OUT OF SCOPE'} {p}")
    if not new_paths:
        lines.append("  no new paths since baseline")
    lines.append(
        "Revert rule: OUT OF SCOPE paths not named by a fixed finding: "
        "`git checkout -- <path>` if tracked, delete if untracked. "
        "Paths present in the baseline are never touched."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Report fix-mode edits against plan scope")
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("--phase", required=True)
    ap.add_argument("--docs", action="store_true")
    ap.add_argument("--root", default=None)
    ns = ap.parse_args()
    print(format_scope_check(ns.state_dir, ns.phase, ns.docs, ns.root))
