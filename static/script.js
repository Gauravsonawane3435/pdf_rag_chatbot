// Safe LocalStorage Access
const storage = {
    get: (key) => {
        try {
            const val = localStorage.getItem(key);
            return (val === 'null' || val === 'undefined') ? null : val;
        } catch (e) { return null; }
    },
    set: (key, val) => {
        try { localStorage.setItem(key, val); } catch (e) { }
    },
    remove: (key) => {
        try { localStorage.removeItem(key); } catch (e) { }
    }
};

let sessionId = storage.get('sessionId');
let currentProvider = 'groq';
let currentModel = 'llama-3.3-70b-versatile';

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const dropZone = document.getElementById('drop-zone');
const docList = document.getElementById('document-list');
const uploadStatus = document.getElementById('upload-status');
const modelSelect = document.getElementById('model-select');
const themeToggle = document.getElementById('theme-toggle');
const analyticsBtn = document.getElementById('analytics-btn');
const analyticsModal = document.getElementById('analytics-modal');
const closeAnalytics = document.getElementById('close-analytics');
const newChatBtn = document.getElementById('new-chat-btn');
const streamToggle = document.getElementById('stream-toggle');
const sessionList = document.getElementById('session-list');
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const closeSidebarBtn = document.getElementById('close-sidebar-btn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');
const visionToggle = document.getElementById('vision-toggle');


// Feedback Utility
function notify(msg, type = 'info') {
    console.log(`[${type}] ${msg}`);
    if (type === 'error') {
        // Just a simple alert for now for maximum visibility in debugging
        alert(`Error: ${msg}`);
    }
}

// Mobile Sidebar Functions
function openSidebar() {
    if (sidebar && sidebarOverlay) {
        sidebar.classList.remove('-translate-x-full');
        sidebarOverlay.classList.remove('hidden');
        setTimeout(() => sidebarOverlay.classList.remove('opacity-0'), 10);
    }
}

function closeSidebar() {
    if (sidebar && sidebarOverlay) {
        sidebar.classList.add('-translate-x-full');
        sidebarOverlay.classList.add('opacity-0');
        setTimeout(() => sidebarOverlay.classList.add('hidden'), 300);
    }
}

function clearChatUI(message = "Upload your documents and let's start a new conversation.") {
    if (!chatMessages) return;
    chatMessages.innerHTML = `
        <div class="max-w-3xl mx-auto text-center py-12">
            <div class="w-16 h-16 md:w-20 md:h-20 bg-primary-100 dark:bg-primary-900/30 rounded-3xl flex items-center justify-center text-primary-600 dark:text-primary-400 mx-auto mb-6">
                <i class="fas fa-robot text-3xl md:text-4xl"></i>
            </div>
            <h2 class="text-2xl md:text-3xl font-bold text-gray-800 dark:text-white mb-3">Hello! I'm NexRetriever</h2>
            <p class="text-sm md:text-base text-gray-500 dark:text-slate-400 max-w-md mx-auto">${message}</p>
        </div>
    `;
    if (docList) docList.innerHTML = '';
}

// Initialize
async function init() {
    notify("Initializing application...");
    const savedId = storage.get('sessionId');
    let data = null;

    try {
        if (savedId) {
            const response = await fetch(`/api/session?session_id=${savedId}`);
            if (response.ok) {
                data = await response.json();
            } else {
                const err = await response.json().catch(() => ({}));
                notify(`Session error: ${err.error || response.statusText}`, 'error');
                storage.remove('sessionId');
                const newRes = await fetch('/api/session');
                data = await newRes.json();
            }
        } else {
            const newRes = await fetch('/api/session');
            data = await newRes.json();
        }

        if (data && data.session_id) {
            sessionId = data.session_id;
            storage.set('sessionId', sessionId);

            if (data.history && data.history.length > 0) {
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                    data.history.forEach(msg => appendMessage(msg.sender, msg.content, msg.sources));
                }
            } else {
                clearChatUI();
            }

            loadDocuments();
            loadSessionHistory();
        }
    } catch (e) {
        console.error("Initialization error:", e);
        notify("Server connection failed. Please refresh.", "error");
    }

    // Theme setup
    const savedTheme = storage.get('theme');
    if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    }
}

