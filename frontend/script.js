const API_BASE = "";
let userId = localStorage.getItem('nyayavani_user_id') || crypto.randomUUID();
localStorage.setItem('nyayavani_user_id', userId);

let currentSessionId = null;
let ragSessionId = localStorage.getItem('nyayavani_rag_session') || null;
let pipelineResult = null;
let userProfile = JSON.parse(localStorage.getItem('nyayavani_profile')) || null;

// Voice Variables
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// DOM Elements
const navLinks = document.querySelectorAll('.nav-pill');
const tabs = document.querySelectorAll('.tab-content');
const processBtn = document.getElementById('process-btn');
const resultsNav = document.getElementById('nav-results');

// Cycling Placeholders for Search Instrument
const placeholders = [
    "Describe your grievance (e.g., 'Severe sewage overflow in Ward 14 causing health hazards for 2 weeks...')",
    "Describe your grievance (e.g., 'Uncleaned garbage pileup in main market area for over 10 days...')",
    "Describe your grievance (e.g., 'Defective streetlights causing safety issues at night on Sector 5 main road...')",
    "Describe your grievance (e.g., 'Unexplained high water bill charges and delayed RTI response from water department...')"
];
let placeholderIdx = 0;

// Theme Toggle
let currentTheme = localStorage.getItem('nyayavani_theme') || 'light';

document.addEventListener('DOMContentLoaded', () => {
    applyTheme(currentTheme);

    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            localStorage.setItem('nyayavani_theme', currentTheme);
            applyTheme(currentTheme);
        });
    }

    if (userProfile) {
        updateProfileUI();
    }
    
    // Cycle Placeholders
    setInterval(() => {
        const textarea = document.getElementById('complaint_text');
        if (textarea && document.activeElement !== textarea && !textarea.value) {
            placeholderIdx = (placeholderIdx + 1) % placeholders.length;
            textarea.placeholder = placeholders[placeholderIdx];
        }
    }, 4500);

    // Navbar Tab Navigation
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const targetTab = link.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });

    // Nav Profile Chip Click
    const profileChip = document.querySelector('.profile-chip');
    if (profileChip) {
        profileChip.addEventListener('click', () => switchTab('dashboard'));
    }

    // Save Profile
    const saveBtn = document.getElementById('save-profile-btn');
    if (saveBtn) saveBtn.addEventListener('click', saveProfile);

    // Voice Recording Trigger
    const voiceTriggerBtn = document.getElementById('voice-trigger-btn');
    if (voiceTriggerBtn) {
        voiceTriggerBtn.addEventListener('click', toggleRecording);
    }

    // Process Complaint
    if (processBtn) {
        processBtn.addEventListener('click', runPipeline);
    }

    // Quick Scenario Chips
    document.querySelectorAll('.quick-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const text = chip.getAttribute('data-text');
            const textarea = document.getElementById('complaint_text');
            if (textarea) {
                textarea.value = text;
                textarea.focus();
            }
        });
    });

    // Studio Document Tabs
    document.querySelectorAll('.studio-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.studio-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDocument(btn.getAttribute('data-doc'));
        });
    });

    // Department Authority Tabs
    document.querySelectorAll('.dept-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.dept-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDepartment(btn.getAttribute('data-dept'));
        });
    });

    // Chat Action Buttons
    const sendRag = document.getElementById('send-rag');
    if (sendRag) sendRag.addEventListener('click', sendRagQuery);

    const tabSendRag = document.getElementById('tab-send-rag');
    if (tabSendRag) tabSendRag.addEventListener('click', sendTabRagQuery);

    const sendFollowup = document.getElementById('send-followup');
    if (sendFollowup) sendFollowup.addEventListener('click', sendFollowupQuestion);
    
    // Expert Chat Widget Toggle
    const chatWidgetBtn = document.getElementById('chat-widget-btn');
    const chatWidgetWindow = document.getElementById('chat-widget-window');
    const closeChatBtn = document.getElementById('close-chat-btn');

    if (chatWidgetBtn && chatWidgetWindow) {
        chatWidgetBtn.addEventListener('click', () => {
            chatWidgetWindow.classList.toggle('widget-hidden');
        });
        if (closeChatBtn) {
            closeChatBtn.addEventListener('click', () => {
                chatWidgetWindow.classList.add('widget-hidden');
            });
        }
    }

    // Document Studio Actions
    const copyBtn = document.getElementById('copy-doc');
    if (copyBtn) copyBtn.addEventListener('click', copyDoc);
    
    const downloadBtn = document.getElementById('download-doc');
    if (downloadBtn) downloadBtn.addEventListener('click', downloadDoc);

    const pdfBtn = document.getElementById('export-pdf-doc');
    if (pdfBtn) pdfBtn.addEventListener('click', exportPdf);

    const printBtn = document.getElementById('print-doc');
    if (printBtn) printBtn.addEventListener('click', printDoc);

    // Docked Bar Back Button
    const dockedBack = document.getElementById('docked-back-btn');
    if (dockedBack) {
        dockedBack.addEventListener('click', () => {
            switchTab('complaint');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // Scroll listener for sticky docked search bar
    window.addEventListener('scroll', () => {
        const searchInstrument = document.querySelector('.search-instrument-glass');
        const dockedBar = document.getElementById('docked-search-bar');
        if (searchInstrument && dockedBar && pipelineResult) {
            const rect = searchInstrument.getBoundingClientRect();
            if (rect.bottom < 0) {
                dockedBar.classList.remove('hidden');
            } else {
                dockedBar.classList.add('hidden');
            }
        }
    });
});

function applyTheme(theme) {
    document.body.setAttribute('data-theme', theme);
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.innerHTML = theme === 'dark' ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
    }
}

