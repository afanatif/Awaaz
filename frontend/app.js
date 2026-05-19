// frontend/app.js

const socket = io();
const logConsole = document.getElementById('log-console');
const statusText = document.getElementById('system-status');
const statusDot = document.querySelector('.dot');
const liveBanner = document.getElementById('live-banner');
const sourceChips = document.getElementById('source-chips');

// UI Elements
const textInput = document.getElementById('text-input');
const sendBtn = document.getElementById('send-btn');
const recordBtn = document.getElementById('record-btn');
const transcriptionDisplay = document.getElementById('transcription-display');
const verdictPanel = document.getElementById('verdict-panel');
const actionsPanel = document.getElementById('actions-panel');
const dashboardPanel = document.getElementById('dashboard-panel');
const sourceIntelPanel = document.getElementById('source-intel-panel');
const sourceIntelList = document.getElementById('source-intel-list');
const filters = document.querySelectorAll('.filter');

let currentFilter = 'all';
const actionStatusByKey = new Map();
let latestPipelineDurationMs = null;

const sourceLabels = {
    NewsAPI: 'News',
    'Yahoo Finance': 'Market',
    Reddit: 'Reddit',
    SBP: 'Regulatory',
    Regulatory: 'Regulatory',
    'SBP + Exchange Rate': 'Regulatory/Macro',
    'SBP Website': 'Regulatory/Macro',
    'Exchange Rate API': 'Regulatory/Macro',
    'Business Recorder': 'Business Recorder',
    'PSX Data Portal': 'PSX',
    'Dawn Business': 'Dawn Business',
    'Profit Pakistan': 'Profit Pakistan',
};

// Setup filters
filters.forEach(f => {
    f.addEventListener('click', () => {
        filters.forEach(x => x.classList.remove('active'));
        f.classList.add('active');
        currentFilter = f.dataset.agent;
        applyFilter();
    });
});

function applyFilter() {
    const entries = logConsole.querySelectorAll('.log-entry');
    entries.forEach(e => {
        if (currentFilter === 'all' || e.dataset.agent === currentFilter || e.dataset.isError === 'true') {
            e.style.display = 'block';
        } else {
            e.style.display = 'none';
        }
    });
    logConsole.scrollTop = logConsole.scrollHeight;
}

function getStanceFromScore(score) {
    const numeric = typeof score === 'number' ? score : 0.5;
    if (numeric >= 0.6) return { key: 'contradicts', label: 'Contradicts' };
    if (numeric <= 0.4) return { key: 'supports', label: 'Supports' };
    return { key: 'unclear', label: 'Unclear' };
}

