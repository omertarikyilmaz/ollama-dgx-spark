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
    reportFiles: [], // Array of File objects for report generator
    reportPreviewData: null,
    selectedLayout: 'standard', // 'standard' or 'modern'
    charts: {}, // Store Chart.js instances
    linkAnalysisHistory: [], // Array of link analysis results
    // OCR State
    ocrResult: null,  // OCR result data
    ocrImage: null,   // Current loaded image
    ocrZoom: 1.0,     // Current zoom level
    ocrSearchMatches: [], // Search match indices
    ocrCurrentMatch: -1,   // Current match index for navigation
    // Whisper State
    whisperFile: null,    // Current audio file
    whisperResult: null,  // Transcription result
    whisperSegmentsExpanded: true,  // Segments panel state
    whisperHistory: []    // Request history for performance tracking
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
    newFiles.forEach(file => {
        if (!currentState.reportFiles.some(f => f.name === file.name)) {
            currentState.reportFiles.push(file);
        }
    });
    renderSelectedFiles();
};

window.removeReportFile = function (index) {
    currentState.reportFiles.splice(index, 1);
    renderSelectedFiles();
};

function renderSelectedFiles() {
    const list = document.getElementById('selected-files-list');
    const actionsPanel = document.getElementById('report-actions-panel');
    const layoutPanel = document.getElementById('layout-control-panel');

    if (!list) return;

    if (currentState.reportFiles.length === 0) {
        list.innerHTML = '';
        if (actionsPanel) actionsPanel.style.display = 'none';
        if (layoutPanel) layoutPanel.style.display = 'none';
        return;
    }

    // Show controls when files exist
    if (layoutPanel) layoutPanel.style.display = 'flex';
    if (actionsPanel) {
        actionsPanel.style.display = 'flex';
        // Ensure download section is hidden if we are just adding files
        if (!currentState.reportPreviewData) {
            const dlSection = document.getElementById('download-section');
            if (dlSection) dlSection.style.display = 'none';
            const prevBtn = document.getElementById('preview-report-btn');
            if (prevBtn) prevBtn.style.display = 'block';
        }
    }

    list.innerHTML = currentState.reportFiles.map((file, index) => `
        <div class="file-item">
            <span class="file-name" title="${file.name}">${file.name.length > 20 ? file.name.substring(0, 18) + '...' : file.name}</span>
            <div class="remove-file" onclick="removeReportFile(${index})"><i class="fas fa-times"></i></div>
        </div>
    `).join('');
}

window.selectReportLayout = function (layout) {
    currentState.selectedLayout = layout;
    document.querySelectorAll('.layout-option').forEach(el => el.classList.remove('active'));
    const activeEl = document.getElementById(`layout-${layout}`);
    if (activeEl) activeEl.classList.add('active');
};

window.resetReportView = function () {
    // Right Panel: Show Placeholder, Hide Preview
    document.getElementById('report-preview-content').style.display = 'none';
    document.getElementById('report-placeholder').style.display = 'flex';

    // Sidebar: Hide Download Section, Show Preview Button
    document.getElementById('download-section').style.display = 'none';
    document.getElementById('preview-report-btn').style.display = 'block';

    // Clear charts
    if (currentState.charts) {
        Object.values(currentState.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') chart.destroy();
        });
    }
    currentState.charts = {};
    currentState.reportPreviewData = null;

    // We keep files and selection
    renderSelectedFiles();
};

window.previewReport = async function () {
    if (currentState.reportFiles.length === 0) {
        showToast('Lütfen en az bir dosya seçin', 'error');
        return;
    }

    const btn = document.getElementById('preview-report-btn');
    const originalContent = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Hazırlanıyor...';
        btn.disabled = true;
    }

    try {
        const formData = new FormData();
        currentState.reportFiles.forEach(file => {
            formData.append('files', file);
        });

        const result = await apiCall('/preview-report', {
            method: 'POST',
            body: formData,
            headers: {}
        });

        if (result.success) {
            currentState.reportPreviewData = result.data;
            showPreviewUI();
        } else {
            showToast(`Hata: ${result.error}`, 'error');
        }

    } catch (error) {
        console.error('Preview error:', error);
        showToast('Önizleme alınamadı', 'error');
    } finally {
        if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }
};

function showPreviewUI() {
    // Right Panel: Hide Placeholder, Show Preview
    document.getElementById('report-placeholder').style.display = 'none';
    document.getElementById('report-preview-content').style.display = 'block';

    // Sidebar: Show Download Section, Hide Preview Button (or keep it as "Update")
    document.getElementById('preview-report-btn').style.display = 'none';
    document.getElementById('download-section').style.display = 'block';

    renderPreviewTable();
    setTimeout(renderPreviewCharts, 100);
}

