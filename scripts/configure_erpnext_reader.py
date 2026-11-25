"""一次性的本地 ERPNext 只读账户配置，绝不注册为 Agent 工具。

使用现有部署文档中记录的管理员登录信息，不使用管理员 API 密钥。
只允许写入 Role、User、User Permission，以及调用官方权限管理器的写方法。
不修改现有业务数据或 ERPNext 文件。
默认仅生成只读配置计划；必须提供 --apply 才会实际配置账户。
"""
import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SOURCE=Path('/Users/zhanggengyu/Documents/ChatGPT/AI智能订货')
BASE='http://127.0.0.1:8080'
ROLE='Supply Chain Agent Phase1 Reader'
USER='supply-chain-agent-phase1@example.invalid'
MARKER='Managed by local supply-chain Agent phase-one configuration.'
DOCTYPES=('Supplier','Item','Warehouse','Bin','Purchase Order')
MANAGER='/api/method/frappe.core.page.permission_manager.permission_manager.'
PERMISSION_FLAGS=('read','select','write','create','delete','submit','cancel','amend','import','share','export','print','email','report','mask','if_owner')

class ConfigurationError(RuntimeError):
    def __init__(self,code,status=None,erp_type=None):
        self.code,self.status,self.erp_type=code,status,erp_type
        super().__init__(code)

class AdminSession:
    def __init__(self):
        self.http=httpx.AsyncClient(base_url=BASE,trust_env=False,timeout=30,follow_redirects=False)
        self.write_log=[]
    async def close(self):
        try: await self.http.post('/api/method/logout')
        finally: await self.http.aclose()
    def decode(self,response):
        try: body=response.json()
        except ValueError: raise ConfigurationError('non_json',response.status_code) from None
        if response.status_code!=200 or body.get('exception') or body.get('exc_type'):
            raise ConfigurationError('configuration_api_failed',response.status_code,body.get('exc_type'))
        return body
    async def get(self,path,params=None):
        return self.decode(await self.http.get(path,params=params))
    async def write(self,path,payload,method='POST'):
        allowed={'/api/resource/Role','/api/resource/User','/api/resource/User Permission',
            '/api/resource/User/'+quote(USER,safe=''),'/api/resource/Role/'+quote(ROLE,safe=''),MANAGER+'add',MANAGER+'update',
            '/api/method/frappe.core.doctype.user.user.generate_keys'}
        if path not in allowed or method not in {'POST','PUT'}:
            raise ConfigurationError('administrative_write_not_allowlisted')
        if path.endswith('generate_keys') and payload.get('user')!=USER:
            raise ConfigurationError('only_dedicated_reader_key_allowed')
        response=self.decode(await self.http.request(method,path,json=payload))
        self.write_log.append({'method':method,'path':path})
        return response
    async def login(self):
        note=(SOURCE/'ERPNext本地演示环境说明.md').read_text()
        usr=re.search(r'初始用户[^`]*`([^`]+)`',note)
        pwd=re.search(r'初始密码[^`]*`([^`]+)`',note)
        if not usr or not pwd: raise ConfigurationError('documented_login_missing')
        self.decode(await self.http.post('/api/method/login',json={'usr':usr.group(1),'pwd':pwd.group(1)}))
        who=await self.get('/api/method/frappe.auth.get_logged_user')
        if who.get('message')!='Administrator': raise ConfigurationError('expected_admin_session')
        # 获取正常认证流程中的 CSRF 令牌，不关闭跨站请求伪造检查。
        page=await self.http.get('/desk')
        match=re.search(r'frappe\.csrf_token\s*=\s*[\"\x27]([^\"\x27]+)',page.text)
        if not match: match=re.search(r'[\"\x27]csrf_token[\"\x27]\s*:\s*[\"\x27]([^\"\x27]+)',page.text)
        if not match: raise ConfigurationError('authenticated_csrf_token_unavailable')
        self.http.headers['X-Frappe-CSRF-Token']=match.group(1)
    async def listed(self,doctype,filters,fields):
        return (await self.get('/api/resource/'+quote(doctype,safe=''),{
            'filters':json.dumps(filters),'fields':json.dumps(fields),'limit_page_length':1000}))['data']
    async def permissions(self,doctype):
        return (await self.get(MANAGER+'get_permissions',{'doctype':doctype}))['message']
    async def counts(self):
        return {dt:(await self.get('/api/method/frappe.client.get_count',{'doctype':dt}))['message'] for dt in DOCTYPES}

