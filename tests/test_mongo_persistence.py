"""真实 Agent MongoDB 集成测试，使用隔离的一次性测试库，不访问 ERP。"""
import os
import uuid
import pytest
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from src.api_view.mongodb_store import MongoDBStore
from src.test.test_progressive_skills import RecordingModel

pytestmark = [pytest.mark.persistence, pytest.mark.skipif(os.getenv("RUN_AGENT_MONGO_TEST") != "1", reason="Opt in to isolated Agent MongoDB integration")]

async def test_checkpoint_interrupt_and_store_survive_new_connections():
    uri=os.getenv("AGENT_TEST_MONGODB_URI", "mongodb://127.0.0.1:27018")
    db="phase1_test_"+uuid.uuid4().hex
    config={"configurable":{"thread_id":"restore"}}
    executed=[]
    @tool
    def local_proposal() -> str:
        """纯本地审批测试，不访问 ERP。"""
        executed.append(True)
        return "approved"
    def build(client, responses):
        return create_deep_agent(model=RecordingModel(responses=responses), tools=[local_proposal],backend=StateBackend(),
            checkpointer=MongoDBSaver(client,db_name=db), interrupt_on={"local_proposal":{"allowed_decisions":["approve","reject"]}})
    client=MongoClient(uri,serverSelectionTimeoutMS=3000)
    store=None
    try:
        client.admin.command("ping")
        graph=build(client,[AIMessage(content="",tool_calls=[{"name":"local_proposal","args":{},"id":"x"}])])
        first=await graph.ainvoke({"messages":[HumanMessage(content="review")]},config)
        assert first.get("__interrupt__")
        client.close()
        client=MongoClient(uri,serverSelectionTimeoutMS=3000)
        graph=build(client,[AIMessage(content="restored")])
        result=await graph.ainvoke(Command(resume={"decisions":[{"type":"approve"}]}),config)
        assert executed==[True]
        assert result["messages"][-1].content=="restored"
        store=MongoDBStore(uri=uri,db_name=db)
        store.put(("test-user",),"preference",{"language":"zh"})
        # 重新打开独立的 Store 客户端，证明数据已保存在 MongoDB 中。
        second=MongoDBStore(uri=uri,db_name=db)
        assert second.get(("test-user",),"preference").value=={"language":"zh"}
        second._client.close()
    finally:
        if store is not None: store._client.close()
        client.drop_database(db)
        client.close()
