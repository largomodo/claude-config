# tests/

Test suite for skills workflow framework.

## Files

| File                         | What                                                 | When to read                                                       |
| ---------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------ |
| `README.md`                  | Test framework architecture, design decisions        | Understanding test design, modifying tests                         |
| `conftest.py`                | Pytest configuration, fixtures, shared utilities     | Modifying test setup, adding fixtures                              |
| `test_workflow_import.py`    | Skill module import tests                            | Debugging import failures                                          |
| `test_workflow_structure.py` | Workflow structural validation tests                 | Debugging validation failures                                      |
| `test_workflow_steps.py`     | Exhaustive parametrized tests for all workflow steps | Running workflow tests, debugging failures                         |
| `test_qr_verify_routing.py`  | QR verify routing, confirm/summary text, decompose/verify dispatch text, walkthrough order, step-count constants | Debugging QR verify routing; changing shared/steps.py dispatch text or decompose steps |
| `test_domain_types.py`       | Unit tests for BoundedInt, ChoiceSet, Constant       | Testing domain type behavior                                       |
| `test_generation.py`         | Schema extraction and input generation for tests     | Modifying test case generation                                     |
| `test_ast.py`                | Property-based AST node and renderer tests           | Testing AST construction and rendering                             |
| `test_serena_policy.py`      | Serena tool-name, allowlist and preamble guards      | Changing agents tools lists, code-navigation convention, serena.py |
| `test_qr_cli.py`             | Verdict transition matrix, iteration stamping and backfill | Changing update-item rules, increment_qr_iteration |
| `test_plan_scope.py`         | Plan file scope union, porcelain parsing, delta classification | Changing fix-mode scope guidance or plan_scope.py |
| `test_plan_handoff.py`       | Provenance header round-trip, executor state resolution, DELIVER block | Changing plan.md provenance or executor --plan-file |

## Test Execution

```bash
# Run all tests (canonical: pydantic and hypothesis tests run instead of skipping)
uvx --with pydantic --with hypothesis pytest tests/ -v

# Run specific test file
pytest tests/test_workflow_steps.py -v

# Run tests for specific workflow
pytest tests/ -k deepthink -v

# Run import tests only
pytest tests/test_workflow_import.py -v

# Run structure validation tests only
pytest tests/test_workflow_structure.py -v
```
