import os
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
key = os.getenv("AZURE_OPENAI_API_KEY")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")

print(f"Endpoint: {endpoint}")
print(f"Key: {key[:5]}..." if key else "Key: None")
print(f"Deployment: {deployment}")

client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=key,
    api_version="2024-02-15-preview"
)

try:
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "user", "content": "Hello"}
        ]
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Error: {e}")
