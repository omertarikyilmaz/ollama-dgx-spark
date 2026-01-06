/**
 * Ollama Haber Sınıflandırıcı - Frontend Application
 * Handles template management, classification, and KV cache settings
 */

const API_BASE = 'http://localhost:8000';

// State
let templates = [];
let selectedTemplateId = null;
let settings = {
    kv_cache_type: 'q8_0',
    num_parallel: 4,
    default_keep_alive: '10m'
};

// ============================================
// Utility Functions
// ============================================

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

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// ============================================
// Health Check & Status
// ============================================

async function checkHealth() {
    const statusEl = document.getElementById('ollama-status');
    const dotEl = statusEl.querySelector('.status-dot');
    const textEl = statusEl.querySelector('.status-text');

    try {
        const health = await apiCall('/health');

        if (health.ollama === 'ok') {
            dotEl.className = 'status-dot connected';
            textEl.textContent = 'Bağlı';
        } else {
            dotEl.className = 'status-dot error';
            textEl.textContent = 'Ollama Bağlantı Hatası';
        }
    } catch (error) {
        dotEl.className = 'status-dot error';
        textEl.textContent = 'API Bağlantı Hatası';
    }
}

// ============================================
// Templates
// ============================================

async function loadTemplates() {
    try {
        const data = await apiCall('/templates');
        templates = data.templates;
        renderTemplates();
    } catch (error) {
        showToast('Şablonlar yüklenemedi', 'error');
    }
}

function renderTemplates() {
    const list = document.getElementById('templates-list');

    if (templates.length === 0) {
        list.innerHTML = `
            <div class="template-item" style="text-align: center; color: var(--text-muted);">
                Henüz şablon yok.<br>Yeni bir şablon oluşturun.
            </div>
        `;
        return;
    }

    list.innerHTML = templates.map(t => `
        <div class="template-item ${t.id === selectedTemplateId ? 'active' : ''}" 
             data-id="${t.id}" 
             onclick="selectTemplate('${t.id}')">
            <h3>${t.name}</h3>
            <div class="template-model">${t.model}</div>
        </div>
    `).join('');
}

function selectTemplate(id) {
    selectedTemplateId = id;
    const template = templates.find(t => t.id === id);

    if (template) {
        document.getElementById('selected-template-name').textContent = template.name;
        document.getElementById('classify-btn').disabled = false;
        renderTemplates();

        // Load template into editor
        loadTemplateIntoEditor(template);
    }
}

function loadTemplateIntoEditor(template) {
    document.getElementById('template-id').value = template.id || '';
    document.getElementById('template-name').value = template.name || '';
    document.getElementById('template-model').value = template.model || 'qwen2.5:32b-instruct-q4_K_M';
    document.getElementById('template-prompt').value = template.prompt_desc || '';
    document.getElementById('template-keepalive').value = template.keep_alive || '10m';
    document.getElementById('template-ctx').value = template.num_ctx || 4096;

    // Render tools/fields
    renderToolsEditor(template.tools || {});

    // Show delete button if editing existing template
    document.getElementById('delete-template-btn').style.display = template.id ? 'block' : 'none';

    // Switch to editor tab
    switchTab('editor');
}

function renderToolsEditor(tools) {
    const container = document.getElementById('tools-editor');
    container.innerHTML = '';

    Object.entries(tools).forEach(([fieldName, config]) => {
        addToolField(fieldName, config);
    });
}

