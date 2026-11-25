import asyncio
import json
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import patch, AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain.agents.middleware import TodoListMiddleware
from src.test.test_progressive_skills import RecordingModel
from src.agent.tool_policy import ReadOnlyToolPolicy, select_tools
from src.agent.main_agent import create_main_agent
from src.api_view.api import chat
from src.agent.backends.sandbox_manager import sandbox_manager

pytestmark = pytest.mark.unit

def call(name, args, id="call-1"):
    return AIMessage(content="", tool_calls=[{"name":name,"args":args,"id":id}])

@tool
def erpnext_suppliers(query: dict) -> str:
    """读取模拟供应商。"""
    return "SUP-001"

@tool
def order_create() -> str:
    """禁止的写入操作。"""
    raise AssertionError("Must never execute")

def build_main(model, tools=None, store=None):
    from src.test.test_hybrid_review import reviewer
    mock_reviewer = reviewer()
    with patch("src.agent.middlewares.review_gate.SafeRubricMiddleware", return_value=mock_reviewer), patch("src.agent.main_agent.get_llm",return_value=model), patch("src.agent.tools.mcp_client.load_mcp_tools_sync",return_value=tools or []), patch("src.agent.jev_router.build_review_router",return_value=None):
        return create_main_agent(checkpointer=InMemorySaver(), store=store)

async def test_actual_main_planning_create_update_and_query():
    model=RecordingModel(responses=[
        call("write_todos",{"todos":[{"content":"查询供应商","status":"in_progress"}]}),
        call("erpnext_suppliers",{"query":{}}),
        call("write_todos",{"todos":[{"content":"查询供应商","status":"completed"}]}),
        AIMessage(content="done"),
    ])
    graph=build_main(model,[erpnext_suppliers, order_create])
    states=[s async for s in graph.astream({"messages":[HumanMessage(content="查询供应商")]}, {"configurable":{"thread_id":"plan"}}, stream_mode="values")]
    assert any(s.get("todos",[{}])[0].get("status")=="in_progress" for s in states if s.get("todos"))
    assert states[-1]["todos"][0]["status"] == "completed"
    assert any(getattr(m,"content",None)=="SUP-001" for m in states[-1]["messages"])
    assert all("order_create" not in str(getattr(t,"name",t)) for t in select_tools([order_create]))

async def test_actual_procurement_subagent_delegation():
    child=RecordingModel(responses=[call("erpnext_suppliers",{"query":{}}), AIMessage(content="SUP-001")])
    parent=RecordingModel(responses=[call("task",{"description":"查询供应商","subagent_type":"procurement-order"}),AIMessage(content="done")])
    from src.agent.subagents.loader import resolve_subagent_tools as resolve
    def resolve_with_model(configs, tools):
        specs=resolve(configs,tools)
        for spec in specs: spec["model"]=child
        return specs
    with patch("src.agent.subagents.loader.resolve_subagent_tools", side_effect=resolve_with_model):
        graph=build_main(parent,[erpnext_suppliers])
    result=await graph.ainvoke({"messages":[HumanMessage(content="查询供应商")]},{"configurable":{"thread_id":"delegate"}})
    assert result["messages"][-1].content == "done"
    assert len(child.seen)==2
    assert "SUP-001" in str(child.seen[-1])

@pytest.mark.parametrize("decision,expected",[("approve",1),("reject",0)])
async def test_real_graph_hitl_via_api_and_sse(decision, expected):
    executed=[]
    @tool
    def review_proposal() -> str:
        """审批本地测试提案，不调用 ERP。"""
        executed.append(True)
        return "proposal reviewed"
    model=RecordingModel(responses=[call("review_proposal",{}),AIMessage(content="done")])
    graph=create_deep_agent(model=model,tools=[review_proposal],backend=StateBackend(),checkpointer=InMemorySaver(),
        interrupt_on={"review_proposal":{"allowed_decisions":["approve","reject"]}})
    session=SimpleNamespace(agent=graph,run_lock=asyncio.Lock())
    app=FastAPI();app.include_router(chat.router)
    with ExitStack() as stack:
        stack.enter_context(patch("src.agent.config.LLM_API_KEY", "scripted-test"))
        for name in ["initialize","save_display_messages","save_harness_trace","save_conversation"]:
            stack.enter_context(patch.object(chat.agent_loader,name,AsyncMock()))
        stack.enter_context(patch.object(chat.agent_loader,"get_session",AsyncMock(return_value=session)))
        stack.enter_context(patch.object(chat.agent_loader,"get_conversation_user_id",AsyncMock(return_value="user-001")))
        stack.enter_context(patch.object(chat.agent_loader,"get_display_messages",AsyncMock(return_value=[])))
        stack.enter_context(patch.object(sandbox_manager,"acquire_lease",return_value=False))
        with TestClient(app) as client:
            first=client.post("/api/chat/stream",json={"message":"review","thread_id":decision,"user_id":"user-001"})
            assert "event: interrupt" in first.text
            assert '"interrupted": true' in first.text
            resumed=client.post(f"/api/chat/{decision}/resume",json={"resume_data":{"decisions":[{"type":decision}]}})
            assert resumed.status_code == 200, resumed.text
            assert "event: done" in resumed.text
            assert '"interrupted": false' in resumed.text
            assert "event: error" not in resumed.text
            assert len(executed)==expected
            duplicate=client.post(f"/api/chat/{decision}/resume",json={"resume_data":{"decisions":[{"type":decision}]}})
            assert duplicate.status_code == 409

