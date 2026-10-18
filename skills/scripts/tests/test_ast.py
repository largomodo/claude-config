"""Property-based tests for AST nodes and renderer.

Test strategy:
- Normal: Each node type renders to expected XML structure
- Edge: Empty children list, None optional fields
- Use hypothesis for generative testing

Node types tested: TextNode, CodeNode, ElementNode
Builder tested: W.el() for constructing ElementNode
"""

import pytest
from hypothesis import given, strategies as st

from skills.lib.workflow.ast import (
    Node,
    Document,
    TextNode,
    CodeNode,
    ElementNode,
    ASTBuilder,
    XMLRenderer,
    render,
    W,
)
# EFFORT_LEVELS parametrizes the acceptance test so the test follows the tuple.
from skills.lib.workflow.constants import EFFORT_LEVELS
from skills.lib.workflow.ast.dispatch import (
    SubagentDispatchNode,
    TemplateDispatchNode,
    RosterDispatchNode,
)
from skills.lib.workflow.ast.dispatch_renderer import (
    render_subagent_dispatch,
    render_template_dispatch,
    render_roster_dispatch,
)


# Strategy builders for generative testing
@st.composite
def text_node(draw):
    """Generate TextNode with arbitrary content."""
    content = draw(st.text(min_size=0, max_size=100))
    return TextNode(content)


@st.composite
def code_node(draw):
    """Generate CodeNode with optional language."""
    content = draw(st.text(min_size=0, max_size=100))
    language = draw(st.one_of(st.none(), st.sampled_from(["python", "bash", "js"])))
    return CodeNode(content, language)


@st.composite
def element_node(draw):
    """Generate ElementNode with variable attrs and children."""
    tag = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll", "Lu"))))
    num_attrs = draw(st.integers(min_value=0, max_value=3))
    attrs = {f"attr{i}": draw(st.text(min_size=1, max_size=10)) for i in range(num_attrs)}
    num_children = draw(st.integers(min_value=0, max_value=2))
    children = [draw(text_node()) for _ in range(num_children)]
    return ElementNode(tag, attrs, children)


# Tests for individual node types
class TestTextNode:
    """Test TextNode rendering."""

    @given(text_node())
    def test_text_node_renders_as_plain_string(self, node):
        """TextNode should render as plain content."""
        renderer = XMLRenderer()
        result = render(Document([node]), renderer)
        assert result == node.content

    def test_empty_text_node(self):
        """Empty text content should render as empty string."""
        node = TextNode("")
        result = render(Document([node]), XMLRenderer())
        assert result == ""


class TestCodeNode:
    """Test CodeNode rendering."""

    @given(code_node())
    def test_code_node_with_language(self, node):
        """CodeNode should render with language tag if present."""
        renderer = XMLRenderer()
        result = render(Document([node]), renderer)
        if node.language:
            assert result.startswith(f"```{node.language}\n")
            assert result.endswith("```")
            assert node.content in result
        else:
            assert result.startswith("```\n")
            assert result.endswith("```")

    def test_code_node_no_language(self):
        """CodeNode without language should render generic code block."""
        node = CodeNode("print('hello')", None)
        result = render(Document([node]), XMLRenderer())
        assert result == "```\nprint('hello')\n```"


class TestElementNode:
    """Test ElementNode rendering."""

    def test_element_with_attrs_and_children(self):
        """ElementNode with attrs and children should render properly."""
        node = ElementNode(
            "div",
            {"class": "container", "id": "main"},
            [TextNode("content")]
        )
        result = render(Document([node]), XMLRenderer())
        assert '<div class="container" id="main">' in result
        assert "content" in result
        assert "</div>" in result

    def test_element_empty_children(self):
        """ElementNode with empty children should render self-closing."""
        node = ElementNode("br", {}, [])
        result = render(Document([node]), XMLRenderer())
        assert result == "<br />"

    def test_element_no_attrs(self):
        """ElementNode without attrs should render tag only."""
        node = ElementNode("p", {}, [TextNode("text")])
        result = render(Document([node]), XMLRenderer())
        assert result.startswith("<p>\n")
        assert "</p>" in result

    @given(element_node())
    def test_element_node_generative(self, node):
        """ElementNode should always produce valid XML structure."""
        renderer = XMLRenderer()
        result = render(Document([node]), renderer)
        if node.children:
            assert f"<{node.tag}" in result
            assert f"</{node.tag}>" in result
        else:
            assert f"<{node.tag}" in result
            assert "/>" in result or f"</{node.tag}>" in result


class TestBuilder:
    """Test ASTBuilder fluent API."""

    def test_builder_immutability(self):
        """Builder methods should return new instances."""
        b1 = W.el("div", TextNode("first"))
        b2 = b1.el("span", TextNode("second"))
        assert b1 is not b2
        doc1 = b1.build()
        doc2 = b2.build()
        assert len(doc1.children) == 1
        assert len(doc2.children) == 2

    def test_builder_el_with_attrs(self):
        """Builder el() should create ElementNode with attrs."""
        doc = W.el("step_header", TextNode("Title"), script="test", step="1", total="5").build()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ElementNode)
        assert doc.children[0].tag == "step_header"
        assert doc.children[0].attrs["script"] == "test"
        assert doc.children[0].attrs["step"] == "1"
        assert doc.children[0].attrs["total"] == "5"

    def test_builder_el_no_attrs(self):
        """Builder el() should work without attrs."""
        doc = W.el("current_action", TextNode("a"), TextNode("b")).build()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ElementNode)
        assert doc.children[0].tag == "current_action"
        assert len(doc.children[0].children) == 2

    def test_builder_el_empty(self):
        """Builder el() should work with no children."""
        doc = W.el("br").build()
        assert len(doc.children) == 1
        assert isinstance(doc.children[0], ElementNode)
        assert doc.children[0].tag == "br"
        assert len(doc.children[0].children) == 0

    def test_builder_core_methods_available(self):
        """Builder should provide core node type methods."""
        b = ASTBuilder()
        assert hasattr(b, "el")
        assert hasattr(b, "build")