function addToolField(name = '', config = {}) {
    const container = document.getElementById('tools-editor');
    const fieldId = `field-${Date.now()}`;

    const fieldHtml = `
        <div class="tool-field" id="${fieldId}">
            <div class="tool-field-header">
                <input type="text" placeholder="Alan Adı (örn: Kategori)" value="${name}" class="field-name-input">
                <button type="button" class="remove-field-btn" onclick="removeToolField('${fieldId}')">×</button>
            </div>
            <div class="form-group">
                <label>Açıklama</label>
                <input type="text" placeholder="Bu alanın açıklaması" value="${config.description || ''}" class="field-desc-input">
            </div>
            <div class="enum-editor">
                <label>Seçenekler (her satırda bir tane, boş bırakılırsa serbest metin)</label>
                <textarea class="field-enum-input" placeholder="Örn:
POZİTİF
NEGATİF
NÖTR">${(config.enum || []).join('\n')}</textarea>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', fieldHtml);
}

function removeToolField(fieldId) {
    document.getElementById(fieldId).remove();
}

function collectToolsFromEditor() {
    const tools = {};
    const fields = document.querySelectorAll('.tool-field');

    fields.forEach(field => {
        const name = field.querySelector('.field-name-input').value.trim();
        if (!name) return;

        const description = field.querySelector('.field-desc-input').value.trim();
        const enumText = field.querySelector('.field-enum-input').value.trim();
        const enumValues = enumText ? enumText.split('\n').map(s => s.trim()).filter(s => s) : null;

        tools[name] = {
            description: description,
            type: 'string'
        };

        if (enumValues && enumValues.length > 0) {
            tools[name].enum = enumValues;
        }
    });

    return tools;
}

async function saveTemplate(e) {
    e.preventDefault();

    const templateId = document.getElementById('template-id').value;
    const template = {
        name: document.getElementById('template-name').value,
        model: document.getElementById('template-model').value,
        prompt_desc: document.getElementById('template-prompt').value,
        tools: collectToolsFromEditor(),
        keep_alive: document.getElementById('template-keepalive').value,
        num_ctx: parseInt(document.getElementById('template-ctx').value)
    };

    try {
        if (templateId) {
            await apiCall(`/templates/${templateId}`, {
                method: 'PUT',
                body: JSON.stringify(template)
            });
            showToast('Şablon güncellendi', 'success');
        } else {
            await apiCall('/templates', {
                method: 'POST',
                body: JSON.stringify(template)
            });
            showToast('Şablon oluşturuldu', 'success');
        }

        await loadTemplates();
        resetEditor();
    } catch (error) {
        showToast('Şablon kaydedilemedi', 'error');
    }
}

async function deleteTemplate() {
    const templateId = document.getElementById('template-id').value;
    if (!templateId) return;

    if (!confirm('Bu şablonu silmek istediğinize emin misiniz?')) return;

    try {
        await apiCall(`/templates/${templateId}`, { method: 'DELETE' });
        showToast('Şablon silindi', 'success');

        if (selectedTemplateId === templateId) {
            selectedTemplateId = null;
            document.getElementById('selected-template-name').textContent = 'Seçiniz...';
            document.getElementById('classify-btn').disabled = true;
        }

        await loadTemplates();
        resetEditor();
    } catch (error) {
        showToast('Şablon silinemedi', 'error');
    }
}

function resetEditor() {
    document.getElementById('template-id').value = '';
    document.getElementById('template-name').value = '';
    document.getElementById('template-prompt').value = '';
    document.getElementById('tools-editor').innerHTML = '';
    document.getElementById('delete-template-btn').style.display = 'none';
}

// ============================================
// Classification
// ============================================

async function classifyNews() {
    if (!selectedTemplateId) {
        showToast('Lütfen bir şablon seçin', 'error');
        return;
    }

    const newsText = document.getElementById('news-input').value.trim();
    if (!newsText) {
        showToast('Lütfen haber metni girin', 'error');
        return;
    }

    const btn = document.getElementById('classify-btn');
    const originalContent = btn.innerHTML;
    btn.innerHTML = '<span class="loading"></span> Sınıflandırılıyor...';
    btn.disabled = true;

    try {
        const result = await apiCall('/classify', {
            method: 'POST',
            body: JSON.stringify({
                template_id: selectedTemplateId,
                news_text: newsText
            })
        });

        displayResult(result);
    } catch (error) {
        showToast('Sınıflandırma hatası', 'error');
        document.getElementById('result-content').innerHTML = `
            <div style="color: var(--danger);">Hata: ${error.message}</div>
        `;
    } finally {
        btn.innerHTML = originalContent;
        btn.disabled = false;
    }
}

function displayResult(response) {
    const content = document.getElementById('result-content');
    const responseTime = document.getElementById('response-time');
    const tokensPerSec = document.getElementById('tokens-per-sec');

    if (!response.success) {
        content.innerHTML = `<div style="color: var(--danger);">Hata: ${response.error}</div>`;
        return;
    }

    // Update metrics
    responseTime.textContent = `${response.response_time_ms?.toFixed(0) || '--'}ms`;
    tokensPerSec.textContent = `${response.tokens_per_second?.toFixed(1) || '--'} t/s`;

    // Render result fields
    const result = response.result;
    if (typeof result === 'object') {
        content.innerHTML = Object.entries(result).map(([key, value]) => `
            <div class="result-field">
                <span class="field-name">${key}</span>
                <span class="field-value">${value}</span>
            </div>
        `).join('');
    } else {
        content.innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
    }
}

// ============================================
// Settings
// ============================================

async function loadSettings() {
    try {
        settings = await apiCall('/settings');

        document.getElementById('kv-cache-type').value = settings.kv_cache_type;
        document.getElementById('num-parallel').value = settings.num_parallel;
        document.getElementById('keep-alive').value = settings.default_keep_alive;
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    const newSettings = {
        kv_cache_type: document.getElementById('kv-cache-type').value,
        num_parallel: parseInt(document.getElementById('num-parallel').value),
        default_keep_alive: document.getElementById('keep-alive').value
    };

    try {
        settings = await apiCall('/settings', {
            method: 'PUT',
            body: JSON.stringify(newSettings)
        });
        showToast('Ayarlar kaydedildi', 'success');
    } catch (error) {
        showToast('Ayarlar kaydedilemedi', 'error');
    }
}

// ============================================
// Tab Management
// ============================================

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });
}

// ============================================
// Event Listeners
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize
    checkHealth();
    loadTemplates();
    loadSettings();

    // Periodic health check
    setInterval(checkHealth, 30000);

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // New template button
    document.getElementById('new-template-btn').addEventListener('click', () => {
        resetEditor();
        switchTab('editor');
    });

    // Template form
    document.getElementById('template-form').addEventListener('submit', saveTemplate);
    document.getElementById('delete-template-btn').addEventListener('click', deleteTemplate);
    document.getElementById('add-field-btn').addEventListener('click', () => addToolField());

    // Classification
    document.getElementById('classify-btn').addEventListener('click', classifyNews);
    document.getElementById('clear-btn').addEventListener('click', () => {
        document.getElementById('news-input').value = '';
        document.getElementById('result-content').innerHTML = '<div class="placeholder">Sonuç burada görünecek...</div>';
    });

    // Settings
    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);
});
