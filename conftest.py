"""离线测试不得将脚本模型的运行记录发送到真实 Langfuse 项目。

真实追踪验收由 evals.phase1_acceptance 显式执行。单独的回调测试
仍可使用自己的模拟客户端覆盖此测试夹具。
"""
import pytest

@pytest.fixture(autouse=True)
def disable_live_telemetry_for_tests(monkeypatch):
    monkeypatch.setenv('ERP_LANGFUSE_ENABLED','false')
