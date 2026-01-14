# RAG Retrieval Evaluation

This project evaluates the performance of your RAG retrieval system using Azure AI Search and Azure OpenAI as a judge. It uses the `RetrievalEvaluator` from the `azure-ai-evaluation` SDK to qualitatively assess if retrieved documents are relevant to test queries.

## Prerequisites

- Python 3.9+
- An Azure OpenAI resource with a model deployed (e.g., GPT-4).
- An Azure AI Search resource with an index containing your documents.

## Setup

1.  **Install Dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure Environment:**

    Rename or copy `.env` to `.env.local` (or just edit `.env`) and fill in your details:

    ```env
    AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
    AZURE_OPENAI_DEPLOYMENT=gpt-4
    AZURE_SEARCH_ENDPOINT=https://<your-service>.search.windows.net
    AZURE_SEARCH_INDEX=<your-index-name>
    ```

    *Authentication:*
    - **Note:** Your Azure OpenAI resource appears to have Key-based authentication disabled.
    - The script is configured to use **Azure Credentials (RBAC)** via `DefaultAzureCredential`.
    - Ensure you are logged in:
      ```bash
      az login
      ```
    - Ensure your user has the **"Cognitive Services OpenAI Contributor"** (or User) role on the OpenAI resource.

## Usage

1.  **Add Test Queries:**
    Open `evaluate_retrieval.py` and modify the `test_queries` list with questions relevant to your document set.

2.  **Run Evaluation:**

    ```bash
    python evaluate_retrieval.py
    ```

## Notes

- **Sanitization:** The script includes logic to strip image file references (e.g., `.png`, `![image]`) from the retrieved text. This prevents the evaluator from attempting to resolve local image paths, which can cause errors.

1.  **Retrieval:** The script queries your Azure AI Search index for the top 3 documents matching each query.
2.  **Formatting:** It combines the content of these documents into a context block.
3.  **Judging:** It sends the `query` and `retrieved_context` to the `RetrievalEvaluator` (powered by GPT-4). The model judges whether the context provides sufficient information to answer the query, returning a score from 1 (Irrelevant) to 5 (Highly Relevant).
