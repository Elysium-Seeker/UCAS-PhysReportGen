/**
 * 大物实验报告生成器 - 前端逻辑
 * v2.0 - 支持历史记录、PDF 提取、Python 自动画图
 */

// 全局状态
const state = {
    currentStep: 1,
    sessionId: null,
    uploadedFiles: {
        guide: [],
        data_sheet: [],
        preview_report: []
    },
    latexInstalled: false,
    apiConfigured: false,
    apiSettings: {
        url: '',
        key: '',
        model: 'gpt-4o'
    }
};

// =====================================================
// 初始化
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
    initUploadZones();
    checkLatexStatus();
    loadApiSettings();
    setDefaultDate();

    // 监听历史记录模态框打开
    const historyBtn = document.querySelector('button[onclick="openModal(\'historyModal\')"]');
    if (historyBtn) {
        historyBtn.onclick = () => {
            openModal('historyModal');
            loadHistory();
        };
    }
});

function setDefaultDate() {
    const dateInput = document.getElementById('date');
    if (dateInput) {
        const today = new Date().toISOString().split('T')[0];
        dateInput.value = today;
    }
}

// =====================================================
// API 设置
// =====================================================

function loadApiSettings() {
    const saved = localStorage.getItem('apiSettings');
    if (saved) {
        try {
            state.apiSettings = JSON.parse(saved);
            document.getElementById('apiUrl').value = state.apiSettings.url || '';
            document.getElementById('apiKey').value = state.apiSettings.key || '';
            document.getElementById('apiModel').value = state.apiSettings.model || 'gpt-4o';
            updateApiStatus();
        } catch (e) {
            console.error('Failed to load API settings:', e);
        }
    }
}

function saveApiSettings() {
    state.apiSettings = {
        url: document.getElementById('apiUrl').value.trim(),
        key: document.getElementById('apiKey').value.trim(),
        model: document.getElementById('apiModel').value.trim() || 'gpt-4o'
    };

    localStorage.setItem('apiSettings', JSON.stringify(state.apiSettings));

    // 同步到后端
    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state.apiSettings)
    }).then(r => r.json()).then(result => {
        if (result.success) {
            showToast('API 设置已保存', 'success');
            updateApiStatus();
            closeModal('settingsModal');
        } else {
            showToast(result.message || '保存失败', 'error');
        }
    }).catch(err => {
        showToast('保存失败: ' + err.message, 'error');
    });
}

function updateApiStatus() {
    const statusEl = document.getElementById('apiStatus');
    const indicator = statusEl.querySelector('.status-indicator');
    const text = statusEl.querySelector('span:last-child');

    if (state.apiSettings.url && state.apiSettings.key) {
        state.apiConfigured = true;
        indicator.classList.remove('not-installed', 'checking');
        indicator.classList.add('installed');
        text.textContent = 'API 已配置';
    } else {
        state.apiConfigured = false;
        indicator.classList.remove('installed', 'checking');
        indicator.classList.add('not-installed');
        text.textContent = 'API 未配置';
    }
}

// =====================================================
// 步骤导航
// =====================================================

function goToStep(step) {
    // 验证当前步骤
    if (step > state.currentStep && !validateStep(state.currentStep)) {
        return;
    }

    // 更新状态
    state.currentStep = step;

    // 更新 UI
    document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
    document.getElementById(`step${step}`).classList.add('active');

    document.querySelectorAll('.nav-steps .step').forEach((el, index) => {
        el.classList.remove('active');
        if (index + 1 < step) {
            el.classList.add('completed');
        } else if (index + 1 === step) {
            el.classList.add('active');
        }
    });
}

function validateStep(step) {
    if (step === 1) {
        const requiredFields = ['name', 'studentId', 'experimentName', 'supervisor'];
        for (const field of requiredFields) {
            const input = document.getElementById(field);
            if (!input || !input.value.trim()) {
                showToast(`请填写${getFieldLabel(field)}`, 'warning');
                input?.focus();
                return false;
            }
        }
    }
    return true;
}

function getFieldLabel(field) {
    const labels = {
        name: '姓名',
        studentId: '学号',
        experimentName: '实验名称',
        supervisor: '指导教师'
    };
    return labels[field] || field;
}

// =====================================================
// 文件上传
// =====================================================

