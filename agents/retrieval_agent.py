"""
Retrieval Agent for Adaptive RAG System

This agent handles document retrieval from ChromaDB collections using the Claude Agent SDK.
It implements the retrieval_strategy_skill and provides a chromadb_retriever tool.

Architecture:
- Uses Claude Agent SDK with custom MCP tools
- Retrieves documents from ChromaDB vector store
- Supports querying specific collections or all collections
- Returns documents with metadata for downstream grading
- Integrates WebSearchAgent as a subagent for external web queries

Usage:
    from agents.retrieval_agent import RetrievalAgent

    agent = RetrievalAgent()
    documents = await agent.retrieve_documents("best laptop for gaming", ["catalog"])
    web_docs = await agent.retrieve_from_web("Windows 11 blue screen error")
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
# sdk_patch must be imported before create_sdk_mcp_server to fix the
# Server version parameter incompatibility with the mcp library.
import sdk_patch  # noqa: F401
from claude_agent_sdk import tool, create_sdk_mcp_server, query, ClaudeAgentOptions

# Load environment variables
load_dotenv()

# Import existing ChromaDB functions
from tools.chromadb_tool import query_chromadb, query_specific_collections
from config import TOP_K, COLLECTIONS
from prompts import load_prompt


# Helper function for retrieval (not wrapped as tool)
def _retrieve_from_chromadb(
    query_text: str,
    collections: List[str],
    top_k: int
) -> List[Dict[str, Any]]:
    """
    Helper function to retrieve documents from ChromaDB.

    This is the core retrieval logic used by both the tool and direct methods.

    Args:
        query_text: The search query
        collections: List of collection names to search (empty for all)
        top_k: Number of documents per collection

    Returns:
        List of retrieved documents with metadata
    """
    if collections:
        # Query specific collections
        results = query_specific_collections(query_text, collections, top_k)
    else:
        # Query all collections
        results = query_chromadb(query_text, top_k)

    return results


# Tool: ChromaDB Retriever
@tool(
    name="chromadb_retriever",
    description="Retrieve documents from ChromaDB vector database. Queries one or more collections and returns relevant documents with metadata.",
    # Must use full JSON Schema format (with "type", "properties", "required"),
    # NOT Python types like {"query_text": str, "collections": list}.
    # The sdk_patch.py list_tools handler passes JSON Schema dicts through as-is,
    # but converts Python types via fallback — where `list` becomes {"type": "string"}
    # instead of {"type": "array"}, breaking tool parameter visibility for the agent.
    input_schema={
        "type": "object",
        "properties": {
            "query_text": {
                "type": "string",
                "description": "The search query text"
            },
            "collections": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of collection names to search (empty array for all collections)"
            },
            "top_k": {
                "type": "integer",
                "description": "Number of documents to retrieve per collection"
            }
        },
        "required": ["query_text"]
    }
)
async def chromadb_retriever(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retrieve documents from ChromaDB collections (tool wrapper).

    Args:
        args: Dictionary containing:
            - query_text: The search query
            - collections: List of collection names to search (or empty for all)
            - top_k: Number of documents per collection

    Returns:
        Dictionary with content containing retrieved documents
    """
    query_text = args.get("query_text", "")
    collections = args.get("collections", [])
    top_k = args.get("top_k", TOP_K)

    # Normalize collections to a list (Claude may pass a string instead of an array)
    if isinstance(collections, str):
        collections = [c.strip() for c in collections.split(',') if c.strip()]
    elif not isinstance(collections, list):
        collections = [collections] if collections else []

    # Validate inputs
    if not query_text:
        return {
            "content": [{
                "type": "text",
                "text": "Error: query_text is required"
            }]
        }

    # Query ChromaDB using helper function
    try:
        results = _retrieve_from_chromadb(query_text, collections, top_k)

        # Format results for agent
        result_text = f"Retrieved {len(results)} documents:\n\n"

        for i, doc in enumerate(results, 1):
            result_text += f"Document {i}:\n"
            result_text += f"  Collection: {doc['collection']}\n"
            result_text += f"  Similarity Score: {doc['similarity_score']:.4f}\n"
            result_text += f"  Content: {doc['document'][:200]}...\n"
            result_text += f"  Metadata: {doc['metadata']}\n\n"

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
                "text": f"Error retrieving documents: {str(e)}"
            }]
        }