class TestExhaustiveness:
    """Test exhaustiveness checking."""

    def test_all_node_types_render(self):
        """All 3 node types should render without error."""
        nodes = [
            TextNode("text"),
            CodeNode("code", "py"),
            ElementNode("div", {}, []),
        ]
        renderer = XMLRenderer()
        for node in nodes:
            result = render(Document([node]), renderer)
            assert isinstance(result, str)


class TestIntegration:
    """Integration tests for complex documents."""

    def test_complete_workflow_document(self):
        """Build and render complete workflow step using W.el()."""
        # Build step header
        header = W.el("step_header", TextNode("Step 1"), script="test", step="1", total="3").build()

        # Build current action with nested elements
        forbidden = ElementNode("forbidden", {}, [TextNode("Don't do this")])
        actions = W.el("current_action", TextNode("Action description"), forbidden).build()

        # Build invoke_after
        invoke = W.el("invoke_after", TextNode("python test.py --step 2")).build()

        # Combine into document
        doc = Document(header.children + actions.children + invoke.children)
        result = render(doc, XMLRenderer())

        assert "step_header" in result
        assert "current_action" in result
        assert "invoke_after" in result
        assert "Step 1" in result
        assert 'script="test"' in result

    def test_nested_elements(self):
        """Test deeply nested element structure."""
        inner = ElementNode("inner", {}, [TextNode("content")])
        middle = ElementNode("middle", {}, [inner])
        outer = ElementNode("outer", {"level": "1"}, [middle])

        result = render(Document([outer]), XMLRenderer())

        assert '<outer level="1">' in result
        assert "<middle>" in result
        assert "<inner>" in result
        assert "content" in result
        assert "</inner>" in result
        assert "</middle>" in result
        assert "</outer>" in result


class TestDispatchEffort:
    """Effort field on the three dispatch nodes and its rendering.

    The effort lever exists only if scripts can set it per dispatch, so every node type must
    carry, validate and render it the same way.
    """

    @staticmethod
    def _node(index, effort):
        """One node of dispatch type `index` (0 subagent, 1 template, 2 roster) built with effort.

        Construction runs __post_init__, so an invalid effort raises here.
        """
        builders = (
            lambda: SubagentDispatchNode(agent_type="general-purpose", command="python3 -m x --step 1", effort=effort),
            lambda: TemplateDispatchNode(
                agent_type="general-purpose",
                template="Explore $name",
                targets=({"name": "a"}, {"name": "b"}),
                command="python3 -m x --name $name",
                effort=effort,
            ),
            lambda: RosterDispatchNode(
                agent_type="general-purpose",
                shared_context="ctx",
                agents=("one", "two"),
                command="python3 -m x --step 1",
                effort=effort,
            ),
        )
        return builders[index]()

    def _nodes(self, effort):
        """One node of each dispatch type built with the same effort."""
        return [self._node(i, effort) for i in range(3)]

    def test_effort_rendered_for_each_node_type(self):
        """A set effort reaches the rendered text of every node type."""
        sub, tpl, ros = self._nodes("low")
        assert "<effort>low</effort>" in render_subagent_dispatch(sub)
        assert "Set effort: low on each Task call." in render_template_dispatch(tpl)
        assert "Set effort: low on each Task call." in render_roster_dispatch(ros)

    def test_unset_effort_renders_explicit_omit_line(self):
        """An unset effort renders an explicit omit line, so no value carries over from a previous step."""
        sub, tpl, ros = self._nodes(None)
        assert "<effort>DEFAULT (omit effort parameter from Task tool)</effort>" in render_subagent_dispatch(sub)
        assert "Omit the effort parameter (agent default)." in render_template_dispatch(tpl)
        assert "Omit the effort parameter (agent default)." in render_roster_dispatch(ros)

    @pytest.mark.parametrize("index", [0, 1, 2], ids=["subagent", "template", "roster"])
    @pytest.mark.parametrize("effort", ["turbo", "HIGH", ""])
    def test_unknown_effort_raises_at_construction(self, index, effort):
        """Values outside EFFORT_LEVELS, including wrong case and the empty string, fail when each node type is built."""
        with pytest.raises(ValueError, match="effort must be one of"):
            self._node(index, effort)

    @pytest.mark.parametrize("effort", EFFORT_LEVELS)
    def test_every_level_is_accepted(self, effort):
        """The accepted set equals EFFORT_LEVELS, so a level added there is covered without editing this test."""
        assert len(self._nodes(effort)) == 3

    def test_parallel_constraint_type_and_count(self):
        """The parallel constraint uses type=parallel and states the dispatch count in its one-message sentence."""
        _, tpl, ros = self._nodes(None)
        for out in (render_template_dispatch(tpl), render_roster_dispatch(ros)):
            assert '<execution_constraint type="parallel">' in out
            assert "Send all 2 Task calls in this one message" in out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
