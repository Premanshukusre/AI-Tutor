// AI Tutor Frontend Application Logic
document.addEventListener('DOMContentLoaded', () => {
    // State
    let activeDocId = null;
    let documents = [];
    let chatHistory = [];

    // DOM Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const uploadProgress = document.getElementById('uploadProgress');
    const uploadStatusText = document.getElementById('uploadStatusText');
    
    const docList = document.getElementById('docList');
    const docCount = document.getElementById('docCount');
    const btnLoadSample = document.getElementById('btnLoadSample');
    
    const activeDocInfo = document.getElementById('activeDocInfo');
    const activeDocName = document.getElementById('activeDocName');
    const docStatusBadge = document.getElementById('docStatusBadge');
    const btnClearChat = document.getElementById('btnClearChat');
    
    const chatContainer = document.getElementById('chatContainer');
    const welcomeScreen = document.getElementById('welcomeScreen');
    const chatMessages = document.getElementById('chatMessages');
    
    const suggestionsBar = document.getElementById('suggestionsBar');
    const suggestionsChips = document.getElementById('suggestionsChips');
    
    const chatForm = document.getElementById('chatForm');
    const questionInput = document.getElementById('questionInput');
    const btnSend = document.getElementById('btnSend');

    // Auto-resize textarea
    questionInput.addEventListener('input', () => {
        questionInput.style.height = 'auto';
        questionInput.style.height = (questionInput.scrollHeight) + 'px';
    });

    // Enter to submit (Shift+Enter for newline)
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Upload Drag & Drop Handlers
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Handle File Upload API
    async function handleFileUpload(file) {
        const formData = new FormData();
        formData.append('file', file);

        uploadProgress.classList.remove('hidden');
        uploadStatusText.textContent = `Processing "${file.name}"...`;

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Upload failed');
            }

            uploadStatusText.textContent = 'Upload successful!';
            setTimeout(() => uploadProgress.classList.add('hidden'), 1500);

            await fetchDocuments();
            selectDocument(data.document.doc_id);
        } catch (err) {
            alert(`Error: ${err.message}`);
            uploadProgress.classList.add('hidden');
        } finally {
            fileInput.value = '';
        }
    }

    // Load Sample Textbook
    btnLoadSample.addEventListener('click', async () => {
        uploadProgress.classList.remove('hidden');
        uploadStatusText.textContent = 'Loading Sample CS Textbook...';

        const sampleText = `# Introduction to Computer Science & Operating Systems
Author: Prof. Alan Turing | Department of Computer Science

## Chapter 1: Foundations of Computer Architecture
Computer architecture is the set of rules and methods that describe the functionality, organization, and implementation of computer systems. The core component is the Central Processing Unit (CPU), which executes instructions.

The CPU consists of:
1. Arithmetic Logic Unit (ALU): Performs basic mathematical and logical operations.
2. Control Unit (CU): Directs the operation of the processor by decoding instructions.
3. Registers: High-speed internal memory locations used for temporary storage of data during execution.

Memory Hierarchy:
- Registers (Fastest, smallest capacity)
- Cache (L1, L2, L3)
- Main Memory (RAM: Random Access Memory)
- Secondary Storage (SSD, Hard Disk Drives)

## Chapter 2: Operating System Principles & Memory Management
An Operating System (OS) acts as an intermediary between the computer hardware and application programs. Key responsibilities include process scheduling, memory management, file system storage, and device management.

### Virtual Memory and Paging
Virtual memory is a memory management technique that provides an idealized abstraction of the storage resources available to a machine. It creates the illusion to users of a very large main memory.

Paging is a memory management scheme by which a computer stores and retrieves data from secondary storage for use in main memory. In a paging scheme, the operating system retrieves data from secondary storage in same-size blocks called pages. Paging avoids external fragmentation and allows physical address space of a process to be non-contiguous.

### Process vs Thread
A Process is an executing instance of a program with its own dedicated memory space.
A Thread is the smallest unit of execution within a process. Multiple threads within the same process share memory and resources, enabling efficient concurrent processing.

## Chapter 3: Data Structures & Algorithm Analysis
Data structures organize data for efficient access and modification.

Common Data Structures:
- Arrays: Contiguous memory allocation, fast O(1) indexed lookup.
- Linked Lists: Dynamic size, sequential access, nodes linked by memory pointers.
- Binary Search Trees (BST): Hierarchical tree structure where left child < root < right child. Average search time complexity is O(log n).
- Hash Tables: Key-value store using a hash function. Provides average O(1) time complexity for insertions and lookups.
`;
        const blob = new Blob([sampleText], { type: 'text/plain' });
        const file = new File([blob], 'Intro_To_Computer_Science.txt', { type: 'text/plain' });

        await handleFileUpload(file);
    });

    // Fetch Documents from Server
    async function fetchDocuments() {
        try {
            const res = await fetch('/api/documents');
            const data = await res.json();
            documents = data.documents || [];
            renderDocList();
        } catch (err) {
            console.error('Failed to fetch documents:', err);
        }
    }

    // Render Sidebar Document List
    function renderDocList() {
        docCount.textContent = documents.length;
        if (documents.length === 0) {
            docList.innerHTML = `
                <div class="empty-docs">
                    <i class="fa-regular fa-folder-open"></i>
                    <p>No documents uploaded yet. Upload a PDF, DOCX, or TXT file to start studying.</p>
                </div>
            `;
            activeDocId = null;
            updateActiveDocHeader();
            return;
        }

        docList.innerHTML = documents.map(doc => `
            <div class="doc-item ${doc.doc_id === activeDocId ? 'active' : ''}" data-id="${doc.doc_id}">
                <div class="doc-info">
                    <div class="doc-icon"><i class="fa-solid ${getFileIcon(doc.filename)}"></i></div>
                    <div>
                        <div class="doc-name" title="${escapeHtml(doc.filename)}">${escapeHtml(doc.filename)}</div>
                        <div class="doc-meta-sub">${doc.total_pages} pg • ${doc.total_chunks} chunks</div>
                    </div>
                </div>
                <button class="btn-del-doc" data-id="${doc.doc_id}" title="Remove Document">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `).join('');

        // Add Click Event Listeners
        docList.querySelectorAll('.doc-item').forEach(el => {
            el.addEventListener('click', (e) => {
                if (e.target.closest('.btn-del-doc')) return;
                selectDocument(el.dataset.id);
            });
        });

        docList.querySelectorAll('.btn-del-doc').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const targetBtn = e.target.closest('.btn-del-doc');
                const id = targetBtn ? targetBtn.dataset.id : btn.dataset.id;
                if (id) {
                    await deleteDocument(id);
                }
            });
        });
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        if (ext === 'pdf') return 'fa-file-pdf';
        if (ext === 'docx' || ext === 'doc') return 'fa-file-word';
        return 'fa-file-lines';
    }

    // Select Active Document
    function selectDocument(doc_id) {
        activeDocId = doc_id;
        renderDocList();
        updateActiveDocHeader();
    }

    // Delete Document
    async function deleteDocument(doc_id) {
        if (!confirm('Are you sure you want to remove this document?')) return;
        try {
            const res = await fetch(`/api/documents/${doc_id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Failed to delete document');
            if (activeDocId === doc_id) {
                activeDocId = null;
            }
            await fetchDocuments();
            updateActiveDocHeader();
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    }

    // Update Header State
    function updateActiveDocHeader() {
        const activeDoc = documents.find(d => d.doc_id === activeDocId);
        if (activeDoc) {
            activeDocName.textContent = activeDoc.filename;
            docStatusBadge.textContent = "Ready to answer";
            docStatusBadge.className = "doc-status-badge active";
            questionInput.disabled = false;
            btnSend.disabled = false;
            questionInput.placeholder = `Ask a question about "${activeDoc.filename}"...`;
            suggestionsBar.classList.remove('hidden');
        } else {
            activeDocName.textContent = "No Document Selected";
            docStatusBadge.textContent = "Select a document";
            docStatusBadge.className = "doc-status-badge inactive";
            questionInput.disabled = true;
            btnSend.disabled = true;
            questionInput.placeholder = "Select or upload a document to enable questions...";
            suggestionsBar.classList.add('hidden');
        }
    }

    // Handle QA Form Submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = questionInput.value.trim();
        if (!question || !activeDocId) return;

        // Hide welcome screen if visible
        welcomeScreen.classList.add('hidden');

        // Render User Message
        appendMessage('user', question);
        questionInput.value = '';
        questionInput.style.height = 'auto';

        // Render Loading Indicator
        const loadingId = appendLoadingMessage();

        try {
            const res = await fetch('/api/qa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    doc_id: activeDocId,
                    question: question,
                    history: chatHistory
                })
            });

            const data = await res.json();
            removeMessage(loadingId);

            if (!res.ok) {
                throw new Error(data.detail || 'Failed to get answer');
            }

            // Render Assistant Message with Sources & Grounding status
            appendMessage('assistant', data.answer, data.sources, data.grounded);
        } catch (err) {
            removeMessage(loadingId);
            appendMessage('assistant', `Sorry, an error occurred while searching: ${err.message}`, [], false);
        }
    });

    // Render Messages
    function appendMessage(role, text, sources = [], grounded = true) {
        chatHistory.push({ role: role, content: text });
        const msgRow = document.createElement('div');
        msgRow.className = `message-row ${role}`;
        
        const avatarIcon = role === 'user' ? 'fa-user-graduate' : 'fa-brain';
        
        let sourcesHtml = '';
        if (role === 'assistant' && sources && sources.length > 0) {
            sourcesHtml = `
                <div class="sources-card">
                    <div class="sources-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
                        <span><i class="fa-solid fa-quote-left"></i> Verified Sources (${sources.length})</span>
                        <i class="fa-solid fa-chevron-down"></i>
                    </div>
                    <div class="sources-list">
                        ${sources.map(s => `
                            <div class="source-item">
                                <div class="source-top">
                                    <span>${escapeHtml(s.section)} (Page ${s.page_num})</span>
                                    <span class="source-tag">${s.match_percent}% match</span>
                                </div>
                                <div class="source-snippet">"${escapeHtml(s.snippet)}"</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }

        let ungroundedBadge = '';
        if (role === 'assistant' && !grounded) {
            ungroundedBadge = `
                <div class="un-grounded-badge">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    Not contained in active document
                </div>
            `;
        }

        msgRow.innerHTML = `
            <div class="avatar"><i class="fa-solid ${avatarIcon}"></i></div>
            <div class="message-bubble">
                <div class="message-text">${escapeHtml(text)}</div>
                ${ungroundedBadge}
                ${sourcesHtml}
                <div class="message-meta">
                    <span>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                </div>
            </div>
        `;

        chatMessages.appendChild(msgRow);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function appendLoadingMessage() {
        const id = 'loading_' + Date.now();
        const msgRow = document.createElement('div');
        msgRow.className = 'message-row assistant';
        msgRow.id = id;
        msgRow.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-brain"></i></div>
            <div class="message-bubble">
                <div class="message-text" style="display:flex; align-items:center; gap: 0.5rem; color: var(--text-muted);">
                    <div class="spinner"></div> Searching document context...
                </div>
            </div>
        `;
        chatMessages.appendChild(msgRow);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    // Clear Chat
    btnClearChat.addEventListener('click', () => {
        chatMessages.innerHTML = '';
        chatHistory = [];
        welcomeScreen.classList.remove('hidden');
    });

    // Suggestions chips click
    suggestionsChips.addEventListener('click', (e) => {
        const chip = e.target.closest('.chip');
        if (chip && !questionInput.disabled) {
            questionInput.value = chip.dataset.prompt;
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    function escapeHtml(str) {
        if (!str) return '';
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initial Fetch
    fetchDocuments();
});