// Event Listeners setup
function setupEventListeners() {
    if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', openSidebar);
    if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

    if (chatInput && sendBtn) {
        chatInput.addEventListener('input', () => {
            const hasText = chatInput.value.trim() !== '';
            sendBtn.disabled = !hasText;

            // Visual feedback for send button like ChatGPT
            if (hasText) {
                sendBtn.classList.add('bg-primary-600', 'text-white');
                sendBtn.classList.remove('bg-gray-200', 'dark:bg-slate-800', 'text-gray-400', 'dark:text-slate-600');
            } else {
                sendBtn.classList.remove('bg-primary-600', 'text-white');
                sendBtn.classList.add('bg-gray-200', 'dark:bg-slate-800', 'text-gray-400', 'dark:text-slate-600');
            }

            chatInput.style.height = 'auto';
            chatInput.style.height = chatInput.scrollHeight + 'px';
        });
        sendBtn.addEventListener('click', sendMessage);
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    const mobileNewChat = document.getElementById('mobile-new-chat-btn');
    if (mobileNewChat) mobileNewChat.onclick = () => window.location.reload();

    const mobileUpload = document.getElementById('mobile-upload-btn');
    if (mobileUpload && fileInput) mobileUpload.onclick = () => fileInput.click();

    const scrollBottomBtn = document.getElementById('scroll-bottom-btn');
    if (scrollBottomBtn && chatMessages) {
        chatMessages.addEventListener('scroll', () => {
            const isScrolledUp = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight > 200;
            if (isScrolledUp) scrollBottomBtn.classList.add('show');
            else scrollBottomBtn.classList.remove('show');
        });
        scrollBottomBtn.onclick = () => {
            chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        };
    }

    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', handleFileUpload);
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-primary-500', 'bg-primary-50');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('border-primary-500', 'bg-primary-50');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-primary-500', 'bg-primary-50');
            handleFileUpload({ target: { files: e.dataTransfer.files } });
        });
    }

    if (modelSelect) {
        modelSelect.addEventListener('change', (e) => {
            const val = e.target.value;
            if (val.includes('/')) {
                const [provider, model] = val.split('/');
                currentProvider = provider;
                currentModel = model;
            }
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.documentElement.classList.toggle('dark');
            storage.set('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
        });
    }

    if (analyticsBtn) analyticsBtn.addEventListener('click', showAnalytics);
    if (closeAnalytics) closeAnalytics.addEventListener('click', () => analyticsModal.classList.add('hidden'));

    if (newChatBtn) {
        newChatBtn.addEventListener('click', async () => {
            let needsNewSession = true;
            try {
                if (sessionId) {
                    const histRes = await fetch(`/api/session?session_id=${sessionId}`);
                    if (histRes.ok) {
                        const histData = await histRes.json();
                        const docRes = await fetch(`/api/documents?session_id=${sessionId}`);
                        const docs = await docRes.json();
                        if (docs.length === 0 && (!histData.history || histData.history.length === 0)) {
                            needsNewSession = false;
                        }
                    }
                }
            } catch (e) { }

            if (needsNewSession) {
                const response = await fetch('/api/session');
                const data = await response.json();
                sessionId = data.session_id;
                storage.set('sessionId', sessionId);
            }

            clearChatUI(needsNewSession ? "New session started. Ready for your documents." : "This is already a new session.");
            loadSessionHistory();
            // Automatically close sidebar on mobile after switching/starting session
            if (window.innerWidth < 1024) closeSidebar();
        });
    }
}

