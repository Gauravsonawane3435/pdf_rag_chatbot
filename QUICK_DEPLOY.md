# 🚀 Quick Deployment Steps for Render

## ✅ Files Ready
All deployment files have been created and pushed to GitHub!

## 📝 Quick Steps

### 1️⃣ Go to Render
Visit: https://dashboard.render.com/

### 2️⃣ Create New Web Service
- Click "New +" → "Web Service"
- Connect your GitHub repository: `Gauravsonawane3435/pdf_rag_chatbot`

### 3️⃣ Configure Service
```
Name: nexretriever-rag-chatbot
Branch: main
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

### 4️⃣ Add Environment Variables
**Required:**
```
GROQ_API_KEY = your_groq_api_key_here
```

**Optional:**
```
OPENAI_API_KEY = your_key_here
ANTHROPIC_API_KEY = your_key_here
COHERE_API_KEY = your_key_here
HUGGINGFACE_API_KEY = your_key_here
```

### 5️⃣ Deploy!
Click "Create Web Service" and wait 5-10 minutes.

## 🔑 Get Groq API Key (Free & Fast)
1. Visit: https://console.groq.com/
2. Sign up for free
3. Go to API Keys
4. Create new key
5. Copy and paste in Render environment variables

## 📱 Your Live URL
After deployment:
```
https://nexretriever-rag-chatbot.onrender.com
```

## ⚠️ Important Notes
- **Free tier**: Service sleeps after 15 min of inactivity
- **First request**: May take 30-60 seconds after sleep
- **Storage**: Uploaded files are temporary (reset on restart)
- **Upgrade**: For production, consider paid tier

## 🐛 If Something Goes Wrong
1. Check build logs in Render dashboard
2. Verify environment variables are set
3. Ensure API keys are valid
4. Review DEPLOYMENT.md for detailed troubleshooting

---
**Need help?** Check the full guide in `DEPLOYMENT.md`
