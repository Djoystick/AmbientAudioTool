from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from .predicates import Predicate


class AllNode(BaseModel):
    op: Literal["ALL"]
    nodes: list["ConditionNode"]

    @field_validator("nodes")
    @classmethod
    def require_two_or_more(cls, value: list["ConditionNode"]) -> list["ConditionNode"]:
        if len(value) < 2:
            raise ValueError("ALL node must contain at least two child nodes")
        return value


class AnyNode(BaseModel):
    op: Literal["ANY"]
    nodes: list["ConditionNode"]

    @field_validator("nodes")
    @classmethod
    def require_two_or_more(cls, value: list["ConditionNode"]) -> list["ConditionNode"]:
        if len(value) < 2:
            raise ValueError("ANY node must contain at least two child nodes")
        return value


class NotNode(BaseModel):
    op: Literal["NOT"]
    node: "ConditionNode"


class RefNode(BaseModel):
    op: Literal["REF"]
    ref_id: str = Field(min_length=1)


class PredicateNode(BaseModel):
    op: Literal["PRED"]
    predicate: Predicate


ConditionNode = Annotated[
    AllNode | AnyNode | NotNode | RefNode | PredicateNode,
    Field(discriminator="op"),
]


class ConditionExpression(BaseModel):
    id: str = Field(min_length=1)
    name: str | None = None
    root: ConditionNode


def walk_condition_tree(node: ConditionNode):
    """Yield condition nodes in depth-first order."""
    yield node
    if isinstance(node, (AllNode, AnyNode)):
        for child in node.nodes:
            yield from walk_condition_tree(child)
    elif isinstance(node, NotNode):
        yield from walk_condition_tree(node.node)


AllNode.model_rebuild()
AnyNode.model_rebuild()
NotNode.model_rebuild()
PredicateNode.model_rebuild()
