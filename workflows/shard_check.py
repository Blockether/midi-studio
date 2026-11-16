"""Shard check: a temporary workflow for a test of the shards. Remove it after the test."""

from durable.workflows import activity, workflow


@activity(title="First")
def first(ctx, mode: str) -> str:
    return ctx.ask(f"Reply with only this one word: {mode}")


@activity(title="Approve")
def approve(ctx):
    return ctx.gate("go", "Approve the step")


@activity(title="Second")
def second(ctx) -> str:
    return ctx.ask("Reply with only this one word: second")


@activity(title="Delegate")
def split(ctx) -> list[str]:
    return ctx.delegate(["Reply with only the one word: one", "Reply with only the one word: two"])


@workflow(title="Shard check")
def shard_check(ctx, mode: str = "ask"):
    a = first(ctx, mode)
    if mode == "gate":
        return {"a": a, "b": second(ctx)} if approve(ctx).approved else {"a": a}
    if mode == "team":
        return {"a": a, "answers": split(ctx)}
    return {"a": a, "b": second(ctx)}
