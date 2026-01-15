import os
import json
import logging
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, QueryType
from azure.ai.evaluation import RetrievalEvaluator
from openai import AzureOpenAI

# Load environment variables
load_dotenv(override=True)

# Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")

# Setup Logging
logging.basicConfig(level=logging.WARNING)

def get_search_client():
    # Treat placeholder or empty string as None
    key = AZURE_SEARCH_KEY
    if key and ("<your-key>" in key or "#" in key):
         # Try to clean it if it has comments
         if "#" in key:
             key = key.split("#")[0].strip()
         if "<your-key>" in key:
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

def get_openai_client():
    # Force Token Auth since Key Auth is disabled on the resource
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-02-15-preview"
    )

def generate_embedding(client, text, model_name):
    # Ensure deployment name matches what is deployed in your Azure OpenAI service
    return client.embeddings.create(input=[text], model=model_name).data[0].embedding

def main():
    # 1. Initialize Clients
    search_client = get_search_client()
    openai_client = get_openai_client()
    
    # Model config for the Judge (Azure OpenAI)
    model_config = {
        "azure_endpoint": AZURE_OPENAI_ENDPOINT,
        "azure_deployment": AZURE_OPENAI_DEPLOYMENT,
        "api_key": AZURE_OPENAI_API_KEY, # Evaluator might check this
        "api_version": "2024-02-15-preview" 
    }
    
    # Initialize the RetrievalEvaluator
    credential = DefaultAzureCredential()
    
    # Force remove api_key so SDK uses the TokenCredential
    if "api_key" in model_config:
        del model_config["api_key"]

    try:
        evaluator = RetrievalEvaluator(model_config=model_config, credential=credential)
    except Exception as e:
        print(f"Warning: Failed to initialize RetrievalEvaluator: {e}")
        evaluator = None

    # 2. Define Test Queries
    test_queries = [
        "What are the benefits of SharePoint?",
        "How do I create a communication site?",
        "How to publish to internet sites?" 
    ]

    print(f"Starting evaluation of {len(test_queries)} queries... (Saving full context)")
    print(f"Using Embedding Model: {AZURE_OPENAI_EMBEDDING_DEPLOYMENT} (Assumed match for index dimension 3072)")
    print("-" * 50)

    results = []

    for query in test_queries:
        print(f"Processing Query: {query}")
        
        # 3. Retrieve Documents
        try:
            # Generate Embedding
            try:
                embedding = generate_embedding(openai_client, query, AZURE_OPENAI_EMBEDDING_DEPLOYMENT)
                vector_query = VectorizedQuery(vector=embedding, k_nearest_neighbors=50, fields="text_vector")
            except Exception as e:
                print(f"  Error generating embedding: {e}")
                print(f"  Ensure deployment '{AZURE_OPENAI_EMBEDDING_DEPLOYMENT}' exists.")
                continue

            # Hybrid Search + Semantic Reranking
            search_results = search_client.search(
                search_text=query,
                vector_queries=[vector_query],
                top=3, # RAG context window
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name="semantic-docs"
            )
            
            # Combine retrieved chunks
            retrieved_docs = []
            formatted_docs = []
            retrieved_chunks_info = []

            for i, doc in enumerate(search_results, 1):
                content = doc.get('chunk') or doc.get('content') or str(doc)
                title = doc.get('title') or "Unknown Source"
                
                # Raw content for evaluator
                retrieved_docs.append(content)
                
                # Formatted content for debugging/JSON
                formatted_docs.append(f"--- [Chunk {i} | Source: {title}] ---\n{content}")

                chunk_meta = {
                    "search_score": doc.get("@search.score"),
                    "reranker_score": doc.get("@search.reranker_score"),
                    "id": doc.get("id") or doc.get("chunk_id"),
                    "title": doc.get("title")
                }
                chunk_meta = {k: v for k, v in chunk_meta.items() if v is not None}
                retrieved_chunks_info.append(chunk_meta)
            
            # Context used for LLM evaluation (clean)
            retrieved_context = "\n\n".join(retrieved_docs)
            
            # Context saved to file for user inspection (detailed)
            debug_context = "\n\n".join(formatted_docs)
            
            # Sanitization of evaluation context
            retrieved_context = retrieved_context.replace("cs-1.png", "cs-1_placeholder")
            retrieved_context = retrieved_context.replace(".png", "_png")
            retrieved_context = retrieved_context.replace(".jpg", "_jpg")
            retrieved_context = retrieved_context.replace("![", "[") # Break image syntax
            
            if not retrieved_context.strip():
                print("  Warning: No documents found.")
                continue

            print(f"  > Retrieved {len(retrieved_docs)} docs.")
            for info in retrieved_chunks_info:
                 print(f"    - [{info.get('reranker_score', 0.0):.2f}] {info.get('title')}")

            # 4. Evaluate
            score = None
            reason = None
            if evaluator:
                try:
                    eval_result = evaluator(query=query, context=retrieved_context)
                    score = eval_result.get('retrieval') or eval_result.get('gpt_retrieval')
                    reason = eval_result.get('retrieval_reason') or eval_result.get('gpt_retrieval_reason')
                    print(f"  > Score: {score}")
                    print(f"  > Reason: {reason}")
                except Exception as e:
                    print(f"  Evaluation failed: {e}")

            results.append({
                "query": query,
                "score": score,
                "reason": reason,
                "retrieved_context_preview": retrieved_context[:200] + "...",
                "full_retrieved_context": debug_context,
                "retrieved_chunks": retrieved_chunks_info
            })

        except Exception as e:
            print(f"  Error processing query: {e}")

    # 5. Summary
    print("-" * 50)
    if results:
        valid_scores = [r['score'] for r in results if r['score'] is not None]
        if valid_scores:
            avg_score = sum(valid_scores) / len(valid_scores)
            print(f"Average Retrieval Score: {avg_score:.2f} / 5.0")
        
        with open("evaluation_results_formatted.json", "w") as f:
            json.dump(results, f, indent=2)
        print("Detailed results saved to evaluation_results_formatted.json")
    else:
        print("No results to summarize.")

if __name__ == "__main__":
    main()
