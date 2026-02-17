# 🔧 Render Deployment Troubleshooting Guide

## ✅ Latest Fixes Applied

### Issues Fixed:
1. ✅ **Python 3.14 Compatibility** - Downgraded to Python 3.11.9
2. ✅ **Pydantic V1 Warning** - Fixed by using compatible Python version
3. ✅ **Port Binding** - Added startup script with proper configuration
4. ✅ **Directory Creation** - Ensured uploads and instance folders exist
5. ✅ **Logging** - Added access and error logging for debugging

---

## 🚀 Manual Deployment Steps (Recommended)

Since you're having issues with auto-deploy, let's do it manually:

### Step 1: Delete Existing Service (If Any)
1. Go to Render Dashboard: https://dashboard.render.com/
2. Find your service
3. Click Settings → Delete Service
4. Confirm deletion

### Step 2: Create Fresh Web Service
1. Click **"New +"** → **"Web Service"**
2. Select **"Build and deploy from a Git repository"**
3. Click **"Connect a repository"**
4. Choose: `Gauravsonawane3435/pdf_rag_chatbot`
5. Click **"Connect"**

### Step 3: Configure Service Settings

Fill in EXACTLY as shown:

```
Name: nexretriever-rag-chatbot
Region: Oregon (US West) or closest to you
Branch: main
Root Directory: (leave empty)
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: bash start.sh
```

### Step 4: Select Plan
- Choose **Free** (or paid if you prefer)

### Step 5: Advanced Settings

Click **"Advanced"** and add these environment variables:

**REQUIRED:**
```
GROQ_API_KEY
Value: your_actual_groq_api_key_here
```

**OPTIONAL (only if you have these keys):**
```
OPENAI_API_KEY
Value: your_openai_key

ANTHROPIC_API_KEY  
Value: your_anthropic_key

COHERE_API_KEY
Value: your_cohere_key
```

### Step 6: Deploy
1. Click **"Create Web Service"**
2. Wait for build to complete (5-10 minutes)
3. Monitor the logs

---

## 📊 What to Look For in Logs

### ✅ Success Indicators:
```
==> Downloading Python 3.11.9
==> Installing dependencies
==> Successfully installed gunicorn
==> Starting service with 'bash start.sh'
[INFO] Listening at: http://0.0.0.0:10000
[INFO] Using worker: gthread
[INFO] Booting worker with pid: 123
==> Your service is live 🎉
```

### ❌ Error Indicators:
```
ModuleNotFoundError: No module named 'X'
→ Missing dependency in requirements.txt

ImportError: cannot import name 'X'
→ Version compatibility issue

No open ports detected
→ App not binding to PORT correctly

API key not found
→ Environment variable not set
```

---

## 🔍 Alternative: Use Render Blueprint

If manual setup still fails, try using the render.yaml directly:

### Step 1: Create from Blueprint
1. Go to Render Dashboard
2. Click **"New +"** → **"Blueprint"**
3. Connect your repository
4. Render will auto-detect `render.yaml`
5. Click **"Apply"**

### Step 2: Add Environment Variables
After blueprint is applied:
1. Go to your service
2. Click **"Environment"**
3. Add `GROQ_API_KEY` and other keys
4. Click **"Save Changes"**
5. Service will auto-redeploy

---

## 🐛 Common Issues & Solutions

### Issue 1: "No open ports detected"
**Cause:** App not binding to PORT
**Solution:**
- Ensure `start.sh` has execute permissions
- Check that `$PORT` environment variable is being used
- Verify gunicorn is starting correctly

**Manual Fix:**
In Render dashboard, update Start Command to:
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 120 --log-level info --access-logfile - --error-logfile -
```

### Issue 2: "Python 3.14 Pydantic warning"
**Cause:** Wrong Python version
**Solution:**
- Ensure `runtime.txt` contains `python-3.11.9`
- Rebuild service from scratch
- Check build logs for Python version

### Issue 3: "ModuleNotFoundError"
**Cause:** Missing dependencies
**Solution:**
- Check `requirements.txt` is complete
- Add missing packages
- Push changes and redeploy

### Issue 4: "Build succeeds but app crashes"
**Cause:** Runtime error
**Solution:**
- Check application logs (not build logs)
- Look for Python errors
- Verify environment variables are set
- Check database initialization

### Issue 5: "Slow or timing out"
**Cause:** Free tier limitations
**Solution:**
- Upgrade to paid tier ($7/month)
- Reduce worker count to 1
- Optimize app startup time

---

## 🔑 Getting Groq API Key

If you don't have a Groq API key yet:

1. Visit: https://console.groq.com/
2. Sign up (free account)
3. Click **"API Keys"** in sidebar
4. Click **"Create API Key"**
5. Give it a name: "NexRetriever"
6. Click **"Submit"**
7. **COPY THE KEY** (you won't see it again!)
8. Paste it in Render environment variables

---

## 📝 Verification Checklist

Before deploying, verify:

- [ ] `runtime.txt` contains `python-3.11.9`
- [ ] `Procfile` contains `web: bash start.sh`
- [ ] `start.sh` exists in repository
- [ ] `requirements.txt` includes `gunicorn`
- [ ] `app.py` uses `PORT` environment variable
- [ ] `GROQ_API_KEY` is set in Render
- [ ] Latest code is pushed to GitHub

---

## 🆘 If Still Not Working

### Option 1: Check Logs
1. Go to your service in Render
2. Click **"Logs"** tab
3. Look for specific error messages
4. Share the error with me for help

### Option 2: Test Locally
Test if the app works with gunicorn locally:

```bash
# Install gunicorn
pip install gunicorn

# Test locally
PORT=5000 gunicorn app:app --bind 0.0.0.0:5000 --workers 1 --threads 2

# Open browser
http://localhost:5000
```

If it works locally but not on Render, it's likely an environment variable issue.

### Option 3: Simplify Start Command
Try the simplest possible start command:

```bash
gunicorn app:app
```

Render should auto-detect the PORT. If this works, gradually add back options.

---

## 💡 Pro Tips

1. **Enable Auto-Deploy After Success:**
   - Settings → Build & Deploy
   - Enable "Auto-Deploy: Yes"

2. **Add Health Check Endpoint:**
   - Helps Render know when app is ready
   - Add to `app.py`:
   ```python
   @app.route('/health')
   def health():
       return {'status': 'healthy'}, 200
   ```

3. **Monitor Startup Time:**
   - Free tier has 90-second startup limit
   - If exceeded, upgrade to paid tier

4. **Use Persistent Disk (Paid Feature):**
   - Keeps uploaded files between restarts
   - Settings → Disks → Add Disk

---

## 📞 Get Help

If you're still stuck:
1. Share the **build logs** (from Logs tab)
2. Share the **application logs** (after build completes)
3. Confirm environment variables are set
4. Verify GitHub repo has latest code

---

**The latest fixes are now on GitHub. Try the manual deployment steps above!** 🚀
