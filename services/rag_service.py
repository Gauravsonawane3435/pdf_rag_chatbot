import os
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

class RAGService:
    def __init__(self, config):
        self.config = config
        self.embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
        self.vector_store_path = config.VECTOR_STORE_PATH

    def get_vector_store(self, session_id):
        save_path = f"{self.vector_store_path}_{session_id}"
        if os.path.exists(save_path):
            return FAISS.load_local(save_path, self.embeddings, allow_dangerous_deserialization=True)
        return None

    def add_documents(self, session_id, documents):
        chunks = self.text_splitter.split_documents(documents)
        vector_store = self.get_vector_store(session_id)
        
        if vector_store:
            vector_store.add_documents(chunks)
        else:
            vector_store = FAISS.from_documents(chunks, self.embeddings)
            
        save_path = f"{self.vector_store_path}_{session_id}"
        vector_store.save_local(save_path)
        return vector_store

    def get_retriever(self, vector_store, llm, use_reranker=True):
        base_retriever = vector_store.as_retriever(search_kwargs={"k": 10})
        
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
