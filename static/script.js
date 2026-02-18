let sessionId = localStorage.getItem('sessionId');
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

// Mobile Sidebar Elements
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const closeSidebarBtn = document.getElementById('close-sidebar-btn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');

// Mobile Sidebar Functions
function openSidebar() {
    sidebar.classList.remove('-translate-x-full');
    sidebarOverlay.classList.remove('hidden', 'opacity-0');
}

function closeSidebar() {
    if (sidebar && sidebarOverlay) {
        sidebar.classList.add('-translate-x-full');
        sidebarOverlay.classList.add('opacity-0');
        setTimeout(() => {
            sidebarOverlay.classList.add('hidden');
        }, 300);
    }
}

function clearChatUI(message = "Upload your documents and let's start a new conversation.") {
    chatMessages.innerHTML = `
        <div class="max-w-3xl mx-auto text-center py-12">
            <div class="w-16 h-16 md:w-20 md:h-20 bg-primary-100 dark:bg-primary-900/30 rounded-3xl flex items-center justify-center text-primary-600 dark:text-primary-400 mx-auto mb-6">
                <i class="fas fa-robot text-3xl md:text-4xl"></i>
            </div>
            <h2 class="text-2xl md:text-3xl font-bold text-gray-800 dark:text-white mb-3">Hello! I'm NexRetriever</h2>
            <p class="text-sm md:text-base text-gray-500 dark:text-slate-400 max-w-md mx-auto">${message}</p>
        </div>
    `;
    docList.innerHTML = '';
}

// Mobile Sidebar Event Listeners
if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', openSidebar);
}

if (closeSidebarBtn) {
    closeSidebarBtn.addEventListener('click', closeSidebar);
}

if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', closeSidebar);
}

