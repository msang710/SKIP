"""Public semantic input schema. References never assert host provenance."""
from typing import Literal, Union
from typing_extensions import TypedDict, NotRequired
from .authoring_types import Submission

class Span(TypedDict):
    part_id: str
    start: int
    end: int

class TargetRef(TypedDict):
    kind: Literal['goal','decision','requirement','plan','work_item','evidence']
    id: str
    revision: int

class IntentBody(TypedDict):
    acts: list[Literal['answer','investigate','decide','requirements','design','tasks','implement','validate','deploy','resume','cancel','create_goal','record','unresolved']]
    constraints: list[Literal['implement','deploy','design_change']]
    targets: list[TargetRef]
    evidence_spans: list[Span]
    unresolved: list[str]

class GoalFields(TypedDict):
    title: str
    intent: str
    success_definition: str

class CreateTarget(TypedDict):
    mode: Literal['create']
    fields: GoalFields

class ExistingTarget(TypedDict):
    mode: Literal['existing']
    goal_id: str
    revision: int

class NoTarget(TypedDict):
    mode: Literal['none']

EntryTarget = Union[CreateTarget,ExistingTarget,NoTarget]

class EntrySubmission(TypedDict):
    input_id: str
    input_digest: str
    expected_revision: int
    body: IntentBody
    target: EntryTarget
    records: list[Submission]


class GoalChange(TypedDict):
    id: str
    revision: int
    state_version: int
    from_state: Literal['active','held','completed','archived']
    to_state: Literal['active','held','completed','archived']
    reason: str
    evidence: list[TargetRef]

class GoalTransition(TypedDict):
    input_id: str
    input_digest: str
    evidence_spans: list[Span]
    changes: list[GoalChange]


class RecordReplacement(TypedDict):
    kind: Literal['decision','requirement','plan','work_item']
    id: str
    revision: int

class RecordStateSubmission(TypedDict):
    kind: Literal['goal','decision','requirement','plan','work_item']
    id: str
    revision: int
    state_version: int
    from_state: Literal['active','held','completed','rejected','superseded','archived']
    to_state: Literal['active','held','completed','rejected','superseded','archived']
    reason: NotRequired[str]
    replacement: NotRequired[RecordReplacement | None]

RecordReplacement.__pydantic_config__={'extra':'forbid'}
RecordStateSubmission.__pydantic_config__={'extra':'forbid'}
