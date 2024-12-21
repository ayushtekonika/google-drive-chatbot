import os
import re
from uuid import uuid4
from typing import Callable
from qdrant_client import QdrantClient
from langchain_core.documents.base import Document
from langchain_mistralai import MistralAIEmbeddings
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct
)

def extract_file_details(file_path):
    # Extract the file name from the path
    file_name = os.path.basename(file_path)
    # Extract the prefix and the cleaned file name
    match = re.match(r'^([^_]+)_(.+)', file_name)
    if match:
        prefix = match.group(1)
        cleaned_file_name = match.group(2)
    else:
        prefix = ""  # No prefix found
        cleaned_file_name = file_name
    return {"prefix": prefix, "filename": cleaned_file_name}


class QdrantDB:
    def __init__(self):
        QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
        QDRANT_URL = os.getenv("QDRANT_URL")
        QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
        MISTRALAI_API_KEY=os.getenv("MISTRALAI_API_KEY")
        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            https=True,
            timeout=60,
        )
        
        self.collection_name = QDRANT_COLLECTION
        self.embedding_function: MistralAIEmbeddings = MistralAIEmbeddings(
                model="mistral-embed",
                api_key=MISTRALAI_API_KEY
            )
        self.vector_size = 1024  # Adjust vector size as needed
        # self.vector_size = 1536

    def create_collection(self):
        """
        Creates a collection if it does not exist.
        """
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=Distance.COSINE
                ),
            )
            # return False
        else:
            print(f"Collection {self.collection_name} already exists.")
            # return True

    def add_documents(self, documents: list[Document], processing_id: str, progress_callback: Callable[[str, int, int, str], None]):
        """
        Add a list of documents with unique IDs to the collection.
        Each document should be embedded and stored with its metadata.
        """
        vector_metadata_content = []
        embedded_count = 0
        for doc in documents:
            doc_vector = self.embedding_function.embed_query(doc.page_content)
            file_details = extract_file_details(doc.metadata["source"])
            id = str(uuid4())
            doc.metadata["metadata"] = {
                "id": id,
                "source": file_details["filename"],
                "rfp_status": file_details["prefix"],
                "page": doc.metadata["page"],
                "page_content": doc.page_content
            }
            embedded_count += 1
            vector_metadata_content.append([doc_vector, doc.metadata, id])
            progress_callback(processing_id, embedded_count, len(documents), "Embedding Documents")

        # Upsert the documents to the collection
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=vector_metadata[2], vector=vector_metadata[0], payload=vector_metadata[1]
                )
                for idx, vector_metadata in enumerate(vector_metadata_content)
            ],
        )
        progress_callback(processing_id, embedded_count, len(documents), "Inserting Documents in DB")

def initialiseVectorDatabase():
    qdrant_class = QdrantDB()
    qdrant_class.create_collection()



