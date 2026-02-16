"""
Web Search Agent for Adaptive RAG System

This agent handles web search using the Exa AI API through the Claude Agent SDK.
It acts as a subagent of the RetrievalAgent for queries requiring external web information.

Architecture:
- Uses Claude Agent SDK with custom MCP tools
- Performs web search using Exa AI
- Returns results in standardized document format compatible with grader
- Integrates as a subagent within the RetrievalAgent

Usage:
    from agents.web_search_agent import WebSearchAgent

    agent = WebSearchAgent()
    documents = await agent.search_web("Windows 11 blue screen error")
"""

import os
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv
# sdk_patch must be imported before create_sdk_mcp_server to fix the
# Server version parameter incompatibility with the mcp library.
import sdk_patch  # noqa: F401
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

# Load environment variables
load_dotenv()

# Import existing Exa search function
from tools.exa_tool import search_web
from config import TOP_K
from prompts import load_prompt


# Tool: Exa Web Search
@tool(
    name="exa_web_search",
    description="Search the web using Exa AI to find relevant external information. Returns web documents with content and metadata.",
    # Must use full JSON Schema format (with "type", "properties", "required"),
    # NOT Python types like {"query": str, "num_results": int}.
    # The sdk_patch.py list_tools handler passes JSON Schema dicts through as-is,
    # but converts Python types via fallback — where `list` becomes {"type": "string"}
    # instead of {"type": "array"}, breaking tool parameter visibility for the agent.
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"},
            "num_results": {"type": "integer", "description": "Number of results to return"}
        },
        "required": ["query", "num_results"]
    }
)
async def exa_web_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform web search using Exa AI (tool wrapper).

    Args:
        args: Dictionary containing:
            - query: The search query
            - num_results: Number of results to return

    Returns:
        Dictionary with content containing search results
    """
    query = args.get("query", "")
    num_results = args.get("num_results", TOP_K)

    # Validate inputs
    if not query:
        return {
            "content": [{
                "type": "text",
                "text": "Error: query is required"
            }]
        }

    # Perform web search
    try:
        results = search_web(query, num_results=num_results)

        # Format results for agent
        result_text = f"Found {len(results)} web search results:\n\n"

        for i, doc in enumerate(results, 1):
            result_text += f"Result {i}:\n"
            result_text += f"  Title: {doc['title']}\n"
            result_text += f"  URL: {doc['source']}\n"
            result_text += f"  Relevance Score: {doc['similarity_score']:.4f}\n"
            result_text += f"  Content preview: {doc['document'][:200]}...\n\n"

        return {
            "content": [{
                "type": "text",
                "text": result_text
            }],
            "documents": results  # Include full results for programmatic access
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"Error performing web search: {str(e)}"
            }]
        }


class WebSearchAgent:
    """
    Web Search Agent using Claude Agent SDK.

    This agent handles web searches using Exa AI through custom MCP tools.
    It acts as a subagent of the RetrievalAgent for external information retrieval.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the Web Search Agent.

        Args:
            model: Claude model to use for agent reasoning
        """
        self.model = model

        # Create MCP server with exa_web_search tool
        self.mcp_server = create_sdk_mcp_server(
            name="web_search_server",
            tools=[exa_web_search]
        )

        # Configure agent options
        self.agent_options = ClaudeAgentOptions(
            system_prompt=self._get_system_prompt(),
            mcp_servers={"web_search": self.mcp_server},
            allowed_tools=["mcp__web_search__exa_web_search"],
            model=self.model
            # permission_mode removed for production deployment
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the web search agent."""
        # Load prompt from markdown file instead of inline string (L7 pattern)
        return load_prompt("web_search_agent.md")

    @classmethod
    def as_agent_definition(cls):
        """
        Return an AgentDefinition describing this agent as a subagent.

        Follows the L7 reference pattern so that RetrievalAgent (or any
        orchestrator using ClaudeAgentOptions.agents) can reference the
        web-search capability structurally. The existing programmatic
        call path (search_web / search_web_direct) remains unchanged.
        """
        from claude_agent_sdk import AgentDefinition
        return AgentDefinition(
            description="Searches the web using Exa AI for external information.",
            prompt=load_prompt("web_search_agent.md"),
            tools=["mcp__web_search__exa_web_search"],
            model="haiku"
        )

    async def search_web(
        self,
        query: str,
        num_results: int = TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Search the web using the agent with ClaudeSDKClient.

        Note: This method uses ClaudeSDKClient (required for custom MCP tools).
        The agent will use the exa_web_search tool to fetch results.

        Args:
            query: The search query
            num_results: Number of results to return

        Returns:
            List of web search results in standardized document format
        """
        from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, ToolUseBlock

        # Build the prompt for the agent
        prompt = f"""Search the web for this query: "{query}"

Retrieve {num_results} relevant web results.

Use the exa_web_search tool to perform the search."""

        # Execute the agent query using ClaudeSDKClient
        tool_used = False
        try:
            async with ClaudeSDKClient(options=self.agent_options) as client:
                await client.query(prompt)

                # Process response - check if tool was called
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                if block.name == "mcp__web_search__exa_web_search":
                                    tool_used = True
                                    # Tool was called successfully
                                    # Now retrieve results using the same parameters
                                    tool_input = block.input
                                    query_from_tool = tool_input.get("query", query)
                                    num_results_from_tool = tool_input.get("num_results", num_results)

                                    # Use the underlying search_web function to get actual results
                                    return search_web(
                                        query_from_tool,
                                        num_results=num_results_from_tool
                                    )

        except Exception as e:
            print(f"Error in web search agent: {e}")
            # Fall back to direct search
            return await self.search_web_direct(query, num_results)

        # If tool wasn't used, fall back to direct method
        if not tool_used:
            print("Warning: Agent did not use exa_web_search tool, falling back to direct method")
            return await self.search_web_direct(query, num_results)

        return []

    async def search_web_direct(
        self,
        query: str,
        num_results: int = TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Direct web search without agent reasoning (for testing).

        This bypasses the agent and calls the underlying search_web function directly.
        Useful for testing and debugging.

        Args:
            query: The search query
            num_results: Number of results to return

        Returns:
            List of web search results
        """
        return search_web(query, num_results=num_results)


# Convenience function for standalone usage
async def web_search(
    query: str,
    num_results: int = TOP_K,
    use_agent: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function to perform web search.

    Args:
        query: The search query
        num_results: Number of results to return
        use_agent: If True, use agent reasoning; if False, direct call

    Returns:
        List of web search results
    """
    agent = WebSearchAgent()

    if use_agent:
        return await agent.search_web(query, num_results)
    else:
        return await agent.search_web_direct(query, num_results)


if __name__ == "__main__":
    # Test the web search agent
    async def test():
        print("Testing Web Search Agent...")

        # Test 1: Direct search (no agent)
        print("\n=== Test 1: Direct Search ===")
        agent = WebSearchAgent()
        results = await agent.search_web_direct(
            query="Windows 11 blue screen error",
            num_results=3
        )
        print(f"Retrieved {len(results)} web results")
        if results:
            print(f"First result: {results[0]['title']}")
            print(f"URL: {results[0]['source']}")

        # Test 2: Agent-based search
        print("\n=== Test 2: Agent-Based Search ===")
        results = await agent.search_web(
            query="Windows 11 blue screen error",
            num_results=3
        )
        print(f"Retrieved {len(results)} web results via agent")
        if results:
            print(f"First result: {results[0]['title']}")

    asyncio.run(test())