@pytest.mark.parametrize("name",["order_create","execute","install_skill","unknown_write"])
async def test_tool_policy_blocks_sync_and_async(name):
    from unittest.mock import Mock
    request=SimpleNamespace(tool_call={"name":name,"id":"x","args":{}})
    sync=Mock();async_handler=AsyncMock()
    policy=ReadOnlyToolPolicy()
    assert policy.wrap_tool_call(request,sync).status=="error"
    assert (await policy.awrap_tool_call(request,async_handler)).status=="error"
    sync.assert_not_called();async_handler.assert_not_called()

async def test_legacy_transport_cannot_write():
    from src.mcp_server.http_base import ERPHttpClient
    for name in ("get","post","put","patch","delete"):
        with pytest.raises(PermissionError): await getattr(ERPHttpClient(),name)("/anything")

def test_resume_validation():
    from src.agent.schema import ResumeRequest
    from pydantic import ValidationError
    assert ResumeRequest.model_validate({"resume":{"decisions":[{"type":"reject"}]}}).resume_data.decisions[0].type=="reject"
    for data in [{}, {"decisions":[]}, {"decisions":[{"type":"edit"}]}, {"decisions":[{"type":"approve"}],"supplement":"x"}]:
        with pytest.raises(ValidationError): ResumeRequest(resume_data=data)

async def test_real_main_sse_plan_tool_and_completion():
    model=RecordingModel(responses=[
        call("write_todos",{"todos":[{"content":"读取供应商","status":"in_progress"}]}),
        call("erpnext_suppliers",{"query":{}}),
        call("write_todos",{"todos":[{"content":"读取供应商","status":"completed"}]}),AIMessage(content="done")])
    graph=build_main(model,[erpnext_suppliers])
    session=SimpleNamespace(agent=graph,run_lock=asyncio.Lock())
    with ExitStack() as stack:
        stack.enter_context(patch.object(chat.agent_loader,"get_session",AsyncMock(return_value=session)))
        stack.enter_context(patch.object(chat.agent_loader,"get_display_messages",AsyncMock(return_value=[])))
        for name in ("save_display_messages","save_harness_trace","save_conversation"):
            stack.enter_context(patch.object(chat.agent_loader,name,AsyncMock()))
        stack.enter_context(patch.object(sandbox_manager,"acquire_lease",return_value=False))
        chunks=[s async for s in chat.stream_chat_response("查询供应商","sse-plan")]
    events=[(s.splitlines()[0][7:],json.loads(s.splitlines()[1][6:])) for s in chunks]
    kinds={k for k,v in events}
    assert {"todo_update","tool_start","tool_result","tool_end","done"} <= kinds
    assert "error" not in kinds
    assert any(k=="review_result" and v["verdict"]=="satisfied" for k,v in events)
    assert any(k=="todo_update" and any(t["status"]=="completed" for t in v.get("todos",[])) for k,v in events)

async def test_approval_never_overrides_write_policy():
    model=RecordingModel(responses=[call("order_create",{}),AIMessage(content="blocked")])
    graph=create_deep_agent(model=model,tools=[order_create],backend=StateBackend(),checkpointer=InMemorySaver(),
        middleware=[ReadOnlyToolPolicy()],interrupt_on={"order_create":{"allowed_decisions":["approve","reject"]}})
    config={"configurable":{"thread_id":"deny-write"}}
    first=await graph.ainvoke({"messages":[HumanMessage(content="create")]},config)
    assert first.get("__interrupt__")
    result=await graph.ainvoke(Command(resume={"decisions":[{"type":"approve"}]}),config)
    assert any(getattr(m,"status",None)=="error" and "只读策略" in str(m.content) for m in result["messages"])
    assert result["messages"][-1].content=="blocked"
