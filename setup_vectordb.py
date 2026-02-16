"""
TechMart Vector Database Setup Script

This script initializes ChromaDB and loads documents from CSV files.
indexing with Jina Embeddings v3.
"""

import os
import csv
import json
import httpx
from typing import List
from dotenv import load_dotenv
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents

# Load environment variables
load_dotenv()

# Import configuration
from config import CHROMA_DB_PATH, COLLECTIONS


class JinaEmbeddingFunction(EmbeddingFunction):
    """
    Custom embedding function for ChromaDB using Jina Embeddings v3.

    This class implements ChromaDB's EmbeddingFunction interface to generate
    embeddings using the Jina AI API.
    """

    def __init__(self, api_key: str = None, model: str = "jina-embeddings-v3"):
        """
        Initialize the Jina embedding function.

        Args:
            api_key: Jina API key (defaults to JINA_API_KEY from environment)
            model: Jina model to use (default: jina-embeddings-v3)
        """
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        self.model = model
        self.base_url = "https://api.jina.ai/v1/embeddings"
        self.embedding_dimension = 1024

        if not self.api_key:
            raise ValueError(
                "JINA_API_KEY not found. Please set it in your .env file."
            )

    def __call__(self, input: Documents) -> List[List[float]]:
        """
        Generate embeddings for a list of documents.

        Args:
            input: List of text documents to embed

        Returns:
            List of embedding vectors
        """
        return self._generate_embeddings_sync(input)

    def _generate_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronously generate embeddings using Jina API.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "input": texts,
            "task": "retrieval.passage"  # For document indexing
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()
                embeddings = [item["embedding"] for item in result["data"]]

                print(f"  Generated {len(embeddings)} embeddings (dimension: {len(embeddings[0])})")
                return embeddings

        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error generating embeddings: {e}")
            raise


def csv_to_pipe_separated_text(row, collection_name="catalog"):
    """
    Convert a CSV row to pipe-separated text format.

    Args:
        row: Dictionary containing CSV row data
        collection_name: Name of the collection (catalog, faq, troubleshooting)

    Returns:
        String with pipe-separated key-value pairs
    """
    if collection_name == "catalog":
        # Format: Product ID | Name | Category | Price | Description | Specs
        specs = row.get('specs_json', '{}')
        try:
            specs_dict = json.loads(specs.replace("'", '"'))
            specs_text = " | ".join([f"{k}: {v}" for k, v in specs_dict.items()])
        except:
            specs_text = specs

        text = (
            f"Product ID: {row['product_id']} | "
            f"Name: {row['name']} | "
            f"Category: {row['category']} | "
            f"Price: ${row['price']} | "
            f"Description: {row['short_desc']} | "
            f"Specifications: {specs_text}"
        )
        return text

    elif collection_name == "faq":
        # Format: Question | Answer | Tags
        text = (
            f"Question: {row['question']} | "
            f"Answer: {row['answer']} | "
            f"Tags: {row['tags']}"
        )
        return text

    elif collection_name == "troubleshooting":
        # Format: Issue | Product ID | Symptoms | Resolution Steps
        text = (
            f"Issue: {row['issue_title']} | "
            f"Product ID: {row['product_id']} | "
            f"Symptoms: {row['symptoms']} | "
            f"Resolution Steps: {row['steps']}"
        )
        return text

    return ""


def initialize_chromadb():
    """
    Initialize ChromaDB client with persistent storage.

    Returns:
        ChromaDB client instance
    """
    print(f"Initializing ChromaDB at {CHROMA_DB_PATH}...")

    # Create persistent client
    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
    )

    print(f"ChromaDB initialized successfully!")
    return client


def load_sample_catalog_documents(client, num_samples=5):
    """
    Load sample documents from techmart_catalog.csv into ChromaDB.

    Args:
        client: ChromaDB client instance
        num_samples: Number of sample documents to load (default: 5)
    """
    print(f"\nLoading {num_samples} sample documents from catalog...")

    # Get or create collection
    collection = client.get_or_create_collection(
        name="catalog",
        metadata={"description": "TechMart product catalog"}
    )

    # Read CSV file
    csv_path = "data/techmart_catalog.csv"
    documents = []
    metadatas = []
    ids = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= num_samples:
                break

            # Convert to pipe-separated text
            document_text = csv_to_pipe_separated_text(row, "catalog")

            # Create metadata
            metadata = {
                "source": "techmart_catalog.csv",
                "collection": "catalog",
                "row_index": idx,
                "product_id": row['product_id'],
                "name": row['name'],
                "category": row['category'],
                "price": row['price']
            }

            # Create document ID
            doc_id = f"catalog_{idx}"

            documents.append(document_text)
            metadatas.append(metadata)
            ids.append(doc_id)

            print(f"  [{idx+1}] {row['product_id']}: {row['name']}")

    # Add documents to collection
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    print(f"\nSuccessfully added {len(documents)} documents to 'catalog' collection!")
    return collection


