from rank_bm25 import BM25Okapi
from typing import List, Any
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import PrivateAttr, Field
import numpy as np


class HybridRetriever(BaseRetriever):
    """
    Hybrid retriever combining BM25 (keyword-based) and semantic search.
    Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
    """
    vector_retriever: Any = Field(description="FAISS semantic retriever")
    documents: List[Document] = Field(description="List of all documents for BM25 indexing")
    k: int = Field(default=10, description="Number of documents to retrieve")
    alpha: float = Field(default=0.5, description="Weight for combining scores (0=only BM25, 1=only semantic)")
    _bm25: Any = PrivateAttr()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Build BM25 index safely
        try:
            tokenized_docs = []
            for doc in self.documents:
                if hasattr(doc, 'page_content') and doc.page_content:
                    tokenized_docs.append(doc.page_content.lower().split())
                else:
                    tokenized_docs.append([])
            self._bm25 = BM25Okapi(tokenized_docs)
        except Exception as e:
            print(f"BM25 initialization failed: {e}")
            self._bm25 = None
        
    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """Retrieve documents using hybrid search."""
        
        # 1. Semantic Search (FAISS) - Get this first
        semantic_docs = self.vector_retriever.invoke(query)[:self.k * 2]
        
        if not self._bm25:
            # Fallback if BM25 failed
            return semantic_docs[:self.k]
            
        # 2. BM25 Keyword Search
        tokenized_query = query.lower().split()
        if not tokenized_query:
            return semantic_docs[:self.k]
            
        bm25_scores = self._bm25.get_scores(tokenized_query)
        
        # Get top-k BM25 results
        bm25_top_indices = np.argsort(bm25_scores)[::-1][:self.k * 2]  # Get more for fusion
        bm25_docs = [(self.documents[i], bm25_scores[i]) for i in bm25_top_indices]
        

        
        # 3. Reciprocal Rank Fusion (RRF)
        doc_scores = {}
        
        # Add BM25 scores
        for rank, (doc, score) in enumerate(bm25_docs):
            doc_id = id(doc)
            rrf_score = 1 / (60 + rank + 1)  # RRF formula
            doc_scores[doc_id] = {
                'doc': doc,
                'score': (1 - self.alpha) * rrf_score
            }
        
        # Add semantic scores
        for rank, doc in enumerate(semantic_docs):
            doc_id = id(doc)
            rrf_score = 1 / (60 + rank + 1)
            if doc_id in doc_scores:
                doc_scores[doc_id]['score'] += self.alpha * rrf_score
            else:
                doc_scores[doc_id] = {
                    'doc': doc,
                    'score': self.alpha * rrf_score
                }
        
        # Sort by combined score and return top-k
        sorted_docs = sorted(doc_scores.values(), key=lambda x: x['score'], reverse=True)
        return [item['doc'] for item in sorted_docs[:self.k]]
    
    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """Async version - not implemented, falls back to sync."""
        return self._get_relevant_documents(query, run_manager=run_manager)
