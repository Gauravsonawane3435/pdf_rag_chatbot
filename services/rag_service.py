import os
import pickle
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_cohere import CohereRerank as LangChainCohereRerank
from services.hybrid_retriever import HybridRetriever

class RAGService:
    def __init__(self, config):
        self.config = config
        self._embeddings = None
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
        self.vector_store_path = config.VECTOR_STORE_PATH
        # Store documents for BM25 hybrid search
        self.documents_cache = {}

    @property
    def embeddings(self):
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name=self.config.EMBEDDING_MODEL)
        return self._embeddings

    def get_vector_store(self, session_id):
        save_path = f"{self.vector_store_path}_{session_id}"
        if os.path.exists(save_path):
            return FAISS.load_local(save_path, self.embeddings, allow_dangerous_deserialization=True)
        return None

    def add_documents(self, session_id, documents):
        chunks = self.text_splitter.split_documents(documents)
        if not chunks:
            return None
            
        vector_store = self.get_vector_store(session_id)
        if vector_store:
            vector_store.add_documents(chunks)
        else:
            vector_store = FAISS.from_documents(chunks, self.embeddings)
            
        save_path = f"{self.vector_store_path}_{session_id}"
        vector_store.save_local(save_path)
        
        # Cache all documents for BM25 hybrid search
        if session_id not in self.documents_cache:
            self.documents_cache[session_id] = []
        self.documents_cache[session_id].extend(chunks)
        
        # Persist document cache
        self._save_documents_cache(session_id)
        
        return vector_store
    
    def _save_documents_cache(self, session_id):
        """Save documents cache for BM25."""
        cache_path = f"{self.vector_store_path}_{session_id}_docs.pkl"
        with open(cache_path, 'wb') as f:
            pickle.dump(self.documents_cache.get(session_id, []), f)
    
    def _load_documents_cache(self, session_id):
        """Load documents cache for BM25."""
        cache_path = f"{self.vector_store_path}_{session_id}_docs.pkl"
        if os.path.exists(cache_path):
            with open(cache_path, 'rb') as f:
                self.documents_cache[session_id] = pickle.load(f)
                return self.documents_cache[session_id]
        return []
    
    def remove_session_cache(self, session_id):
        """Remove session from in-memory cache."""
        if session_id in self.documents_cache:
            del self.documents_cache[session_id]

    def get_retriever(self, vector_store, llm, session_id, use_hybrid=True, use_reranker=True):
        base_retriever = vector_store.as_retriever(search_kwargs={"k": 10})
        
        # Use Hybrid Search (BM25 + Semantic)
        if use_hybrid:
            # Load cached documents for BM25
            documents = self.documents_cache.get(session_id) or self._load_documents_cache(session_id)
            if documents:
                base_retriever = HybridRetriever(
                    vector_retriever=base_retriever,
                    documents=documents,
                    k=10,
                    alpha=0.6  # 60% semantic, 40% keyword
                )
        
        if use_reranker and os.getenv("COHERE_API_KEY"):
            compressor = LangChainCohereRerank(
                cohere_api_key=os.getenv("COHERE_API_KEY"),
                model="rerank-english-v3.0",
                top_n=5
            )
            retriever = ContextualCompressionRetriever(
                base_compressor=compressor, base_retriever=base_retriever
            )
            return retriever
        
        return base_retriever

    def get_rag_chain(self, llm, retriever):
        # Contextualize question (Query Rewriting)
        contextualize_q_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        
        history_aware_retriever = create_history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )

        # Answer question
        system_prompt = (
            "You are an expert AI assistant specialized in analyzing documents and providing clear, structured insights. "
            "Use the provided context to answer the user's question accurately. "
            "\n\n"
            "STRICT FORMATTING RULES:\n"
            "1. Use '## Phase X - Title' or '### Section Title' for headings to organize content.\n"
            "2. Use bullet points (•) for all key details and lists. Ensure they are clean and perfectly aligned.\n"
            "3. Use horizontal rules (---) between major sections for visual separation.\n"
            "4. Use bold text for key terms to make them stand out.\n"
            "5. If explaining a roadmap or process, structure it chronologically or logically.\n"
            "6. Aim for an 'exam-ready' or 'professional summary' tone - clear, concise, and comprehensive.\n"
            "\n"
            "If the context doesn't contain the answer, state that clearly but provide any relevant information you can find. "
            "\n\nContext:\n{context}"
        )
        
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
        
        return rag_chain

    def format_chat_history(self, messages):
        history = []
        for msg in messages:
            if msg.sender == 'user':
                history.append(HumanMessage(content=msg.content))
            else:
                history.append(AIMessage(content=msg.content))
        return history