function isProfileComplete() {
    if (!userProfile) return false;
    const isNameValid = userProfile.name && userProfile.name.trim() !== "" && userProfile.name !== "Citizen";
    const isAddressValid = userProfile.address && userProfile.address.trim() !== "";
    return isNameValid && isAddressValid;
}

function switchTab(tabId) {
    navLinks.forEach(l => l.classList.remove('active'));
    tabs.forEach(t => t.classList.remove('active'));

    const activeLink = document.querySelector(`.nav-pill[data-tab="${tabId}"]`);
    const activeTab = document.getElementById(tabId);

    if (activeLink) activeLink.classList.add('active');
    if (activeTab) activeTab.classList.add('active');

    if (tabId === 'history') loadHistory();

    const widgetContainer = document.querySelector('.floating-chat-container');
    if (widgetContainer) {
        if (tabId === 'results' || tabId === 'rag') {
            widgetContainer.style.display = 'block';
        } else {
            widgetContainer.style.display = 'none';
        }
    }
}

function saveProfile() {
    userProfile = {
        name: document.getElementById('user_name').value || "Citizen",
        state: document.getElementById('user_state').value,
        address: document.getElementById('user_address').value || "Not provided",
        contact: document.getElementById('user_contact').value || "Not provided"
    };
    localStorage.setItem('nyayavani_profile', JSON.stringify(userProfile));
    updateProfileUI();
    alert('✅ Profile saved! You can now file your grievance.');
    switchTab('complaint');
}

function updateProfileUI() {
    const navName = document.getElementById('nav-user-name');
    if (navName) navName.innerText = userProfile.name || "Citizen";
    
    if (document.getElementById('user_name')) {
        document.getElementById('user_name').value = userProfile.name || "";
        document.getElementById('user_state').value = userProfile.state || "Delhi";
        document.getElementById('user_address').value = userProfile.address || "";
        document.getElementById('user_contact').value = userProfile.contact || "";
    }
}

async function toggleRecording() {
    const statusText = document.getElementById('record-status');
    const micBtn = document.getElementById('voice-trigger-btn');
    const voiceBar = document.getElementById('voice-input-container');

    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                await sendAudioToBackend(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;
            if (micBtn) micBtn.classList.add('recording');
            if (voiceBar) voiceBar.classList.remove('hidden');
            if (statusText) statusText.innerText = "[RECORDING...] Speak clearly in English or Hindi";
        } catch (err) {
            alert("Microphone permission denied: " + err.message);
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        if (micBtn) micBtn.classList.remove('recording');
        if (statusText) statusText.innerText = "Transcribing voice with Whisper STT...";
    }
}

