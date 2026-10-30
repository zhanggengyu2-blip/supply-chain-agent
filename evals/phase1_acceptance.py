"""Real-service acceptance. No ERP writes, credential discovery, or raw errors.

Default: inspect configuration and local services only.
--model: contact the configured model issuer, run real Tool Calling and trace it.
--erp: authenticate as configured reader, audit permissions and compare REST/MCP.
--trace-id: independently read back a Langfuse trace and its token usage.
"""
import argparse
import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from fastmcp import Client
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from src.agent import env_utils  # load only this project's configuration
from src.agent.config import get_llm
from src.agent.observability import Trace, client as langfuse_client
from src.agent.tool_policy import ERP_READ_TOOLS
from src.mcp_server.erpnext.client import ERPNextClient, ERPNextError
from src.mcp_server.erpnext.models import ERPNextSettings, Query, BinQuery, PurchaseOrderQuery
from src.mcp_server.erpnext.adapter import ERPNextAdapter

ERP_FIELDS = ('ERPNEXT_API_KEY', 'ERPNEXT_API_SECRET', 'ERPNEXT_API_USER', 'ERPNEXT_COMPANY', 'ERPNEXT_WAREHOUSES')
TRACE_FIELDS = ('LANGFUSE_BASE_URL', 'LANGFUSE_PUBLIC_KEY', 'LANGFUSE_SECRET_KEY', 'ERP_TRACE_HASH_KEY')
WRITE_PERMISSIONS = ('write', 'create', 'delete', 'submit', 'cancel', 'amend', 'import', 'share')
AUDIT_DOCTYPES = ('Supplier', 'Item', 'Warehouse', 'Bin', 'Purchase Order', 'Stock Entry', 'Stock Reconciliation', 'Purchase Receipt', 'Purchase Invoice')
MAPPING = {'Supplier':'erpnext_suppliers', 'Item':'erpnext_items', 'Warehouse':'erpnext_warehouses', 'Bin':'erpnext_bins', 'Purchase Order':'erpnext_purchase_orders'}


def missing(fields):
    return [field for field in fields if not os.getenv(field, '').strip()]


def safe_error(exc):
    # Never serialize exception text, request objects, response bodies or credentials.
    result = {'status': 'failed', 'error_type': type(exc).__name__}
    if isinstance(exc, ERPNextError): result['error_code'] = exc.code
    code = getattr(exc, 'status_code', None) or getattr(exc, 'status', None)
    if isinstance(code, int): result['http_status'] = code
    return result


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def audit_permissions(client, samples):
    """Read effective permission booleans; never test denial by attempting a write."""
    checks=[]
    for doctype in AUDIT_DOCTYPES:
        sample = samples.get(doctype)
        # Empty docname asks for doctype/role-level permission in this Frappe version.
        for scope, docname in [('doctype', '')] + ([('sample_document', sample)] if sample else []):
            for permission in WRITE_PERMISSIONS:
                body=await client._get('/api/method/frappe.client.has_permission',
                    {'doctype':doctype, 'docname':docname, 'perm_type':permission})
                value=(body.get('message') or {}).get('has_permission')
                if not isinstance(value, bool): raise ERPNextError('invalid_permission_payload')
                checks.append({'doctype':doctype, 'scope':scope, 'permission':permission, 'allowed':value})
    denied=all(not row['allowed'] for row in checks)
    return {'status':'passed' if denied else 'failed', 'checks':checks,
            'limitation':'Only listed DocTypes and returned sample documents are audited; this is not proof of account-wide permissions.'}