// Initialize
async function init() {
    const savedId = localStorage.getItem('sessionId');
    let data;

    try {
        if (savedId) {
            const response = await fetch(`/api/session?session_id=${savedId}`);
            if (response.ok) {
                data = await response.json();
            } else {
                // If saved session is gone, get a new one
                localStorage.removeItem('sessionId'); // Clear localStorage for invalid session
                const newRes = await fetch('/api/session');
                data = await newRes.json();
            }
        } else {
            const newRes = await fetch('/api/session');
            data = await newRes.json();
        }

        sessionId = data.session_id;
        localStorage.setItem('sessionId', sessionId);

        if (data.history && data.history.length > 0) {
            chatMessages.innerHTML = '';
            data.history.forEach(msg => appendMessage(msg.sender, msg.content, msg.sources));
        } else {
            clearChatUI();
        }

        loadDocuments();
        loadSessionHistory();
    } catch (e) {
        console.error("Initialization error:", e);
    }

    if (localStorage.getItem('theme') === 'dark' || (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
    }
}

// Event Listeners
chatInput.addEventListener('input', () => {
    sendBtn.disabled = chatInput.value.trim() === '';
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

modelSelect.addEventListener('change', (e) => {
    const [provider, model] = e.target.value.split('/');
    currentProvider = provider;
    currentModel = model;
});

themeToggle.addEventListener('click', () => {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
});

analyticsBtn.addEventListener('click', showAnalytics);
closeAnalytics.addEventListener('click', () => analyticsModal.classList.add('hidden'));

newChatBtn.addEventListener('click', async () => {
    // Check if current session is empty or invalid
    let needsNewSession = true;
    try {
        const histRes = await fetch(`/api/session?session_id=${sessionId}`);
        if (histRes.ok) {
            const histData = await histRes.json();
            const docRes = await fetch(`/api/documents?session_id=${sessionId}`);
            const docs = await docRes.json();

            // If it's already an empty session in the DB, we don't need a new record
            if (docs.length === 0 && (!histData.history || histData.history.length === 0)) {
                needsNewSession = false;
            }
        }
    } catch (e) { }

    if (needsNewSession) {
        const response = await fetch('/api/session');
        const data = await response.json();
        sessionId = data.session_id;
        localStorage.setItem('sessionId', sessionId);
    }

    clearChatUI(needsNewSession ? "New session started. Ready for your documents." : "This is already a new session.");
    loadSessionHistory();

    if (window.innerWidth < 768) {
        closeSidebar();
    }
});

// Functions
async function loadSessionHistory() {
    try {
        const response = await fetch('/api/history');
        const sessions = await response.json();

        sessionList.innerHTML = '';
        sessions.forEach(s => {
            const div = document.createElement('div');
            div.className = `group p-3 rounded-xl cursor-pointer transition-all border flex items-center justify-between gap-2 ${s.id === sessionId ? 'bg-primary-50 dark:bg-primary-900/10 border-primary-200 dark:border-primary-800' : 'bg-transparent border-transparent hover:bg-gray-100 dark:hover:bg-slate-800'}`;

            div.onclick = () => {
                switchSession(s.id);
                // Close sidebar on mobile
                if (window.innerWidth < 768) {
                    closeSidebar();
                }
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

            // Add event listener to the delete button
            const deleteBtn = div.querySelector('.delete-session-btn');
            deleteBtn.onclick = (e) => {
                e.stopPropagation(); // Prevent switching session
                deleteSession(s.id);
            };

            sessionList.appendChild(div);
        });
    } catch (e) {
        console.error('Failed to load session history:', e);
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
                // If we deleted the current session, clean up localStorage
                localStorage.removeItem('sessionId');
                sessionId = null;
                // init will handle creating a new one properly
                init();
            } else {
                loadSessionHistory();
            }
        } else {
            alert('Failed to delete session');
        }
    } catch (e) {
        alert('Error deleting session');
    }
}

async function switchSession(id) {
    sessionId = id;
    localStorage.setItem('sessionId', sessionId);

    const response = await fetch(`/api/session?session_id=${sessionId}`);
    const data = await response.json();

    chatMessages.innerHTML = '';
    if (data.history && data.history.length > 0) {
        data.history.forEach(msg => appendMessage(msg.sender, msg.content, msg.sources));
    } else {
        chatMessages.innerHTML = `
            <div class="max-w-3xl mx-auto text-center py-12">
                <div class="w-20 h-20 bg-primary-100 dark:bg-primary-900/30 rounded-3xl flex items-center justify-center text-primary-600 dark:text-primary-400 mx-auto mb-6">
                    <i class="fas fa-robot text-4xl"></i>
                </div>
                <h2 class="text-3xl font-bold text-gray-800 dark:text-white mb-3">Hello!</h2>
                <p class="text-gray-500 dark:text-slate-400 max-w-md mx-auto">This is a previous session. You can continue our conversation here.</p>
            </div>
        `;
    }

    loadDocuments();
    loadSessionHistory();
}
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    chatInput.value = '';
    chatInput.style.height = 'auto';
    sendBtn.disabled = true;

    appendMessage('user', text);

    if (streamToggle.checked) {
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
        typingIndicator.remove();

        if (data.error) {
            appendMessage('bot', `Error: ${data.error}`);
        } else {
            appendMessage('bot', data.answer, data.sources);
            // Refresh history to update title if it was "New Chat"
            loadSessionHistory();
        }
    } catch (e) {
        typingIndicator.remove();
        appendMessage('bot', 'Failed to connect to server.');
    }
}

async function handleStreamingChat(text) {
    const botMsgDiv = createBotMessageShell();
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

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));

                    if (data.token) {
                        fullAnswer += data.token;
                        contentDiv.innerHTML = formatContent(fullAnswer);
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }

                    if (data.done) {
                        if (data.sources && data.sources.length > 0) {
                            appendSources(botMsgDiv, data.sources);
                        }
                        // Refresh history to update title
                        loadSessionHistory();
                    }

                    if (data.error) {
                        contentDiv.innerHTML += `<div class="text-red-500 mt-2">Error: ${data.error}</div>`;
                    }
                }
            }
        }
    } catch (e) {
        contentDiv.innerHTML = 'Failed to connect to streaming server.';
    } finally {
        sendBtn.disabled = false;
    }
}

