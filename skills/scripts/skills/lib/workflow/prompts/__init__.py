"""Plain-text prompt building blocks for workflows.

Prompts as strings composed via f-strings. No XML, no AST.
"""

from skills.lib.workflow.prompts.subagent import (
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
# Serena tool policy: read/edit preambles plus the tool-name tuples, so
# mode_main and leaf sub-agent scripts share one import surface
from skills.lib.workflow.prompts.serena import (
    SERENA_READ_PREAMBLE,
    SERENA_EDIT_PREAMBLE,
    SERENA_READ_TOOLS,
    SERENA_EDIT_TOOLS,
    SERENA_MEMORY_READ_TOOLS,
    SERENA_SUBAGENT_DENIED_TOOLS,
    SERENA_EXCLUDED_TOOLS,
)

__all__ = [
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
    # Serena tool policy
    "SERENA_READ_PREAMBLE",
    "SERENA_EDIT_PREAMBLE",
    "SERENA_READ_TOOLS",
    "SERENA_EDIT_TOOLS",
    "SERENA_MEMORY_READ_TOOLS",
    "SERENA_SUBAGENT_DENIED_TOOLS",
    "SERENA_EXCLUDED_TOOLS",
]
