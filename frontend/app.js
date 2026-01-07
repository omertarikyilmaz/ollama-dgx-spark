/**
 * Medya Takip Merkezi - AI Hub Application Logic
 */

// API base URL
const API_BASE = `http://${window.location.hostname}:8000`;

// State
let currentState = {
    page: 'home',
    templates: [],
    selectedTemplateId: null,
    chatSessions: [], // { id, title, history, timestamp }
    activeSessionId: null,
    analysisResults: {
        language: null,
        sector: null
    },
    reportFiles: [] // Array of File objects for report generator
};

// Initial state load
function initChatState() {
    const saved = localStorage.getItem('minnal_chat_sessions');
    if (saved) {
        currentState.chatSessions = JSON.parse(saved);
        if (currentState.chatSessions.length > 0) {
            currentState.activeSessionId = currentState.chatSessions[0].id;
        }
    }
}
initChatState();

// ============================================
// Core Navigation (SPA)
// ============================================

window.navigateTo = function (pageId) {
    // Update State
    currentState.page = pageId;

    // Update UI
    document.querySelectorAll('.service-view').forEach(view => {
        view.classList.remove('active');
    });

    const targetView = document.getElementById(`view-${pageId}`);
    if (targetView) targetView.classList.add('active');

    // Special handling per page
    if (pageId === 'news' && currentState.templates.length === 0) {
        loadTemplates();
    }

    if (pageId === 'chat') {
        renderChatSessions();
        renderActiveSessionMessages();
    }

    // Scroll to top
    window.scrollTo(0, 0);
};

