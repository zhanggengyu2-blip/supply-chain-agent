"""Phase one ERPNext read-only MCP gateway (loopback only)."""
from fastmcp import FastMCP
from src.mcp_server.server_config import MCP_HOST, MCP_PORT
from src.mcp_server.tools.erpnext_tools import register_erpnext_tools

mcp = FastMCP(name="ERPNext-ReadOnly-MCP", instructions="ERPNext 供应链只读查询；没有业务写入工具。", mask_error_details=True)
register_erpnext_tools(mcp)

if __name__ == "__main__":
    mcp.run(transport="sse", host=MCP_HOST, port=MCP_PORT)
