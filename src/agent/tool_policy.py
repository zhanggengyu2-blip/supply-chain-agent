"""阶段一允许名单，由主 Agent 和所有子 Agent 共同使用。

审批不会授予 ERP 写权限；遇到未知工具时默认拒绝。
虚拟文件系统工具操作图状态，不操作宿主机文件系统。
"""
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

ERP_READ_TOOLS = frozenset({"erpnext_suppliers", "erpnext_items", "erpnext_warehouses", "erpnext_bins", "erpnext_purchase_orders"})
LOCAL_TOOLS = frozenset({"write_todos", "task", "read_memory", "remember", "list_skills", "read_skill", "read_skill_resource",
    "ls", "read_file", "write_file", "edit_file", "glob", "grep", "compact_conversation"})
ALLOWED_TOOLS = ERP_READ_TOOLS | LOCAL_TOOLS

def select_tools(tools):
    return [tool for tool in tools if tool.name in ALLOWED_TOOLS]

class ReadOnlyToolPolicy(AgentMiddleware):
    """运行时的兜底限制，同时拦截模型编造或动态添加的未授权工具。"""
    def wrap_tool_call(self, request, handler):
        if request.tool_call["name"] not in ALLOWED_TOOLS:
            return ToolMessage(content="工具被阶段一只读策略阻止；人工审批不能解除此限制。", status="error", tool_call_id=request.tool_call["id"])
        return handler(request)

    async def awrap_tool_call(self, request, handler):
        if request.tool_call["name"] not in ALLOWED_TOOLS:
            return ToolMessage(content="工具被阶段一只读策略阻止；人工审批不能解除此限制。", status="error", tool_call_id=request.tool_call["id"])
        return await handler(request)
