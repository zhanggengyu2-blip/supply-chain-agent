"""Whitespace-only model chunks carry Markdown structure and must survive SSE."""
import asyncio
import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import pytest
from langchain_core.messages import AIMessageChunk
from src.api_view.api import chat
from src.agent.backends.sandbox_manager import sandbox_manager

pytestmark=pytest.mark.unit

async def test_sse_and_saved_message_preserve_whitespace_chunks():
    pieces=['##',' ','采购调查','\n','\n','| 状态 | 结果 |','\n','| --- | --- |','\n','| 配置 | 缺失 |','\n']
    async def stream(**kwargs):
        for piece in pieces:
            yield (), 'messages', (AIMessageChunk(content=piece),{})
    session=SimpleNamespace(agent=SimpleNamespace(astream=stream),run_lock=asyncio.Lock())
    save=AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(patch.object(chat.agent_loader,'get_session',AsyncMock(return_value=session)))
        stack.enter_context(patch.object(chat.agent_loader,'get_display_messages',AsyncMock(return_value=[])))
        stack.enter_context(patch.object(chat.agent_loader,'save_display_messages',save))
        for name in ('save_harness_trace','save_conversation'):
            stack.enter_context(patch.object(chat.agent_loader,name,AsyncMock()))
        stack.enter_context(patch.object(sandbox_manager,'acquire_lease',return_value=False))
        chunks=[s async for s in chat.stream_chat_response('格式测试','format-test')]
    events=[(s.splitlines()[0][7:],json.loads(s.splitlines()[1][6:])) for s in chunks]
    assert ''.join(v['content'] for k,v in events if k=='token')==''.join(pieces)
    assert save.await_args.args[1][-1]['content']==''.join(pieces)

async def test_subagent_boundaries_and_internal_grader_are_separate():
    async def stream(**kwargs):
        for namespace,chunk in [
            ((),AIMessageChunk(content='开始')),
            (('tools:child',),AIMessageChunk(content='子Agent结果')),
            (('SafeRubricMiddleware.after_agent:grader',),AIMessageChunk(content='INTERNAL',tool_call_chunks=[{'name':'GraderResponse','args':'{}','id':'grader','index':0}])),
            ((),AIMessageChunk(content='| 状态 | 结果 |\n| --- | --- |\n| 查询 | 阻塞 |')),
        ]:
            yield namespace,'messages',(chunk,{})
    session=SimpleNamespace(agent=SimpleNamespace(astream=stream),run_lock=asyncio.Lock())
    with ExitStack() as stack:
        stack.enter_context(patch.object(chat.agent_loader,'get_session',AsyncMock(return_value=session)))
        stack.enter_context(patch.object(chat.agent_loader,'get_display_messages',AsyncMock(return_value=[])))
        for name in ('save_display_messages','save_harness_trace','save_conversation'):
            stack.enter_context(patch.object(chat.agent_loader,name,AsyncMock()))
        stack.enter_context(patch.object(sandbox_manager,'acquire_lease',return_value=False))
        chunks=[s async for s in chat.stream_chat_response('边界测试','boundary-test')]
    events=[(s.splitlines()[0][7:],json.loads(s.splitlines()[1][6:])) for s in chunks]
    content=''.join(v['content'] for k,v in events if k=='token')
    assert content.startswith('开始\n\n子Agent结果\n\n| 状态')
    assert 'INTERNAL' not in content
    assert not any(k=='tool_start' and v.get('name')=='GraderResponse' for k,v in events)


async def test_interrupted_execution_is_failed_and_partial_results_are_saved():
    async def stream(**kwargs):
        yield (), 'messages', (AIMessageChunk(content='已读取的真实样本'), {})
        raise TimeoutError('PRIVATE_PROVIDER_MESSAGE_DO_NOT_EXPORT')
    session = SimpleNamespace(agent=SimpleNamespace(astream=stream), run_lock=asyncio.Lock())
    save = AsyncMock()
    with ExitStack() as stack:
        stack.enter_context(patch.object(chat.agent_loader, 'get_session', AsyncMock(return_value=session)))
        stack.enter_context(patch.object(chat.agent_loader, 'get_display_messages', AsyncMock(return_value=[])))
        stack.enter_context(patch.object(chat.agent_loader, 'save_display_messages', save))
        for name in ('save_harness_trace', 'save_conversation'):
            stack.enter_context(patch.object(chat.agent_loader, name, AsyncMock()))
        stack.enter_context(patch.object(sandbox_manager, 'acquire_lease', return_value=False))
        chunks = [s async for s in chat.stream_chat_response('失败测试', 'failed-test')]
    events = [(s.splitlines()[0][7:], json.loads(s.splitlines()[1][6:])) for s in chunks]
    assert events[-1] == ('done', {'thread_id': 'failed-test', 'interrupted': False, 'failed': True})
    assert next(data for kind, data in events if kind == 'error')['code'] == 'execution_failed'
    assert 'PRIVATE_PROVIDER_MESSAGE' not in ''.join(chunks)
    partial = save.await_args.args[1][-1]
    assert partial['execution_status'] == 'failed'
    assert partial['content'].startswith('已读取的真实样本')
    assert '任务尚未完成' in partial['content']
    assert not session.run_lock.locked()
