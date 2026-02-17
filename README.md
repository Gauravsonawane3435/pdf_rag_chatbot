# 🚀 NexRetriever - Advanced PDF RAG Chatbot

A **state-of-the-art** PDF-based Retrieval-Augmented Generation (RAG) chatbot with cutting-edge features including **Hybrid Search**, **Multi-Modal Processing**, and **Interactive PDF Viewing**.

## ✨ Advanced Features

### 🎯 **1. Hybrid Search (BM25 + Semantic)**
Combines the best of both worlds:
- **BM25 Keyword Search**: Excellent for exact matches and technical terms
- **Semantic Search (FAISS)**: Understands context and meaning
- **Reciprocal Rank Fusion**: Intelligently merges results for superior accuracy
- **60/40 Split**: 60% semantic, 40% keyword for optimal retrieval

### 🖼️ **2. Multi-Modal RAG**
Goes beyond simple text extraction:
- **Table Extraction**: Automatically detects and formats tables from PDFs
- **Image Analysis**: Uses Groq's free **Llama 3.2 Vision** model to analyze charts, diagrams, and visual content
- **Structured Data**: Converts tables to markdown format for better understanding
- **Visual Intelligence**: Describes graphs, charts, and important visual elements

### 📄 **3. Interactive PDF Viewer**
View source documents with ease:
- **Built-in PDF Viewer**: Click any source citation to view the PDF
- **Page Navigation**: Jump directly to the cited page
- **Clickable Sources**: All source tags are interactive
- **Seamless Integration**: No need to download or open external apps

## 🛠️ Tech Stack

- **Backend**: Flask (Python)
- **LLM Orchestration**: LangChain
- **LLM Providers**: 
  - Groq (Llama 3.3 70B + Llama 3.2 Vision) - **FREE**
  - OpenAI (GPT-4 Turbo)
  - Anthropic (Claude 3.5 Sonnet)
  - Cohere (Command R+)
- **Embeddings**: HuggingFace (`all-MiniLM-L6-v2`)
- **Vector Database**: FAISS
- **Keyword Search**: BM25 (rank-bm25)
- **PDF Processing**: 
  - pdfplumber (tables)
  - pdf2image (images)
  - PyPDF (text)
- **Reranking**: Cohere Rerank v3
- **Caching**: Redis
- **Frontend**: HTML/CSS/JS with Tailwind CSS
- **PDF Viewing**: PDF.js

## 📋 Prerequisites

- Python 3.8+
- **Groq API Key** (Free at [console.groq.com](https://console.groq.com/))
- Optional: Cohere API Key for reranking (Free tier available)

## 🚀 Installation & Setup

### 1. Clone the repository
```bash
git clone https://github.com/Gauravsonawane3435/pdf_rag_chatbot.git
cd pdf_rag_chatbot
```

### 2. Create virtual environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file:
```env
GROQ_API_KEY=your_groq_api_key_here
COHERE_API_KEY=your_cohere_key_here  # Optional for reranking
SECRET_KEY=your-secret-key
REDIS_HOST=localhost
REDIS_PORT=6379
```

### 5. Run the application
```bash
python app.py
```

### 6. Access the app
Open your browser and navigate to: `http://127.0.0.1:5000`

## 💡 Usage Guide

### Upload Documents
1. Click the upload area or drag & drop files
2. Supported formats: PDF, DOCX, CSV, XLSX, Images
3. Wait for processing (multi-modal extraction in progress!)

### Ask Questions
1. Type your question in the chat input
2. Get AI-powered answers with source citations
3. Click on any source tag to view the PDF at that exact page

### View PDFs
- Click on any PDF in the documents list
- Click on source citations in chat responses
- Navigate through pages with arrow buttons

### Advanced Features
- **Streaming**: Toggle real-time response streaming
- **Model Selection**: Choose from Groq, OpenAI, Anthropic, or Cohere
- **Analytics**: View query performance and statistics
- **Dark Mode**: Toggle theme for comfortable viewing
- **Chat History**: Access previous conversations from sidebar

## 🎨 What Makes This Advanced?

### Traditional RAG vs. NexRetriever

| Feature | Traditional RAG | NexRetriever |
|---------|----------------|--------------|
| Search Method | Semantic only | **Hybrid (BM25 + Semantic)** |
| PDF Processing | Text only | **Text + Tables + Images** |
| Visual Content | Ignored | **Analyzed with Vision AI** |
| Source Viewing | External apps | **Built-in PDF viewer** |
| Table Handling | Poor | **Structured extraction** |
| Accuracy | Good | **Excellent** |

## 🔧 Configuration

### Hybrid Search Settings
Edit `services/rag_service.py`:
```python
alpha=0.6  # 0=only BM25, 1=only semantic
```

### Multi-Modal Processing
- **Vision Analysis**: Analyzes every 3rd page (configurable in `multimodal_processor.py`)
- **Table Detection**: Automatic
- **Image Quality**: 150 DPI (adjustable)

### PDF Viewer
- **Scale**: 1.5x (modify in `script.js`)
- **Canvas rendering**: High quality

## 📊 Performance Tips

1. **Hybrid Search**: Best for technical documents with specific terminology
2. **Multi-Modal**: Ideal for documents with charts, graphs, and tables
3. **Reranking**: Enable Cohere reranking for highest accuracy
4. **Caching**: Responses are cached for faster repeated queries

## 🐛 Troubleshooting

### PDF.js not loading
- Check browser console for errors
- Ensure CDN is accessible
- Clear browser cache

### Vision model errors
- Verify Groq API key is valid
- Check if Llama 3.2 Vision is available in your region
- Falls back to text-only if vision fails

### BM25 search issues
- Ensure documents are being cached properly
- Check `vector_db_*_docs.pkl` files exist

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **Groq** for lightning-fast inference and free Vision API
- **LangChain** for RAG orchestration
- **Cohere** for reranking capabilities
- **PDF.js** for client-side PDF rendering

## 📧 Contact

**Gaurav Sonawane**
- GitHub: [@Gauravsonawane3435](https://github.com/Gauravsonawane3435)
- Project: [pdf_rag_chatbot](https://github.com/Gauravsonawane3435/pdf_rag_chatbot)

---

⭐ **Star this repo if you find it useful!**

Built with ❤️ using cutting-edge AI technology
