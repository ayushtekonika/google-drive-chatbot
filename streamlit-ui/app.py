import os
import streamlit as st
from streamlit.components.v1 import html
import requests
from urllib.parse import urlencode
import time
import webbrowser
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from langchain_mistralai import ChatMistralAI
from langchain_mistralai import MistralAIEmbeddings
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever, create_retrieval_chain

env_path = Path('.env')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)



QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION")
MISTRALAI_API_KEY=os.getenv("MISTRALAI_API_KEY")
API_BASE_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000")

def redirect_to_google_consent():
    auth_url = f"{API_BASE_URL}/auth"
    webbrowser.open(auth_url)

def open_page():
    url = f"{API_BASE_URL}/auth"
    open_script= """
        <script type="text/javascript">
            window.open('%s', '_blank').focus();
        </script>
    """ % (url)
    html(open_script)
# FastAPI base URL (adjust if hosted elsewhere)

# Streamlit app
st.title("Google Drive Chatbot")

# Retrieve the URL query parameters
query_params = st.query_params
processing_id = query_params.get("processing_id")

def retrieve_as_retriever(metadata_filter: Optional[Dict[str, Any]] = None) -> VectorStoreRetriever:
    """Load the existing vectorstore and retrieve top_k relevant documents based on the query."""
    try:
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        embeddings = MistralAIEmbeddings(model="mistral-embed", api_key=MISTRALAI_API_KEY)
        search_kwargs={"k": 3, "with_payload": True}
        if metadata_filter:
            filter = qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="rfp_status",
                            match=qdrant_models.MatchValue(value=metadata_filter["rfp_status"])
                        )
                    ]
                )
            search_kwargs["filter"] = filter
        
        # Initialize the vectorstore
        vectorstore = QdrantVectorStore(
            client=qdrant_client,
            collection_name=QDRANT_COLLECTION,
            embedding=embeddings,
            metadata_payload_key="metadata"
        )
        
        # Retrieve the top 3 documents using similarity search
        return vectorstore.as_retriever(search_type="similarity", search_kwargs=search_kwargs)
    except Exception as e:
        print(f"Error during document retrieval: {e}")
        raise e

def format_docs_with_id(docs: List[Document]) -> str:
    formatted = set([
        f"Source: {os.path.basename(os.path.normpath(doc.metadata['source']))} \n Page Number: {doc.metadata['page']}"
        for i, doc in enumerate(docs)
    ])
    return "\n\n" + "\n\n".join(formatted)


class ChatAssistant:    
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.llm = ChatMistralAI(
                        model="mistral-large-latest",
                        temperature=0.2,
                        max_retries=2,
                        api_key=MISTRALAI_API_KEY
                    )


    def generate_response(self, metadata_filter: Optional[Dict[str, Any]] = None) -> RunnableWithMessageHistory:
        retriever = retrieve_as_retriever(metadata_filter)

        ### Contextualize question ###
        contextualize_q_system_prompt = """Given a chat history and the latest user question \
        which might reference context in the chat history, formulate a standalone question \
        which can be understood without the chat history. Do NOT answer the question, \
        just reformulate it if needed and otherwise return it as is."""
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", contextualize_q_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        history_aware_retriever = create_history_aware_retriever(
            self.llm, retriever, contextualize_q_prompt
        )


        ### Answer question ###
        qa_system_prompt = """You are an intelligent assistant designed to help \
        users interact with documents related to the company's Requests for Proposals (RFPs) \
        and their responses. Use the retrieved context from the document database to provide \
        accurate, concise, and helpful answers to questions. \
        Ensure you prioritize factual information from the documents and clarify if the information is not available. \
        Maintain professionalism and be concise. \
        If a user asks a question outside the scope of the documents, politely inform them.

        {context}"""
        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
            ]
        )
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)

        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

        store = {}

        def get_session_history(session_id: str) -> BaseChatMessageHistory:
            if session_id not in store:
                store[session_id] = ChatMessageHistory()
            return store[session_id]

        conversational_rag_chain: RunnableWithMessageHistory = RunnableWithMessageHistory(
            rag_chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        return conversational_rag_chain


    def Response(self, conversational_rag_chain: RunnableWithMessageHistory, query, session_id):

        response = conversational_rag_chain.invoke(
                {"input": query},
                config={
                    "configurable": {"session_id": session_id}
                },  # constructs a key "abc123" in `store`.
            )
        
        response_with_references = f"{response['answer']}\n````` {format_docs_with_id(response['context'])}"
        response = response["answer"]

        return response_with_references


def main():
    
    if not processing_id:
        if 'assistant' not in st.session_state:
            st.session_state.assistant = ChatAssistant()
            st.session_state.conversational_rag_chain = None
        session_id = "123455"  # Static session ID for example purposes

        st.write("Click the button below to sync files with Google Drive.")
        st.button("Sync with Google Drive", on_click=open_page)

        rfp_status = st.radio("RFPs to chat with", options=["all", "new", "submitted"], index=0, horizontal=True)
        # query = st.text_input("Your question:", placeholder="Type your question here...")
        # if st.button("Submit") and query:
        #     with st.spinner("Generating response..."):
        #         # Generate response using the selected RFP status
        #         filter_metadata = None
        #         if rfp_status != "all":
        #             filter_metadata = {"rfp_status": rfp_status}
        #         if st.session_state.conversational_rag_chain is None:
        #             st.session_state.conversational_rag_chain = st.session_state.assistant.generate_response(
        #                 metadata_filter=filter_metadata
        #             )
        #         response = st.session_state.assistant.Response(
        #             st.session_state.conversational_rag_chain, query, session_id
        #         )
        #         st.write(response)
        
        # Accept user input
        if prompt := st.chat_input("What is up?"):
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)
                filter_metadata = None
                if rfp_status != "all":
                    filter_metadata = {"rfp_status": rfp_status}
                if st.session_state.conversational_rag_chain is None:
                    st.session_state.conversational_rag_chain = st.session_state.assistant.generate_response(
                        metadata_filter=filter_metadata
                    )
                response = st.session_state.assistant.Response(
                    st.session_state.conversational_rag_chain, prompt, session_id
                )
        
            # Display assistant response in chat message container
            with st.chat_message("assistant"):
                response = st.write(response)

    else:
        # Processing ID found, poll the status
        st.write(f"Processing ID: {processing_id}")
        status_placeholder = st.empty()  # Placeholder for status updates
        progress_text = "Downloading documents..."
        my_bar = st.progress(0, text=progress_text)
        while True:
            # API call to check status
            status_url = f"{API_BASE_URL}/download_status/{processing_id}"
            try:
                response = requests.get(status_url)
                if response.status_code == 200:
                    json_resp = response.json()
                    print(json_resp)
                    status = json_resp.get("status", "unknown")
                    processed = json_resp.get("processed", 0)
                    total = json_resp.get("total", 1)
                    current_process = json_resp.get("current_process")
                    progress = (processed/total)
                    status_placeholder.write(f"Document Ingestion Status: {status}")
                    progress_text = f"{current_process}..."
                    my_bar.progress(progress, text=progress_text)

                    # Exit the loop if the status is completed or failed
                    if status in ["completed", "failed"]:
                        break
                else:
                    status_placeholder.error(f"Failed to fetch status: {response.json().get('detail', 'Unknown error')}")
                    break
            except Exception as e:
                print(e)
                status_placeholder.error(f"Error fetching download status: {str(e)}")
                break

            time.sleep(1)  # Poll every 1 second

        st.write("Loading Chatbot...")
        time.sleep(1)
        st.query_params.clear()
        st.rerun()

if __name__=="__main__":
    main()