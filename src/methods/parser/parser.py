import re
from abc import ABC, abstractmethod
from typing import List, Any, Tuple

from .ast_nodes import Line, SubTask, Statement, AssertBlock, FunctionDef

ASSERT_RE = re.compile(r"\s*assert\((.+)\)$")
ELSE_RE = re.compile(r"\s*else:\s*(.+)$")
COMMENT_RE = re.compile(r"\s*#\s*(.+)$")
FUNC_RE = re.compile(r"^def (\w+)\(\):$")
ACTION_RE = re.compile(r"\b(?<!\.)([^:\.\s_]+)\(.*\)")


def tokenize_lines(text: str) -> list[Line]:
    lines = []
    for lineno, raw in enumerate(text.splitlines()):
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        lines.append(Line(indent, raw.strip(), lineno))
    return lines


class LineParser(ABC):
    @abstractmethod
    def match(self, lines: list[Line], index: int) -> bool: ...

    @abstractmethod
    def parse(
        self,
        lines: list[Line],
        index: int,
    ) -> Tuple[Any, int] | None:
        """
        Returns: (node, lines_consumed)
        """
        ...


class CommentTaskParser(LineParser):
    def match(self, lines, index):
        return bool(COMMENT_RE.match(lines[index].text))

    def parse(self, lines, index):
        m = COMMENT_RE.match(lines[index].text)

        if not m:
            return

        return SubTask(m.group(1).strip()), 1


class AssertParser(LineParser):
    def match(self, lines, index):
        return bool(ASSERT_RE.match(lines[index].text))

    def parse(self, lines, index):
        m = ASSERT_RE.match(lines[index].text)

        if not m:
            return

        condition = m.group(1).strip()
        else_actions = []
        consumed = 1

        while index + consumed < len(lines):
            line = lines[index + consumed].text
            m = ELSE_RE.match(line)

            if not m:
                break

            else_actions.append(m.group(1).strip())
            consumed += 1

        return AssertBlock(condition, else_actions), consumed


class StatementParser(LineParser):
    def match(self, lines, index):
        line = lines[index].text
        return bool(line) and not line.startswith("#")

    def parse(self, lines, index):
        return Statement(lines[index].text), 1


class IndentationParser:
    def __init__(self, line_parsers: List[LineParser]):
        self.line_parsers: List[LineParser] = line_parsers

    def parse_block(self, lines: List[Line], start: int):
        ast = []
        index = start
        base_indent = lines[start].indent

        while index < len(lines):
            line = lines[index]

            if line.indent < base_indent:
                break

            parsed_line = self.parse_line(lines, index)

            if not parsed_line:
                index += 1
                continue

            node, consumed = parsed_line
            ast.append(node)
            index += consumed

        return ast, index

    def parse_line(self, lines: List[Line], index: int):
        for parser in self.line_parsers:
            if parser.match(lines, index):
                return parser.parse(lines, index)

        raise SyntaxError(f"Invalid syntax at line {lines[index].lineno}")


class FunctionParser(LineParser):
    def __init__(self, indent_parser: IndentationParser):
        self.indent_parser = indent_parser

    def match(self, lines, index):
        return bool(FUNC_RE.match(lines[index].text))

    def parse(self, lines, index):
        m = FUNC_RE.match(lines[index].text)

        if not m:
            return None

        name = m.group(1).strip()

        body, next_index = self.indent_parser.parse_block(
            lines,
            index + 1,
        )

        return FunctionDef(name, body), next_index - index


class Parser:
    def __init__(self, parsers: list[LineParser]):
        self.parsers = parsers
        self.ast: List[FunctionDef] = []
        self.indent_parser = IndentationParser(parsers)

    def parse(self, text: str):
        lines = tokenize_lines(text)

        if len(lines) == 0:
            raise SyntaxError("No code to parse.")

        ast, _ = self.indent_parser.parse_block(lines, 0)
        self.ast = ast

    def emit_function_body(self, body: list, out: List[str]):
        subtask_count = 0
        subtasks: List[str] = []
        actions: List[str] = []
        base_indent = " " * 4

        for node in body:
            if isinstance(node, SubTask):
                out.append(f"{base_indent}task.track_subtask({subtask_count})")
                subtasks.append(node.label)
                subtask_count += 1

            elif isinstance(node, Statement):
                m = ACTION_RE.match(node.text)

                if m:
                    actions.append(m.group(1))

                out.append(f"{base_indent}{node.text}")

            elif isinstance(node, AssertBlock):
                out.append(f'{base_indent}if assert_("{node.condition}") == False:')

                for act in node.else_actions:
                    out.append(f"{base_indent * 2}{act}")

                    m = ACTION_RE.match(act)

                    if m:
                        actions.append(m.group(1))

                actions.append("assert_")

        return subtasks, list(set(actions))

    def emit(self):
        out = []
        function_artifacts: List[Tuple[List[str], List[str]]] = []

        for node in self.ast:
            if isinstance(node, FunctionDef):
                out.append(f"def {node.name}():")
                function_artifacts.append(self.emit_function_body(node.body, out))

        return "\n".join(out), function_artifacts