class RetrievalAgent:
    """
    Retrieval Agent using Claude Agent SDK.

    This agent handles document retrieval from ChromaDB using custom MCP tools.
    It implements the retrieval_strategy_skill for intelligent document fetching.
    It includes WebSearchAgent as a subagent for external web queries.
    """

    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        """
        Initialize the Retrieval Agent.

        Args:
            model: Claude model to use for agent reasoning
        """
        self.model = model

        # Create MCP server with chromadb_retriever tool
        self.mcp_server = create_sdk_mcp_server(
            name="retrieval_server",
            tools=[chromadb_retriever]
        )

        # Configure agent options
        self.agent_options = ClaudeAgentOptions(
            system_prompt=self._get_system_prompt(),
            mcp_servers={"retrieval": self.mcp_server},
            allowed_tools=["mcp__retrieval__chromadb_retriever"],
            model=self.model
            # permission_mode removed for production deployment
        )

        # Formal subagent pattern (SDK AgentDefinition):
        # RetrievalAgent's Claude instance invokes WebSearchAgent via the "Agent" tool
        # rather than calling it directly as a Python object. The MCP server for
        # exa_web_search must be registered here so the subagent can access the tool
        # when it runs inside this agent's session.
        from agents.web_search_agent import exa_web_search, WebSearchAgent as _WebSearchAgent
        self._web_search_mcp_server = create_sdk_mcp_server(
            name="web_search_server",
            tools=[exa_web_search]
        )

        # Structured output schema: ensures retrieve_from_web always gets a typed
        # list back from the subagent instead of free-form text that needs parsing.
        self._web_results_schema = {
            "type": "object",
            "properties": {
                "documents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "document": {"type": "string"},
                            "title": {"type": "string"},
                            "source": {"type": "string"},
                            "similarity_score": {"type": "number"},
                            "collection": {"type": "string"}
                        },
                        "required": ["document", "source", "similarity_score", "collection"],
                        # additionalProperties: True preserves extra fields (e.g. metadata)
                        # returned by exa_tool without needing to enumerate them here.
                        "additionalProperties": True
                    }
                }
            },
            "required": ["documents"],
            "additionalProperties": False
        }

        # Separate options from self.agent_options: this session uses "Agent" (not
        # chromadb_retriever), declares the web-search subagent, and enforces
        # structured output so retrieve_from_web can return List[Dict] directly.
        self.web_search_options = ClaudeAgentOptions(
            system_prompt=self._get_system_prompt(),
            mcp_servers={"web_search": self._web_search_mcp_server},
            allowed_tools=["Agent"],  # "Agent" tool is required for subagent invocation
            agents={"web-search": _WebSearchAgent.as_agent_definition()},
            model=self.model,
            output_format={"type": "json_schema", "schema": self._web_results_schema}
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the retrieval agent."""
        # Load prompt from markdown file, then fill in the {collections} placeholder
        prompt_template = load_prompt("retrieval_agent.md")
        return prompt_template.format(collections=', '.join(COLLECTIONS))

    async def retrieve_documents(
        self,
        query_text: str,
        collections: Optional[List[str]] = None,
        top_k: int = TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents from ChromaDB using the agent with ClaudeSDKClient.

        Note: This method uses ClaudeSDKClient (required for custom MCP tools).
        The agent will use the chromadb_retriever tool to fetch documents.

        Args:
            query_text: The search query
            collections: List of collection names to search (None = all)
            top_k: Number of documents per collection

        Returns:
            List of retrieved documents with metadata
        """
        from claude_agent_sdk import ClaudeSDKClient, AssistantMessage, ToolUseBlock

        # Build the prompt for the agent
        if collections:
            collections_str = ", ".join(collections)
            prompt = f"""Retrieve documents for this query: "{query_text}"

Search these collections: {collections_str}
Retrieve {top_k} documents per collection.

Use the chromadb_retriever tool to fetch the documents."""
        else:
            prompt = f"""Retrieve documents for this query: "{query_text}"

Search all available collections.
Retrieve {top_k} documents per collection.

Use the chromadb_retriever tool to fetch the documents."""

        # Execute the agent query using ClaudeSDKClient (required for custom MCP tools)
        tool_used = False
        try:
            async with ClaudeSDKClient(options=self.agent_options) as client:
                await client.query(prompt)

                # Process response - check if tool was called
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                if block.name == "mcp__retrieval__chromadb_retriever":
                                    tool_used = True
                                    # Tool was called successfully
                                    # Now retrieve documents using the same parameters
                                    tool_input = block.input
                                    query_from_tool = tool_input.get("query_text", query_text)
                                    collections_from_tool = tool_input.get("collections", collections or [])
                                    top_k_from_tool = tool_input.get("top_k", top_k)

                                    # Ensure collections is a list (not a string that gets iterated char-by-char)
                                    if isinstance(collections_from_tool, str):
                                        # Handle comma-separated string: "troubleshooting, faq" -> ["troubleshooting", "faq"]
                                        if ', ' in collections_from_tool or ',' in collections_from_tool:
                                            collections_from_tool = [c.strip() for c in collections_from_tool.split(',')]
                                        else:
                                            collections_from_tool = [collections_from_tool] if collections_from_tool else []
                                    elif collections_from_tool is None:
                                        collections_from_tool = []
                                    elif not isinstance(collections_from_tool, list):
                                        # Convert any other type to list
                                        collections_from_tool = [collections_from_tool]

                                    # Use helper function to get actual documents
                                    return _retrieve_from_chromadb(
                                        query_from_tool,
                                        collections_from_tool,
                                        top_k_from_tool
                                    )

        except Exception as e:
            print(f"Error in retrieval agent: {e}")
            # Fall back to direct retrieval
            return await self.retrieve_documents_direct(query_text, collections, top_k)

        # If tool wasn't used or didn't return documents, fall back to direct method
        if not tool_used:
            print("Warning: Agent did not use chromadb_retriever tool, falling back to direct method")
            return await self.retrieve_documents_direct(query_text, collections, top_k)

        return []

    async def retrieve_documents_direct(
        self,
        query_text: str,
        collections: Optional[List[str]] = None,
        top_k: int = TOP_K
    ) -> List[Dict[str, Any]]:
        """
        Direct retrieval without agent reasoning (for testing).

        This bypasses the agent and calls the underlying helper function directly.
        Useful for testing and debugging.

        Args:
            query_text: The search query
            collections: List of collection names to search (None = all)
            top_k: Number of documents per collection

        Returns:
            List of retrieved documents with metadata
        """
        # Use helper function directly (not the tool wrapper)
        return _retrieve_from_chromadb(
            query_text=query_text,
            collections=collections or [],
            top_k=top_k
        )

    async def retrieve_from_web(
        self,
        query_text: str,
        num_results: int = TOP_K,
        use_agent: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents from web search using the WebSearchAgent formal subagent.

        Uses the SDK AgentDefinition pattern: RetrievalAgent invokes WebSearchAgent
        via the Agent tool, with structured output to extract the results.

        Args:
            query_text: The search query
            num_results: Number of web results to return
            use_agent: If True, invoke via formal subagent; if False, direct call

        Returns:
            List of web search results in standardized document format
        """
        if not use_agent:
            # Bypass the subagent entirely — useful for unit tests and debugging.
            from tools.exa_tool import search_web as _search_web
            return _search_web(query_text, num_results=num_results)

        from claude_agent_sdk import ClaudeSDKClient, ResultMessage

        # The prompt tells the parent agent to delegate to "web-search" via the Agent tool.
        # self.web_search_options registers that subagent, so Claude knows how to invoke it.
        prompt = f"""Use the web-search subagent to find information about: "{query_text}"

Retrieve {num_results} relevant results and return them as documents."""

        result = None
        try:
            async with ClaudeSDKClient(options=self.web_search_options) as client:
                await client.query(prompt)
                # Collect the final ResultMessage, which carries structured_output
                # populated from self._web_results_schema.
                async for message in client.receive_response():
                    if isinstance(message, ResultMessage):
                        result = message
        except Exception as e:
            print(f"Error in web search subagent: {e}")
            from tools.exa_tool import search_web as _search_web
            return _search_web(query_text, num_results=num_results)

        if result is None or not hasattr(result, 'structured_output') or result.structured_output is None:
            print("Warning: web search subagent returned no structured output, falling back")
            from tools.exa_tool import search_web as _search_web
            return _search_web(query_text, num_results=num_results)

        # structured_output is already validated against _web_results_schema,
        # so documents is guaranteed to be a list of dicts with the required fields.
        return result.structured_output.get('documents', [])


# Convenience function for standalone usage
async def retrieve(
    query_text: str,
    collections: Optional[List[str]] = None,
    top_k: int = TOP_K,
    use_agent: bool = True
) -> List[Dict[str, Any]]:
    """
    Convenience function to retrieve documents.

    Args:
        query_text: The search query
        collections: List of collection names to search (None = all)
        top_k: Number of documents per collection
        use_agent: If True, use agent reasoning; if False, direct tool call

    Returns:
        List of retrieved documents with metadata
    """
    agent = RetrievalAgent()

    if use_agent:
        return await agent.retrieve_documents(query_text, collections, top_k)
    else:
        return await agent.retrieve_documents_direct(query_text, collections, top_k)


if __name__ == "__main__":
    # Test the retrieval agent
    async def test():
        print("Testing Retrieval Agent...")

        # Test 1: Direct retrieval (no agent)
        print("\n=== Test 1: Direct Tool Call ===")
        agent = RetrievalAgent()
        docs = await agent.retrieve_documents_direct(
            query_text="gaming laptop",
            collections=["catalog"],
            top_k=3
        )
        print(f"Retrieved {len(docs)} documents")
        if docs:
            print(f"First document: {docs[0]['document'][:100]}...")

        # Test 2: Agent-based retrieval
        print("\n=== Test 2: Agent-Based Retrieval ===")
        docs = await agent.retrieve_documents(
            query_text="gaming laptop",
            collections=["catalog"],
            top_k=3
        )
        print(f"Retrieved {len(docs)} documents via agent")

    asyncio.run(test())
