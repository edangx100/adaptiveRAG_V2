"""
Exa Web Search Tool

This module provides functions to perform web searches using the Exa AI API.
Used as an alternative retrieval path when queries require external web information.
"""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Exa SDK
try:
    from exa_py import Exa
except ImportError:
    raise ImportError(
        "exa_py package not found. Please install it: pip install exa_py"
    )


def initialize_exa_client() -> Exa:
    """
    Initialize and return an Exa client.

    Returns:
        Exa client instance

    Raises:
        ValueError: If EXA_API_KEY is not found in environment
    """
    exa_api_key = os.getenv("EXA_API_KEY")

    if not exa_api_key:
        raise ValueError(
            "EXA_API_KEY not found. Please set it in your .env file.\n"
            "Get your API key at: https://dashboard.exa.ai/"
        )

    return Exa(api_key=exa_api_key)


def search_web(
    query: str,
    num_results: int = 5,
    search_type: str = "auto"
) -> List[Dict[str, Any]]:
    """
    Perform a web search using Exa AI and return results in a standardized format.

    Args:
        query: The search query string
        num_results: Number of results to return (default: 5)
        search_type: Type of search - "auto", "neural", or "keyword" (default: "auto")

    Returns:
        List of dictionaries containing search results with format:
        [
            {
                'document': str,        # Page content/text
                'collection': 'web_search',
                'source': str,          # URL of the page
                'title': str,           # Page title
                'author': str,          # Page author (if available)
                'published_date': str,  # Publication date (if available)
                'similarity_score': float  # Relevance score (normalized to 0-1)
            },
            ...
        ]

    Example:
        >>> results = search_web("Windows 11 blue screen error fix")
        >>> print(f"Found {len(results)} results")
        >>> print(results[0]['title'])
    """
    try:
        # Initialize Exa client
        exa = initialize_exa_client()

        # Perform search with contents
        # The search_and_contents method retrieves both search results and page contents
        search_results = exa.search_and_contents(
            query,
            num_results=num_results,
            type=search_type,
            text=True  # Request text content extraction
        )

        # Convert Exa results to standardized format
        formatted_results = []

        for idx, result in enumerate(search_results.results):
            # Extract text content (limit to reasonable size for context)
            text_content = result.text if hasattr(result, 'text') and result.text else ""

            # Truncate very long content to avoid context overflow
            max_content_length = 2000
            if len(text_content) > max_content_length:
                text_content = text_content[:max_content_length] + "..."

            # Normalize score to 0-1 range (Exa scores are typically 0-1 already)
            # If no score is available, assign based on rank
            if hasattr(result, 'score') and result.score is not None:
                similarity_score = float(result.score)
            else:
                # Assign decreasing scores based on result position
                similarity_score = 1.0 - (idx * 0.1)
                similarity_score = max(0.1, similarity_score)  # Minimum score of 0.1

            formatted_result = {
                'document': text_content,
                'collection': 'web_search',
                'source': result.url,
                'title': result.title if hasattr(result, 'title') else "Unknown",
                'author': result.author if hasattr(result, 'author') else None,
                'published_date': result.published_date if hasattr(result, 'published_date') else None,
                'similarity_score': similarity_score
            }

            formatted_results.append(formatted_result)

        return formatted_results

    except Exception as e:
        print(f"Error performing web search with Exa: {e}")
        raise


def test_exa_search():
    """
    Test the Exa web search functionality with sample queries.
    """
    print("=" * 80)
    print("EXA WEB SEARCH TOOL - TEST")
    print("=" * 80)
    print()

    test_queries = [
        "Windows 11 blue screen error fixes",
        "latest laptop gaming trends 2024",
        "how to troubleshoot slow computer performance"
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\nTest {i}/{len(test_queries)}: {query}")
        print("-" * 80)

        try:
            results = search_web(query, num_results=3)

            print(f"Found {len(results)} results:\n")

            for j, result in enumerate(results, 1):
                print(f"{j}. {result['title']}")
                print(f"   URL: {result['source']}")
                print(f"   Score: {result['similarity_score']:.3f}")
                if result['author']:
                    print(f"   Author: {result['author']}")
                if result['published_date']:
                    print(f"   Published: {result['published_date']}")
                print(f"   Content preview: {result['document'][:150]}...")
                print()

        except Exception as e:
            print(f"Error: {e}")
            print()

    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    # Run test suite
    test_exa_search()
