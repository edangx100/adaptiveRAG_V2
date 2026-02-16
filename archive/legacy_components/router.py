"""
Query routing component using Claude API with structured outputs.
Routes queries to appropriate collections (vectordb, web_search, direct_llm).
"""

import os
import sys
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anthropic import Anthropic
from dotenv import load_dotenv
from prompts import routing_prompt

# Load environment variables
load_dotenv()

# Initialize Anthropic client
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# JSON schema for routing decision
ROUTING_SCHEMA = {
    "type": "object",
    "properties": {
        "route": {
            "type": "string",
            "enum": ["vectordb", "web_search", "direct_llm"],
            "description": "The routing destination for the query"
        },
        "strategy": {
            "type": "string",
            "enum": ["single_collection", "multi_collection", "comprehensive"],
            "description": "Search strategy (only for vectordb route)"
        },
        "collections": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["catalog", "faq", "troubleshooting"]
            },
            "description": "Collections to search (only for vectordb route)"
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the routing decision"
        }
    },
    "required": ["route", "reasoning"],
    "additionalProperties": False
}


def route_query(query: str, model: str = "claude-sonnet-4-5") -> dict:
    """
    Route a query to the appropriate collections using Claude API with structured outputs.

    Args:
        query: The user query to route
        model: The Claude model to use (default: claude-sonnet-4-5)

    Returns:
        dict: Routing decision with keys:
            - route: "vectordb" | "web_search" | "direct_llm"
            - strategy: "single_collection" | "multi_collection" | "comprehensive" (if route=vectordb)
            - collections: List of collections to search (if route=vectordb)
            - reasoning: Explanation of the routing decision

    Example:
        >>> result = route_query("What gaming laptops do you have?")
        >>> print(result)
        {
            "route": "vectordb",
            "strategy": "single_collection",
            "collections": ["catalog"],
            "reasoning": "This is a product inquiry about gaming laptops..."
        }
    """
    # Format the prompt with the query
    formatted_prompt = routing_prompt.format(query=query)

    # Call Claude API with structured outputs
    response = client.beta.messages.create(
        model=model,
        max_tokens=1024,
        betas=["structured-outputs-2025-11-13"],
        messages=[
            {
                "role": "user",
                "content": formatted_prompt
            }
        ],
        output_format={
            "type": "json_schema",
            "schema": ROUTING_SCHEMA
        }
    )

    # Parse the JSON response
    routing_decision = json.loads(response.content[0].text)

    return routing_decision


if __name__ == "__main__":
    # Test the router with diverse queries
    test_queries = [
        "What gaming laptops do you have?",
        "What are your return policies?",
        "My laptop won't turn on",
        "Windows 11 blue screen error 0x0000007E",
        "Hello, thanks for your help!"
    ]

    print("=" * 80)
    print("QUERY ROUTER TEST")
    print("=" * 80)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: {query}")
        print("-" * 80)

        result = route_query(query)

        print(f"Route: {result['route']}")
        if result['route'] == 'vectordb':
            print(f"Strategy: {result.get('strategy', 'N/A')}")
            print(f"Collections: {result.get('collections', [])}")
        print(f"Reasoning: {result['reasoning']}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
