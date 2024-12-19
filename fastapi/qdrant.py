from qdrant_client import QdrantClient
from langchain_core.documents.base import Document
from langchain_mistralai import MistralAIEmbeddings
from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct
)


class QdrantDB:
    def __init__(self, url: str, api_key: str, collection_name: str, embedding_function: MistralAIEmbeddings):
        self.client = QdrantClient(
            url=url,
            api_key=api_key,
            https=True,
            timeout=60,
        )
        
        self.collection_name = collection_name
        self.embedding_function = embedding_function
        self.vector_size = 1024  # Adjust vector size as needed
        # self.vector_size = 1536

        # Create collection if it doesn't exist
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size, distance=Distance.COSINE
                ),
            )

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

    def add_documents(self, documents: list[Document]):
        """
        Add a list of documents with unique IDs to the collection.
        Each document should be embedded and stored with its metadata.
        """
        vector_metadata_content = []
        for doc in documents:
            doc_vector = self.embedding_function.embed_query(doc.page_content)
            doc.metadata["text"] = doc.page_content
            # doc.metadata["result"] = (
            #     doc.metadata["source"].split("\\")[-1].split(".")[0]
            # )
            vector_metadata_content.append([doc_vector, doc.metadata])

        # Upsert the documents to the collection
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=idx, vector=vector_metadata[0], payload=vector_metadata[1]
                )
                for idx, vector_metadata in enumerate(vector_metadata_content)
            ],
        )