function initUploadZones() {
    const zones = document.querySelectorAll('.upload-zone');

    zones.forEach(zone => {
        const input = zone.querySelector('input[type="file"]');
        const type = zone.dataset.type;

        // 点击上传
        zone.addEventListener('click', () => input.click());

        // 选择文件
        input.addEventListener('change', (e) => {
            handleFiles(e.target.files, type);
        });

        // 拖拽上传
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files, type);
        });
    });
}

async function handleFiles(files, type) {
    if (!files || files.length === 0) return;

    const formData = new FormData();
    formData.append('type', type);

    if (state.sessionId) {
        formData.append('session_id', state.sessionId);
    }

    for (const file of files) {
        formData.append('files', file);
    }

    showLoading('正在上传文件...');

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            state.sessionId = result.session_id;
            state.uploadedFiles[type].push(...result.files);
            updateFileList(type);
            showToast('文件上传成功', 'success');
        } else {
            showToast(result.message || '上传失败', 'error');
        }
    } catch (error) {
        showToast('上传失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

function updateFileList(type) {
    const listId = {
        guide: 'guideFiles',
        data_sheet: 'dataFiles',
        preview_report: 'previewFiles'
    }[type];

    const listEl = document.getElementById(listId);
    if (!listEl) return;

    listEl.innerHTML = state.uploadedFiles[type].map((file, index) => `
        <div class="file-item">
            <span class="file-name">
                <span>📄</span>
                <span>${file.name}</span>
            </span>
            <span class="remove-btn" onclick="removeFile('${type}', ${index})">✕</span>
        </div>
    `).join('');
}

function removeFile(type, index) {
    state.uploadedFiles[type].splice(index, 1);
    updateFileList(type);
}

// =====================================================
// 报告生成
// =====================================================

async function generateReport() {
    // 验证信息
    if (!validateStep(1)) {
        goToStep(1);
        return;
    }

    // 检查 API 配置
    if (!state.apiConfigured) {
        showToast('请先配置 API 设置', 'warning');
        openModal('settingsModal');
        return;
    }

    // 检查是否上传了数据记录表
    if (state.uploadedFiles.data_sheet.length === 0) {
        showToast('请至少上传一张数据记录表照片', 'warning');
        return;
    }

    // 收集表单数据
    const data = {
        session_id: state.sessionId,
        name: document.getElementById('name').value,
        student_id: document.getElementById('studentId').value,
        class_num: document.getElementById('classNum').value || '1',
        group_num: document.getElementById('groupNum').value || '01',
        seat_num: document.getElementById('seatNum').value || '1',
        experiment_name: document.getElementById('experimentName').value,
        supervisor: document.getElementById('supervisor').value,
        date: document.getElementById('date').value,
        room: document.getElementById('room').value,
        is_makeup: document.getElementById('isMakeup').checked,
        additional_requirements: document.getElementById('additionalRequirements').value,
        // API 设置
        api_url: state.apiSettings.url,
        api_key: state.apiSettings.key,
        api_model: state.apiSettings.model
    };

    showLoading('正在启动生成任务...', 'AI 正在分析数据并生成图表，请稍候...');

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            // 开始轮询任务状态
            pollTaskStatus(result.task_id);
        } else {
            hideLoading();
            showToast(result.message || '启动失败', 'error');
        }
    } catch (error) {
        hideLoading();
        if (error.message.includes('Failed to fetch')) {
            showToast('无法连接到服务器。请检查：1. 后台程序是否正在运行 2. 网络连接是否正常', 'error');
        } else {
            showToast('请求失败: ' + error.message, 'error');
        }
    }
}

