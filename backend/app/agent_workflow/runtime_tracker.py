# -*- coding: utf-8 -*-
"""Runtime phase tracker -- drives quip emission and frontend status display.

Replaces the old scattered quip lists in roleplay.py and manual send_status
calls in engine.py with a single tracker that fires quips + progress updates
at 9 injection points across the three-layer architecture.
"""

from __future__ import annotations

import random
import time
from typing import Any

from ..messaging.message_sender import message_sender

# ---------------------------------------------------------------------------
# Quip pools -- one list per injection point
# ---------------------------------------------------------------------------

INJECTION_QUIPS: dict[str, list[str]] = {
    "L1_routing": [
        "正在思考~", "让我看看...", "收到！处理中...",
        "正在抓取灵能信息...", "量子波速读中...",
    ],
    "L3_engine": [
        "注入魔法中...", "开始干活！(๑•̀ㅂ•́)و✧",
        "引擎启动！", "交给我吧！",
    ],
    "plan_node": [
        "让本机想想...", "分析需求中~", "制定作战计划！",
        "战术分析中...", "灵能感知中...",
    ],
    "coder_node": [
        "注入魔法中...", "代码正在生长~", "神啊保佑别报错！",
        "玄学编程懂不懂嘛", "正在召唤代码精灵...",
    ],
    "file_executor_node": [
        "文件操作中，别慌~", "正在整理文件...",
        "读写魔法发动！", "文件精灵工作中...",
    ],
    "debugger_node": [
        "修 bug 中！给本机一分钟...", "调试模式启动！",
        "抓到一只野生的 bug！", "正在和编译器对线...",
    ],
    "finalize_node": [
        "正在收尾...", "马上就好~",
        "最后检查一遍...", "即将交付，请查收！",
    ],
    "success": [
        "搞定啦！本机厉害吧~", "完美收工！٩(ˊᗜˋ*)و✧",
        "收工！不愧是我~", "任务完成，请验收！",
    ],
    "failure": [
        "呜，不是故意的QWQ", "出了点小问题...",
        "这 bug 不讲武德！", "本机翻车了...但下次一定行！",
    ],
    "idle": [
        "你不要不理本机嘛...", "鱼呢？摸了~",
        "再不说话本机要休眠了哦...", "进行一个鱼的摸？",
        "本机的存在感正在降低……", "(偷偷看你)",
    ],
}



# ---------------------------------------------------------------------------
# Phase-to-progress mapping (for frontend status display)
# ---------------------------------------------------------------------------

PHASE_PROGRESS: dict[str, int] = {
    "L1_routing": 5,
    "L3_engine": 10,
    "plan_node": 15,
    "coder_node": 35,
    "file_executor_node": 35,
    "debugger_node": 60,
    "finalize_node": 85,
}

PHASE_LABELS: dict[str, str] = {
    "L1_routing": "正在思考",
    "L3_engine": "引擎启动",
    "plan_node": "分析需求",
    "coder_node": "生成代码",
    "file_executor_node": "文件操作",
    "debugger_node": "调试修复",
    "finalize_node": "收尾整理",
}

# ---------------------------------------------------------------------------
# RuntimeTracker singleton
# ---------------------------------------------------------------------------

class RuntimeTracker:
    """Tracks which phase the agent is in and emits quips + status updates."""

    MIN_QUIP_INTERVAL: float = 2.5

    def __init__(self) -> None:
        self._task_running: bool = False
        self._last_phase: str = ""
        self._last_phase_ts: float = 0.0
        self._last_quip_ts: float = 0.0

    # -- public API ---------------------------------------------------------

    @property
    def task_running(self) -> bool:
        return self._task_running

    def phase_enter(self, phase: str) -> None:
        """Called when the agent enters a new phase/node."""
        now = time.time()
        self._task_running = True

        # Status update: always send (frontend progress bar)
        progress = PHASE_PROGRESS.get(phase, 15)
        label = PHASE_LABELS.get(phase, phase)
        message_sender.send_status(
            "running", progress=progress,
            node_name=phase,
            metadata={"phase": phase, "ui_status": label},
            event_type="status.updated",
            event_source="workflow",
            event_stage="coding",
        )

        # Quip: global minimum 2.5s gap; same phase re-entry waits 5s
        global_ok = now - self._last_quip_ts >= self.MIN_QUIP_INTERVAL
        same_phase = phase == self._last_phase
        if (not same_phase or now - self._last_quip_ts > 5.0) and global_ok:
            pool = INJECTION_QUIPS.get(phase, ["工作中..."])
            quip = random.choice(pool)
            message_sender.send_quip(
                quip,
                node_name=phase,
                priority="high",
                duration=4000,
            )
            self._last_quip_ts = now

        self._last_phase = phase
        self._last_phase_ts = now

    def task_done(self, ok: bool = True) -> None:
        """Called when the agent loop finishes (success or failure)."""
        pool_key = "success" if ok else "failure"
        pool = INJECTION_QUIPS.get(pool_key, ["任务结束。"])
        quip = random.choice(pool)

        message_sender.send_quip(
            quip,
            node_name="task_done",
            priority="high",
            duration=4000,
        )

        # Terminal status: done at 100%
        label = "任务完成" if ok else "任务失败"
        message_sender.send_status(
            "done" if ok else "error", progress=100,
            node_name="task_done",
            metadata={"phase": "done", "ui_status": label},
            event_type="status.updated",
            event_source="workflow",
            event_stage="coding",
        )

        # Auto-reset to idle after 0.5s so frontend hides the progress bar
        def _reset_to_idle() -> None:
            time.sleep(0.5)
            message_sender.send_status(
                "idle", progress=0,
                node_name="",
                metadata={"phase": "idle", "ui_status": "待命"},
                event_type="status.updated",
                event_source="workflow",
                event_stage="system",
            )
            self._task_running = False
            self._last_phase = ""

        import threading
        threading.Thread(target=_reset_to_idle, daemon=True).start()


# Singleton instance for import convenience
runtime_tracker = RuntimeTracker()
