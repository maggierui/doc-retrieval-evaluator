import os
import json
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.ai.evaluation import RetrievalEvaluator

# Load environment variables
load_dotenv()

# Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")

def get_search_client():
    # Treat placeholder or empty string as None
    key = AZURE_SEARCH_KEY
    if key and "<your-key>" in key:
        key = None

    if key:
        credential = AzureKeyCredential(key)
    else:
        credential = DefaultAzureCredential()
        
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=credential
    )

def main():
    # 1. Initialize Clients
    search_client = get_search_client()
    
    # Model config for the Judge (Azure OpenAI)
    model_config = {
        "azure_endpoint": AZURE_OPENAI_ENDPOINT,
        "azure_deployment": AZURE_OPENAI_DEPLOYMENT,
        "api_key": AZURE_OPENAI_API_KEY,
        "api_version": "2024-02-15-preview" # Update as needed
    }
    
    # Initialize the RetrievalEvaluator
    # We force DefaultAzureCredential because Key-based auth is disabled on the Azure OpenAI resource.
    credential = DefaultAzureCredential()
    
    # Remove api_key from model_config to ensure the SDK uses the TokenCredential
    if "api_key" in model_config:
        del model_config["api_key"]

    evaluator = RetrievalEvaluator(model_config=model_config, credential=credential)

    # 2. Define Test Queries
    # You can load this from a file or add more here.
    test_queries = [
        "What are the benefits of SharePoint?",
        "How do I create a communication site?",
        # Add your specific domain queries here
    ]

    print(f"Starting evaluation of {len(test_queries)} queries...")
    print("-" * 50)

    results = []

    for query in test_queries:
        print(f"Processing Query: {query}")
        
        # 3. Retrieve Documents
        # We retrieve top 3 documents to simulate the RAG context window
        try:
            search_results = search_client.search(search_text=query, top=3)
            
            # Combine retrieved chunks into a single context string
            # Note: We assume the index has a 'content' field. Adjust if your field is named differently (e.g., 'text', 'chunk').
            retrieved_docs = []
            retrieved_chunks_info = []

            for doc in search_results:
                # Fallback to getting all values if 'content' key specific doesn't exist used for demo
                content = doc.get('content') or doc.get('text') or doc.get('chunk') or str(doc)
                retrieved_docs.append(content)

                # Capture metadata for debugging
                chunk_meta = {
                    "search_score": doc.get("@search.score"),
                    "id": doc.get("id") or doc.get("chunk_id"),
                    "filepath": doc.get("filepath") or doc.get("filename") or doc.get("metadata_storage_name"),
                    "url": doc.get("url"),
                    "title": doc.get("title")
                }
                # Clean up None values
                chunk_meta = {k: v for k, v in chunk_meta.items() if v is not None}
                retrieved_chunks_info.append(chunk_meta)
            
            retrieved_context = "\n\n".join(retrieved_docs)
            
            # Aggressive sanitization to prevent Prompty/Markdown image loading issues
            retrieved_context = retrieved_context.replace("cs-1.png", "cs-1_png_placeholder")
            retrieved_context = retrieved_context.replace(".png", "_png")
            retrieved_context = retrieved_context.replace(".jpg", "_jpg")
            # Break Markdown image syntax just in case
            retrieved_context = retrieved_context.replace("![", "[")
            
            if not retrieved_context.strip():
                print("  Warning: No documents found.")
                continue

            print(f"  > Retrieved {len(retrieved_docs)} docs. Context length: {len(retrieved_context)} chars.")
            
            # Debug: Check for image paths in context
            if "cs-1.png" in retrieved_context:
                print("  > WARNING: Found 'cs-1.png' in retrieved context!")
            
            # 4. Evaluate using LLM Judge
            # Usage: Try passing query and context directly for single-turn evaluation
            try:
                # Direct call for query + context
                eval_result = evaluator(query=query, context=retrieved_context)
            except Exception as e:
                print(f"  > Direct call failed ({e}). Trying conversation format...")
                conversation_input = {
                    "messages": [{"role": "user", "content": query}],
                    "context": retrieved_context
                }
                eval_result = evaluator(conversation=conversation_input)
            
            # Debug: Print the full result to understand why score isn't appearing
            # print(f"DEBUG: eval_result = {eval_result}")

            # Extract score
            # Note: The key might be 'gpt_retrieval' or 'retrieval' depending on SDK version.
            score = eval_result.get('retrieval') or eval_result.get('gpt_retrieval')

            if score is None:
                print(f"  > Warning: Score is None. Raw result: {eval_result}")
            else:
                print(f"  > Score: {score}")

            results.append({
                "query": query,
                "score": score,
                "retrieved_context_preview": retrieved_context[:200] + "...",
                "retrieved_chunks": retrieved_chunks_info
            })

        except Exception as e:
            print(f"  Error processing query: {e}")

    # 5. Summary
    print("-" * 50)
    if results:
        avg_score = sum(r['score'] for r in results if r['score'] is not None) / len(results)
        print(f"Average Retrieval Score: {avg_score:.2f} / 5.0")
        
        # Save detailed results
        with open("evaluation_results.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Detailed results saved to evaluation_results.json")
    else:
        print("No results to summarize.")

if __name__ == "__main__":
    main()
