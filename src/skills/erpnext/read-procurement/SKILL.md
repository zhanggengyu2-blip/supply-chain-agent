---
name: erpnext-read-procurement
description: ERPNext 阶段一采购只读查询，解释字段、分页和权限范围。
---
使用 erpnext_suppliers / erpnext_items / erpnext_warehouses / erpnext_bins / erpnext_purchase_orders。
工具输入均为 query 对象，支持 name 精确筛选、limit（1～100）、offset（从 0 开始）。
Bin 还支持 item_code 和 warehouse；采购订单支持 supplier、status（原始字符串）、docstatus（0 草稿、1 已提交、2 已取消）。
使用 has_more 判断是否需要继续分页，不将单页结果当全量数据。
Supplier/Item 是共享主数据，遵循固定 API 用户权限。Warehouse/Bin 受公司和仓库白名单限制。
采购订单当前只返回表头，按公司和 Frappe 权限过滤，不按仓库筛选；不要声称已校验订单行的仓库。
actual_qty 是实物库存，projected_qty 是含计划因素的预计数量，不等于可用库存。
查询无数据、认证失败、权限失败应分别说明；没有权限时不得换用数据库或管理员凭据。
阶段一禁止业务写入。旧 Java ERP 的 partId、orderNumber、数字业务状态及写工具均不适用。
