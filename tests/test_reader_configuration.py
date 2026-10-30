"""Reader provisioning writes only account configuration, never ERP business docs."""
from unittest.mock import AsyncMock
import pytest
from scripts.configure_erpnext_reader import AdminSession,ConfigurationError,ROLE,semantic_permissions

pytestmark=pytest.mark.unit

@pytest.mark.parametrize('path,method',[
    ('/api/resource/Purchase Order','POST'),
    ('/api/resource/Stock Entry','POST'),
    ('/api/resource/User/Administrator','PUT'),
    ('/api/resource/Role/System%20Manager','PUT'),
])
async def test_business_or_other_account_writes_are_rejected(path,method):
    admin=AdminSession()
    admin.http.request=AsyncMock()
    try:
        with pytest.raises(ConfigurationError,match='administrative_write_not_allowlisted'):
            await admin.write(path,{},method=method)
        admin.http.request.assert_not_called()
    finally: await admin.http.aclose()

async def test_admin_key_generation_is_never_allowed():
    admin=AdminSession();admin.http.request=AsyncMock()
    try:
        with pytest.raises(ConfigurationError,match='only_dedicated_reader_key_allowed'):
            await admin.write('/api/method/frappe.core.doctype.user.user.generate_keys',{'user':'Administrator'})
        admin.http.request.assert_not_called()
    finally: await admin.http.aclose()

def test_existing_permissions_preserved_semantically_when_custom_rows_copied():
    original=[{'name':'old','role':'Existing Role','read':1,'permlevel':0,'write':0}]
    copied=[{'name':'new','role':'Existing Role','read':1,'permlevel':0,'write':0},
            {'role':ROLE,'read':1,'select':1,'permlevel':0}]
    assert semantic_permissions(original)==semantic_permissions(copied)
    copied[0]['write']=1
    assert semantic_permissions(original)!=semantic_permissions(copied)