def load_all_collections(client):
    """
    Load all documents from all three collections into ChromaDB.

    This function loads:
    - catalog documents from techmart_catalog.csv
    - FAQ documents from techmart_faq.csv
    - troubleshooting documents from techmart_troubleshooting.csv

    Args:
        client: ChromaDB client instance

    Returns:
        Dictionary of collection name -> collection instance
    """
    # Initialize Jina Embeddings v3
    print("\nInitializing Jina Embeddings v3...")
    jina_embedding_function = JinaEmbeddingFunction()
    print("✓ Jina Embeddings v3 initialized successfully")

    collections_data = {
        "catalog": {
            "file": "data/techmart_catalog.csv",
            "description": "TechMart product catalog",
            "metadata_fields": ["product_id", "name", "category", "price", "short_desc"]
        },
        "faq": {
            "file": "data/techmart_faq.csv",
            "description": "TechMart frequently asked questions",
            "metadata_fields": ["question", "tags"]
        },
        "troubleshooting": {
            "file": "data/techmart_troubleshooting.csv",
            "description": "TechMart troubleshooting guides",
            "metadata_fields": ["issue_title", "product_id", "symptoms"]
        }
    }

    collections = {}
    total_docs = 0

    for collection_name, config in collections_data.items():
        print(f"\n{'='*60}")
        print(f"Loading collection: {collection_name}")
        print(f"{'='*60}")

        # Get or create collection with Jina embeddings
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"description": config["description"]},
            embedding_function=jina_embedding_function
        )

        # Read CSV file
        documents = []
        metadatas = []
        ids = []

        with open(config["file"], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                # Convert to pipe-separated text
                document_text = csv_to_pipe_separated_text(row, collection_name)

                # Create metadata with all CSV columns
                metadata = {
                    "source": config["file"].split("/")[-1],
                    "collection": collection_name,
                    "row_index": idx
                }

                # Add collection-specific metadata fields
                for field in config["metadata_fields"]:
                    if field in row:
                        metadata[field] = row[field]

                # Create document ID with format: {collection}_{index}
                doc_id = f"{collection_name}_{idx}"

                documents.append(document_text)
                metadatas.append(metadata)
                ids.append(doc_id)

        # Add documents to collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        doc_count = len(documents)
        total_docs += doc_count
        collections[collection_name] = collection

        print(f"✓ Loaded {doc_count} documents into '{collection_name}' collection")

    print(f"\n{'='*60}")
    print(f"INDEXING COMPLETE")
    print(f"{'='*60}")
    print(f"Total documents indexed: {total_docs}")
    print(f"Collections created: {', '.join(collections.keys())}")

    return collections


def test_basic_query(collection, query_text="laptop for professionals"):
    """
    Test basic similarity search query.

    Args:
        collection: ChromaDB collection instance
        query_text: Query string to search for
    """
    print(f"\n{'='*60}")
    print(f"Testing similarity search with query: '{query_text}'")
    print(f"{'='*60}")

    # Query the collection
    results = collection.query(
        query_texts=[query_text],
        n_results=3
    )

    # Display results
    print(f"\nFound {len(results['documents'][0])} relevant products:\n")

    for idx, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"Result {idx+1}:")
        print(f"  Product: {metadata['name']}")
        print(f"  Category: {metadata['category']}")
        print(f"  Price: ${metadata['price']}")
        print(f"  Similarity Score: {1 - distance:.4f}")
        print(f"  Document: {doc[:150]}...")
        print()


def test_all_collections(collections):
    """
    Test queries on all three collections to verify proper indexing.

    Args:
        collections: Dictionary of collection name -> collection instance
    """
    print(f"\n{'='*60}")
    print("TESTING ALL COLLECTIONS")
    print(f"{'='*60}")

    # Test catalog collection
    print(f"\n[TEST 1] Catalog Collection - Query: 'laptop for professionals'")
    print("-" * 60)
    catalog_results = collections["catalog"].query(
        query_texts=["laptop for professionals"],
        n_results=3
    )
    for idx, (doc, metadata) in enumerate(zip(
        catalog_results['documents'][0],
        catalog_results['metadatas'][0]
    )):
        print(f"\n  Result {idx+1}:")
        print(f"    ID: {metadata.get('product_id', 'N/A')}")
        print(f"    Name: {metadata.get('name', 'N/A')}")
        print(f"    Category: {metadata.get('category', 'N/A')}")
        print(f"    Price: ${metadata.get('price', 'N/A')}")
        print(f"    Document: {doc[:120]}...")

    # Test FAQ collection
    print(f"\n[TEST 2] FAQ Collection - Query: 'shipping and delivery times'")
    print("-" * 60)
    faq_results = collections["faq"].query(
        query_texts=["shipping and delivery times"],
        n_results=3
    )
    for idx, (doc, metadata) in enumerate(zip(
        faq_results['documents'][0],
        faq_results['metadatas'][0]
    )):
        print(f"\n  Result {idx+1}:")
        print(f"    Question: {metadata.get('question', 'N/A')}")
        print(f"    Tags: {metadata.get('tags', 'N/A')}")
        print(f"    Document: {doc[:120]}...")

    # Test troubleshooting collection
    print(f"\n[TEST 3] Troubleshooting Collection - Query: 'mouse not working'")
    print("-" * 60)
    troubleshooting_results = collections["troubleshooting"].query(
        query_texts=["mouse not working"],
        n_results=3
    )
    for idx, (doc, metadata) in enumerate(zip(
        troubleshooting_results['documents'][0],
        troubleshooting_results['metadatas'][0]
    )):
        print(f"\n  Result {idx+1}:")
        print(f"    Issue: {metadata.get('issue_title', 'N/A')}")
        print(f"    Product ID: {metadata.get('product_id', 'N/A')}")
        print(f"    Document: {doc[:120]}...")


def main():
    """
    Main function to set up ChromaDB with all three collections.
    Indexing
    """
    print("="*60)
    print("TechMart Vector Database Setup")
    print("Complete Indexing of All Collections")
    print("="*60)

    # Initialize ChromaDB
    client = initialize_chromadb()

    # Load all collections with complete indexing
    collections = load_all_collections(client)

    # Test queries on all collections
    test_all_collections(collections)

    print("\n" + "="*60)
    print("Load Collections COMPLETE!")
    print("="*60)
    print(f"ChromaDB directory: {CHROMA_DB_PATH}")
    print(f"Collections available: {list(collections.keys())}")
    print("All collections are ready for querying!")
    print("="*60)


if __name__ == "__main__":
    main()
