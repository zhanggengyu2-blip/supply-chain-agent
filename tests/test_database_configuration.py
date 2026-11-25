"""验证运行时所有 MongoDB 客户端均使用共享配置，不建立真实连接。"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.agent import config
from src.agent.backends.sandbox_manager import SandboxManager, SandboxState
from src.api_view import web_config
from src.api_view.agent_loader import AgentLoader
from src.api_view.mongodb_store import MongoDBStore

pytestmark = pytest.mark.unit


@pytest.fixture
def configured_database(monkeypatch):
    # 设置有冲突的环境变量，暴露绕过共享配置的调用方。
    monkeypatch.setenv("MONGODB_URI", "mongodb://wrong-source.invalid:27017")
    monkeypatch.setenv("MONGODB_DB_NAME", "wrong_source")
    uri, name = "mongodb://shared-settings.invalid:27018", "shared_settings_test"
    monkeypatch.setattr(config, "MONGODB_URI", uri)
    monkeypatch.setattr(config, "MONGODB_DB_NAME", name)
    return uri, name


async def test_web_history_uses_shared_database(configured_database, monkeypatch):
    uri, name = configured_database
    client = MagicMock()
    monkeypatch.setattr(web_config, "_client", None)
    with patch.object(web_config, "AsyncIOMotorClient", return_value=client) as connect:
        assert web_config.get_db() is client[name]
        connect.assert_called_once_with(uri)
        client.__getitem__.assert_called_with(name)
        await web_config.close_mongo_client()
    client.close.assert_called_once()
    assert web_config._client is None


def test_checkpoint_and_store_are_built_and_passed_from_shared_settings(configured_database):
    uri, name = configured_database
    loader = object.__new__(AgentLoader)  # 不修改正在运行的单例。
    client, saver, store = MagicMock(), MagicMock(), MagicMock()
    with (
        patch("pymongo.MongoClient", return_value=client) as connect,
        patch("langgraph.checkpoint.mongodb.MongoDBSaver", return_value=saver) as checkpoint,
        patch("src.api_view.mongodb_store.MongoDBStore", return_value=store) as long_term,
    ):
        loader._initialize_resources_sync()
    connect.assert_called_once_with(uri)
    checkpoint.assert_called_once_with(client, db_name=name)
    long_term.assert_called_once_with(uri=uri, db_name=name, collection_name="langgraph_store")
    with patch("src.agent.main_agent.create_main_agent") as build:
        loader._build_agent_for_user("unit-user", "测试用户")
    assert build.call_args.kwargs["checkpointer"] is saver
    assert build.call_args.kwargs["store"] is store


@pytest.mark.parametrize("explicit", [False, True])
def test_store_defaults_to_shared_settings_and_accepts_isolated_overrides(configured_database, explicit):
    uri, name = configured_database
    kwargs = {}
    if explicit:
        uri, name = "mongodb://isolated-test.invalid:27019", "isolated_override"
        kwargs = {"uri": uri, "db_name": name}
    client = MagicMock()
    with patch("src.api_view.mongodb_store.MongoClient", return_value=client) as connect:
        store = MongoDBStore(**kwargs)
    connect.assert_called_once_with(uri, serverSelectionTimeoutMS=5000)
    client.__getitem__.assert_called_once_with(name)
    assert store._db is client[name]


@pytest.mark.parametrize("operation", ["persist", "restore", "cleanup"])
def test_dormant_sandbox_mapping_uses_shared_settings_without_creating_containers(configured_database, operation):
    uri, name = configured_database
    manager = object.__new__(SandboxManager)
    client = MagicMock()
    cache = client[name].sandbox_cache
    cache.find_one.return_value = None
    entry = SimpleNamespace(user_id="unit-user", state="claimed", to_dict=lambda: {"user_id": "unit-user"})
    with patch("pymongo.MongoClient", return_value=client) as connect, patch("docker.from_env") as docker:
        if operation == "persist":
            manager._persist_to_mongodb(entry)
            cache.update_one.assert_called_once()
            assert entry.state == SandboxState.CACHED
        elif operation == "restore":
            assert manager._restore_from_mongodb("unit-user") is None
            cache.find_one.assert_called_once_with({"user_id": "unit-user"})
        else:
            manager._cleanup_mongodb_cache("unit-user")
            cache.delete_one.assert_called_once_with({"user_id": "unit-user"})
    connect.assert_called_once_with(uri, serverSelectionTimeoutMS=3000)
    client.__getitem__.assert_called_with(name)
    docker.assert_not_called()
    client.close.assert_called_once()