def semantic_permissions(rows):
    return Counter(tuple([r.get('role'),int(r.get('permlevel') or 0)]+[int(r.get(k) or 0) for k in PERMISSION_FLAGS])
        for r in rows if r.get('role')!=ROLE)

def write_env(values):
    p=ROOT/'.env';lines=[];seen=set()
    for line in p.read_text().splitlines():
        name=line.split('=',1)[0]
        if name in values:
            if name not in seen: lines.append(name+'='+json.dumps(values[name],ensure_ascii=False));seen.add(name)
        else: lines.append(line)
    for name,value in values.items():
        if name not in seen: lines.append(name+'='+json.dumps(value,ensure_ascii=False))
    p.write_text('\n'.join(lines)+'\n');p.chmod(0o600)

async def main(apply):
    manifest=json.loads((SOURCE/'erpnext-demo/演示数据清单.json').read_text())
    company=manifest['company']
    warehouses=[manifest['records'][key]['name'] for key in ('wh-main','wh-store','wh-reject','wh-wip')]
    report={'timestamp':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'mode':'apply' if apply else 'plan',
        'user':USER,'role':ROLE,'company':company,'warehouses':warehouses,
        'business_writes_allowed':False,'administrator_api_key_generated':False}
    admin=AdminSession();user_exists=False
    try:
        await admin.login()
        existing=await admin.listed('User',[['name','=',USER]],['name','bio','enabled'])
        if existing:
            if existing[0].get('bio')!=MARKER: raise ConfigurationError('unmanaged_user_collision')
            user_exists=True
        roles=await admin.listed('Role',[['name','=',ROLE]],['name','desk_access'])
        if roles and not user_exists: raise ConfigurationError('unmanaged_role_collision')
        actual=await admin.listed('Warehouse',[['name','in',warehouses]],['name','company','disabled','is_group'])
        if {w['name'] for w in actual if w['company']==company and not w['disabled'] and not w['is_group']}!=set(warehouses):
            raise ConfigurationError('warehouse_manifest_scope_mismatch')
        before_permissions={dt:semantic_permissions(await admin.permissions(dt)) for dt in DOCTYPES}
        before_counts=await admin.counts()
        if not apply:
            report.update(status='ready',business_counts=before_counts)
        else:
            if not roles:
                await admin.write('/api/resource/Role',{'role_name':ROLE,'desk_access':0})
            elif roles[0].get('desk_access'):
                # 在此部署中，Desk User 会隐式授予 Item.share 权限。
                # 仅移除本项目专用角色的桌面访问权限；不得修改
                # 已有的 Desk User 角色或其他用户的权限。
                await admin.write('/api/resource/Role/'+quote(ROLE,safe=''),{'desk_access':0},method='PUT')
            for dt in DOCTYPES:
                current=await admin.permissions(dt)
                own=[row for row in current if row.get('role')==ROLE]
                if not own:
                    await admin.write(MANAGER+'add',{'parent':dt,'role':ROLE,'permlevel':0})
                    own=[row for row in await admin.permissions(dt) if row.get('role')==ROLE]
                if len(own)!=1 or int(own[0].get('permlevel') or 0)!=0: raise ConfigurationError('unexpected_reader_permission_rows')
                for flag in PERMISSION_FLAGS:
                    target=1 if flag in {'read','select'} else 0
                    if int(own[0].get(flag) or 0)!=target:
                        await admin.write(MANAGER+'update',{'doctype':dt,'role':ROLE,'permlevel':0,'ptype':flag,'value':str(target),'if_owner':0})
                after=await admin.permissions(dt)
                if semantic_permissions(after)!=before_permissions[dt]: raise ConfigurationError('existing_role_permissions_changed')
                own=[r for r in after if r.get('role')==ROLE][0]
                if any(int(own.get(k) or 0)!=(1 if k in {'read','select'} else 0) for k in PERMISSION_FLAGS):
                    raise ConfigurationError('reader_permissions_not_readonly')
            if not user_exists:
                await admin.write('/api/resource/User',{'email':USER,'first_name':'Supply Chain Agent Reader','enabled':0,
                    'send_welcome_email':0,'user_type':'Website User','bio':MARKER,'roles':[{'role':ROLE}]})
                user_exists=True
            user_path='/api/resource/User/'+quote(USER,safe='')
            # 将账户转换为仅供 API 使用的身份期间，保持账户禁用。
            await admin.write(user_path,{'enabled':0,'user_type':'Website User','send_welcome_email':0},method='PUT')
            user=(await admin.get(user_path))['data']
            if user.get('user_type')!='Website User': raise ConfigurationError('api_only_user_type_required')
            assigned={r['role'] for r in user.get('roles',[])}
            if assigned-{'All','Desk User',ROLE}: raise ConfigurationError('unexpected_reader_roles')
            for allow,values in [('Company',[company]),('Warehouse',warehouses)]:
                prior=await admin.listed('User Permission',[['user','=',USER],['allow','=',allow]],['name','for_value','apply_to_all_doctypes'])
                if {p['for_value'] for p in prior}-set(values): raise ConfigurationError('unexpected_existing_user_scope')
                for value in values:
                    if not any(p['for_value']==value and p.get('apply_to_all_doctypes') for p in prior):
                        await admin.write('/api/resource/User Permission',{'user':USER,'allow':allow,'for_value':value,'apply_to_all_doctypes':1})
            stored=dotenv_values(ROOT/'.env')
            if stored.get('ERPNEXT_API_USER')==USER and stored.get('ERPNEXT_API_KEY') and stored.get('ERPNEXT_API_SECRET'):
                key,secret=stored['ERPNEXT_API_KEY'],stored['ERPNEXT_API_SECRET']
            else:
                generated=(await admin.write('/api/method/frappe.core.doctype.user.user.generate_keys',{'user':USER}))['message']
                key,secret=generated['api_key'],generated['api_secret']
            write_env({'ERPNEXT_API_USER':USER,'ERPNEXT_API_KEY':key,'ERPNEXT_API_SECRET':secret,
                'ERPNEXT_COMPANY':company,'ERPNEXT_WAREHOUSES':','.join(warehouses),'ERPNEXT_BASE_URL':BASE})
            await admin.write(user_path,{'enabled':1,'send_welcome_email':0},method='PUT')
            # 身份核对和实际权限检查只能使用新建只读用户的令牌。
            from src.mcp_server.erpnext.models import ERPNextSettings
            from src.mcp_server.erpnext.client import ERPNextClient
            from evals.phase1_acceptance import audit_permissions
            async with ERPNextClient(ERPNextSettings.from_env()) as reader:
                audit=await audit_permissions(reader,{})
                report['permission_audit']=audit
                if audit['status']!='passed': raise ConfigurationError('reader_effective_write_permission_detected')
            after_counts=await admin.counts()
            if after_counts!=before_counts: raise ConfigurationError('business_counts_changed_during_configuration')
            report.update(status='passed',existing_role_permissions_preserved=True,business_counts_before=before_counts,
                business_counts_after=after_counts,reader_roles=sorted(assigned),identity_verified=True,
                effective_write_permissions_denied=len(audit['checks']),reader_user_type=user['user_type'],
                desk_user_inheritance_removed=True,admin_write_requests=admin.write_log)
    except Exception as exc:
        # 不打印原始错误、请求/响应体、登录信息或令牌。
        report.update(status='failed',error_type=type(exc).__name__)
        if isinstance(exc,ConfigurationError): report.update(error_code=exc.code,http_status=exc.status,erp_error_type=exc.erp_type)
        if apply and user_exists:
            try:
                await admin.write('/api/resource/User/'+quote(USER,safe=''),{'enabled':0},method='PUT')
                report['reader_disabled_on_failure']=True
            except Exception: report['reader_disabled_on_failure']=False
    finally:
        await admin.close()
    dest=ROOT/'docs/evidence/erpnext-reader-configuration.json'
    dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if report['status']=='failed': raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    asyncio.run(main(args.apply))