function escapeHtml(value) {
    return (value || '')
        .toString()
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function renderSourceIntelligence(analysis) {
    if (!analysis || analysis.event_type !== 'analysis_completed') return;

    const scores = analysis.source_scores || {};
    const evidenceBySource = analysis.source_evidence || {};
    const reasoningBySource = analysis.source_reasoning || {};

    const order = [
        'news',
        'market',
        'reddit',
        'regulatory',
        'business_recorder',
        'psx',
        'dawn_business',
        'profit_pakistan',
    ];
    const labels = {
        news: 'News',
        market: 'Market',
        reddit: 'Reddit',
        regulatory: 'Regulatory/Macro',
        business_recorder: 'Business Recorder',
        psx: 'PSX',
        dawn_business: 'Dawn Business',
        profit_pakistan: 'Profit Pakistan',
    };

    sourceIntelList.innerHTML = '';
    order.forEach(key => {
        if (!(key in scores)) return;
        const stance = getStanceFromScore(scores[key]);
        const evidence = evidenceBySource[key] || 'No detailed source summary available for this run.';
        const reasoning = reasoningBySource[key] || 'Reasoning chain unavailable for this source.';
        const score = Number(scores[key]);

        const card = document.createElement('div');
        card.className = 'source-intel-item';
        card.innerHTML = `
            <div class="source-intel-head">
                <span class="source-intel-name">${labels[key]}</span>
                <span class="source-intel-badge ${stance.key}">${stance.label}</span>
            </div>
            <div class="source-intel-line"><strong>This source says:</strong> ${escapeHtml(evidence)}</div>
            <div class="source-intel-note"><strong>Why:</strong> ${escapeHtml(reasoning)}</div>
            <div class="source-intel-note">Analyst contradiction score: ${isNaN(score) ? 'N/A' : score.toFixed(2)}</div>
        `;
        sourceIntelList.appendChild(card);
    });

    if (sourceIntelList.children.length > 0) {
        sourceIntelPanel.classList.remove('hidden');
    }
}

function renderStrategistReasoning(reasoningByAction) {
    if (!reasoningByAction || typeof reasoningByAction !== 'object') return;

    const actionsList = document.getElementById('actions-list');
    if (!actionsList) return;

    const existingReasoningDiv = document.getElementById('strategist-reasoning-panel');
    if (existingReasoningDiv) existingReasoningDiv.remove();

    const reasoningDiv = document.createElement('div');
    reasoningDiv.id = 'strategist-reasoning-panel';
    reasoningDiv.className = 'strategist-reasoning-section';
    reasoningDiv.innerHTML = '<h2>Strategist Narrative</h2>';

    const order = Object.keys(reasoningByAction).sort();
    order.forEach(key => {
        const r = reasoningByAction[key];
        const card = document.createElement('div');
        card.className = 'strategist-reasoning-item';
        card.innerHTML = `
            <div class="strategist-reasoning-head">
                <span class="strategist-action-name">${escapeHtml(r.action_name || 'Action')}</span>
                <span class="badge type">${escapeHtml(r.action_type || 'unknown')}</span>
            </div>
            <div class="strategist-reasoning-body">
                <div class="strategist-section"><strong>What to do:</strong> ${escapeHtml(r.what || '')}</div>
                <div class="strategist-section"><strong>Why:</strong> ${escapeHtml(r.why || '')}</div>
                <div class="strategist-section"><strong>Based on:</strong> ${escapeHtml(r.based_on || '')}</div>
            </div>
        `;
        reasoningDiv.appendChild(card);
    });

    actionsList.parentNode.insertBefore(reasoningDiv, actionsList);
}

function renderSourceIntelligenceFromLogs() {
    fetch('/api/logs')
        .then(r => r.json())
        .then(all => {
            if (!Array.isArray(all)) return;
            const analysis = [...all].reverse().find(e => e && e.event_type === 'analysis_completed');
            if (!analysis) return;
            renderSourceIntelligence(analysis);
        })
        .catch(() => {});
}

// Socket.io Log Receiver
socket.on('log_entry', (data) => {
    appendLog(data);
    updatePipelineUI(data);
});

function appendLog(data) {
    const div = document.createElement('div');
    div.className = 'log-entry';
    div.dataset.agent = data.agent_name;
    const isError = !!data.error || (data.event_type && data.event_type.includes('fail'));
    div.dataset.isError = isError;

    const ts = data.timestamp.substring(11, 23); // HH:MM:SS.sss
    let html = `<span class="ts">[${ts}]</span>`;
    html += `<span class="agent">[${data.agent_name.toUpperCase()}]</span>`;
    
    let eventStr = data.event_type;
    if (data.duration_ms) eventStr += ` (${data.duration_ms}ms)`;
    html += `<span class="event">${eventStr}</span>`;

    const summary = data.output_summary || data.input_summary;
    if (summary) {
        let sumStr = typeof summary === 'object' ? JSON.stringify(summary) : summary;
        if (sumStr.length > 150) sumStr = sumStr.substring(0, 147) + '...';
        html += `<span class="summary">${sumStr}</span>`;
    }

    if (data.error) {
        html += `<span class="error">ERROR: ${data.error}</span>`;
    }

    div.innerHTML = html;
    logConsole.appendChild(div);
    
    // Auto scroll if filtered
    if (currentFilter === 'all' || currentFilter === data.agent_name || isError) {
        logConsole.scrollTop = logConsole.scrollHeight;
    } else {
        div.style.display = 'none';
    }
}

// State Machine for UI
function resetUI() {
    logConsole.innerHTML = '';
    transcriptionDisplay.classList.add('hidden');
    verdictPanel.classList.add('hidden');
    actionsPanel.classList.add('hidden');
    dashboardPanel.classList.add('hidden');
    sourceIntelPanel.classList.add('hidden');
    document.getElementById('actions-list').innerHTML = '';
    sourceIntelList.innerHTML = '';
    document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
    sourceChips.innerHTML = '';
    actionStatusByKey.clear();
    latestPipelineDurationMs = null;
    statusText.innerText = 'Processing...';
    statusDot.classList.add('pulse');
    liveBanner.classList.remove('complete');
    liveBanner.classList.add('running');
    liveBanner.innerText = 'Pipeline running… waiting for first agent output.';
    
    // Reset gauge
    const gaugeFill = document.getElementById('gauge-fill');
    gaugeFill.style.strokeDashoffset = 125;
}

function normalizeActionKey(raw) {
    return (raw || '').toString().trim().toLowerCase().replace(/\s+/g, '-');
}

function getActionNameFromInput(inputSummary) {
    if (!inputSummary) return '';
    const bracketed = inputSummary.match(/\[\d+\]\s*(?:[^:]+:\s*)?(.+)/);
    if (bracketed && bracketed[1]) return bracketed[1].trim();
    const colon = inputSummary.match(/:\s*(.+)$/);
    if (colon && colon[1]) return colon[1].trim();
    return inputSummary.trim();
}

function updateSourceChip(data) {
    if (!data || !data.input_summary) return;
    if (!data.event_type || !data.event_type.startsWith('source_fetch_')) return;

    const raw = data.input_summary;
    let label = sourceLabels[raw] || raw;
    if (raw.includes('SBP') || raw.includes('Exchange Rate')) {
        label = 'Regulatory/Macro';
    }
    const id = `source-${normalizeActionKey(label)}`;
    let chip = document.getElementById(id);
    if (!chip) {
        chip = document.createElement('span');
        chip.className = 'source-chip';
        chip.id = id;
        sourceChips.appendChild(chip);
    }

    const ok = data.event_type === 'source_fetch_completed';
    chip.classList.remove('ok', 'fail');
    chip.classList.add(ok ? 'ok' : 'fail');
    chip.innerText = `${label}: ${ok ? 'ok' : 'fallback'}`;
}

function syncFromHistory() {
    fetch('/api/logs')
        .then(r => r.json())
        .then(entries => {
            if (!Array.isArray(entries)) return;
            const lastStartup = entries.map((e, i) => ({ e, i }))
                .filter(x => x.e && x.e.event_type === 'startup')
                .map(x => x.i)
                .pop();
            const scoped = typeof lastStartup === 'number' ? entries.slice(lastStartup) : entries;

            scoped.forEach(entry => {
                appendLog(entry);
                updatePipelineUI(entry);
            });
            applyFilter();
        })
        .catch(() => {});
}

function updatePipelineUI(log) {
    updateSourceChip(log);

    // Activate agent cards
    if (log.agent_name && log.agent_name !== 'system') {
        document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
        const card = document.getElementById(`agent-${log.agent_name}`);
        if (card) card.classList.add('active');
        if (log.agent_name !== 'monitor') {
            const label = log.agent_name.charAt(0).toUpperCase() + log.agent_name.slice(1);
            liveBanner.classList.add('running');
            liveBanner.classList.remove('complete');
            liveBanner.innerText = `This agent is running: ${label}`;
        }
    }

    if (log.event_type === 'startup') {
        statusText.innerText = 'Processing...';
        statusDot.classList.add('pulse');
    }

    if (log.event_type === 'whisper_transcription_completed' || log.event_type === 'language_translation') {
        transcriptionDisplay.innerText = `"${log.output_summary}"`;
        transcriptionDisplay.classList.remove('hidden');
    }

    if (log.event_type === 'analysis_completed') {
        verdictPanel.classList.remove('hidden');
        renderSourceIntelligence(log);
        const vText = document.getElementById('verdict-text');
        vText.innerText = log.verdict.replace('_', ' ').toUpperCase();
        vText.className = 'verdict-text ' + log.verdict;
        const verdictExplanation = document.getElementById('verdict-explanation');
        verdictExplanation.innerText = `Contradiction score: ${Math.round((log.contradiction_score || 0.5) * 100)}%`;
        
        // Gauge (125 = empty, 0 = full red)
        const score = log.contradiction_score || 0.5;
        const fill = document.getElementById('gauge-fill');
        fill.style.strokeDashoffset = 125 - (score * 125);
        
        if (score < 0.35) fill.style.stroke = 'var(--agent-4)';
        else if (score < 0.60) fill.style.stroke = 'var(--agent-5)';
        else fill.style.stroke = 'var(--error)';
    }

    if (log.event_type === 'action_generated') {
        actionsPanel.classList.remove('hidden');
        const list = document.getElementById('actions-list');
        const div = document.createElement('div');
        div.className = 'action-item';
        const actionKey = normalizeActionKey(log.action_name);
        div.id = `action-ui-${actionKey}`;
        actionStatusByKey.set(actionKey, `status-${actionKey}`);
        div.innerHTML = `
            <div class="action-header">
                <span class="action-name">${log.action_name}</span>
                <div class="action-badges">
                    <span class="badge type">${log.action_type}</span>
                    <span class="badge status pending" id="status-${actionKey}">Pending</span>
                </div>
            </div>
        `;
        list.appendChild(div);
    }

    if (log.event_type === 'strategy_generation_completed' && log.raw && log.raw.strategist_reasoning) {
        renderStrategistReasoning(log.raw.strategist_reasoning);
    }

    if (log.event_type === 'execution_completed' || log.event_type === 'execution_failed') {
        const rawActionName = getActionNameFromInput(log.input_summary);
        if (rawActionName) {
            const actionKey = normalizeActionKey(rawActionName);
            const statusId = actionStatusByKey.get(actionKey) || `status-${actionKey}`;
            const statusBadge = document.getElementById(statusId);
            if (statusBadge) {
                if (log.event_type === 'execution_completed') {
                    statusBadge.innerText = 'Completed';
                    statusBadge.className = 'badge status completed';
                } else {
                    statusBadge.innerText = 'Failed';
                    statusBadge.className = 'badge status failed';
                }
            }
        }
    }

    if (log.event_type === 'pipeline_completed') {
        document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('active'));
        statusText.innerText = 'Complete';
        statusDot.classList.remove('pulse');
        latestPipelineDurationMs = typeof log.duration_ms === 'number' ? log.duration_ms : null;
        liveBanner.classList.remove('running');
        liveBanner.classList.add('complete');
        liveBanner.innerText = '🎉 Pipeline complete! Outcome saved and dashboard updated.';
        fetchOutcome();
    }
}

