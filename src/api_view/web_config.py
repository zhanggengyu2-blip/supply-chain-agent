"""
MongoDB 连接配置
Motor AsyncIOMotorClient 连接.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from ..agent import config as agent_config

# 全局 Motor 客户端
_client: AsyncIOMotorClient = None


def get_mongo_client() -> AsyncIOMotorClient:
    """获取 MongoDB 异步客户端"""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(agent_config.MONGODB_URI)
    return _client


def get_db():
    """获取数据库实例"""
    return get_mongo_client()[agent_config.MONGODB_DB_NAME]


async def close_mongo_client():
    """关闭 MongoDB 连接"""
    global _client
    if _client:
        _client.close()
        _client = None
