"""从正在运行的图中读取配置；Runtime 本身没有 config 属性。"""
def current_thread_id(runtime=None) -> str:
    from langgraph.config import get_config

    try:
        config = get_config()
    except RuntimeError:
        # 兼容直接测试中间件的场景和旧调用方。
        config = getattr(runtime, "config", {})
    value = config.get("configurable", {}).get("thread_id") if isinstance(config, dict) else None
    return str(value) if value is not None else ""
