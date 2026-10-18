"""Plain-text prompt building blocks for workflows.

Prompts as strings composed via f-strings. No XML, no AST.
"""

from skills.lib.workflow.prompts.subagent import (
    # Configuration
    # EFFORT_LEVELS is re-exported so leaf scripts that pick an effort per dispatch import it from here.
    EFFORT_LEVELS,
    # Building blocks
    task_tool_instruction,
    sub_agent_invoke,
    parallel_constraint,
    # Dispatch templates
    subagent_dispatch,
    template_dispatch,
    roster_dispatch,
)
# format_step provides step assembly: body content + continuation directive
from skills.lib.workflow.prompts.step import format_step
# format_file_content provides file content embedding with 4-backtick fencing
from skills.lib.workflow.prompts.file import format_file_content
# Serena REPL policy: read/edit/docs preambles plus the MCP tool names and
# facade-method tuples, so mode_main and leaf sub-agent scripts share one
# import surface
from skills.lib.workflow.prompts.serena import (
    SERENA_READ_PREAMBLE,
    SERENA_EDIT_PREAMBLE,
    SERENA_DOCS_PREAMBLE,
    SERENA_MCP_TOOLS,
    SERENA_READ_METHODS,
    SERENA_EDIT_METHODS,
    SERENA_MEMORY_READ_METHODS,
    SERENA_SUBAGENT_DENIED_METHODS,
    SERENA_HOST_COVERED_METHODS,
)

# Renaming a name listed here requires updating its importers (cli.py, leaf
# scripts, tests) in the same change.
__all__ = [
    # Configuration
    "EFFORT_LEVELS",
    # Building blocks
    "task_tool_instruction",
    "sub_agent_invoke",
    "parallel_constraint",
    # Dispatch templates
    "subagent_dispatch",
    "template_dispatch",
    "roster_dispatch",
    # Step assembly
    "format_step",
    # File content embedding
    "format_file_content",
    # Serena REPL policy
    "SERENA_READ_PREAMBLE",
    "SERENA_EDIT_PREAMBLE",
    "SERENA_DOCS_PREAMBLE",
    "SERENA_MCP_TOOLS",
    "SERENA_READ_METHODS",
    "SERENA_EDIT_METHODS",
    "SERENA_MEMORY_READ_METHODS",
    "SERENA_SUBAGENT_DENIED_METHODS",
    "SERENA_HOST_COVERED_METHODS",
]
