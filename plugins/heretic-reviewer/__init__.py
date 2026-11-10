"""Automatic advisory reviews without changing the conversation leader."""

from .reviewer import HereticReviewer


def register(ctx):
    reviewer = HereticReviewer()
    ctx.register_hook("pre_llm_call", reviewer.capture)
    ctx.register_hook("post_tool_call", reviewer.tool_completed)
    ctx.register_hook("pre_response", reviewer.review)
    ctx.register_hook("on_session_end", reviewer.forget)
    ctx.register_hook("on_session_reset", reviewer.forget)