function renderPreviewTable() {
    const tbody = document.querySelector('#preview-summary-table tbody');
    const tfoot = document.querySelector('#preview-summary-table tfoot');
    if (!tbody || !tfoot || !currentState.reportPreviewData) return;

    const data = currentState.reportPreviewData;

    tbody.innerHTML = data.summary_table.map(row => `
        <tr>
            <td>${row.Mecra || ''}</td>
            <td class="text-right">${row['Haber Adedi'] || 0}</td>
            <td class="text-right">${(row['Erişim'] || 0).toLocaleString('tr-TR')}</td>
            <td class="text-right">${(row['Reklam Eşdeğeri(TL)'] || 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })}</td>
        </tr>
    `).join('');

    const totals = data.totals;
    if (totals) {
        tfoot.innerHTML = `
            <tr>
                <td>${totals.Mecra}</td>
                <td class="text-right">${totals['Haber Adedi']}</td>
                <td class="text-right">${(totals['Erişim'] || 0).toLocaleString('tr-TR')}</td>
                <td class="text-right">${(totals['Reklam Eşdeğeri(TL)'] || 0).toLocaleString('tr-TR', { maximumFractionDigits: 0 })} TL</td>
            </tr>
        `;
    }
}

function renderPreviewCharts() {
    const data = currentState.reportPreviewData ? currentState.reportPreviewData.chart_data : null;
    if (!data) return;

    const ctxHaber = document.getElementById('chart-haber');
    const ctxErisim = document.getElementById('chart-erisim');
    const ctxReklam = document.getElementById('chart-reklam');

    const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#6366f1'];

    const createChart = (canvas, label, values) => {
        if (!canvas) return null;
        return new Chart(canvas.getContext('2d'), {
            type: 'pie',
            data: {
                labels: data.labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors.slice(0, data.labels.length),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                }
            }
        });
    };

    if (currentState.charts.haber) currentState.charts.haber.destroy();
    currentState.charts.haber = createChart(ctxHaber, 'Haber Adedi', data.haber_adedi);

    if (data.erisim && data.erisim.some(v => v > 0)) {
        if (currentState.charts.erisim) currentState.charts.erisim.destroy();
        currentState.charts.erisim = createChart(ctxErisim, 'Erişim', data.erisim);
    }

    if (data.reklam && data.reklam.some(v => v > 0)) {
        if (currentState.charts.reklam) currentState.charts.reklam.destroy();
        currentState.charts.reklam = createChart(ctxReklam, 'Reklam Eşdeğeri', data.reklam);
    }
}

window.downloadFinalReport = async function () {
    const btn = document.querySelector('.preview-actions .btn-primary');
    const originalContent = btn ? btn.innerHTML : '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İndiriliyor...';
        btn.disabled = true;
    }

    try {
        const formData = new FormData();
        currentState.reportFiles.forEach(file => {
            formData.append('files', file);
        });
        formData.append('layout_type', currentState.selectedLayout);

        const response = await fetch(`${API_BASE}/generate-report`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errText = await response.text();
            throw new Error('İndirme hatası');
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `MTM_Yonetici_Ozeti_${currentState.selectedLayout}.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showToast('Rapor başarıyla indirildi!', 'success');

    } catch (error) {
        console.error('Download error:', error);
        showToast(`İndirme hatası: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }
};

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

    const previewBtn = document.getElementById('preview-report-btn');
    if (previewBtn) {
        previewBtn.addEventListener('click', window.previewReport);
    }

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

    // Link Analysis
    const analyzeLinkBtn = document.getElementById('analyze-link-btn');
    if (analyzeLinkBtn) {
        analyzeLinkBtn.addEventListener('click', analyzeLink);
    }
    const linkInput = document.getElementById('link-url-input');
    if (linkInput) {
        linkInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') analyzeLink();
        });
    }
    const exportLinkBtn = document.getElementById('export-link-analysis-btn');
    if (exportLinkBtn) {
        exportLinkBtn.addEventListener('click', exportLinkAnalysis);
    }

    // OCR
    initOCRListeners();

    // Whisper
    initWhisperListeners();
});

// ============================================
// Link Analysis Service
// ============================================

async function analyzeLink() {
    const urlInput = document.getElementById('link-url-input');
    const url = urlInput?.value.trim();

    if (!url) {
        showToast('Lütfen bir URL girin', 'error');
        return;
    }

    const btn = document.getElementById('analyze-link-btn');
    const originalContent = btn?.innerHTML || '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analiz ediliyor...';
        btn.disabled = true;
    }

    try {
        const result = await apiCall('/analyze-link', {
            method: 'POST',
            body: JSON.stringify({ url })
        });

        // Add to history
        currentState.linkAnalysisHistory.unshift(result);

        // Display result
        displayLinkAnalysisResult(result);
        renderLinkAnalysisHistory();

        // Show export button
        const exportBtn = document.getElementById('export-link-analysis-btn');
        if (exportBtn) exportBtn.style.display = 'block';

        // Clear input
        urlInput.value = '';

        showToast('Analiz tamamlandı!', 'success');

    } catch (error) {
        console.error('Link analysis error:', error);
        showToast(`Analiz hatası: ${error.message}`, 'error');
    } finally {
        if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }
}