async function loadSessionHistory() {
    if (!sessionList) return;
    try {
        const response = await fetch('/api/history');
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Server error ${response.status}`);
        }
        const sessions = await response.json();

        sessionList.innerHTML = '';
        sessions.forEach(s => {
            const div = document.createElement('div');
            div.className = `group p-3 rounded-xl cursor-pointer transition-all border flex items-center justify-between gap-2 ${s.id === sessionId ? 'bg-primary-50 dark:bg-primary-900/10 border-primary-200 dark:border-primary-800' : 'bg-transparent border-transparent hover:bg-gray-100 dark:hover:bg-slate-800'}`;

            div.onclick = () => {
                switchSession(s.id);
                if (window.innerWidth < 768) closeSidebar();
            };

            div.innerHTML = `
                <div class="flex-1 min-w-0">
                    <div class="text-xs font-semibold text-gray-700 dark:text-slate-200 truncate">${s.preview}</div>
                    <div class="text-[10px] text-gray-400 mt-1">${new Date(s.updated_at).toLocaleDateString()}</div>
                </div>
                <button class="delete-session-btn opacity-40 group-hover:opacity-100 p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-700 transition-all" data-id="${s.id}" title="Delete Chat">
                    <i class="fas fa-trash-can text-[10px]"></i>
                </button>
            `;

            const deleteBtn = div.querySelector('.delete-session-btn');
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                deleteSession(s.id);
            };

            sessionList.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load session history:', e);
        // Don't annoy with alerts for history fetch failures on init unless explicit
    }
}

async function deleteSession(id) {
    if (!confirm('Are you sure you want to delete this chat session?')) return;
    try {
        const response = await fetch('/api/delete-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: id })
        });
        if (response.ok) {
            if (id === sessionId) {
                storage.remove('sessionId');
                sessionId = null;
                init();
            } else {
                loadSessionHistory();
            }
        }
    } catch (e) { notify('Error deleting session', 'error'); }
}

async function switchSession(id) {
    sessionId = id;
    storage.set('sessionId', sessionId);
    try {
        const response = await fetch(`/api/session?session_id=${sessionId}`);
        const data = await response.json();
        if (chatMessages) {
            chatMessages.innerHTML = '';
            if (data.history && data.history.length > 0) {
                data.history.forEach(msg => appendMessage(msg.sender, msg.content, msg.sources));
            } else {
                clearChatUI("This is a previous session. You can continue our conversation here.");
            }
        }
        loadDocuments();
        loadSessionHistory();
    } catch (e) { notify('Failed to switch sessions', 'error'); }
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = '';
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;
    appendMessage('user', text);
    if (streamToggle && streamToggle.checked) {
        await handleStreamingChat(text);
    } else {
        await handleNormalChat(text);
    }
}

async function handleNormalChat(text) {
    const typingIndicator = appendTypingIndicator();
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                question: text,
                provider: currentProvider,
                model: currentModel
            })
        });
        const data = await response.json();
        if (typingIndicator) typingIndicator.remove();
        if (data.error) {
            appendMessage('bot', `Error: ${data.error}`);
        } else {
            appendMessage('bot', data.answer, data.sources);
            loadSessionHistory();
        }
    } catch (e) {
        if (typingIndicator) typingIndicator.remove();
        appendMessage('bot', 'Failed to connect to server.');
    } finally {
        if (sendBtn) sendBtn.disabled = false;
    }
}

async function handleStreamingChat(text) {
    const botMsgDiv = createBotMessageShell();
    if (!botMsgDiv) return;
    const contentDiv = botMsgDiv.querySelector('.prose');
    let fullAnswer = "";
    try {
        const response = await fetch('/api/chat-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionId,
                question: text,
                provider: currentProvider,
                model: currentModel
            })
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.error || `Server returned ${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.substring(6));
                        if (data.token) {
                            fullAnswer += data.token;
                            contentDiv.innerHTML = formatContent(fullAnswer);
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }
                        if (data.done) {
                            loadSessionHistory();
                        }
                        if (data.error) {
                            contentDiv.innerHTML += `<div class="text-red-500 mt-2">Error: ${data.error}</div>`;
                        }
                    } catch (err) { }
                }
            }
        }
    } catch (e) {
        if (contentDiv) contentDiv.innerHTML = `<div class="text-red-500">Error: ${e.message || 'Failed to connect to streaming server.'}</div>`;
    } finally {
        if (sendBtn) sendBtn.disabled = false;
    }
}

