import sys
import os
import asyncio
import traceback

_log = open(r"C:\Users\fabian.ang.qj\Desktop\MCP\create-mcp-server\mcp_debug.log", "w")
_log.write("Script started\n"); _log.flush()

try:
    from mcp.server.fastmcp import FastMCP
    _log.write("FastMCP imported\n"); _log.flush()

    mcp = FastMCP("test")

    @mcp.tool()
    def hello() -> str:
        """Say hello."""
        return "hello from mcp_server"

    # Use SelectorEventLoop on Windows — ProactorEventLoop has issues with pipe stdin/stdout
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        _log.write("Set WindowsSelectorEventLoopPolicy\n"); _log.flush()

    _log.write("Starting mcp.run()\n"); _log.flush()
    mcp.run()
    _log.write("mcp.run() finished\n"); _log.flush()

except Exception as e:
    _log.write(f"ERROR: {e}\n")
    _log.write(traceback.format_exc())
    _log.flush()

_log.close()
