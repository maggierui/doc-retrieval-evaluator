import os
import base64
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

load_dotenv()

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")

def get_search_client():
    key = AZURE_SEARCH_KEY
    if key and "<your-key>" in key:
        key = None
    if key:
        credential = AzureKeyCredential(key)
    else:
        credential = DefaultAzureCredential()
    return SearchClient(AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, credential)

def decode_id(doc_id):
    """
    Tries to find a base64 encoded URL within the ID string and decode it.
    """
    try:
        # The ID format seen is: <hash>_<base64url>_pages_<num>
        # e.g. 42a2af166b30_aHR..._pages_0
        parts = doc_id.split('_')
        for part in parts:
            # Base64 encoded URLs are usually long.
            if len(part) > 20: 
                try:
                    # Fix padding for base64
                    padding = len(part) % 4
                    if padding > 0:
                        part += "=" * (4 - padding)
                    decoded = base64.urlsafe_b64decode(part).decode('utf-8')
                    if "http" in decoded:
                        return decoded
                except Exception:
                    continue
        return "Could not decode source URL from ID"
    except Exception as e:
        return f"Error decoding: {e}"

def inspect_specific_ids():
    client = get_search_client()
    
    # IDs from the user's report
    target_ids = [
        "42a2af166b30_aHR0cHM6Ly9zdHpwejV4dmcyZWxzdmUuYmxvYi5jb3JlLndpbmRvd3MubmV0L2RvY3MvT2ZmaWNlRG9jcy1TaGFyZVBvaW50LXByL1NoYXJlUG9pbnQvU2hhcmVQb2ludFNlcnZlci9hZG1pbmlzdHJhdGlvbi9yYnMtcGxhbm5pbmcubWQ7MTA1_pages_0",
        "f5e06cdd18ba_aHR0cHM6Ly9zdHpwejV4dmcyZWxzdmUuYmxvYi5jb3JlLndpbmRvd3MubmV0L2RvY3MvT2ZmaWNlRG9jcy1TaGFyZVBvaW50LXByL1NoYXJlUG9pbnQvU2hhcmVQb2ludFNlcnZlci9zZWFyY2gvY2hhbmdpbmctdGhlLXJhbmtpbmctb2Ytc2VhcmNoLXJlc3VsdHMubWQ7NA2_pages_0"
    ]

    print(f"Inspecting {len(target_ids)} specific chunk IDs...")

    for tid in target_ids:
        print(f"\n{'='*20}\nTarget ID: {tid}")
        decoded_url = decode_id(tid)
        print(f"Origin URL: {decoded_url}")
        
        # Try to retrieve by search filter since we don't know if 'chunk_id' or 'id' is the key field
        # We try filtering on both 'chunk_id' and 'id' just in case.
        # Note: In OAI Search, hyphenated fields like chunk_id need to be checked.
        
        found_doc = None
        
        # Strategy 1: filter by chunk_id
        try:
            results = client.search(search_text="*", filter=f"chunk_id eq '{tid}'", top=1)
            for doc in results:
                found_doc = doc
                print("Found via filter 'chunk_id'")
        except Exception:
            pass

        if not found_doc:
            # Strategy 2: filter by id (if `id` is the field name)
            try:
                results = client.search(search_text="*", filter=f"id eq '{tid}'", top=1)
                for doc in results:
                    found_doc = doc
                    print("Found via filter 'id'")
            except Exception:
                pass
        
        # Strategy 3: Search by title if ID lookup failed (fallback)
        if not found_doc:
             # Try extracting filename from decoded url
             if "http" in decoded_url:
                 filename = decoded_url.split('/')[-1].split(';')[0] # remove ;105 suffix if any
                 print(f"Looking up by filename: {filename}")
                 results = client.search(search_text=filename, top=1)
                 for doc in results:
                     found_doc = doc
                     print("Found via filename search (approximation)")

        if found_doc:
            print(f"Title: {found_doc.get('title')}")
            content = found_doc.get('content') or found_doc.get('text') or found_doc.get('chunk') or ""
            print(f"Content Length: {len(content)}")
            print("-" * 20)
            print(content)
            print("-" * 20)
            
            # Print available keys to help debug
            print(f"Available fields: {list(found_doc.keys())}")
        else:
            print("Could not retrieve document from index.")

if __name__ == "__main__":
    inspect_specific_ids()