function createBotMessageShell() {
    if (!chatMessages) return null;
    const div = document.createElement('div');
    div.className = 'flex justify-start animate-slide-in';
    div.innerHTML = `
        <div class="max-w-[100%] md:max-w-[80%] flex flex-row items-start gap-3 md:gap-4">
            <div class="bot-avatar w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm bg-gray-200 dark:bg-slate-800 text-gray-500 dark:text-slate-400">
                <i class="fas fa-robot"></i>
            </div>
            <div class="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 text-gray-800 dark:text-slate-100 chat-bubble-bot shadow-sm message-container w-full min-w-0 overflow-hidden">
                <div class="prose dark:prose-invert text-sm leading-relaxed overflow-hidden break-words"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return div;
}


async function handleFileUpload(e) {

    const files = (e.target && e.target.files) ? e.target.files : (e.dataTransfer ? e.dataTransfer.files : []);
    if (!files || files.length === 0) return;
    if (!sessionId) {
        notify("Please wait until the session is initialized.", "error");
        return;
    }
    const formData = new FormData();
    formData.append('session_id', sessionId);
    formData.append('use_vision', visionToggle ? visionToggle.checked : false);
    for (const file of files) formData.append('files', file);

    if (uploadStatus) {
        uploadStatus.classList.remove('hidden');
        uploadStatus.classList.add('flex');
    }

    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.error) notify(data.error, 'error');
        else {
            notify(`Successfully uploaded ${data.files.length} documents.`);
            loadDocuments();
        }
    } catch (e) {
        notify('Upload failed. Check your internet connection.', 'error');
    } finally {
        if (uploadStatus) {
            uploadStatus.classList.add('hidden');
            uploadStatus.classList.remove('flex');
        }
    }
}


async function loadDocuments() {
    if (!docList || !sessionId) return;
    try {
        const response = await fetch(`/api/documents?session_id=${sessionId}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.error || `Server error ${response.status}`);
        }
        const docs = await response.json();
        docList.innerHTML = '';
        docs.forEach(doc => {
            const div = document.createElement('div');
            const isPdf = doc.file_type === 'pdf';
            div.className = `flex items-center justify-between p-3 bg-gray-50 dark:bg-slate-800/50 rounded-xl border border-gray-100 dark:border-slate-800 animate-slide-in ${isPdf ? 'cursor-pointer hover:bg-primary-50 dark:hover:bg-primary-900/10 transition-colors' : ''}`;
            if (isPdf) div.onclick = () => openPdfViewer(doc.filename, 1);
            div.innerHTML = `
                <div class="flex items-center gap-3 overflow-hidden">
                    <i class="fas ${getFileIcon(doc.file_type)} text-primary-500"></i>
                    <span class="text-sm font-medium text-gray-700 dark:text-slate-200 truncate">${doc.filename}</span>
                </div>
                <span class="text-[10px] text-gray-400 font-bold uppercase">${doc.file_type}</span>
            `;
            docList.appendChild(div);
        });
    } catch (e) { }
}

function getFileIcon(ext) {
    const map = { 'pdf': 'fa-file-pdf', 'docx': 'fa-file-word', 'csv': 'fa-file-csv', 'xlsx': 'fa-file-excel', 'xls': 'fa-file-excel', 'png': 'fa-file-image', 'jpg': 'fa-file-image', 'jpeg': 'fa-file-image' };
    return map[ext] || 'fa-file';
}