window.switchNewsTab = function (tab) {
    document.querySelectorAll('.news-tab-content').forEach(c => c.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    const targetTab = document.getElementById(`${tab}-tab`);
    if (targetTab) targetTab.style.display = 'block';
    if (event && event.currentTarget) event.currentTarget.classList.add('active');
};

// ============================================
// AI Chat Service (Professional Sessions)
// ============================================

window.createNewChatSession = function () {
    const newSession = {
        id: Date.now().toString(),
        title: 'Yeni Sohbet',
        history: [],
        timestamp: new Date().toISOString()
    };
    currentState.chatSessions.unshift(newSession);
    currentState.activeSessionId = newSession.id;
    saveSessionsToStorage();
    renderChatSessions();
    renderActiveSessionMessages();
};

function saveSessionsToStorage() {
    localStorage.setItem('minnal_chat_sessions', JSON.stringify(currentState.chatSessions));
}

function renderChatSessions() {
    const list = document.getElementById('chat-session-list');
    if (!list) return;

    list.innerHTML = currentState.chatSessions.map(s => `
        <div class="session-item ${s.id === currentState.activeSessionId ? 'active' : ''}" onclick="switchChatSession('${s.id}')">
            <div class="session-name">${s.title}</div>
            <div class="delete-session" onclick="event.stopPropagation(); deleteChatSession('${s.id}')">
                <i class="fas fa-trash-alt"></i>
            </div>
        </div>
    `).join('');
}

window.switchChatSession = function (id) {
    currentState.activeSessionId = id;
    renderChatSessions();
    renderActiveSessionMessages();
};

window.deleteChatSession = function (id) {
    currentState.chatSessions = currentState.chatSessions.filter(s => s.id !== id);
    if (currentState.activeSessionId === id) {
        currentState.activeSessionId = currentState.chatSessions.length > 0 ? currentState.chatSessions[0].id : null;
    }
    saveSessionsToStorage();
    renderChatSessions();
    renderActiveSessionMessages();
};

function renderActiveSessionMessages() {
    const container = document.getElementById('chat-messages');
    const welcome = document.getElementById('chat-welcome-screen');

    container.innerHTML = '';
    if (welcome) container.appendChild(welcome);

    const activeSession = currentState.chatSessions.find(s => s.id === currentState.activeSessionId);

    if (activeSession && activeSession.history.length > 0) {
        if (welcome) welcome.style.display = 'none';
        activeSession.history.forEach(msg => appendMessageUI(msg.role, msg.content));
    } else {
        if (welcome) welcome.style.display = 'flex';
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    // Check if we have an active session, if not create one
    if (!currentState.activeSessionId) {
        window.createNewChatSession();
    }

    const activeSession = currentState.chatSessions.find(s => s.id === currentState.activeSessionId);

    // Auto-update title if it's the first message
    if (activeSession.history.length === 0) {
        activeSession.title = message.substring(0, 30) + (message.length > 30 ? '...' : '');
        renderChatSessions();
    }

    // Clear input
    input.value = '';

    // Add User Message to State
    activeSession.history.push({ role: 'user', content: message });
    saveSessionsToStorage();

    // Add User Message to UI
    if (document.getElementById('chat-welcome-screen')) {
        document.getElementById('chat-welcome-screen').style.display = 'none';
    }
    appendMessageUI('user', message);

    try {
        const response = await apiCall('/chat', {
            method: 'POST',
            body: JSON.stringify({
                message: message,
                history: activeSession.history.slice(0, -1) // Send history excluding recent msg if prompt wants context
            })
        });

        // Add AI Message to state
        activeSession.history.push({ role: 'assistant', content: response.response });
        saveSessionsToStorage();

        // Add AI Message to UI
        appendMessageUI('ai', response.response);
    } catch (error) {
        showToast('Chat hatası: ' + error.message, 'error');
    }
}

function appendMessageUI(role, text) {
    const container = document.getElementById('chat-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'user' : 'ai'}`;
    msgDiv.textContent = text;
    container.appendChild(msgDiv);

    // Auto scroll
    container.scrollTop = container.scrollHeight;
}

// ============================================
// Language Detection Service
// ============================================

async function detectLanguage() {
    const text = document.getElementById('lang-text-input').value.trim();
    if (!text) {
        showToast('Lütfen metin girin', 'error');
        return;
    }

    const btn = document.getElementById('lang-detect-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> Analiz Ediliyor...';
    btn.disabled = true;

    try {
        const result = await apiCall('/detect-language', {
            method: 'POST',
            body: JSON.stringify({ text })
        });

        renderLanguageResult(result);
    } catch (error) {
        showToast('Dil tespiti başarısız', 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

function renderLanguageResult(res) {
    const panel = document.getElementById('lang-result-panel');
    const confidencePercent = (res.confidence * 100).toFixed(0);

    panel.innerHTML = `
        <div class="result-card">
            <div class="result-item">
                <span class="label">Tespit Edilen Dil</span>
                <span class="value">${res.language_name} (${res.language.toUpperCase()})</span>
            </div>
            <div class="result-item">
                <span class="label">Güven Skoru</span>
                <span class="value">%${confidencePercent}</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                </div>
            </div>
        </div>
    `;
}

// ============================================
// Sector Classification Service
// ============================================

async function classifySector() {
    const text = document.getElementById('sector-text-input').value.trim();
    if (!text) {
        showToast('Lütfen haber metni girin', 'error');
        return;
    }

    const btn = document.getElementById('sector-classify-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> Sınıflandırılıyor...';
    btn.disabled = true;

    try {
        const result = await apiCall('/classify-sector', {
            method: 'POST',
            body: JSON.stringify({ news_text: text })
        });

        renderSectorResult(result);
    } catch (error) {
        showToast('Sektör sınıflandırma başarısız', 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

function renderSectorResult(res) {
    const panel = document.getElementById('sector-result-panel');
    const confidencePercent = (res.confidence * 100).toFixed(0);

    const importanceMeta = {
        1: { label: 'KRİTİK', emoji: '⚠️', color: 'var(--level-1)' },
        2: { label: 'ÇOK ÖNEMLİ', emoji: '⚡', color: 'var(--level-2)' },
        3: { label: 'ÖNEMLİ', emoji: 'ℹ️', color: 'var(--level-3)' },
        4: { label: 'ORTA ÖNEM', emoji: '📊', color: 'var(--level-4)' },
        5: { label: 'DÜŞÜK ÖNEM', emoji: '📰', color: 'var(--level-5)' }
    };

    const meta = importanceMeta[res.importance_level] || importanceMeta[5];

    panel.innerHTML = `
        <div class="result-card">
            <div class="result-item">
                <span class="label">Önem Seviyesi</span>
                <div class="importance-badge" style="background: ${meta.color}20; color: ${meta.color}; border: 1px solid ${meta.color}40;">
                    <span>${meta.emoji}</span>
                    <span>Seviye ${res.importance_level}: ${meta.label}</span>
                </div>
                <div class="importance-reasoning">
                    ${res.importance_reasoning}
                </div>
            </div>
            <div class="result-item">
                <span class="label">Ana Sektör</span>
                <span class="value">${res.sector}</span>
            </div>
            <div class="result-item">
                <span class="label">Alt Kategori</span>
                <span class="value" style="color: var(--text-secondary);">${res.subsector}</span>
            </div>
            <div class="result-item">
                <span class="label">Anahtar Kelimeler</span>
                <div class="keyword-chips">
                    ${res.keywords.map(k => `<span class="chip">${k}</span>`).join('')}
                </div>
            </div>
            <div class="result-item">
                <span class="label">Güven Skoru</span>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                </div>
            </div>
        </div>
    `;
}

// ============================================
// Traditional News Classification (Templates)
// ============================================

async function loadTemplates() {
    try {
        const data = await apiCall('/templates');
        currentState.templates = data.templates;
        renderTemplatesList();
    } catch (error) {
        showToast('Şablonlar yüklenemedi', 'error');
    }
}

function renderTemplatesList() {
    const list = document.getElementById('templates-list');
    list.innerHTML = currentState.templates.map(t => `
        <div class="template-item ${t.id === currentState.selectedTemplateId ? 'active' : ''}" 
             onclick="selectNewsTemplate('${t.id}')"
             style="padding: 1rem; background: var(--bg-tertiary); border-radius: 12px; margin-bottom: 0.5rem; cursor: pointer; border: 1px solid var(--border);">
            <div style="font-weight: 600; font-size: 0.875rem;">${t.name}</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${t.model}</div>
        </div>
    `).join('');
}

function selectNewsTemplate(id) {
    currentState.selectedTemplateId = id;
    const template = currentState.templates.find(t => t.id === id);
    if (!template) return;

    document.getElementById('selected-template-badge').style.display = 'flex';
    document.getElementById('selected-template-name').textContent = template.name;
    document.getElementById('classify-btn').disabled = false;
    renderTemplatesList();
}

async function classifyNewsWithTemplate() {
    const text = document.getElementById('news-input').value.trim();
    if (!text || !currentState.selectedTemplateId) return;

    const btn = document.getElementById('classify-btn');
    btn.innerHTML = '<span class="loading-spinner"></span>';
    btn.disabled = true;

    try {
        const result = await apiCall('/classify', {
            method: 'POST',
            body: JSON.stringify({
                template_id: currentState.selectedTemplateId,
                news_text: text
            })
        });

        displayNewsResult(result);
    } catch (error) {
        showToast('Sınıflandırma hatası', 'error');
    } finally {
        btn.innerHTML = '🚀 Sınıflandır';
        btn.disabled = false;
    }
}

function displayNewsResult(response) {
    const content = document.getElementById('news-result-content');
    if (!response.success) {
        content.innerHTML = `<div style="color: var(--danger);">Hata: ${response.error}</div>`;
        return;
    }

    const result = response.result;
    content.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            ${Object.entries(result).map(([key, value]) => `
                <div style="display: flex; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem;">
                    <span style="min-width: 140px; color: var(--accent-blue); font-weight: 600; font-size: 0.875rem;">${key}</span>
                    <span style="font-size: 0.875rem;">${value}</span>
                </div>
            `).join('')}
        </div>
    `;
}

// ============================================
// Report Generator Service
// ============================================

window.handleReportFiles = function (files) {
    const newFiles = Array.from(files).filter(f => f.name.endsWith('.xlsx') || f.name.endsWith('.xls'));
    currentState.reportFiles = [...currentState.reportFiles, ...newFiles];
    renderSelectedFiles();
};

function renderSelectedFiles() {
    const list = document.getElementById('selected-files-list');
    const actions = document.getElementById('report-actions');
    if (!list) return;

    if (currentState.reportFiles.length === 0) {
        list.innerHTML = '';
        actions.style.display = 'none';
        return;
    }

    actions.style.display = 'block';
    list.innerHTML = currentState.reportFiles.map((file, index) => `
        <div class="file-item">
            <div class="file-info">
                <i class="fas fa-file-excel"></i>
                <span class="file-name">${file.name}</span>
            </div>
            <div class="remove-file" onclick="removeReportFile(${index})">
                <i class="fas fa-times"></i>
            </div>
        </div>
    `).join('');
}

window.removeReportFile = function (index) {
    currentState.reportFiles.splice(index, 1);
    renderSelectedFiles();
};

async function generateReport() {
    if (currentState.reportFiles.length === 0) {
        showToast('Lütfen en az bir dosya seçin', 'error');
        return;
    }

    const btn = document.getElementById('generate-report-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<span class="loading-spinner"></span> Rapor Hazırlanıyor...';
    btn.disabled = true;

    try {
        const formData = new FormData();
        currentState.reportFiles.forEach(file => {
            formData.append('files', file);
        });

        const response = await fetch(`${API_BASE}/generate-report`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error('Rapor oluşturma hatası');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'MTM_Yonetici_Ozeti_Raporu.xlsx';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        showToast('Rapor başarıyla oluşturuldu ve indirildi');

        // Reset after success?
        currentState.reportFiles = [];
        renderSelectedFiles();
    } catch (error) {
        showToast('Rapor oluşturulurken hata oluştu', 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

// ============================================
// Generic Helpers
// ============================================

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options
        });
        if (!response.ok) throw new Error(`API Error: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Connection check
async function checkSystemHealth() {
    const dot = document.getElementById('ollama-status-dot');
    const text = document.getElementById('ollama-status-text');
    try {
        const health = await apiCall('/health');
        if (health.ollama === 'ok') {
            dot.className = 'status-dot online';
            text.textContent = 'Ollama Bağlı';
        } else {
            dot.className = 'status-dot offline';
            text.textContent = 'Ollama Hatası';
        }
    } catch {
        dot.className = 'status-dot offline';
        text.textContent = 'API Bağlantı Hatası';
    }
}

// ============================================
// Event Listeners
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    checkSystemHealth();
    setInterval(checkSystemHealth, 30000);

    // Initial view
    navigateTo('home');

    // Chat
    document.getElementById('chat-send-btn').addEventListener('click', sendChatMessage);
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    // Language
    document.getElementById('lang-detect-btn').addEventListener('click', detectLanguage);

    // Sector
    document.getElementById('sector-classify-btn').addEventListener('click', classifySector);

    // News
    document.getElementById('classify-btn').addEventListener('click', classifyNewsWithTemplate);
    document.getElementById('clear-btn').addEventListener('click', () => {
        document.getElementById('news-input').value = '';
        document.getElementById('news-result-content').innerHTML = '<div class="result-placeholder">Sonuç burada görünecek...</div>';
    });

    // Report
    const fileInput = document.getElementById('report-file-input');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => window.handleReportFiles(e.target.files));
    }

    document.getElementById('generate-report-btn').addEventListener('click', generateReport);

    const uploadZone = document.getElementById('report-upload-zone');
    if (uploadZone) {
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            window.handleReportFiles(e.dataTransfer.files);
        });
    }
});