function displayLinkAnalysisResult(result) {
    const placeholder = document.getElementById('link-result-placeholder');
    const content = document.getElementById('link-result-content');

    if (placeholder) placeholder.style.display = 'none';
    if (content) {
        content.style.display = 'block';
        content.innerHTML = `
            <div class="result-card" style="animation: fadeIn 0.3s ease;">
                <div class="result-item">
                    <span class="label">Domain</span>
                    <span class="value">${result.domain}</span>
                </div>
                <div class="result-item">
                    <span class="label">Başlık</span>
                    <span class="value" style="font-size: 1rem;">${result.title || '-'}</span>
                </div>
                <div class="result-item">
                    <span class="label">Dil</span>
                    <span class="value">${result.language}</span>
                </div>
                <div class="result-item">
                    <span class="label">İçerik Türü</span>
                    <span class="value">${result.content_type}</span>
                </div>
                <div class="result-item">
                    <span class="label">Şehir</span>
                    <span class="value">${result.city || 'Genel'}</span>
                </div>
                <div class="result-item">
                    <span class="label">Kapsam</span>
                    <span class="value">${result.scope}</span>
                </div>
                <hr style="border-color: var(--border); margin: 0.5rem 0;">
                <div class="result-item">
                    <span class="label">Aylık Ziyaretçi</span>
                    <span class="value" style="color: var(--accent-blue);">${result.monthly_visitors || 'Veri Yok'}</span>
                </div>
                <div class="result-item">
                    <span class="label">Günlük Ziyaretçi</span>
                    <span class="value">${result.daily_visitors || '-'}</span>
                </div>
                <div class="result-item">
                    <span class="label">Günlük Sayfa Gör.</span>
                    <span class="value">${result.daily_pageviews || '-'}</span>
                </div>
                <div class="result-item">
                    <span class="label">Global Sıralama</span>
                    <span class="value" style="color: var(--accent-purple);">${result.global_rank || '-'}</span>
                </div>
                <hr style="border-color: var(--border); margin: 0.5rem 0;">
                <div class="result-item">
                    <span class="label">Güven Skoru</span>
                    <div class="confidence-bar"><div class="confidence-fill" style="width: ${(result.confidence * 100).toFixed(0)}%;"></div></div>
                </div>
            </div>
        `;
    }
}

function renderLinkAnalysisHistory() {
    const list = document.getElementById('link-history-list');
    if (!list) return;

    if (currentState.linkAnalysisHistory.length === 0) {
        list.innerHTML = '<p style="font-size: 0.8rem; color: var(--text-muted);">Henüz analiz yok</p>';
        return;
    }

    list.innerHTML = currentState.linkAnalysisHistory.slice(0, 10).map((item, idx) => `
        <div class="file-item" style="cursor: pointer;" onclick="displayLinkAnalysisResult(currentState.linkAnalysisHistory[${idx}])">
            <span class="file-name" title="${item.url}">${item.domain}</span>
            <span style="font-size: 0.7rem; color: var(--text-muted);">${item.content_type}</span>
        </div>
    `).join('');
}