async function pollTaskStatus(taskId) {
    const pollInterval = 2000; // 2秒轮询一次

    try {
        const response = await fetch(`/api/task/${taskId}`);
        const result = await response.json();

        if (result.success && result.task) {
            const task = result.task;

            // 更新进度显示
            if (task.message) {
                document.getElementById('loadingText').textContent = task.message;
            }
            if (task.progress) {
                document.getElementById('loadingSubtext').textContent = `进度: ${task.progress}%`;
            }

            if (task.status === 'completed') {
                hideLoading();
                state.sessionId = task.result.session_id;
                showPdfPreview(task.result.pdf_url);
                enableDownloadButtons();
                goToStep(3);

                let message = task.result.message || '报告生成成功！';
                if (task.result.figures_generated > 0) {
                    message += ` 自动生成了 ${task.result.figures_generated} 张图表`;
                }
                showToast(message, 'success');

            } else if (task.status === 'failed') {
                hideLoading();
                showToast('生成失败: ' + (task.error || '未知错误'), 'error');
            } else {
                // 继续轮询
                setTimeout(() => pollTaskStatus(taskId), pollInterval);
            }
        } else {
            // 任务未找到或请求失败，重试
            setTimeout(() => pollTaskStatus(taskId), pollInterval);
        }
    } catch (error) {
        console.error('Polling error:', error);
        // 网络错误等，稍微延迟后重试
        setTimeout(() => pollTaskStatus(taskId), pollInterval + 1000);
    }
}

function showPdfPreview(url) {
    const placeholder = document.querySelector('.pdf-placeholder');
    const iframe = document.getElementById('pdfFrame');

    if (placeholder) placeholder.style.display = 'none';
    if (iframe) {
        iframe.style.display = 'block';
        iframe.src = url + '?t=' + Date.now();  // 添加时间戳避免缓存
    }
}

function enableDownloadButtons() {
    document.getElementById('downloadPdfBtn').disabled = false;
    document.getElementById('downloadTexBtn').disabled = false;
    document.getElementById('modifyBtn').disabled = false;
}

// =====================================================
// 历史记录
// =====================================================

async function loadHistory() {
    const listEl = document.getElementById('historyList');
    listEl.innerHTML = '<p style="text-align:center; padding: 20px;">加载中...</p>';

    try {
        const response = await fetch('/api/history');
        const result = await response.json();

        if (result.success && result.records.length > 0) {
            listEl.innerHTML = result.records.map(record => {
                const date = new Date(record.created_at).toLocaleString('zh-CN');
                const hasFigures = record.info?.has_figures ?
                    '<span class="tag">📊 含图表</span>' : '';

                return `
                <div class="history-item">
                    <div class="history-info">
                        <h4>${record.experiment_name || '未命名实验'}</h4>
                        <div class="meta">
                            <span>👤 ${record.student_name}</span>
                            <span>📅 ${date}</span>
                            ${hasFigures}
                        </div>
                    </div>
                    <div class="history-actions">
                        <button class="btn btn-sm btn-outline" onclick="restoreSession('${record.id}')">
                            查看
                        </button>
                        <button class="btn btn-sm btn-outline danger" onclick="deleteHistory('${record.id}')">
                            删除
                        </button>
                    </div>
                </div>
                `;
            }).join('');
        } else {
            listEl.innerHTML = `
                <div style="text-align: center; padding: 40px; color: var(--text-muted);">
                    <div style="font-size: 48px; margin-bottom: 16px;">📚</div>
                    <p>暂无历史记录</p>
                    <p style="font-size: 0.9rem;">生成的报告将自动保存在这里</p>
                </div>
            `;
        }
    } catch (error) {
        listEl.innerHTML = `<p style="color: red; text-align: center;">加载失败: ${error.message}</p>`;
    }
}

