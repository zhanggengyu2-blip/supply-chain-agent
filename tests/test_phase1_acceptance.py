"""Audit logic tests use simulated permission responses, never business writes."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from evals import phase1_acceptance as acceptance

pytestmark=pytest.mark.unit

async def test_permission_audit_checks_role_and_sample_without_writes():
    async def get(path,params):
        assert path=='/api/method/frappe.client.has_permission'
        assert params['perm_type'] in acceptance.WRITE_PERMISSIONS
        return {'message':{'has_permission':False}}
    client=SimpleNamespace(_get=AsyncMock(side_effect=get))
    result=await acceptance.audit_permissions(client,{'Purchase Order':'PO-test'})
    assert result['status']=='passed'
    assert any(c['scope']=='sample_document' for c in result['checks'])
    assert len(result['checks'])==(len(acceptance.AUDIT_DOCTYPES)+1)*len(acceptance.WRITE_PERMISSIONS)

async def test_permission_audit_fails_if_any_write_granted():
    client=SimpleNamespace(_get=AsyncMock(return_value={'message':{'has_permission':True}}))
    result=await acceptance.audit_permissions(client,{})
    assert result['status']=='failed'

async def test_permission_audit_unknown_is_not_false():
    client=SimpleNamespace(_get=AsyncMock(return_value={'message':{}}))
    with pytest.raises(acceptance.ERPNextError,match='invalid_permission_payload'):
        await acceptance.audit_permissions(client,{})

def test_safe_error_does_not_serialize_exception_body():
    error=RuntimeError('SECRET API KEY AND PRIVATE RESPONSE')
    assert 'SECRET' not in json.dumps(acceptance.safe_error(error))

async def test_missing_credentials_block_erp_before_network():
    with patch.object(acceptance,'missing',return_value=['ERPNEXT_API_KEY']), patch.object(acceptance,'ERPNextClient') as client:
        result=await acceptance.verify_erp('http://127.0.0.1:9000/sse')
        assert result['status']=='blocked'
        client.assert_not_called()

async def test_trace_verification_requires_credentials():
    with patch.object(acceptance,'missing',return_value=['LANGFUSE_SECRET_KEY']):
        assert (await acceptance.verify_trace('test-trace'))['status']=='blocked'

@pytest.mark.parametrize('tokens,expected',[(42,'passed'),(0,'failed')])
async def test_trace_readback_requires_real_usage_fields(tokens,expected,monkeypatch):
    from unittest.mock import Mock
    monkeypatch.setenv('ERP_LANGFUSE_ENABLED','true')
    rows=[SimpleNamespace(name='erp.request',type='SPAN',input=None,output=None),
          SimpleNamespace(name='model.call',type='GENERATION',input=None,output=None,usage_details={'input':tokens,'output':0}),
          SimpleNamespace(name='tool.erpnext_items',type='SPAN',input=None,output=None)]
    get_many=Mock(return_value=SimpleNamespace(data=rows,meta=SimpleNamespace(cursor=None)))
    client=SimpleNamespace(api=SimpleNamespace(observations=SimpleNamespace(get_many=get_many)))
    with patch.object(acceptance,'missing',return_value=[]),patch.object(acceptance,'langfuse_client',return_value=client):
        result=await acceptance.verify_trace('test-trace')
    assert result['status']==expected
    assert result['total_tokens']==tokens
    assert result['business_payloads_empty']
