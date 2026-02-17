# 🚀 Deploying NexRetriever to Render

This guide will help you deploy your NexRetriever PDF RAG Chatbot to Render.

## 📋 Prerequisites

1. A [Render account](https://render.com/) (free tier available)
2. Your GitHub repository with the latest code
3. API keys for the LLM providers you want to use:
   - Groq API Key (recommended - free tier available)
   - OpenAI API Key (optional)
   - Anthropic API Key (optional)
   - Cohere API Key (optional)
   - HuggingFace API Key (optional)

## 📁 Deployment Files

The following files have been created for Render deployment:

- ✅ `render.yaml` - Render service configuration
- ✅ `Procfile` - Process file for running the app
- ✅ `runtime.txt` - Python version specification
- ✅ `requirements.txt` - Updated with gunicorn

## 🔧 Step-by-Step Deployment Guide

### Step 1: Push Changes to GitHub

```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### Step 2: Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** button
3. Select **"Web Service"**

### Step 3: Connect Your Repository

1. Click **"Connect a repository"**
2. Authorize Render to access your GitHub account (if not already done)
3. Select your repository: `Gauravsonawane3435/pdf_rag_chatbot`

### Step 4: Configure Your Web Service

Fill in the following details:

- **Name**: `nexretriever-rag-chatbot` (or your preferred name)
- **Region**: Choose closest to your location
- **Branch**: `main`
- **Root Directory**: Leave empty
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

### Step 5: Choose Your Plan

- Select **Free** tier (or paid tier for better performance)
- Free tier limitations:
  - 512 MB RAM
  - Spins down after 15 minutes of inactivity
  - Slower cold starts

### Step 6: Add Environment Variables

Click **"Advanced"** and add the following environment variables:

**Required:**
```
GROQ_API_KEY = your_groq_api_key_here
```

**Optional (add only if you want to use these providers):**
```
OPENAI_API_KEY = your_openai_api_key_here
ANTHROPIC_API_KEY = your_anthropic_api_key_here
COHERE_API_KEY = your_cohere_api_key_here
HUGGINGFACE_API_KEY = your_huggingface_api_key_here
```

**Additional Settings:**
```
PYTHON_VERSION = 3.11.0
```

### Step 7: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repository
   - Install dependencies
   - Build your application
   - Deploy it to a live URL

### Step 8: Monitor Deployment

- Watch the build logs in real-time
- Deployment typically takes 5-10 minutes
- Once complete, you'll see "Live" status

### Step 9: Access Your Application

Your app will be available at:
```
https://nexretriever-rag-chatbot.onrender.com
```
(Replace with your actual service name)

## 🔑 Getting API Keys

### Groq (Recommended - Free & Fast)
1. Visit [Groq Console](https://console.groq.com/)
2. Sign up for a free account
3. Go to API Keys section
4. Create a new API key
5. Copy and save it securely

### OpenAI (Optional)
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up and add payment method
3. Go to API Keys
4. Create new secret key

### Anthropic (Optional)
1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up for an account
3. Navigate to API Keys
4. Generate a new key

### Cohere (Optional)
1. Visit [Cohere Dashboard](https://dashboard.cohere.com/)
2. Sign up for free account
3. Go to API Keys section
4. Create a new key

## ⚙️ Important Notes

### File Storage
- Render's free tier has **ephemeral storage**
- Uploaded PDFs and vector stores will be lost when the service restarts
- For persistent storage, consider:
  - Upgrading to a paid plan with persistent disk
  - Using external storage (AWS S3, Google Cloud Storage)
  - Using a managed database for vector storage

### Database
- SQLite database will reset on each deployment
- For production, consider using:
  - Render PostgreSQL (free tier available)
  - External database service

### Performance Optimization
- Free tier spins down after 15 minutes of inactivity
- First request after spin-down will be slow (30-60 seconds)
- Consider upgrading to paid tier for:
  - Always-on service
  - More RAM (better for vector operations)
  - Faster performance

## 🐛 Troubleshooting

### Build Fails
- Check build logs for specific errors
- Ensure all dependencies are in `requirements.txt`
- Verify Python version compatibility

### Application Crashes
- Check application logs in Render dashboard
- Verify all environment variables are set correctly
- Check for memory issues (upgrade plan if needed)

### Slow Performance
- Free tier has limited resources
- Consider upgrading to paid tier
- Optimize vector store size
- Reduce number of documents processed

### API Key Issues
- Double-check API keys are correct
- Ensure no extra spaces in environment variables
- Verify API keys have proper permissions

## 📊 Monitoring

Access logs and metrics:
1. Go to Render Dashboard
2. Click on your service
3. Navigate to "Logs" tab for real-time logs
4. Check "Metrics" for performance data

## 🔄 Updating Your Deployment

To deploy updates:
```bash
git add .
git commit -m "Your update message"
git push origin main
```

Render will automatically detect changes and redeploy!

## 💡 Tips for Production

1. **Use PostgreSQL**: Replace SQLite with Render PostgreSQL
2. **Add Persistent Disk**: Store uploaded files permanently
3. **Enable Auto-Deploy**: Automatic deployments on git push
4. **Set up Custom Domain**: Use your own domain name
5. **Monitor Usage**: Keep track of API usage and costs
6. **Implement Rate Limiting**: Prevent abuse
7. **Add Authentication**: Secure your application
8. **Use CDN**: For faster static file delivery

## 📞 Support

If you encounter issues:
- Check [Render Documentation](https://render.com/docs)
- Visit [Render Community](https://community.render.com/)
- Review application logs
- Check GitHub repository issues

---

**Happy Deploying! 🚀**