async function restoreSession(sessionId) {
    showLoading('正在恢复记录...');
    try {
        const response = await fetch(`/api/history/${sessionId}`);
        const result = await response.json();

        if (result.success) {
            state.sessionId = sessionId;
            closeModal('historyModal');
            showPdfPreview(result.pdf_url);
            enableDownloadButtons();

            // 填充表单
            if (result.record) {
                const r = result.record;
                document.getElementById('experimentName').value = r.experiment_name || '';
                document.getElementById('name').value = r.student_name || '';
                if (r.info) {
                    document.getElementById('supervisor').value = r.info.supervisor || '';
                    document.getElementById('date').value = r.info.date || '';
                }
            }

            goToStep(3);
            showToast('已加载历史报告', 'success');
        } else {
            showToast(result.message || '加载失败', 'error');
        }
    } catch (error) {
        showToast('加载出错: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteHistory(sessionId) {
    if (!confirm('确定要删除这条记录吗？删除后无法恢复。')) {
        return;
    }

    try {
        const response = await fetch(`/api/history/${sessionId}`, {
            method: 'DELETE'
        });
        const result = await response.json();

        if (result.success) {
            loadHistory(); // 重新加载列表
            showToast('记录已删除', 'success');
        } else {
            showToast('删除失败', 'error');
        }
    } catch (error) {
        showToast('删除出错: ' + error.message, 'error');
    }
}

// =====================================================
// 下载
// =====================================================

function downloadPdf() {
    if (state.sessionId) {
        window.location.href = `/api/download/${state.sessionId}`;
    }
}

function downloadTex() {
    if (state.sessionId) {
        window.location.href = `/api/download-tex/${state.sessionId}`;
    }
}

// =====================================================
// 修改报告
// =====================================================

async function modifyReport() {
    const modification = document.getElementById('modificationInput').value;

    if (!modification.trim()) {
        showToast('请输入修改要求', 'warning');
        return;
    }

    showLoading('正在处理修改请求...');

    try {
        const response = await fetch('/api/modify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: state.sessionId,
                modification: modification,
                api_url: state.apiSettings.url,
                api_key: state.apiSettings.key,
                api_model: state.apiSettings.model
            })
        });

        const result = await response.json();

        if (result.success) {
            if (result.pdf_url) {
                showPdfPreview(result.pdf_url);
            }
            showToast(result.message || '修改成功', 'success');
        } else {
            showToast(result.message || '修改失败', 'error');
        }
    } catch (error) {
        showToast('修改失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// =====================================================
// LaTeX 编辑器
// =====================================================

async function editLatex() {
    if (!state.sessionId) {
        showToast('请先生成报告', 'warning');
        return;
    }

    showLoading('正在加载 LaTeX 代码...');

    try {
        // 获取当前 LaTeX 内容
        const response = await fetch('/api/modify', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: state.sessionId,
                modification: ''
            })
        });

        const result = await response.json();

        if (result.tex_content) {
            document.getElementById('texEditor').value = result.tex_content;
            openModal('texModal');
        }
    } catch (error) {
        showToast('加载失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

async function updateTex() {
    const texContent = document.getElementById('texEditor').value;

    if (!texContent.trim()) {
        showToast('LaTeX 内容不能为空', 'warning');
        return;
    }

    showLoading('正在重新编译...');

    try {
        const response = await fetch('/api/update-tex', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: state.sessionId,
                tex_content: texContent
            })
        });

        const result = await response.json();

        if (result.success) {
            closeModal('texModal');
            showPdfPreview(result.pdf_url);
            showToast('更新成功！', 'success');
        } else {
            showToast(result.message || '编译失败', 'error');
        }
    } catch (error) {
        showToast('更新失败: ' + error.message, 'error');
    } finally {
        hideLoading();
    }
}

// =====================================================
// LaTeX 状态检查
// =====================================================

async function checkLatexStatus() {
    const statusEl = document.getElementById('latexStatus');
    const indicator = statusEl.querySelector('.status-indicator');
    const text = statusEl.querySelector('span:last-child');

    try {
        const response = await fetch('/api/check-latex');
        const result = await response.json();

        state.latexInstalled = result.installed;

        indicator.classList.remove('checking');
        if (result.installed) {
            indicator.classList.add('installed');
            text.textContent = 'LaTeX 已安装';
        } else {
            indicator.classList.add('not-installed');
            text.textContent = 'LaTeX 未安装';
            showToast('未检测到 LaTeX 环境，PDF 编译功能不可用', 'warning');
        }
    } catch (error) {
        indicator.classList.remove('checking');
        indicator.classList.add('not-installed');
        text.textContent = '检查失败';
    }
}

// =====================================================
// 模态框
// =====================================================

window.openModal = function (modalId) {
    document.getElementById(modalId).classList.add('active');
}

window.closeModal = function (modalId) {
    document.getElementById(modalId).classList.remove('active');
}

// 点击模态框外部关闭
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });
});

// ESC 键关闭模态框
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
    }
});

// =====================================================
// 加载指示器
// =====================================================

function showLoading(text = '加载中...', subtext = '') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingSubtext').textContent = subtext;
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}

// =====================================================
// Toast 消息
// =====================================================

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span>${getToastIcon(type)}</span>
            <span>${message}</span>
        </div>
    `;

    container.appendChild(toast);

    // 自动移除
    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function getToastIcon(type) {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    return icons[type] || icons.info;
}
