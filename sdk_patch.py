"""
Patch for claude-agent-sdk 0.1.x to fix Server version parameter incompatibility
"""
import claude_agent_sdk
from typing import List, Callable, Any

def patched_create_sdk_mcp_server(
    name: str, version: str = "1.0.0", tools: list = None
):
    """
    Patched version of create_sdk_mcp_server that works with mcp library without version support
    """
    from mcp.server import Server
    from mcp.types import ImageContent, TextContent, Tool

    # Create MCP server instance WITHOUT version parameter
    server = Server(name)
    # SDK's _handle_sdk_mcp_request accesses server.version during init
    server.version = version

    # Register tools if provided (same logic as original)
    if tools:
        # Store tools for access in handlers
        tool_map = {tool_def.name: tool_def for tool_def in tools}

        # Register list_tools handler to expose available tools
        @server.list_tools()
        async def list_tools() -> list[Tool]:
            """Return the list of available tools."""
            tool_list = []
            for tool_def in tools:
                # Convert input_schema to JSON Schema format
                if isinstance(tool_def.input_schema, dict):
                    if (
                        "type" in tool_def.input_schema
                        and "properties" in tool_def.input_schema
                    ):
                        schema = tool_def.input_schema
                    else:
                        properties = {}
                        for param_name, param_type in tool_def.input_schema.items():
                            if param_type is str:
                                properties[param_name] = {"type": "string"}
                            elif param_type is int:
                                properties[param_name] = {"type": "integer"}
                            elif param_type is float:
                                properties[param_name] = {"type": "number"}
                            elif param_type is bool:
                                properties[param_name] = {"type": "boolean"}
                            else:
                                properties[param_name] = {"type": "string"}
                        schema = {
                            "type": "object",
                            "properties": properties,
                            "required": list(properties.keys()),
                        }
                else:
                    schema = {"type": "object", "properties": {}}

                tool_list.append(
                    Tool(
                        name=tool_def.name,
                        description=tool_def.description,
                        inputSchema=schema,
                    )
                )
            return tool_list

        # Register call_tool handler to execute tools
        @server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
            """Execute a tool by name with given arguments."""
            if name not in tool_map:
                raise ValueError(f"Tool '{name}' not found")

            tool_def = tool_map[name]
            result = await tool_def.handler(arguments)

            content: list[TextContent | ImageContent] = []
            if "content" in result:
                for item in result["content"]:
                    if item.get("type") == "text":
                        content.append(TextContent(type="text", text=item["text"]))
                    if item.get("type") == "image":
                        content.append(
                            ImageContent(
                                type="image",
                                data=item["data"],
                                mimeType=item["mimeType"],
                            )
                        )

            return content

    # Return SDK server configuration
    return claude_agent_sdk.McpSdkServerConfig(type="sdk", name=name, instance=server)

# Apply the patch
claude_agent_sdk.create_sdk_mcp_server = patched_create_sdk_mcp_server
