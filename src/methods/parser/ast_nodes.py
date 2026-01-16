from dataclasses import dataclass

from typing import List


@dataclass
class Line:
    indent: int
    text: str
    lineno: int


@dataclass
class Statement:
    text: str


@dataclass
class AssertBlock:
    condition: str
    else_actions: List[str]


@dataclass
class SubTask:
    label: str


@dataclass
class Block:
    body: list


@dataclass
class FunctionDef:
    name: str
    body: list