async function sendAudioToBackend(blob) {
    const statusText = document.getElementById('record-status');
    const voiceBar = document.getElementById('voice-input-container');
    const formData = new FormData();
    formData.append('file', blob, 'recording.wav');

    try {
        const res = await fetch(`${API_BASE}/voice/transcribe`, {
            method: 'POST',
            body: formData
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        if (data.text) {
            const textarea = document.getElementById('complaint_text');
            if (textarea) textarea.value = data.text;
            if (voiceBar) voiceBar.classList.add('hidden');
        } else {
            throw new Error("Transcription empty");
        }
    } catch (err) {
        alert("Transcription Error: " + err.message);
        if (voiceBar) voiceBar.classList.add('hidden');
    }
}

function updateTerminalChecklist(stepIdx, text) {
    for (let i = 1; i <= 5; i++) {
        const row = document.getElementById(`term-step-${i}`);
        if (row) {
            if (i < stepIdx) {
                row.className = "terminal-row completed";
                row.querySelector('.term-status').innerText = "[COMPLETED]";
            } else if (i === stepIdx) {
                row.className = "terminal-row";
                row.querySelector('.term-status').innerText = "[RUNNING]";
            } else {
                row.className = "terminal-row pending";
                row.querySelector('.term-status').innerText = "[PENDING]";
            }
        }
    }
}

async function runPipeline() {
    const textarea = document.getElementById('complaint_text');
    const text = textarea ? textarea.value : "";
    if (!text.trim()) return alert("Please provide a description of your grievance.");

    if (!isProfileComplete()) {
        alert("📋 Profile Action Required:\n\nPlease complete your Citizen Profile (Full Name, Address, State & Contact) before filing an official legal case file.");
        switchTab('dashboard');
        return;
    }

    const loader = processBtn.querySelector('.loader');
    const btnText = processBtn.querySelector('span');

    processBtn.disabled = true;
    if (loader) loader.classList.remove('hidden');
    if (btnText) btnText.innerText = "Processing Case...";

    const terminalCard = document.getElementById('loading-steps');
    if (terminalCard) terminalCard.classList.remove('hidden');
    updateTerminalChecklist(1, "1. Categorizing grievance & assessing severity...");

    let stepIndex = 1;
    const stepInterval = setInterval(() => {
        stepIndex++;
        if (stepIndex <= 5) {
            updateTerminalChecklist(stepIndex, `Step ${stepIndex}`);
        }
    }, 4000);

    try {
        const res = await fetch(`${API_BASE}/complaint/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                complaint_text: text,
                user_state: userProfile.state,
                user_name: userProfile.name,
                user_address: userProfile.address,
                user_contact: userProfile.contact,
                user_id: userId
            })
        });

        if (!res.ok) throw new Error(await res.text());

        let jobData = await res.json();
        currentSessionId = jobData.session_id;
        const currentJobId = jobData.job_id;
        
        while (jobData.status === "processing") {
            await new Promise(r => setTimeout(r, 2500));
            const statusRes = await fetch(`${API_BASE}/complaint/status/${currentJobId}`);
            if (!statusRes.ok) throw new Error("Server Error: " + await statusRes.text());
            jobData = await statusRes.json();
        }

        if (jobData.status === "error") throw new Error(jobData.error);
        if (!jobData.result) throw new Error("Result missing");

        pipelineResult = jobData.result;
        
        updateTerminalChecklist(6, "Done");

        renderResults();
        switchTab('results');

        // Update Docked Bar Header
        const dockedText = document.getElementById('docked-grievance-text');
        const dockedBadge = document.getElementById('docked-severity-badge');
        if (dockedText && dockedBadge) {
            dockedText.innerText = text;
            const sev = (pipelineResult.analysis.severity || 'Medium').toUpperCase();
            dockedBadge.innerText = sev;
            dockedBadge.style.color = sev === 'CRITICAL' ? 'var(--severity-critical)' : sev === 'HIGH' ? 'var(--saffron)' : 'var(--india-green)';
        }

    } catch (err) {
        alert("⚠️ Guardrail Alert: " + err.message);
    } finally {
        clearInterval(stepInterval);
        if (terminalCard) terminalCard.classList.add('hidden');
        processBtn.disabled = false;
        if (loader) loader.classList.add('hidden');
        if (btnText) btnText.innerText = "File Case";
    }
}

function renderResults() {
    const analysis = pipelineResult.analysis;
    const outputs = pipelineResult.outputs;
    const department = pipelineResult.department;

    document.getElementById('res-category').innerText = (analysis.department_category || "N/A").replace(/_/g, ' ').toUpperCase();
    
    const sev = document.getElementById('res-severity');
    const sevDot = document.getElementById('res-severity-dot');
    const severityStr = (analysis.severity || "Medium").toUpperCase();
    
    if (sev) sev.innerText = severityStr;
    if (sevDot) {
        const c = severityStr === 'CRITICAL' ? 'var(--severity-critical)' : severityStr === 'HIGH' ? 'var(--saffron)' : 'var(--india-green)';
        sevDot.style.backgroundColor = c;
    }
    
    // Render Escalation Path Stepper with Arrows
    const escalationContainer = document.getElementById('escalation-path');
    const path = department.escalation_path || [];
    escalationContainer.innerHTML = '';
    if (path.length) {
        path.forEach((step, index) => {
            const isLast = index === path.length - 1;
            escalationContainer.innerHTML += `
                <div class="roadmap-step-wrapper">
                    <div class="roadmap-step-card">
                        <span class="roadmap-step-num font-mono">STEP 0${index + 1}</span>
                        <span class="roadmap-step-title font-heading">${step}</span>
                    </div>
                    ${!isLast ? '<div class="roadmap-arrow"><i class="fa-solid fa-arrow-right"></i></div>' : ''}
                </div>
            `;
        });
    } else {
        escalationContainer.innerHTML = '<p class="text-muted font-mono">No specific escalation path found.</p>';
    }

    // Render Legal Rights Cards
    const rightsContainer = document.getElementById('legal-rights-list');
    const rights = outputs.key_legal_rights || [];
    rightsContainer.innerHTML = '';
    if (rights.length) {
        rights.forEach((right, i) => {
            rightsContainer.innerHTML += `
                <div class="right-item-card">
                    <i class="fa-solid fa-scale-balanced scale-instrument-icon" style="margin-top:0"></i>
                    <div>
                        <span class="right-act-tag font-mono">CITIZEN RIGHT #${i+1}</span>
                        <div class="right-title font-heading">${right}</div>
                    </div>
                </div>
            `;
        });
    } else {
        rightsContainer.innerHTML = '<p class="text-muted font-mono">General legal rights applicable under Indian Law.</p>';
    }

    renderDepartment('central');
    renderDocument('letter');
}

function renderDepartment(type) {
    if (!pipelineResult || !pipelineResult.department) return;
    const dept = pipelineResult.department;
    let deptData = {};
    
    if (type === 'central') {
        deptData = dept.central_details || dept.central || {};
    } else if (type === 'state') {
        deptData = dept.state_details || dept.state || {};
    }

    const orgName = deptData.organization || deptData.name || dept.department_name || "N/A";
    const helpline = deptData.helpline || "N/A";
    const portal = deptData.portal || "N/A";

    const nameEl = document.getElementById('dept-name');
    const helplineEl = document.getElementById('dept-helpline');
    const portalLink = document.getElementById('dept-portal');

    if (nameEl) nameEl.innerText = orgName;
    if (helplineEl) helplineEl.innerText = helpline;
    
    if (portalLink) {
        if (portal && portal !== "N/A") {
            portalLink.href = portal;
            portalLink.style.display = "inline-flex";
        } else {
            portalLink.style.display = "none";
        }
    }
}

function renderDocument(type) {
    if (!pipelineResult || !pipelineResult.outputs) return;
    const outputs = pipelineResult.outputs;
    let content = "";
    
    if (type === 'letter') {
        content = outputs.formal_letter || "Drafting formal letter...";
    } else if (type === 'email') {
        if (outputs.email && typeof outputs.email === 'object') {
            const toStr = outputs.email.to || "N/A";
            const subjStr = outputs.email.subject || "N/A";
            const bodyStr = outputs.email.body || "";
            content = `TO: ${toStr}\nSUBJECT: ${subjStr}\n\n${bodyStr}`;
        } else if (typeof outputs.email === 'string') {
            content = outputs.email;
        } else {
            content = outputs.email_draft || "Drafting email payload...";
        }
    } else if (type === 'twitter') {
        content = outputs.twitter_post || outputs.twitter || "Drafting X post...";
    }

    const docContent = document.getElementById('doc-content');
    if (docContent) docContent.innerText = content;
}

function copyDoc() {
    const content = document.getElementById('doc-content').innerText;
    navigator.clipboard.writeText(content);
    alert("Copied document text to clipboard!");
}

function downloadDoc() {
    const content = document.getElementById('doc-content').innerText;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'NyayaVaani_Case_Document.txt';
    a.click();
}

function exportPdf() {
    const content = document.getElementById('doc-content').innerText;
    if (!content.trim()) return alert("No document content to export.");

    const activeTabBtn = document.querySelector('.studio-tab.active');
    const docType = activeTabBtn ? activeTabBtn.innerText.trim() : "Legal_Document";

    const opt = {
        margin:       0.5,
        filename:     `NyayaVaani_${docType.replace(/[^a-zA-Z0-9]/g, '_')}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2 },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };

    const container = document.createElement('div');
    container.style.padding = '20px';
    container.style.fontFamily = 'Georgia, serif';
    container.style.whiteSpace = 'pre-wrap';
    container.innerHTML = `<h2 style="color: #F2F1ED; border-bottom: 2px solid #FF9933; padding-bottom: 8px;">NyayaVaani Sovereign Legal Document</h2><br>${content}`;

    if (window.html2pdf) {
        window.html2pdf().set(opt).from(container).save();
    } else {
        window.print();
    }
}

function printDoc() {
    window.print();
}

async function sendRagQuery() {
    const input = document.getElementById('rag-input');
    const text = input ? input.value : "";
    if (!text.trim()) return;

    const chatHistory = document.getElementById('rag-chat-history');
    chatHistory.innerHTML += `<div class="user-message-plain font-mono">${text}</div>`;
    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'bot-message-glass';
    botMessageDiv.innerHTML = `<span class="bot-avatar font-mono">AI</span><div class="message-body">...</div>`;
    chatHistory.appendChild(botMessageDiv);

    try {
        const res = await fetch(`${API_BASE}/rag/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text, session_id: ragSessionId })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let botText = "";
        const bodyEl = botMessageDiv.querySelector('.message-body');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            botText += decoder.decode(value, { stream: true });
            bodyEl.innerHTML = marked.parse(botText);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    } catch (err) {
        botMessageDiv.querySelector('.message-body').innerText = "⚠️ Error: " + err.message;
    }
}

async function sendTabRagQuery() {
    const input = document.getElementById('tab-rag-input');
    const text = input ? input.value : "";
    if (!text.trim()) return;

    const chatHistory = document.getElementById('tab-rag-chat-history');
    chatHistory.innerHTML += `<div class="user-message-plain font-mono">${text}</div>`;
    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'bot-message-glass';
    botMessageDiv.innerHTML = `<span class="bot-avatar font-mono">AI</span><div class="message-body">...</div>`;
    chatHistory.appendChild(botMessageDiv);

    try {
        const res = await fetch(`${API_BASE}/rag/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: text, session_id: ragSessionId })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let botText = "";
        const bodyEl = botMessageDiv.querySelector('.message-body');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            botText += decoder.decode(value, { stream: true });
            bodyEl.innerHTML = marked.parse(botText);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    } catch (err) {
        botMessageDiv.querySelector('.message-body').innerText = "⚠️ Error: " + err.message;
    }
}

async function sendFollowupQuestion() {
    const input = document.getElementById('followup-input');
    const text = input ? input.value : "";
    if (!text.trim()) return;

    const chatHistory = document.getElementById('complaint-chat-history');
    chatHistory.innerHTML += `<div class="user-message-plain font-mono">${text}</div>`;
    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    const botMessageDiv = document.createElement('div');
    botMessageDiv.className = 'bot-message-glass';
    botMessageDiv.innerHTML = `<div class="message-body">...</div>`;
    chatHistory.appendChild(botMessageDiv);

    try {
        const res = await fetch(`${API_BASE}/complaint/followup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId, question: text })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let botText = "";
        const bodyEl = botMessageDiv.querySelector('.message-body');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            botText += decoder.decode(value, { stream: true });
            bodyEl.innerHTML = marked.parse(botText);
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    } catch (err) {
        botMessageDiv.querySelector('.message-body').innerText = "⚠️ Error: " + err.message;
    }
}

async function loadHistory() {
    const container = document.getElementById('history-container');
    if (!container) return;

    container.innerHTML = '<p class="text-muted font-mono">Loading cases...</p>';

    try {
        const res = await fetch(`${API_BASE}/history/${userId}`);
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        
        container.innerHTML = '';
        if (data.history && data.history.length) {
            data.history.forEach(item => {
                const category = item.pipeline_result?.analysis?.department_category || "General";
                container.innerHTML += `
                    <div class="glass-card module-card">
                        <div class="stat-box" style="margin-bottom:0.75rem;">
                            <label class="font-mono">CASE ID: ${item.session_id.slice(0, 8)}</label>
                            <span class="stat-value font-heading">${category.replace(/_/g, ' ').toUpperCase()}</span>
                        </div>
                        <p class="font-mono" style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:1rem;">${item.complaint_text.slice(0, 100)}...</p>
                        <button class="btn-saffron-action" onclick="reloadHistoryItem('${item.session_id}')" style="padding:0.4rem 0.85rem; font-size:0.8rem;">View Case</button>
                    </div>
                `;
            });
        } else {
            container.innerHTML = '<p class="text-muted font-mono">No previous cases found.</p>';
        }
    } catch (err) {
        container.innerHTML = `<p class="text-muted font-mono">Error: ${err.message}</p>`;
    }
}

function reloadHistoryItem(sessionId) {
    fetch(`${API_BASE}/history/${userId}`)
        .then(res => res.json())
        .then(data => {
            const item = data.history.find(h => h.session_id === sessionId);
            if (item && item.pipeline_result) {
                currentSessionId = sessionId;
                pipelineResult = item.pipeline_result;
                renderResults();
                switchTab('results');
            }
        });
}