async function exportLinkAnalysis() {
    if (currentState.linkAnalysisHistory.length === 0) {
        showToast('Dışa aktarılacak veri yok', 'error');
        return;
    }

    const btn = document.getElementById('export-link-analysis-btn');
    const originalContent = btn?.innerHTML || '';
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İndiriliyor...';
        btn.disabled = true;
    }

    try {
        const response = await fetch(`${API_BASE}/export-link-analysis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ analyses: currentState.linkAnalysisHistory })
        });

        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const urlObj = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = urlObj;
        a.download = 'yayin_analizi.xlsx';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(urlObj);
        document.body.removeChild(a);

        showToast('Excel indirildi!', 'success');

    } catch (error) {
        console.error('Export error:', error);
        showToast('Excel indirme hatası', 'error');
    } finally {
        if (btn) {
            btn.innerHTML = originalContent;
            btn.disabled = false;
        }
    }
}

// ============================================
// Newspaper OCR Service
// ============================================

function initOCRListeners() {
    const fileInput = document.getElementById('ocr-file-input');
    const uploadZone = document.getElementById('ocr-upload-zone');
    const extractBtn = document.getElementById('ocr-extract-btn');
    const searchInput = document.getElementById('ocr-search-input');

    if (fileInput) {
        fileInput.addEventListener('change', (e) => handleOCRFileSelect(e.target.files[0]));
    }

    if (uploadZone) {
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleOCRFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    if (extractBtn) {
        extractBtn.addEventListener('click', extractOCRText);
    }

    if (searchInput) {
        searchInput.addEventListener('input', debounce(performOCRSearch, 300));
    }
}

function handleOCRFileSelect(file) {
    console.log('File selected:', file);

    if (!file || !file.type.startsWith('image/')) {
        showToast('Lütfen geçerli bir görsel dosyası seçin', 'error');
        return;
    }

    showToast('Görsel yükleniyor...', 'info');

    const reader = new FileReader();
    reader.onload = (e) => {
        console.log('File loaded, size:', e.target.result.length);
        currentState.ocrImage = e.target.result;
        currentState.ocrResult = null;
        currentState.ocrZoom = 1.0;
        showOCRImagePreview();
    };
    reader.onerror = (e) => {
        console.error('File read error:', e);
        showToast('Dosya okuma hatası', 'error');
    };
    reader.readAsDataURL(file);
}

function showOCRImagePreview() {
    console.log('Showing OCR preview');

    const uploadZone = document.getElementById('ocr-upload-zone');
    const imageContainer = document.getElementById('ocr-image-container');
    const previewImage = document.getElementById('ocr-preview-image');
    const extractBtn = document.getElementById('ocr-extract-btn');
    const statsPanel = document.getElementById('ocr-stats');
    const textContainer = document.getElementById('ocr-text-container');
    const exportOptions = document.getElementById('ocr-export-options');
    const searchInput = document.getElementById('ocr-search-input');

    // Hide upload, show image
    uploadZone.style.display = 'none';
    imageContainer.style.display = 'flex';
    extractBtn.style.display = 'block';

    // Reset other panels
    statsPanel.style.display = 'none';
    exportOptions.style.display = 'none';
    searchInput.disabled = true;
    searchInput.value = '';
    textContainer.innerHTML = `
        <div class="result-placeholder">
            <i class="fas fa-magic"></i>
            <p>Görsel yüklendi.<br>"Metni Çıkar" butonuna tıklayın.</p>
        </div>
    `;

    // Set image
    previewImage.src = currentState.ocrImage;
    previewImage.onload = () => {
        console.log('Image loaded:', previewImage.naturalWidth, 'x', previewImage.naturalHeight);
        currentState.ocrZoom = 1.0;
        updateOCRZoom();
        showToast('Görsel hazır! "Metni Çıkar" butonuna tıklayın.', 'success');
    };
    previewImage.onerror = () => {
        console.error('Image load error');
        showToast('Görsel yüklenemedi', 'error');
    };
}

async function extractOCRText() {
    console.log('Extract OCR text called');

    if (!currentState.ocrImage) {
        showToast('Önce bir görsel yükleyin', 'error');
        return;
    }

    const btn = document.getElementById('ocr-extract-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor...';
    btn.disabled = true;

    try {
        console.log('Converting image to blob...');
        // Convert base64 to blob
        const response = await fetch(currentState.ocrImage);
        const blob = await response.blob();
        console.log('Blob created, size:', blob.size);

        // Create FormData
        const formData = new FormData();
        formData.append('file', blob, 'newspaper.png');

        console.log('Calling OCR API...');
        // Call API
        const result = await fetch(`${API_BASE}/ocr-newspaper`, {
            method: 'POST',
            body: formData
        });

        console.log('API response status:', result.status);
        const data = await result.json();
        console.log('OCR result:', data);

        if (data.success) {
            currentState.ocrResult = data;
            displayOCRResults();
            drawOCRBboxes();
            showToast(`${data.word_count} kelime, ${data.lines.length} satır bulundu!`, 'success');
        } else {
            console.error('OCR failed:', data.error);
            showToast(`OCR hatası: ${data.error}`, 'error');
        }

    } catch (error) {
        console.error('OCR error:', error);
        showToast('OCR işlemi başarısız: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

function displayOCRResults() {
    const data = currentState.ocrResult;
    if (!data) return;

    const textContainer = document.getElementById('ocr-text-container');
    const statsPanel = document.getElementById('ocr-stats');
    const exportOptions = document.getElementById('ocr-export-options');
    const searchInput = document.getElementById('ocr-search-input');

    // Show stats
    statsPanel.style.display = 'grid';
    document.getElementById('ocr-time').textContent = `${data.processing_time_ms.toFixed(0)} ms`;
    document.getElementById('ocr-word-count').textContent = data.word_count;
    document.getElementById('ocr-line-count').textContent = data.lines.length;

    // Enable search
    searchInput.disabled = false;

    // Show export options
    exportOptions.style.display = 'flex';

    // Render lines with word spans
    textContainer.innerHTML = data.lines.map((line, lineIdx) => {
        const wordsHtml = line.words.map((word, wordIdx) =>
            `<span class="ocr-word" data-line="${lineIdx}" data-word="${wordIdx}">${escapeHtml(word.text)}</span>`
        ).join(' ');

        return `<div class="ocr-line" data-line="${lineIdx}" onclick="highlightOCRLine(${lineIdx})">${wordsHtml}</div>`;
    }).join('');

    // Add click handlers for words
    textContainer.querySelectorAll('.ocr-word').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const lineIdx = parseInt(el.dataset.line);
            const wordIdx = parseInt(el.dataset.word);
            highlightOCRWord(lineIdx, wordIdx);
        });
    });
}

function drawOCRBboxes(highlightLine = -1, highlightWord = -1) {
    const canvas = document.getElementById('ocr-overlay-canvas');
    const img = document.getElementById('ocr-preview-image');
    const data = currentState.ocrResult;

    if (!canvas || !img || !data) return;

    const ctx = canvas.getContext('2d');
    const zoom = currentState.ocrZoom;

    // Set canvas size to match image
    canvas.width = img.naturalWidth * zoom;
    canvas.height = img.naturalHeight * zoom;
    canvas.style.width = `${img.naturalWidth * zoom}px`;
    canvas.style.height = `${img.naturalHeight * zoom}px`;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw all line bboxes
    data.lines.forEach((line, lineIdx) => {
        const isHighlighted = lineIdx === highlightLine;

        // Draw line bbox
        ctx.beginPath();
        ctx.strokeStyle = isHighlighted ? '#3b82f6' : 'rgba(236, 72, 153, 0.5)';
        ctx.lineWidth = isHighlighted ? 3 : 1;
        ctx.fillStyle = isHighlighted ? 'rgba(59, 130, 246, 0.15)' : 'rgba(236, 72, 153, 0.05)';

        const bbox = line.bbox;
        ctx.moveTo(bbox[0][0] * zoom, bbox[0][1] * zoom);
        ctx.lineTo(bbox[1][0] * zoom, bbox[1][1] * zoom);
        ctx.lineTo(bbox[2][0] * zoom, bbox[2][1] * zoom);
        ctx.lineTo(bbox[3][0] * zoom, bbox[3][1] * zoom);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Draw word bboxes if line is highlighted
        if (isHighlighted && highlightWord >= 0 && line.words[highlightWord]) {
            const wordBbox = line.words[highlightWord].bbox;
            ctx.beginPath();
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 2;
            ctx.fillStyle = 'rgba(16, 185, 129, 0.2)';
            ctx.moveTo(wordBbox[0][0] * zoom, wordBbox[0][1] * zoom);
            ctx.lineTo(wordBbox[1][0] * zoom, wordBbox[1][1] * zoom);
            ctx.lineTo(wordBbox[2][0] * zoom, wordBbox[2][1] * zoom);
            ctx.lineTo(wordBbox[3][0] * zoom, wordBbox[3][1] * zoom);
            ctx.closePath();
            ctx.fill();
            ctx.stroke();
        }
    });
}

window.highlightOCRLine = function(lineIdx) {
    // Update text UI
    document.querySelectorAll('.ocr-line').forEach(el => el.classList.remove('active'));
    const lineEl = document.querySelector(`.ocr-line[data-line="${lineIdx}"]`);
    if (lineEl) {
        lineEl.classList.add('active');
        lineEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Draw bboxes with highlight
    drawOCRBboxes(lineIdx);

    // Scroll image to show the line
    scrollToOCRBbox(lineIdx);
};

window.highlightOCRWord = function(lineIdx, wordIdx) {
    // Highlight in text
    document.querySelectorAll('.ocr-word').forEach(el => el.classList.remove('current-match'));
    const wordEl = document.querySelector(`.ocr-word[data-line="${lineIdx}"][data-word="${wordIdx}"]`);
    if (wordEl) {
        wordEl.classList.add('current-match');
    }

    // Draw bboxes with word highlight
    drawOCRBboxes(lineIdx, wordIdx);
};

function scrollToOCRBbox(lineIdx) {
    const data = currentState.ocrResult;
    if (!data || !data.lines[lineIdx]) return;

    const wrapper = document.getElementById('ocr-image-wrapper');
    const bbox = data.lines[lineIdx].bbox;
    const zoom = currentState.ocrZoom;

    // Calculate center of bbox
    const centerY = ((bbox[0][1] + bbox[2][1]) / 2) * zoom;
    const centerX = ((bbox[0][0] + bbox[1][0]) / 2) * zoom;

    // Scroll to center the bbox
    wrapper.scrollTo({
        top: centerY - wrapper.clientHeight / 2,
        left: centerX - wrapper.clientWidth / 2,
        behavior: 'smooth'
    });
}

// Zoom functions
window.zoomOCRImage = function(delta) {
    currentState.ocrZoom = Math.max(0.25, Math.min(3, currentState.ocrZoom + delta));
    updateOCRZoom();
};

window.resetOCRZoom = function() {
    currentState.ocrZoom = 1.0;
    updateOCRZoom();
};

function updateOCRZoom() {
    const img = document.getElementById('ocr-preview-image');
    const canvas = document.getElementById('ocr-overlay-canvas');
    const zoomLabel = document.getElementById('ocr-zoom-level');

    if (img && img.naturalWidth > 0) {
        const newWidth = img.naturalWidth * currentState.ocrZoom;
        const newHeight = img.naturalHeight * currentState.ocrZoom;

        img.style.width = `${newWidth}px`;
        img.style.height = `${newHeight}px`;

        if (canvas) {
            canvas.style.width = `${newWidth}px`;
            canvas.style.height = `${newHeight}px`;
        }
    }

    if (zoomLabel) {
        zoomLabel.textContent = `${Math.round(currentState.ocrZoom * 100)}%`;
    }

    // Redraw bboxes at new zoom
    if (currentState.ocrResult) {
        drawOCRBboxes();
    }
}

window.clearOCRImage = function() {
    currentState.ocrImage = null;
    currentState.ocrResult = null;
    currentState.ocrZoom = 1.0;
    currentState.ocrSearchMatches = [];
    currentState.ocrCurrentMatch = -1;

    // Reset UI
    const uploadZone = document.getElementById('ocr-upload-zone');
    const imageContainer = document.getElementById('ocr-image-container');
    const extractBtn = document.getElementById('ocr-extract-btn');
    const statsPanel = document.getElementById('ocr-stats');
    const textContainer = document.getElementById('ocr-text-container');
    const exportOptions = document.getElementById('ocr-export-options');
    const searchInput = document.getElementById('ocr-search-input');
    const searchCount = document.getElementById('ocr-search-count');
    const searchNav = document.getElementById('ocr-search-nav');

    uploadZone.style.display = 'flex';
    imageContainer.style.display = 'none';
    extractBtn.style.display = 'none';
    statsPanel.style.display = 'none';
    exportOptions.style.display = 'none';
    searchInput.disabled = true;
    searchInput.value = '';
    searchCount.textContent = '';
    searchNav.style.display = 'none';

    textContainer.innerHTML = `
        <div class="result-placeholder">
            <i class="fas fa-file-image"></i>
            <p>Henüz metin çıkarılmadı.<br>Sol taraftan görsel yükleyerek başlayın.</p>
        </div>
    `;

    // Clear file input
    document.getElementById('ocr-file-input').value = '';
};

// Search functions
function performOCRSearch() {
    const searchInput = document.getElementById('ocr-search-input');
    const searchCount = document.getElementById('ocr-search-count');
    const searchNav = document.getElementById('ocr-search-nav');
    const query = searchInput.value.trim().toLowerCase();

    // Reset previous highlights
    document.querySelectorAll('.ocr-word.search-match').forEach(el => el.classList.remove('search-match', 'current-match'));
    currentState.ocrSearchMatches = [];
    currentState.ocrCurrentMatch = -1;

    if (!query || !currentState.ocrResult) {
        searchCount.textContent = '';
        searchNav.style.display = 'none';
        return;
    }

    // Find matches
    const data = currentState.ocrResult;
    data.lines.forEach((line, lineIdx) => {
        line.words.forEach((word, wordIdx) => {
            if (word.text.toLowerCase().includes(query)) {
                currentState.ocrSearchMatches.push({ lineIdx, wordIdx });
                const wordEl = document.querySelector(`.ocr-word[data-line="${lineIdx}"][data-word="${wordIdx}"]`);
                if (wordEl) {
                    wordEl.classList.add('search-match');
                }
            }
        });
    });

    // Update UI
    const matchCount = currentState.ocrSearchMatches.length;
    searchCount.textContent = matchCount > 0 ? `${matchCount} sonuç` : 'Bulunamadı';
    searchNav.style.display = matchCount > 0 ? 'flex' : 'none';

    // Navigate to first match
    if (matchCount > 0) {
        navigateOCRSearch(0, true);
    }
}

window.navigateOCRSearch = function(direction, isFirst = false) {
    const matches = currentState.ocrSearchMatches;
    if (matches.length === 0) return;

    // Update current index
    if (isFirst) {
        currentState.ocrCurrentMatch = 0;
    } else {
        currentState.ocrCurrentMatch += direction;
        if (currentState.ocrCurrentMatch < 0) currentState.ocrCurrentMatch = matches.length - 1;
        if (currentState.ocrCurrentMatch >= matches.length) currentState.ocrCurrentMatch = 0;
    }

    // Remove previous current-match
    document.querySelectorAll('.ocr-word.current-match').forEach(el => el.classList.remove('current-match'));

    // Highlight current match
    const match = matches[currentState.ocrCurrentMatch];
    highlightOCRWord(match.lineIdx, match.wordIdx);

    // Scroll text container
    const wordEl = document.querySelector(`.ocr-word[data-line="${match.lineIdx}"][data-word="${match.wordIdx}"]`);
    if (wordEl) {
        wordEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // Scroll image
    scrollToOCRBbox(match.lineIdx);

    // Update count display
    document.getElementById('ocr-search-count').textContent = `${currentState.ocrCurrentMatch + 1}/${matches.length}`;
};

// Export functions
window.copyOCRText = function() {
    if (!currentState.ocrResult) return;

    const text = currentState.ocrResult.full_text;
    navigator.clipboard.writeText(text).then(() => {
        showToast('Metin panoya kopyalandı!', 'success');
    }).catch(() => {
        showToast('Kopyalama başarısız', 'error');
    });
};

window.downloadOCRText = function() {
    if (!currentState.ocrResult) return;

    const text = currentState.ocrResult.full_text;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gazete_metin.txt';
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);

    showToast('Dosya indirildi!', 'success');
};

// Helper functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================
// Whisper Speech-to-Text Service
// ============================================

function initWhisperListeners() {
    const fileInput = document.getElementById('whisper-file-input');
    const uploadZone = document.getElementById('whisper-upload-zone');
    const transcribeBtn = document.getElementById('whisper-transcribe-btn');

    if (fileInput) {
        fileInput.addEventListener('change', (e) => handleWhisperFileSelect(e.target.files[0]));
    }

    if (uploadZone) {
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                handleWhisperFileSelect(e.dataTransfer.files[0]);
            }
        });
    }

    if (transcribeBtn) {
        transcribeBtn.addEventListener('click', transcribeAudio);
    }

    // Check Whisper health on page load
    checkWhisperHealth();
}

async function checkWhisperHealth() {
    const healthStatus = document.getElementById('whisper-health-status');
    if (!healthStatus) return;

    const dot = healthStatus.querySelector('.health-dot');
    const text = healthStatus.querySelector('.health-text');

    try {
        const response = await apiCall('/whisper-health');

        if (response.status === 'ready') {
            dot.className = 'health-dot online';
            text.textContent = response.cuda_available
                ? `GPU: ${response.device}`
                : 'CPU Modu';
        } else {
            dot.className = 'health-dot offline';
            text.textContent = response.message || 'Whisper hazır değil';
        }
    } catch (error) {
        dot.className = 'health-dot offline';
        text.textContent = 'Bağlantı hatası';
    }
}

function handleWhisperFileSelect(file) {
    if (!file) return;

    // Validate file type
    const validTypes = ['audio/', 'video/mp4', 'video/webm'];
    if (!validTypes.some(t => file.type.startsWith(t))) {
        showToast('Desteklenmeyen dosya türü. MP3, WAV, M4A, FLAC, OGG, WEBM veya MP4 kullanın.', 'error');
        return;
    }

    currentState.whisperFile = file;
    currentState.whisperResult = null;

    // Show audio container
    const uploadZone = document.getElementById('whisper-upload-zone');
    const audioContainer = document.getElementById('whisper-audio-container');
    const transcribeBtn = document.getElementById('whisper-transcribe-btn');
    const fileName = document.getElementById('whisper-file-name');
    const audioPlayer = document.getElementById('whisper-audio-player');

    uploadZone.style.display = 'none';
    audioContainer.style.display = 'block';
    transcribeBtn.disabled = false;

    fileName.textContent = file.name;

    // Create object URL for audio player
    const audioUrl = URL.createObjectURL(file);
    audioPlayer.src = audioUrl;

    // Reset results
    resetWhisperResults();

    showToast('Dosya yüklendi! "Metne Dönüştür" butonuna tıklayın.', 'success');
}

window.clearWhisperFile = function() {
    currentState.whisperFile = null;
    currentState.whisperResult = null;

    const uploadZone = document.getElementById('whisper-upload-zone');
    const audioContainer = document.getElementById('whisper-audio-container');
    const transcribeBtn = document.getElementById('whisper-transcribe-btn');
    const audioPlayer = document.getElementById('whisper-audio-player');
    const fileInput = document.getElementById('whisper-file-input');

    uploadZone.style.display = 'flex';
    audioContainer.style.display = 'none';
    transcribeBtn.disabled = true;

    if (audioPlayer.src) {
        URL.revokeObjectURL(audioPlayer.src);
        audioPlayer.src = '';
    }

    fileInput.value = '';

    resetWhisperResults();
};

function resetWhisperResults() {
    const textContainer = document.getElementById('whisper-text-container');
    const segmentsContainer = document.getElementById('whisper-segments-container');
    const exportOptions = document.getElementById('whisper-export-options');
    const statsPanel = document.getElementById('whisper-stats');

    textContainer.innerHTML = `
        <div class="result-placeholder">
            <i class="fas fa-microphone"></i>
            <p>Henüz transkripsiyon yapılmadı.<br>Sol taraftan ses dosyası yükleyerek başlayın.</p>
        </div>
    `;

    segmentsContainer.style.display = 'none';
    exportOptions.style.display = 'none';
    statsPanel.style.display = 'none';
}

async function transcribeAudio() {
    if (!currentState.whisperFile) {
        showToast('Önce bir ses dosyası yükleyin', 'error');
        return;
    }

    const btn = document.getElementById('whisper-transcribe-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor...';
    btn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', currentState.whisperFile);
        formData.append('model', document.getElementById('whisper-model-select').value);

        const language = document.getElementById('whisper-language-select').value;
        if (language) {
            formData.append('language', language);
        }

        formData.append('task', document.getElementById('whisper-task-select').value);

        const response = await fetch(`${API_BASE}/transcribe`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            currentState.whisperResult = data;
            displayWhisperResults(data);
            showToast(`Transkripsiyon tamamlandı! ${data.segments.length} segment bulundu.`, 'success');
        } else {
            showToast(`Hata: ${data.error}`, 'error');
        }

    } catch (error) {
        console.error('Transcription error:', error);
        showToast('Transkripsiyon hatası: ' + error.message, 'error');
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

function displayWhisperResults(data) {
    const textContainer = document.getElementById('whisper-text-container');
    const segmentsContainer = document.getElementById('whisper-segments-container');
    const segmentsList = document.getElementById('whisper-segments-list');
    const exportOptions = document.getElementById('whisper-export-options');
    const statsPanel = document.getElementById('whisper-stats');

    // Calculate RTF (Real-Time Factor) - how many times faster than realtime
    const processingTimeSec = data.processing_time_ms / 1000;
    const rtf = data.duration / processingTimeSec;

    // Show stats
    statsPanel.style.display = 'grid';
    document.getElementById('whisper-time').textContent = `${processingTimeSec.toFixed(1)}s`;
    document.getElementById('whisper-duration').textContent = formatDuration(data.duration);
    document.getElementById('whisper-speed').textContent = `${rtf.toFixed(1)}x`;
    document.getElementById('whisper-model-used').textContent = data.model_used;

    // Add to history
    const historyEntry = {
        id: Date.now(),
        fileName: currentState.whisperFile?.name || 'Dosya',
        audioDuration: data.duration,
        processingTime: processingTimeSec,
        rtf: rtf,
        model: data.model_used,
        language: data.language,
        timestamp: new Date().toLocaleTimeString('tr-TR')
    };
    currentState.whisperHistory.unshift(historyEntry);
    if (currentState.whisperHistory.length > 20) {
        currentState.whisperHistory.pop(); // Keep max 20 entries
    }
    renderWhisperHistory();

    // Display full text
    textContainer.innerHTML = `
        <div class="whisper-full-text">
            <p>${escapeHtml(data.text)}</p>
        </div>
    `;

    // Display segments
    segmentsContainer.style.display = 'block';
    segmentsList.innerHTML = data.segments.map(seg => `
        <div class="whisper-segment" onclick="seekAudioTo(${seg.start})">
            <div class="segment-time">
                <span class="start">${formatTime(seg.start)}</span>
                <span class="separator">→</span>
                <span class="end">${formatTime(seg.end)}</span>
            </div>
            <div class="segment-text">${escapeHtml(seg.text)}</div>
        </div>
    `).join('');

    // Show export options
    exportOptions.style.display = 'flex';
}

function renderWhisperHistory() {
    const historyList = document.getElementById('whisper-history-list');
    if (!historyList) return;

    if (currentState.whisperHistory.length === 0) {
        historyList.innerHTML = '<div class="history-empty">Henüz istek yok</div>';
        return;
    }

    historyList.innerHTML = currentState.whisperHistory.map(entry => `
        <div class="history-item">
            <div class="history-item-header">
                <span class="history-file" title="${entry.fileName}">${entry.fileName.length > 15 ? entry.fileName.substring(0, 12) + '...' : entry.fileName}</span>
                <span class="history-time">${entry.timestamp}</span>
            </div>
            <div class="history-item-stats">
                <span class="history-stat">
                    <i class="fas fa-clock"></i> ${entry.processingTime.toFixed(1)}s
                </span>
                <span class="history-stat">
                    <i class="fas fa-music"></i> ${formatDuration(entry.audioDuration)}
                </span>
                <span class="history-stat rtf ${entry.rtf >= 10 ? 'fast' : entry.rtf >= 5 ? 'medium' : 'slow'}">
                    <i class="fas fa-bolt"></i> ${entry.rtf.toFixed(1)}x
                </span>
            </div>
        </div>
    `).join('');
}

window.clearWhisperHistory = function() {
    currentState.whisperHistory = [];
    renderWhisperHistory();
    showToast('Geçmiş temizlendi', 'success');
};

window.seekAudioTo = function(seconds) {
    const audioPlayer = document.getElementById('whisper-audio-player');
    if (audioPlayer) {
        audioPlayer.currentTime = seconds;
        audioPlayer.play();
    }
};

window.toggleSegmentsView = function() {
    const segmentsList = document.getElementById('whisper-segments-list');
    currentState.whisperSegmentsExpanded = !currentState.whisperSegmentsExpanded;
    segmentsList.style.display = currentState.whisperSegmentsExpanded ? 'flex' : 'none';
};

window.copyWhisperText = function() {
    if (!currentState.whisperResult) return;

    navigator.clipboard.writeText(currentState.whisperResult.text).then(() => {
        showToast('Metin panoya kopyalandı!', 'success');
    }).catch(() => {
        showToast('Kopyalama başarısız', 'error');
    });
};

window.downloadWhisperText = function() {
    if (!currentState.whisperResult) return;

    const text = currentState.whisperResult.text;
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, 'transkripsiyon.txt');
    showToast('Dosya indirildi!', 'success');
};

window.downloadWhisperSRT = function() {
    if (!currentState.whisperResult) return;

    const segments = currentState.whisperResult.segments;
    let srt = '';

    segments.forEach((seg, idx) => {
        srt += `${idx + 1}\n`;
        srt += `${formatSRTTime(seg.start)} --> ${formatSRTTime(seg.end)}\n`;
        srt += `${seg.text}\n\n`;
    });

    const blob = new Blob([srt], { type: 'text/plain;charset=utf-8' });
    downloadBlob(blob, 'altyazi.srt');
    showToast('SRT dosyası indirildi!', 'success');
};

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (mins > 0) {
        return `${mins}dk ${secs}sn`;
    }
    return `${secs}sn`;
}

function formatSRTTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')},${ms.toString().padStart(3, '0')}`;
}

function getLanguageName(code) {
    const langs = {
        'tr': 'Türkçe',
        'en': 'İngilizce',
        'de': 'Almanca',
        'fr': 'Fransızca',
        'es': 'İspanyolca',
        'ar': 'Arapça',
        'ru': 'Rusça',
        'ja': 'Japonca',
        'zh': 'Çince',
        'ko': 'Korece',
        'pt': 'Portekizce',
        'it': 'İtalyanca'
    };
    return langs[code] || code;
}