async def verify_erp(mcp_url):
    absent=missing(ERP_FIELDS)
    if absent: return {'status':'blocked', 'missing':absent}
    try:
        async with ERPNextClient(ERPNextSettings.from_env()) as erp:
            baseline_audit=await audit_permissions(erp,{})
            if baseline_audit['status']!='passed':
                return {'status':'failed','permissions':baseline_audit}
            adapter=ERPNextAdapter(erp)
            results={}
            for doctype in MAPPING:
                query=BinQuery(limit=5) if doctype=='Bin' else PurchaseOrderQuery(limit=5) if doctype=='Purchase Order' else Query(limit=5)
                results[doctype]=await adapter.query(doctype,query)
            audit=await audit_permissions(erp,{d:r.data[0].name for d,r in results.items() if r.data})
            # Credentials with a detected write grant cannot pass acceptance.
            if audit['status']!='passed': return {'status':'failed', 'permissions':audit}
            checks={}
            async with Client(mcp_url, timeout=30) as mcp:
                for doctype,name in MAPPING.items():
                    remote=await mcp.call_tool(name, {'query':{'limit':5}})
                    expected=results[doctype].model_dump(mode='json')
                    actual=remote.structured_content
                    equal=not remote.is_error and fingerprint(expected)==fingerprint(actual)
                    checks[doctype]={'status':'passed' if equal else 'failed', 'rows':len(expected['data']),
                        'has_more':expected['has_more'], 'rest_mcp_match':equal,
                        'sample_available':bool(expected['data']), 'data_fingerprint':fingerprint(expected['data'])}
            return {'status':'passed' if all(c['rest_mcp_match'] for c in checks.values()) else 'failed',
                    'identity_verified':True, 'tools':checks, 'permissions':audit,
                    'limitation':'Purchase Order headers are company-scoped; line-level warehouse scope is not implemented.'}
    except Exception as exc: return safe_error(exc)


async def verify_model():
    if missing(('DEEPSEEK_API_KEY',)):
        return {'status':'blocked', 'missing':['DEEPSEEK_API_KEY']}
    trace=Trace('phase1-acceptance', 'phase1-model-'+uuid.uuid4().hex)
    config={'callbacks':[trace.callback]} if trace.root else {}
    @tool
    def phase1_readonly_probe(label: str) -> str:
        """Read-only acceptance probe. Pass label=phase1; returns readonly_ok. No ERP access."""
        if label!='phase1': raise ValueError('invalid_probe_label')
        return 'readonly_ok'
    try:
        model=get_llm(thinking=False, timeout=30, max_retries=0, max_tokens=128)
        plain=await model.ainvoke([HumanMessage(content='Reply with exactly PHASE1_OK.')],config)
        if plain.content.strip()!='PHASE1_OK': raise ValueError('plain_response_mismatch')
        prompt=HumanMessage(content='Call phase1_readonly_probe with label phase1, then report its returned value.')
        bound=model.bind_tools([phase1_readonly_probe],tool_choice='phase1_readonly_probe')
        requested=await bound.ainvoke([prompt],config)
        if len(requested.tool_calls)!=1 or requested.tool_calls[0]['name']!='phase1_readonly_probe':
            raise ValueError('tool_call_missing')
        executed=await phase1_readonly_probe.ainvoke(requested.tool_calls[0],config)
        answer=await model.ainvoke([prompt,requested,executed],config)
        if 'readonly_ok' not in str(answer.content): raise ValueError('tool_answer_mismatch')
        usage=[m.usage_metadata or {} for m in (plain,requested,answer)]
        totals={key:sum(u.get(key,0) for u in usage) for key in ('input_tokens','output_tokens','total_tokens')}
        trace.finish('completed')
        if trace.client: await asyncio.to_thread(trace.client.flush)
        return {'status':'passed', 'plain_call':True, 'tool_call':True, 'tool_result_used':True,
                'usage':totals, 'usage_present_for_every_call':all(u.get('total_tokens',0)>0 for u in usage),
                'trace_id':trace.root.trace_id if trace.root else None,
                'scope':'Real model + local safe probe; no ERP business query.'}
    except Exception as exc:
        trace.finish('failed')
        if trace.client: await asyncio.to_thread(trace.client.flush)
        return safe_error(exc)


