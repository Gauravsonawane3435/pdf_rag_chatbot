# PDF RAG Chatbot 📚🤖

A powerful, interactive PDF-based retrieval-augmented generation (RAG) chatbot and web application. This project allows users to upload PDF documents and engage in a contextual conversation with an AI assistant that retrieves information directly from the uploaded content.

## 🌟 Features

- **PDF Document Processing**: Upload and process PDF files to create a searchable knowledge base.
- **RAG Architecture**: Uses Retrieval-Augmented Generation to provide accurate answers based on document context.
- **Groq Acceleration**: Powered by Llama 3.3-70B via Groq for lightning-fast inference.
- **Vector Search**: Implements FAISS for efficient similarity search and document retrieval.
- **Modern UI**: Clean and intuitive web interface for seamless interaction.
- **Concise Answers**: AI is tuned to provide brief, relevant answers based on the context provided.

## 🛠️ Tech Stack

- **Backend**: [Flask](https://flask.palletsprojects.com/) (Python)
- **Orchestration**: [LangChain](https://www.langchain.com/)
- **LLM**: [Groq Cloud](https://groq.com/) (Llama-3.3-70b-versatile)
- **Embeddings**: HuggingFace (`all-MiniLM-L6-v2`)
- **Vector Database**: [FAISS](https://github.com/facebookresearch/faiss)
- **Frontend**: HTML/CSS/JS (Vanilla)

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- A Groq API Key (Get one at [console.groq.com](https://console.groq.com/))

## 🚀 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Gauravsonawane3435/pdf_rag_chatbot.git
   cd pdf_rag_chatbot
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory and add your Groq API key:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   ```

## 💻 Usage

1. **Start the development server**:
   ```bash
   python app.py
   ```

2. **Access the application**:
   Open your browser and navigate to `http://127.0.0.1:5000`

3. **Chatting with your PDF**:
   - Click the "Upload" button to select a PDF file.
   - Wait for the "PDF processed successfully!" message.
   - Start asking questions in the chat box!

## 📂 Project Structure

```text
pdf_rag_chatbot/
├── app.py              # Main Flask application entry point
├── rag.py              # RAG logic (Loading, Splitting, Embedding, Retrieval)
├── llm.py              # LLM configuration and initialization
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (API Keys)
├── data/               # Directory for uploaded PDF storage
├── static/             # Static assets (CSS, JS, Images)
└── templates/          # HTML templates
```

## 🛡️ License

Distributed under the MIT License. See `LICENSE` for more information.

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---
Built with ❤️ by [Gaurav Sonawane](https://github.com/Gauravsonawane3435)
