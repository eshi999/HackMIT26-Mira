from datetime import UTC, datetime

from mira.context.encoding import estimate_tokens
from mira.context.models import ContextRequest, UsageTelemetry


def usage(
    request: ContextRequest,
    text: str,
    count: int,
    *,
    enabled: bool,
    model: str | None = None,
    provider_input_tokens: int | None = None,
    provider_output_tokens: int | None = None,
) -> UsageTelemetry:
    if provider_input_tokens is None and provider_output_tokens is not None:
        raise ValueError("Provider output usage requires provider input usage")
    if any(
        value is not None and value < 0 for value in (provider_input_tokens, provider_output_tokens)
    ):
        raise ValueError("Token counts cannot be negative")
    reported = provider_input_tokens is not None
    return UsageTelemetry(
        task_id=request.task_id,
        company_id=request.company_id,
        profile=request.profile,
        model=model,
        context_items=count,
        context_bytes=len(text.encode("utf-8")),
        input_tokens=provider_input_tokens if reported else estimate_tokens(text),
        output_tokens=provider_output_tokens,
        optimization_enabled=enabled,
        timestamp=datetime.now(UTC),
        usage_source="provider_reported" if reported else "estimated",
        scope="provider_run"
        if reported
        else "serialized_context_only_excludes_instructions_and_tool_repeats",
    )