function fetchOutcome() {
    fetch('/api/outcome')
        .then(r => r.json())
        .then(data => {
            dashboardPanel.classList.remove('hidden');
            
            document.getElementById('alloc-before').innerText = data.metrics_changed.portfolio_allocation.before;
            document.getElementById('alloc-after').innerText = data.metrics_changed.portfolio_allocation.after;
            
            document.getElementById('risk-before').innerText = data.metrics_changed.risk_score.before;
            document.getElementById('risk-after').innerText = data.metrics_changed.risk_score.after;
            
            document.getElementById('token-val').innerText = data.token_estimate;
            const fallbackLatency = Math.round(data.latency_summary.execution_ms + data.latency_summary.ingestion_ms + (data.latency_summary.monitor_ms || 0));
            const totalLatency = latestPipelineDurationMs !== null ? Math.round(latestPipelineDurationMs) : fallbackLatency;
            document.getElementById('latency-val').innerText = `${totalLatency}ms`;
            
            document.getElementById('summary-en').innerText = data.summary_en;
            document.getElementById('summary-ur').innerText = data.summary_ur;

            const verdictExplanation = document.getElementById('verdict-explanation');
            if (verdictExplanation && data.summary_en) {
                verdictExplanation.innerText = data.summary_en;
            }
        })
        .catch(e => console.error("Could not fetch outcome", e));
}

