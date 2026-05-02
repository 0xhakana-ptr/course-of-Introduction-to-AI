from backend.app.schemas import RunResponse
from backend.app.storage.run_store import create_run_record, load_run_record


def create_run(prompt: str, context: str | None) -> RunResponse:
    record = create_run_record(
        prompt=prompt,
        context=context,
        status="queued",
        output="任务已创建。后续可以在这里接入异步执行器或多 Agent 工作流。",
    )
    return RunResponse(
        run_id=str(record["run_id"]),
        status=str(record["status"]),
        output=str(record["output"]),
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
    )


def get_run(run_id: str) -> RunResponse | None:
    record = load_run_record(run_id)
    if record is None:
        return None
    return RunResponse(
        run_id=str(record["run_id"]),
        status=str(record["status"]),
        output=str(record["output"]),
        created_at=str(record["created_at"]),
        updated_at=str(record["updated_at"]),
    )
