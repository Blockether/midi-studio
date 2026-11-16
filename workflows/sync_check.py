"""Sync check."""

from typing import Literal

from pydantic import BaseModel, Field

from durable.workflows import activity, workflow


class Verdict(BaseModel):
    decision: Literal["go", "stop"] = Field(description="go: the request is clear and useful. stop: it is not")
    reason: str


@activity(title="Decide")
def decide(ctx, request: str) -> Verdict:
    return ctx.ask(f"Read this request and decide. Do not write code.\n\n{request}", Verdict)


@activity(title="Write the report")
def report(ctx):
    return ctx.document("REPORT.md", "Write a short report about the request and your decision.")


@workflow(title="Sync check", description="Decide about a request, then write a report.")
def sync_check(ctx, request: str = "Describe the request here."):
    made = decide(ctx, request)
    if made.decision == "stop":
        ctx.note(f"Stopped: {made.reason}")
        return {"decision": "stop", "reason": made.reason}
    return {"decision": "go", "files": [report(ctx).name]}
