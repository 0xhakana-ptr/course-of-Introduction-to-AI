# -*- coding: utf-8 -*-
"""Workspace management API routes for frontend WorkspaceSelector component."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..core.config import settings
from ..tools.safe_fs import get_effective_workspace_dir

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("")
async def get_workspace():
    ws_path = str(get_effective_workspace_dir())
    exists = os.path.isdir(ws_path)
    return {
        "path": ws_path,
        "exists": exists,
        "is_default": Path(ws_path).resolve() == settings.default_workspace_dir.resolve(),
    }


@router.put("")
async def set_workspace(data: dict):
    new_path = str(data.get("path", "")).strip()
    if not new_path:
        raise HTTPException(status_code=400, detail="Workspace path is required")
    resolved = str(Path(new_path).resolve())
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {resolved}")
    settings.accessible_project_root = None
    settings.workspace_dir = Path(resolved)
    settings.runs_dir = settings.workspace_dir / "runs"
    settings.workspace_dir.mkdir(parents=True, exist_ok=True)
    settings.runs_dir.mkdir(parents=True, exist_ok=True)
    return {"path": resolved, "updated": True}


@router.get("/info")
async def get_workspace_info():
    ws_path = str(get_effective_workspace_dir())
    if not os.path.isdir(ws_path):
        return {"path": ws_path, "exists": False, "file_count": 0, "total_size": 0, "subdirs": []}
    file_count = 0
    total_size = 0
    subdirs = []
    try:
        for entry in os.scandir(ws_path):
            if entry.is_file():
                file_count += 1
                try:
                    total_size += entry.stat().st_size
                except OSError:
                    pass
            elif entry.is_dir():
                subdirs.append(entry.name)
    except PermissionError:
        pass
    return {
        "path": ws_path,
        "exists": True,
        "file_count": file_count,
        "total_size": total_size,
        "subdirs": sorted(subdirs),
    }
