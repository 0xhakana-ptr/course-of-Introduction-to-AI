from typing import Annotated

from fastapi import Query

from ..schemas import ATTEMPT_OUTPUT_STREAM


CheckRemoteQuery = Annotated[bool, Query()]
MessagesSinceIdQuery = Annotated[str | None, Query()]

SessionListOffsetQuery = Annotated[int, Query(ge=0)]
SessionListLimitQuery = Annotated[int, Query(ge=1, le=200)]

RunListOffsetQuery = Annotated[int, Query(ge=0)]
RunListLimitQuery = Annotated[int, Query(ge=1, le=100)]

AttemptOutputStreamQuery = Annotated[ATTEMPT_OUTPUT_STREAM, Query()]
AttemptOutputOffsetQuery = Annotated[int, Query(ge=0)]
AttemptOutputLimitQuery = Annotated[int, Query(ge=1, le=20000)]
