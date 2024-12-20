# Example: Fetch stored points directly from Qdrant
from qdrant_client.http import models
from qdrant_client import QdrantClient
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path('.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)



QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
MISTRALAI_API_KEY=os.getenv("MISTRALAI_API_KEY")

qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)

# Retrieve points from the collection
points = qdrant_client.search(
    collection_name=QDRANT_COLLECTION,
    query_vector=[0.1, 0.2, 0.3],  # Replace with any query vector
    limit=3,
    with_payload=True  # Ensure payload is included
)

# # Print results
# for point in points:
#     print(f"ID: {point.id}")
#     print(f"Payload: {point.payload}")


#         qdrant_client = QdrantClient(
#             url=QDRANT_URL,
#             api_key=QDRANT_API_KEY
#         )
#         embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=MISTRALAI_API_KEY)
        
#         # Initialize the vectorstore
#         vectorstore = QdrantVectorStore(
#             client=qdrant_client,
#             collection_name=QDRANT_COLLECTION,
#             embedding=embeddings
#         )
#         dc = vectorstore.similarity_search(query, k=3, kwargs={"with_payload": True})
#         # Print retrieved documents
#         # Print retrieved documents
#         for doc in dc:
#             print(f"Metadata: {doc.metadata}")
#             print(f"Page Content: {doc.page_content}")