async def verify_trace(trace_id):
    absent=missing(TRACE_FIELDS)
    if absent or os.getenv('ERP_LANGFUSE_ENABLED')!='true':
        return {'status':'blocked', 'missing':absent, 'tracing_enabled':os.getenv('ERP_LANGFUSE_ENABLED')=='true'}
    if not trace_id: return {'status':'not_tested', 'reason':'No real execution trace ID yet'}
    try:
        client=langfuse_client()
        if client is None: raise RuntimeError('trace_client_unavailable')
        for delay in (0,2,4,8):
            if delay: await asyncio.sleep(delay)
            response=await asyncio.to_thread(client.api.observations.get_many,
                trace_id=trace_id,limit=1000,fields='basic,io,usage,model')
            data=response.data
            if any(o.name=='erp.request' for o in data) and any(o.name.startswith('tool.') for o in data) and any(o.type=='GENERATION' for o in data): break
        generations=[o for o in data if o.type=='GENERATION']
        tools=[o.name for o in data if o.name.startswith('tool.')]
        usage=[getattr(o,'usage_details',None) or {} for o in generations]
        root=any(o.name=='erp.request' for o in data)
        no_payload=all(o.input in (None,'',{},[]) and o.output in (None,'',{},[]) for o in data)
        tokens=sum(int(u.get('total',0) or (u.get('input',0)+u.get('output',0))) for u in usage)
        usage_complete=bool(generations) and all(int(u.get('total',0) or (u.get('input',0)+u.get('output',0)))>0 for u in usage)
        passed=root and bool(generations) and bool(tools) and tokens>0 and usage_complete and no_payload and not response.meta.cursor
        return {'status':'passed' if passed else 'failed','trace_id':trace_id,'root_found':root,
                'observations':len(data),'generations':len(generations),'tools':tools,
                'total_tokens':tokens,'usage_present_for_every_generation':usage_complete,'business_payloads_empty':no_payload,'has_more':bool(response.meta.cursor)}
    except Exception as exc: return safe_error(exc)


async def main(args):
    report={'timestamp':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'scope':'Phase-one acceptance, no ERP writes',
            'configuration':{'model_key_configured':not missing(('DEEPSEEK_API_KEY',)),
                'erp_missing':missing(ERP_FIELDS),'langfuse_missing':missing(TRACE_FIELDS),
                'tracing_enabled':os.getenv('ERP_LANGFUSE_ENABLED')=='true'}}
    async with httpx.AsyncClient(trust_env=False, timeout=5, follow_redirects=False) as http:
        services={}
        for name,url in [('web','http://127.0.0.1:3000/'),('api','http://127.0.0.1:8000/health'),('erp_public_entry',os.getenv('ERPNEXT_BASE_URL','http://127.0.0.1:8080'))]:
            try:
                response=await http.get(url)
                services[name]={'status':'passed' if response.status_code==200 else 'failed','http_status':response.status_code}
            except Exception as exc: services[name]=safe_error(exc)
        report['services']=services
    mcp_url=os.getenv('MCP_SERVER_URL','http://127.0.0.1:9000').rstrip('/')+'/sse'
    try:
        async with Client(mcp_url,timeout=10) as mcp:
            names={t.name for t in await mcp.list_tools()}
            report['mcp']={'status':'passed' if names==ERP_READ_TOOLS else 'failed','tools':sorted(names),'write_tools_registered':bool(names-ERP_READ_TOOLS)}
    except Exception as exc: report['mcp']=safe_error(exc)
    report['model']=await verify_model() if args.model else {'status':'not_tested','reason':'Model check not requested; --model explicitly runs the configured endpoint.'}
    report['erp']=await verify_erp(mcp_url) if args.erp else {'status':'blocked' if missing(ERP_FIELDS) else 'not_tested','missing':missing(ERP_FIELDS)}
    report['langfuse']=await verify_trace(args.trace_id or report['model'].get('trace_id'))
    report['workbench_business_task']={'status':'not_tested','reason':'Run in the UI after model, ERP permissions and tracing are verified.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',action='store_true')
    parser.add_argument('--erp',action='store_true')
    parser.add_argument('--trace-id')
    parser.add_argument('--output',type=Path,default=Path('docs/evidence/closeout-services.json'))
    asyncio.run(main(parser.parse_args()))
