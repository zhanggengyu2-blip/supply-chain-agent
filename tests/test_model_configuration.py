"""Model capability metadata must agree with the real endpoint's verified mode."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from src.agent import config

pytestmark=pytest.mark.unit

def test_grader_uses_tools_without_mutating_provider_profile():
    provider_profile={'structured_output':True,'tool_calling':True}
    model=SimpleNamespace(profile=provider_profile)
    with patch.object(config,'ChatDeepSeek',return_value=model) as constructor:
        assert config.get_llm(thinking=False) is model
    assert model.profile['structured_output'] is False
    assert model.profile['tool_calling'] is True
    assert provider_profile['structured_output'] is True
    assert constructor.call_args.kwargs['extra_body']['thinking']['type']=='disabled'