function createBotMessageShell() {
    const div = document.createElement('div');
    div.className = 'flex justify-start animate-slide-in';
    div.innerHTML = `
        <div class="max-w-[80%] flex flex-row items-start gap-4">
            <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm bg-gray-200 dark:bg-slate-800 text-gray-500 dark:text-slate-400">
                <i class="fas fa-robot"></i>
            </div>
            <div class="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 text-gray-800 dark:text-slate-100 chat-bubble-bot shadow-sm message-container">
                <div class="prose dark:prose-invert text-sm leading-relaxed"></div>
            </div>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function appendSources(container, sources) {
    const target = container.querySelector('.message-container');
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'mt-3 flex flex-wrap gap-2 pt-2 border-t border-gray-100 dark:border-slate-800';
    sourcesDiv.innerHTML = sources.map(s => `
        <span class="source-tag"><i class="fas fa-file-alt"></i> ${s.filename} (p. ${s.page})</span>
    `).join('');
    target.appendChild(sourcesDiv);
}

async function handleFileUpload(e) {
    const files = e.target.files;
    if (files.length === 0) return;

    const formData = new FormData();
    formData.append('session_id', sessionId);
    for (const file of files) {
        formData.append('files', file);
    }

    uploadStatus.classList.remove('hidden');
    uploadStatus.classList.add('flex');

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.error) {
            alert(data.error);
        } else {
            loadDocuments();
        }
    } catch (e) {
        alert('Upload failed');
    } finally {
        uploadStatus.classList.add('hidden');
        uploadStatus.classList.remove('flex');
    }
}

async function loadDocuments() {
    const response = await fetch(`/api/documents?session_id=${sessionId}`);
    const docs = await response.json();

    docList.innerHTML = '';
    docs.forEach(doc => {
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between p-3 bg-gray-50 dark:bg-slate-800/50 rounded-xl border border-gray-100 dark:border-slate-800 animate-slide-in';
        div.innerHTML = `
            <div class="flex items-center gap-3 overflow-hidden">
                <i class="fas ${getFileIcon(doc.file_type)} text-primary-500"></i>
                <span class="text-sm font-medium text-gray-700 dark:text-slate-200 truncate">${doc.filename}</span>
            </div>
            <span class="text-[10px] text-gray-400 font-bold uppercase">${doc.file_type}</span>
        `;
        docList.appendChild(div);
    });
}

function getFileIcon(ext) {
    const map = {
        'pdf': 'fa-file-pdf',
        'docx': 'fa-file-word',
        'csv': 'fa-file-csv',
        'xlsx': 'fa-file-excel',
        'xls': 'fa-file-excel',
        'png': 'fa-file-image',
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image'
    };
    return map[ext] || 'fa-file';
}

function appendMessage(sender, content, sources = []) {
    const div = document.createElement('div');
    div.className = `flex ${sender === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`;

    let sourcesHtml = '';
    if (sources && sources.length > 0) {
        sourcesHtml = `<div class="mt-3 flex flex-wrap gap-2 pt-2 border-t border-gray-100 dark:border-slate-800">${sources.map(s => `
            <span class="source-tag"><i class="fas fa-file-alt"></i> ${s.filename} (p. ${s.page})</span>
        `).join('')}</div>`;
    }

    div.innerHTML = `
        <div class="max-w-[90%] md:max-w-[80%] flex ${sender === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-4">
            <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm ${sender === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-slate-800 text-gray-500 dark:text-slate-400'}">
                <i class="fas ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i>
            </div>
            <div class="p-4 rounded-2xl ${sender === 'user' ? 'bg-primary-600 text-white chat-bubble-user shadow-lg shadow-primary-500/20' : 'bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 text-gray-800 dark:text-slate-100 chat-bubble-bot shadow-sm'}">
                <div class="prose dark:prose-invert text-sm leading-relaxed">${formatContent(content)}</div>
                ${sourcesHtml}
            </div>
        </div>
    `;

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTypingIndicator() {
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

    // Escaping some HTML to prevent XSS (but allow some for our own tags later)
    let content = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Code blocks
    content = content.replace(/```([\s\S]*?)```/g, '<pre class="bg-slate-950 p-4 rounded-xl my-4 overflow-x-auto text-blue-400"><code>$1</code></pre>');

    // Headers
    content = content.replace(/^### (.*$)/gm, '<h3 class="text-lg font-bold text-gray-900 dark:text-white mt-6 mb-2">$1</h3>');
    content = content.replace(/^## (.*$)/gm, '<h2 class="text-xl font-bold text-gray-900 dark:text-white mt-8 mb-3 pb-2 border-b border-gray-100 dark:border-slate-800">$1</h2>');
    content = content.replace(/^# (.*$)/gm, '<h1 class="text-2xl font-black text-gray-900 dark:text-white mt-10 mb-4">$1</h1>');

    // Horizontal Rules
    content = content.replace(/^---$/gm, '<hr class="my-6 border-gray-100 dark:border-slate-800">');

    // Bold (**text**)
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold text-gray-900 dark:text-white">$1</strong>');

    // Italics (*text*)
    content = content.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');

    // Inline code (`code`)
    content = content.replace(/`([^`]+)`/g, '<code class="bg-gray-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-primary-500 font-mono text-xs">$1</code>');

    // Bullet points (convert lines starting with -, *, +, or • to styled bullets)
    // We use a more robust regex to handle various bullet styles
    content = content.replace(/^\s*[\-\*\+•]\s+(.*)/gm, '<div class="flex items-start gap-3 ml-2 my-2"><span class="w-1.5 h-1.5 rounded-full bg-primary-500 mt-2 flex-shrink-0"></span><span class="text-gray-700 dark:text-slate-300">$1</span></div>');

    // Paragraphs (if not a tag, wrap in p for better spacing)
    // First, split by double newlines
    let paragraphs = content.split(/\n\n+/);
    content = paragraphs.map(p => {
        if (p.startsWith('<h') || p.startsWith('<div') || p.startsWith('<hr') || p.startsWith('<pre')) {
            return p;
        }
        return `<p class="my-3 text-gray-700 dark:text-slate-300">${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return content;
}

async function showAnalytics() {
    analyticsModal.classList.remove('hidden');
    const response = await fetch(`/api/analytics?session_id=${sessionId}`);
    const data = await response.json();

    const avgTime = data.length ? (data.reduce((acc, curr) => acc + curr.response_time, 0) / data.length).toFixed(2) : '0.00';
    const totalWords = data.reduce((acc, curr) => acc + curr.answer_length, 0);

    document.getElementById('avg-time').innerText = `${avgTime}s`;
    document.getElementById('total-queries').innerText = data.length;
    document.getElementById('total-words').innerText = totalWords;

    const rows = document.getElementById('analytics-rows');
    rows.innerHTML = '';
    data.reverse().forEach(a => {
        const div = document.createElement('div');
        div.className = 'grid grid-cols-4 items-center p-3 bg-gray-50 dark:bg-slate-800/30 rounded-xl text-xs text-gray-600 dark:text-slate-400';
        div.innerHTML = `
            <span>${new Date(a.timestamp).toLocaleTimeString()}</span>
            <span class="truncate pr-4">${a.query}</span>
            <span>${a.response_time.toFixed(2)}s</span>
            <span>${a.num_sources} docs</span>
        `;
        rows.appendChild(div);
    });
}

// ========== PDF VIEWER FUNCTIONALITY ==========
let pdfDoc = null;
let currentPage = 1;
let currentPdfUrl = null;

const pdfViewerModal = document.getElementById('pdf-viewer-modal');
const closePdfViewer = document.getElementById('close-pdf-viewer');
const pdfCanvas = document.getElementById('pdf-canvas');
const pdfPrevPage = document.getElementById('pdf-prev-page');
const pdfNextPage = document.getElementById('pdf-next-page');
const pdfCurrentPageSpan = document.getElementById('pdf-current-page');
const pdfTotalPagesSpan = document.getElementById('pdf-total-pages');
const pdfFilenameSpan = document.getElementById('pdf-viewer-filename');

// Initialize PDF.js worker
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

closePdfViewer.addEventListener('click', () => {
    pdfViewerModal.classList.add('hidden');
    pdfDoc = null;
    currentPdfUrl = null;
});

pdfPrevPage.addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        renderPdfPage(currentPage);
    }
});

pdfNextPage.addEventListener('click', () => {
    if (pdfDoc && currentPage < pdfDoc.numPages) {
        currentPage++;
        renderPdfPage(currentPage);
    }
});

async function openPdfViewer(filename, page = 1) {
    const pdfUrl = `/api/view-pdf/${sessionId}/${filename}`;
    currentPdfUrl = pdfUrl;
    currentPage = page;

    pdfFilenameSpan.textContent = filename;
    pdfViewerModal.classList.remove('hidden');

    try {
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        pdfDoc = await loadingTask.promise;
        pdfTotalPagesSpan.textContent = pdfDoc.numPages;
        await renderPdfPage(currentPage);
    } catch (error) {
        console.error('Error loading PDF:', error);
        alert('Failed to load PDF');
        pdfViewerModal.classList.add('hidden');
    }
}

async function renderPdfPage(pageNum) {
    if (!pdfDoc) return;

    const page = await pdfDoc.getPage(pageNum);
    const viewport = page.getViewport({ scale: 1.5 });

    pdfCanvas.width = viewport.width;
    pdfCanvas.height = viewport.height;

    const ctx = pdfCanvas.getContext('2d');
    const renderContext = {
        canvasContext: ctx,
        viewport: viewport
    };

    await page.render(renderContext).promise;
    pdfCurrentPageSpan.textContent = pageNum;
}

// Update source tags to be clickable
// Update source tags to be clickable
function appendSources(container, sources) {
    // Sources display disabled by user request
    return;
}

// Update appendMessage to make sources clickable (duplicate - sources disabled)
function appendMessage(sender, content, sources = []) {
    const div = document.createElement('div');
    div.className = `flex ${sender === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`;

    // Sources removed by request

    div.innerHTML = `
        <div class="max-w-[90%] md:max-w-[80%] flex ${sender === 'user' ? 'flex-row-reverse' : 'flex-row'} items-start gap-4">
            <div class="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm ${sender === 'user' ? 'bg-primary-600 text-white' : 'bg-gray-200 dark:bg-slate-800 text-gray-500 dark:text-slate-400'}">
                <i class="fas ${sender === 'user' ? 'fa-user' : 'fa-robot'}"></i>
            </div>
            <div class="p-4 rounded-2xl ${sender === 'user' ? 'bg-primary-600 text-white chat-bubble-user shadow-lg shadow-primary-500/20' : 'bg-white dark:bg-slate-900 border border-gray-100 dark:border-slate-800 text-gray-800 dark:text-slate-100 chat-bubble-bot shadow-sm'}">
                <div class="prose dark:prose-invert text-sm leading-relaxed">${formatContent(content)}</div>
            </div>
        </div>
    `;

    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update loadDocuments to make PDFs clickable
async function loadDocuments() {
    const response = await fetch(`/api/documents?session_id=${sessionId}`);
    const docs = await response.json();

    docList.innerHTML = '';
    docs.forEach(doc => {
        const div = document.createElement('div');
        const isPdf = doc.file_type === 'pdf';
        div.className = `flex items-center justify-between p-3 bg-gray-50 dark:bg-slate-800/50 rounded-xl border border-gray-100 dark:border-slate-800 animate-slide-in ${isPdf ? 'cursor-pointer hover:bg-primary-50 dark:hover:bg-primary-900/10 transition-colors' : ''}`;

        if (isPdf) {
            div.onclick = () => openPdfViewer(doc.filename, 1);
        }

        div.innerHTML = `
            <div class="flex items-center gap-3 overflow-hidden">
                <i class="fas ${getFileIcon(doc.file_type)} text-primary-500"></i>
                <span class="text-sm font-medium text-gray-700 dark:text-slate-200 truncate">${doc.filename}</span>
            </div>
            <span class="text-[10px] text-gray-400 font-bold uppercase">${doc.file_type}</span>
        `;
        docList.appendChild(div);
    });
}

init();