// Inputs
sendBtn.addEventListener('click', () => {
    const text = textInput.value.trim();
    if (!text) return;
    
    resetUI();
    fetch('/api/process/text', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text})
    }).then(() => syncFromHistory());
    textInput.value = '';
});

textInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendBtn.click();
});

// Voice Recording (Web Audio API)
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

async function startRecording() {
    if (isRecording) return;
    resetUI();
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        isRecording = true;
        
        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };
        
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.wav');
            
            fetch('/api/process/voice', {
                method: 'POST',
                body: formData
            }).then(() => syncFromHistory());
            
            // Stop tracks
            stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        recordBtn.classList.add('recording');
        recordBtn.querySelector('span').innerText = 'Recording... Release to send';
    } catch (err) {
        console.error("Microphone access denied", err);
        alert("Microphone access is required for voice input.");
        isRecording = false;
    }
}

recordBtn.addEventListener('mousedown', () => {
    startRecording();
});

recordBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    startRecording();
}, { passive: false });

recordBtn.addEventListener('mouseup', () => stopRecording());
recordBtn.addEventListener('mouseleave', () => stopRecording());
recordBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    stopRecording();
}, { passive: false });

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('span').innerText = 'Hold to Speak';
        isRecording = false;
    }
}

syncFromHistory();
