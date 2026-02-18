import os
import base64
from io import BytesIO
from typing import List, Dict, Any
import pdfplumber
try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    print("pdf2image not available - vision processing disabled")
from PIL import Image
import pytesseract
from langchain_core.documents import Document as LC_Document
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import json


class MultiModalProcessor:
    """
    Advanced PDF processor that extracts:
    - Text content
    - Tables (structured data)
    - Images (with vision model analysis)
    """
    
    def __init__(self, groq_api_key: str = None):
        """Initialize with optional Groq API for vision analysis."""
        self.groq_api_key = groq_api_key
        self.poppler_path = os.getenv('POPPLER_PATH')
        if groq_api_key:
            # Groq now supports Llama 3.2 Vision models (free!)
            self.vision_llm = ChatGroq(
                api_key=groq_api_key,
                model_name="llama-3.2-90b-vision-preview",
                temperature=0.3
            )
        else:
            self.vision_llm = None
    
    def process_pdf_multimodal(self, file_path: str) -> List[LC_Document]:
        """
        Process PDF with multi-modal extraction.
        Returns documents with text, tables, and image descriptions.
        """
        documents = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # 1. Extract text
                    text = page.extract_text() or ""
                    
                    # 2. Extract tables
                    tables = page.extract_tables()
                    table_text = ""
                    if tables:
                        table_text = self._format_tables(tables, page_num)
                    
                    # 3. Combine text and tables
                    combined_content = text
                    if table_text:
                        combined_content += f"\n\n[TABLES ON PAGE {page_num}]\n{table_text}"
                    
                    if combined_content.strip():
                        doc = LC_Document(
                            page_content=combined_content,
                            metadata={
                                "source": file_path,
                                "page": page_num,
                                "type": "text_and_tables"
                            }
                        )
                        documents.append(doc)
            
            # 4. Extract and analyze images (if vision model available)
            if self.vision_llm:
                image_docs = self._extract_images_with_vision(file_path)
                documents.extend(image_docs)
            
        except Exception as e:
            print(f"Error in multi-modal processing: {e}")
            # Fallback to basic text extraction
            from langchain_community.document_loaders import PyPDFLoader
            loader = PyPDFLoader(file_path)
            documents = loader.load()
        
        return documents
    
    def _format_tables(self, tables: List[List[List[str]]], page_num: int) -> str:
        """Format extracted tables as markdown-style text."""
        formatted = []
        for idx, table in enumerate(tables, start=1):
            if not table:
                continue
            
            formatted.append(f"\n--- Table {idx} on Page {page_num} ---")
            
            # Create markdown table
            for row_idx, row in enumerate(table):
                if row:
                    # Clean cells
                    cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                    formatted.append(" | ".join(cleaned_row))
                    
                    # Add separator after header
                    if row_idx == 0:
                        formatted.append(" | ".join(["---"] * len(cleaned_row)))
        
        return "\n".join(formatted)
    
    def _extract_images_with_vision(self, file_path: str) -> List[LC_Document]:
        """
        Extract images from PDF and analyze them with vision model.
        Uses Groq's free Llama 3.2 Vision model.
        """
        image_docs = []
        
        if not PDF2IMAGE_AVAILABLE:
            print("Skipping vision processing - pdf2image not available")
            return image_docs
        
        try:
            # Convert PDF pages to images
            if self.poppler_path:
                images = convert_from_path(file_path, dpi=150, poppler_path=self.poppler_path)
            else:
                images = convert_from_path(file_path, dpi=150)
            
            for page_num, img in enumerate(images, start=1):
                # Check if page has significant visual content (not just text)
                # For simplicity, we'll analyze every few pages to save API calls
                if page_num % 3 != 0:  # Analyze every 3rd page
                    continue
                
                # Convert image to base64
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                # Analyze with vision model
                try:
                    description = self._analyze_image_with_llm(img_base64, page_num)
                    
                    if description and len(description) > 50:  # Only if meaningful
                        doc = LC_Document(
                            page_content=f"[VISUAL CONTENT FROM PAGE {page_num}]\n{description}",
                            metadata={
                                "source": file_path,
                                "page": page_num,
                                "type": "image_analysis"
                            }
                        )
                        image_docs.append(doc)
                except Exception as e:
                    print(f"Error analyzing image on page {page_num}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error extracting images: {e}")
        
        return image_docs
    
    def _analyze_image_with_llm(self, img_base64: str, page_num: int) -> str:
        """Use Groq vision model to describe image content."""
        if not self.vision_llm:
            return ""
        
        try:
            message = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "Analyze this document page image. Describe any:\n"
                            "- Charts, graphs, or diagrams (explain what they show)\n"
                            "- Important visual elements or figures\n"
                            "- Key information not captured in text\n"
                            "Be concise but informative. If it's just plain text, say 'Text only page'."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    }
                ]
            )
            
            response = self.vision_llm.invoke([message])
            return response.content
        
        except Exception as e:
            print(f"Vision analysis error: {e}")
            return ""
    
    def extract_document_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata from PDF."""
        try:
            with pdfplumber.open(file_path) as pdf:
                return {
                    "num_pages": len(pdf.pages),
                    "metadata": pdf.metadata,
                    "has_tables": any(page.extract_tables() for page in pdf.pages)
                }
        except:
            return {}
