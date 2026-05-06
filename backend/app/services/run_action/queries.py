from ...schemas import (
    ATTEMPT_OUTPUT_STREAM,
    RunAttemptListResponse,
    RunAttemptOutputChunkResponse,
    RunAttemptResponse,
    RunAttemptScriptResponse,
    RunLogResponse,
    RunResponse,
    RunSummaryListResponse,
)
from ...storage.run_store import list_run_records, load_run_record, read_run_log
from ...tools.safe_fs import safe_read_file
from .formatters import (
    find_attempt_record,
    get_attempt_records,
    to_run_attempt_response,
    to_run_response,
    to_run_summary_response,
)
from .types import (
    ATTEMPT_OUTPUT_CHUNK_LIMIT,
    ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT,
    AttemptRecord,
    RunRecord,
)


def _load_run_record_for_query(run_id: str) -> RunRecord | None:
    return load_run_record(run_id, allow_invalid=True)


def _get_attempt_for_query(run_id: str, attempt_number: int) -> tuple[RunRecord, AttemptRecord] | None:
    record = _load_run_record_for_query(run_id)
    if record is None:
        return None

    attempt = find_attempt_record(record, attempt_number)
    if attempt is None:
        return None
    return record, attempt


def get_run(run_id: str) -> RunResponse | None:
    record = _load_run_record_for_query(run_id)
    if record is None:
        return None
    return to_run_response(record)


def get_run_attempts(run_id: str) -> RunAttemptListResponse | None:
    record = _load_run_record_for_query(run_id)
    if record is None:
        return None
    attempts = [to_run_attempt_response(item) for item in get_attempt_records(record)]
    return RunAttemptListResponse(
        run_id=run_id,
        attempt_count=int(record.get("attempt_count") or len(attempts)),
        attempts=attempts,
    )


def get_run_attempt(run_id: str, attempt_number: int) -> RunAttemptResponse | None:
    attempt_data = _get_attempt_for_query(run_id, attempt_number)
    if attempt_data is None:
        return None
    _, attempt = attempt_data
    return to_run_attempt_response(attempt)


def get_run_attempt_script(run_id: str, attempt_number: int) -> RunAttemptScriptResponse | None:
    attempt_data = _get_attempt_for_query(run_id, attempt_number)
    if attempt_data is None:
        return None

    _, attempt = attempt_data
    script_rel_path = str(attempt.get("script_rel_path") or "").strip()
    if not script_rel_path:
        return None

    try:
        content = safe_read_file(script_rel_path)
    except (FileNotFoundError, PermissionError):
        return None

    return RunAttemptScriptResponse(
        run_id=run_id,
        attempt_number=attempt_number,
        attempt_file_name=(
            str(attempt["attempt_file_name"]) if attempt.get("attempt_file_name") is not None else None
        ),
        script_rel_path=script_rel_path,
        content=content,
    )


def get_run_attempt_output_chunk(
    run_id: str,
    attempt_number: int,
    stream: ATTEMPT_OUTPUT_STREAM,
    offset: int = 0,
    limit: int = ATTEMPT_OUTPUT_CHUNK_LIMIT,
) -> RunAttemptOutputChunkResponse | None:
    attempt_data = _get_attempt_for_query(run_id, attempt_number)
    if attempt_data is None:
        return None

    _, attempt = attempt_data
    safe_offset = max(0, offset)
    safe_limit = max(1, min(limit, ATTEMPT_OUTPUT_CHUNK_MAX_LIMIT))
    raw_content = str(attempt.get(stream) or "")
    total_length = len(raw_content)
    if safe_offset > total_length:
        safe_offset = total_length
    end = min(total_length, safe_offset + safe_limit)

    return RunAttemptOutputChunkResponse(
        run_id=run_id,
        attempt_number=attempt_number,
        stream=stream,
        offset=safe_offset,
        limit=safe_limit,
        total_length=total_length,
        has_more=end < total_length,
        content=raw_content[safe_offset:end],
    )


def list_runs() -> list[RunResponse]:
    return [to_run_response(record) for record in list_run_records()]


def list_run_summaries(offset: int = 0, limit: int = 20) -> RunSummaryListResponse:
    records = list_run_records()
    safe_offset = max(0, offset)
    safe_limit = max(1, limit)
    items = [
        to_run_summary_response(record)
        for record in records[safe_offset:safe_offset + safe_limit]
    ]
    return RunSummaryListResponse(
        total=len(records),
        offset=safe_offset,
        limit=safe_limit,
        items=items,
    )


def get_run_log(run_id: str) -> RunLogResponse | None:
    record = _load_run_record_for_query(run_id)
    if record is None:
        return None
    return RunLogResponse(
        run_id=run_id,
        log_path=str(record.get("log_path")) if record.get("log_path") is not None else None,
        content=read_run_log(run_id),
    )
