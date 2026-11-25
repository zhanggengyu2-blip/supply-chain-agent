"""执行证据可提升审查要求；评审不得导致写入操作被重复执行。"""
import json
from deepagents import RubricMiddleware
from langchain.agents.middleware import AgentMiddleware, hook_config
from ..harness import HarnessPhaseState
from ..review_policy import ReviewRoute, compose_rubric, reset_grading


def execution_signals(state):
    messages = state.get("messages", [])[state.get("_review_start", 0):]
    signals = set()
    writes = False
    calls = []
    for m in messages:
        for call in getattr(m, "tool_calls", []) or []:
            name = call.get("name", "").lower()
            calls.append(name)
            if any(word in name for word in ("create", "update", "delete", "remove", "inbound", "outbound", "stock_in", "stock_out", "adjust", "execute", "install")):
                writes = True
                signals.add("write_or_execution_attempt")
            if name == "task":
                # 父 Agent 的状态中可能没有子 Agent 的工具追踪。
                # 因此对委派任务采取保守策略，禁止自动重放。
                writes = True
                signals.add("delegated_task")
        if getattr(m, "type", "") == "tool":
            content = getattr(m, "content", "")
            error = getattr(m, "status", "") == "error"
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                    error |= isinstance(data, dict) and (data.get("success") is False or bool(data.get("error")))
                except (ValueError, TypeError):
                    error |= content.lstrip().lower().startswith(("error", "错误", "失败"))
            if error:
                signals.add("tool_error")
    if len(calls) >= 3:
        signals.add("multiple_tool_calls")
    if len({n for n in calls if any(x in n for x in ("search", "fetch", "query"))}) >= 2:
        signals.add("multiple_sources")
    return sorted(signals), writes


class ReviewExecutionGate(AgentMiddleware):
    """注册在 RubricMiddleware 之后，利用 after_agent 的逆序执行先运行本中间件。"""
    state_schema = HarnessPhaseState

    def __init__(self, config):
        self.config = config

    def after_agent(self, state, runtime):
        signals, writes = execution_signals(state)
        updates = {"_review_signals": signals, "_review_write_attempted": writes}
        if not signals or self.config.get("review", {}).get("mode") == "never":
            return updates
        if not state.get("rubric"):
            route = ReviewRoute(decision="review", reason="执行信号升级", checks=["sources", "constraints"])
            rubric = compose_rubric(route, self.config)
            updates.update(rubric=rubric, _harness_rubric_source="auto", **reset_grading(rubric))
        updates["review_decision"] = {**state.get("review_decision", {}), "decision": "review",
                                      "source": "execution", "signals": signals}
        return updates


class SafeRubricMiddleware(RubricMiddleware):
    """独立的单次评审器可避免重试写入，且不修改共享状态。"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._write_reviewer = RubricMiddleware(**{**kwargs, "max_iterations": 1})

    @hook_config(can_jump_to=["model"])
    def after_agent(self, state, runtime):
        if state.get("_review_write_attempted"):
            return self._write_reviewer.after_agent(state, runtime)
        return super().after_agent(state, runtime)

    @hook_config(can_jump_to=["model"])
    async def aafter_agent(self, state, runtime):
        if state.get("_review_write_attempted"):
            return await self._write_reviewer.aafter_agent(state, runtime)
        return await super().aafter_agent(state, runtime)
