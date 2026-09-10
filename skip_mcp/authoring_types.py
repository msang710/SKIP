"""Discoverable authoring inputs, derived from the Core record field registry."""
from typing import Literal, Union
from typing_extensions import TypedDict, NotRequired
from skip_core.records import FIELDS, CHILDREN

class AuthoringBase(TypedDict):
    goal_id: str
    request_id: str

class Target(TypedDict):
    kind: Literal['decision','requirement','plan','work_item']
    id: str
    revision: int

def record_type(kind):
    fields = TypedDict(kind+'Fields', {k: str for k in FIELDS[kind] if k != 'request_id'})
    groups = {}
    for group, (_, _, _, columns) in CHILDREN[kind].items():
        props = {}
        for col in columns:
            value = int if col.endswith('_revision') or col in ('position','required','recommended') else str
            if col.endswith('_revision') or col == 'position' or (group in ('options','criteria','checks','items') and col in ('option_id','criterion_id','check_id','item_id')):
                value = NotRequired[value]
            props[col] = value
        child = TypedDict(kind+group+'Item', props)
        child.__pydantic_config__={'extra':'forbid'}
        groups[group] = NotRequired[list[child]]
    children = TypedDict(kind+'Children', groups)
    fields.__pydantic_config__={'extra':'forbid'}
    children.__pydantic_config__={'extra':'forbid'}
    submission = TypedDict(kind+'Submission', {'client_ref':str, 'kind':Literal[kind], 'fields':fields, 'children':NotRequired[children]})
    submission.__pydantic_config__={'extra':'forbid'}
    return submission

Submission = Union[tuple(record_type(k) for k in ('decision','requirement','plan','work_item'))]

class Amendment(TypedDict):
    target: Target
    set_fields: NotRequired[dict[str,str]]
    upsert_items: NotRequired[dict[str,list[dict]]]
    remove_items: NotRequired[dict[str,list[dict]]]

class CheckResult(TypedDict):
    check_id: str
    verdict: Literal['PASS','FAIL','NOT_RUN','INCONCLUSIVE']
    explanation: str

class CriterionResult(TypedDict):
    requirement_id: str
    requirement_revision: int
    criterion_id: str
    verdict: Literal['PASS','FAIL','NOT_RUN','INCONCLUSIVE']
    explanation: str

class Output(TypedDict):
    media_type: str
    text: str

class ResultEvidence(TypedDict):
    surface: Literal['source','unit','integration','typecheck','build','package','install','runtime','ui','device','production']
    result: Literal['PASS','FAIL','NOT_RUN','INCONCLUSIVE']
    summary: str
    method: str
    purpose: NotRequired[Literal['verification','injection']]
    checks: NotRequired[list[CheckResult]]
    criteria: NotRequired[list[CriterionResult]]
    payload: NotRequired[Output]

class CurrentFact(TypedDict):
    statement: str
    source_id: str
    supersedes_id: NotRequired[str]

class FailureReport(TypedDict):
    classification: Literal['product','tool','reported','injected','unclassified']
    expected: NotRequired[str]
    conditions: NotRequired[str]
    case_id: NotRequired[str]
    action: NotRequired[str]

for model in (AuthoringBase,Target,Amendment,CheckResult,CriterionResult,Output,ResultEvidence,CurrentFact,FailureReport):
    model.__pydantic_config__={'extra':'forbid'}
