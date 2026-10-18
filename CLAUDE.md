# claude-config

Claude Code configuration: agents, skills, conventions, and output styles for a planning-first LLM workflow.

## Files

| File         | What                                        | When to read                              |
| ------------ | ------------------------------------------- | ----------------------------------------- |
| `README.md`  | Workflow philosophy, principles, quick start | Understanding the workflow, onboarding    |
| `LICENSE`    | License terms                               | Checking usage rights                     |
| `.gitignore` | Allowlist-based tracking (ignore by default) | Adding new tracked directories or files   |
| `claude-env.md` | Untracked; written at container start by claude-env's init-workspace.sh with the container's toolchain index; absent on plain hosts | Never edit or track; imported by the Environment section |

## Subdirectories

| Directory        | What                                          | When to read                                       |
| ---------------- | --------------------------------------------- | --------------------------------------------------- |
| `agents/`        | Sub-agent definitions (architect, developer, ...) | Modifying agent behavior, adding agents          |
| `conventions/`   | Universal conventions for agents and skills   | Writing docs, QR rules, code quality checks         |
| `output-styles/` | Output style definitions                      | Changing response style                             |
| `skills/`        | Skill definitions and Python workflow scripts | Adding/modifying skills, debugging skill behavior   |
| `.github/`       | CI/CD workflows                               | Adding CI jobs, debugging workflow failures         |

## Test

```bash
cd skills/scripts && pytest tests/ -v
```

## Environment

@claude-env.md
