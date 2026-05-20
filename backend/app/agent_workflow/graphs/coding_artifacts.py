from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
from threading import Lock


_ARTIFACT_LOCK = Lock()
_ARTIFACTS: dict[str, dict[str, object]] = {}
_ARTIFACT_PREFIX = "artifact://coding"


def _normalize_artifact_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower().replace("_", "-")
    return normalized or "artifact"


def store_coding_artifact(
    kind: str,
    payload: Mapping[str, object],
) -> str:
    artifact_kind = _normalize_artifact_kind(kind)
    artifact_payload = deepcopy(dict(payload))
    digest = sha256(repr((artifact_kind, artifact_payload)).encode("utf-8")).hexdigest()[:16]
    artifact_ref = f"{_ARTIFACT_PREFIX}/{artifact_kind}/{digest}"
    with _ARTIFACT_LOCK:
        _ARTIFACTS[artifact_ref] = artifact_payload
    return artifact_ref


def read_coding_artifact(artifact_ref: str) -> dict[str, object] | None:
    with _ARTIFACT_LOCK:
        artifact = _ARTIFACTS.get(str(artifact_ref or "").strip())
        return deepcopy(artifact) if artifact is not None else None


def clear_coding_artifacts() -> None:
    with _ARTIFACT_LOCK:
        _ARTIFACTS.clear()