function appendMessage(sender, content, sources = []) {
    if (!chatMessages) return;
    const div = document.createElement('div');
    div.className = `flex ${sender === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`;
    div.innerHTML = `
        <div class="max-w-[100%] md:max-w-[80%] flex ${sender === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-3 md:gap-4 w-full">
            <div class="${sender === 'user' ? 'user-avatar' : 'bot-avatar'} w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm ${sender === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-slate-800 text-gray-500 dark:text-slate-400'}">
                <i class="fas ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i>
            </div>
            <div class="p-4 rounded-2xl ${sender === 'user' ? 'bg-primary-600 text-white chat-bubble-user shadow-lg shadow-primary-500/20' : 'bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 text-gray-800 dark:text-slate-100 chat-bubble-bot shadow-sm'} w-full min-w-0 overflow-hidden">
                <div class="prose dark:prose-invert text-sm leading-relaxed overflow-hidden break-words">${formatContent(content)}</div>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function appendTypingIndicator() {
    if (!chatMessages) return null;
    const div = document.createElement('div');
    div.className = 'flex justify-start animate-slide-in';
    div.innerHTML = `
        <div class="max-w-[90%] md:max-w-[80%] flex items-start gap-4">
            <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-slate-800 flex items-center justify-center text-gray-500">
                <i class="fas fa-robot text-sm"></i>
            </div>
            <div class="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 flex gap-1">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function formatContent(text) {
    if (!text) return "";
    let content = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    content = content.replace(/```([\s\S]*?)```/g, '<pre class="bg-slate-950 p-4 rounded-xl my-4 overflow-x-auto text-blue-400"><code>$1</code></pre>');
    content = content.replace(/^### (.*$)/gm, '<h3 class="text-lg font-bold text-gray-900 dark:text-white mt-6 mb-2">$1</h3>');
    content = content.replace(/^## (.*$)/gm, '<h2 class="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-3 pb-2 border-b border-gray-100 dark:border-slate-800">$1</h2>');
    content = content.replace(/^# (.*$)/gm, '<h1 class="text-2xl font-black text-gray-900 dark:text-white mt-10 mb-4">$1</h1>');
    content = content.replace(/^---$/gm, '<hr class="my-6 border-gray-100 dark:border-slate-800">');
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900 dark:text-white">$1</strong>');
    content = content.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');
    content = content.replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-primary-500 font-mono text-xs">$1</code>');
    content = content.replace(/^\s*[\-\*\+•]\s+(.*)/gm, '<div class="flex items-start gap-3 ml-2 my-2"><span class="w-1.5 h-1.5 rounded-full bg-primary-500 mt-2 flex-shrink-0"></span><span class="text-gray-700 dark:text-slate-300">$1</span></div>');
    let paragraphs = content.split(/\n\n+/);
    return paragraphs.map(p => {
        if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<hr') || p.startsWith('<pre')) return p;
        return `<p class="my-3 text-gray-700 dark:text-slate-300">${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');
}

async function showAnalytics() {
    if (!analyticsModal || !sessionId) return;
    analyticsModal.classList.remove('hidden');
    try {
        const response = await fetch(`/api/analytics?session_id=${sessionId}`);
        const data = await response.json();
        const avgTime = data.length ? (data.reduce((acc, curr) => acc + curr.response_time, 0) / data.length).toFixed(2) : '0.00';
        const totalWords = data.reduce((acc, curr) => acc + curr.answer_length, 0);
        document.getElementById('avg-time').innerText = `${avgTime}s`;
        document.getElementById('total-queries').innerText = data.length;
        document.getElementById('total-words').innerText = totalWords;
        const rows = document.getElementById('analytics-rows');
        if (rows) {
            rows.innerHTML = '';
            data.reverse().forEach(a => {
                const div = document.createElement('div');
                div.className = 'grid grid-cols-4 items-center p-3 bg-gray-50 dark:bg-slate-800/30 rounded-xl text-xs text-gray-600 dark:text-slate-400';
                div.innerHTML = `<span>${new Date(a.timestamp).toLocaleTimeString()}</span><span class="truncate pr-4">${a.query}</span><span>${a.response_time.toFixed(2)}s</span><span>${a.num_sources} docs</span>`;
                rows.appendChild(div);
            });
        }
    } catch (e) { }
}

// PDF Viewer Functionality
let pdfDoc = null;
let currentPage = 1;

const pdfViewerModal = document.getElementById('pdf-viewer-modal');
const closePdfViewer = document.getElementById('close-pdf-viewer');
const pdfCanvas = document.getElementById('pdf-canvas');
const pdfPrevPage = document.getElementById('pdf-prev-page');
const pdfNextPage = document.getElementById('pdf-next-page');
const pdfCurrentPageSpan = document.getElementById('pdf-current-page');
const pdfTotalPagesSpan = document.getElementById('pdf-total-pages');
const pdfFilenameSpan = document.getElementById('pdf-viewer-filename');

if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

if (closePdfViewer) closePdfViewer.addEventListener('click', () => { if (pdfViewerModal) pdfViewerModal.classList.add('hidden'); pdfDoc = null; });
if (pdfPrevPage) pdfPrevPage.addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderPdfPage(currentPage); } });
if (pdfNextPage) pdfNextPage.addEventListener('click', () => { if (pdfDoc && currentPage < pdfDoc.numPages) { currentPage++; renderPdfPage(currentPage); } });

async function openPdfViewer(filename, page = 1) {
    if (!pdfViewerModal) return;
    const pdfUrl = `/api/view-pdf/${sessionId}/${filename}`;
    currentPage = page;
    if (pdfFilenameSpan) pdfFilenameSpan.textContent = filename;
    pdfViewerModal.classList.remove('hidden');
    try {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        pdfDoc = await loadingTask.promise;
        if (pdfTotalPagesSpan) pdfTotalPagesSpan.textContent = pdfDoc.numPages;
        await renderPdfPage(currentPage);
    } catch (error) {
        console.error('Error loading PDF:', error);
        pdfViewerModal.classList.add('hidden');
    }
}

async function renderPdfPage(pageNum) {
    if (!pdfDoc || !pdfCanvas) return;
    try {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.5 });
        pdfCanvas.width = viewport.width;
        pdfCanvas.height = viewport.height;
        const ctx = pdfCanvas.getContext('2d');
        const renderContext = { canvasContext: ctx, viewport: viewport };
        await page.render(renderContext).promise;
        if (pdfCurrentPageSpan) pdfCurrentPageSpan.textContent = pageNum;
    } catch (e) { }
}

// Global initialization
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    init();
});
