const API_BASE = "";
let userId = localStorage.getItem('nyayavani_user_id') || crypto.randomUUID();
localStorage.setItem('nyayavani_user_id', userId);

let currentSessionId = null;
let pipelineResult = null;
let userProfile = JSON.parse(localStorage.getItem('nyayavani_profile')) || null;

// Voice Variables
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// DOM Elements
const navLinks = document.querySelectorAll('.nav-links li');
const tabs = document.querySelectorAll('.tab-content');
const processBtn = document.getElementById('process-btn');
const resultsNav = document.getElementById('nav-results');

// Mode Toggles
const btnTextMode = document.getElementById('btn-text-mode');
const btnVoiceMode = document.getElementById('btn-voice-mode');
const textContainer = document.getElementById('text-input-container');
const voiceContainer = document.getElementById('voice-input-container');
const voiceTriggerBtn = document.getElementById('voice-trigger-btn');

document.addEventListener('DOMContentLoaded', () => {
    if (userProfile) {
        updateProfileUI();
    }
    
    // Sidebar Navigation
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            const targetTab = link.getAttribute('data-tab');
            switchTab(targetTab);
        });
    });

    // Save Profile
    document.getElementById('save-profile-btn').addEventListener('click', saveProfile);

    // Mode Selection
    if (btnTextMode) btnTextMode.addEventListener('click', () => setInputMode('text'));
    if (btnVoiceMode) btnVoiceMode.addEventListener('click', () => setInputMode('voice'));

    // Voice Recording
    if (voiceTriggerBtn) {
        voiceTriggerBtn.addEventListener('click', toggleRecording);
    }

    // Process Complaint
    processBtn.addEventListener('click', runPipeline);

    // Default to text mode
    setInputMode('text');

    // Results Tab Logic
    document.querySelectorAll('.doc-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.doc-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDocument(btn.getAttribute('data-doc'));
        });
    });

    document.querySelectorAll('.dept-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.dept-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDepartment(btn.getAttribute('data-dept'));
        });
    });

    // Chat
    document.getElementById('send-followup').addEventListener('click', sendFollowup);
    document.getElementById('send-rag').addEventListener('click', sendRagQuery);
    
    // Expert Chat Widget Toggle
    const chatWidgetBtn = document.getElementById('chat-widget-btn');
    const chatWidgetWindow = document.getElementById('chat-widget-window');
    const closeChatBtn = document.getElementById('close-chat-btn');

    if (chatWidgetBtn && chatWidgetWindow) {
        chatWidgetBtn.addEventListener('click', () => {
            chatWidgetWindow.classList.toggle('widget-hidden');
        });
        closeChatBtn.addEventListener('click', () => {
            chatWidgetWindow.classList.add('widget-hidden');
        });
    }
    
    document.querySelectorAll('.sample-q').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('rag-input').value = btn.innerText;
            sendRagQuery();
        });
    });

    document.getElementById('copy-doc').addEventListener('click', copyDoc);
    document.getElementById('download-doc').addEventListener('click', downloadDoc);
});

function setInputMode(mode) {
    if (mode === 'text') {
        btnTextMode.classList.add('active');
        btnVoiceMode.classList.remove('active');
        textContainer.classList.remove('hidden');
        voiceContainer.classList.add('hidden');
    } else {
        btnVoiceMode.classList.add('active');
        btnTextMode.classList.remove('active');
        voiceContainer.classList.remove('hidden');
        textContainer.classList.add('hidden');
    }
}

async function toggleRecording() {
    const statusText = document.getElementById('record-status');
    const recordingHint = document.getElementById('recording-hint');

    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                await uploadAudio(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;
            voiceTriggerBtn.classList.add('recording');
            statusText.innerText = "Listening...";
            recordingHint.innerText = "Click again to stop and transcribe.";
        } catch (err) {
            alert("Microphone access denied or not available.");
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        voiceTriggerBtn.classList.remove('recording');
        statusText.innerText = "Processing...";
        recordingHint.innerText = "Sending audio to Whisper AI...";
    }
}

async function uploadAudio(blob) {
    const statusText = document.getElementById('record-status');
    const recordingHint = document.getElementById('recording-hint');
    
    const formData = new FormData();
    formData.append('audio', blob, 'recording.webm');

    try {
        const res = await fetch(`${API_BASE}/transcribe`, {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            const textarea = document.getElementById('complaint_text');
            textarea.value = (textarea.value + " " + data.text).trim();
            
            // Switch back to text mode to show results
            setInputMode('text');
            statusText.innerText = "Click the microphone to start speaking";
            recordingHint.innerText = "Your voice will be transcribed into text automatically.";
        } else {
            throw new Error("Transcription failed");
        }
    } catch (err) {
        alert("Error transcribing audio: " + err.message);
        statusText.innerText = "Click the microphone to start speaking";
        recordingHint.innerText = "Your voice will be transcribed into text automatically.";
    }
}


function switchTab(tabId) {
    navLinks.forEach(l => l.classList.remove('active'));
    tabs.forEach(t => t.classList.remove('active'));

    const activeLink = document.querySelector(`.nav-links li[data-tab="${tabId}"]`);
    const activeTab = document.getElementById(tabId);

    if (activeLink) activeLink.classList.add('active');
    if (activeTab) activeTab.classList.add('active');

    if (tabId === 'history') loadHistory();

    const widgetContainer = document.querySelector('.floating-chat-container');
    if (widgetContainer) {
        if (tabId === 'results') {
            widgetContainer.style.display = 'flex';
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
    alert('Profile saved! You can now file a complaint.');
    switchTab('complaint');
}

function updateProfileUI() {
    document.getElementById('display-name').innerText = userProfile.name;
    document.getElementById('display-state').innerText = userProfile.state;
    document.querySelectorAll('.user-name-span').forEach(el => el.innerText = userProfile.name);
    
    if (document.getElementById('user_name')) {
        document.getElementById('user_name').value = userProfile.name;
        document.getElementById('user_state').value = userProfile.state;
        document.getElementById('user_address').value = userProfile.address;
        document.getElementById('user_contact').value = userProfile.contact;
    }
}

async function runPipeline() {
    const text = document.getElementById('complaint_text').value;
    if (!text.trim()) return alert("Please provide a description of your problem (type it or use voice).");

    if (!userProfile) {
        alert("Please complete your profile in the Dashboard first.");
        return switchTab('dashboard');
    }

    const loader = processBtn.querySelector('.loader');
    const btnText = processBtn.querySelector('span');

    processBtn.disabled = true;
    loader.classList.remove('hidden');
    btnText.innerText = "Analyzing Grievance...";

    const steps = [
        "✨ Analyzer Agent is analyzing your complaint...",
        "✨ Support Router Agent is finding government departments...",
        "✨ Researcher Agent is studying legal acts...",
        "✨ Writer Agent is drafting your formal letter...",
        "✨ Social Media Agent is escalating the issue..."
    ];
    let stepIndex = 0;
    const loadingSteps = document.getElementById('loading-steps');
    const loadingText = document.getElementById('loading-text');
    loadingSteps.classList.remove('hidden');
    loadingText.innerText = steps[0];

    const stepInterval = setInterval(() => {
        stepIndex++;
        if(stepIndex < steps.length) {
            loadingText.innerText = steps[stepIndex];
        }
    }, 4500);

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

        btnText.innerText = "Analyzing Grievance... (Please wait)";
        
        while (jobData.status === "processing") {
            await new Promise(r => setTimeout(r, 3000));
            const statusRes = await fetch(`${API_BASE}/complaint/status/${currentJobId}`);
            if (!statusRes.ok) {
                const text = await statusRes.text();
                throw new Error("Server Error: " + text);
            }
            jobData = await statusRes.json();
        }

        if (jobData.status === "error") {
            throw new Error(jobData.error);
        }

        if (!jobData.result) {
            throw new Error("Job completed but result is missing. JobData: " + JSON.stringify(jobData));
        }

        pipelineResult = jobData.result;

        resultsNav.classList.remove('hidden');
        renderResults();
        switchTab('results');

    } catch (err) {
        alert("System Busy: " + err.message);
    } finally {
        clearInterval(stepInterval);
        loadingSteps.classList.add('hidden');
        processBtn.disabled = false;
        loader.classList.add('hidden');
        btnText.innerText = "Analyze & Generate Action Plan";
    }
}

function renderResults() {
    const analysis = pipelineResult.analysis;
    const outputs = pipelineResult.outputs;
    const department = pipelineResult.department;

    document.getElementById('res-category').innerText = (analysis.department_category || "N/A").replace(/_/g, ' ').toUpperCase();
    
    const sev = document.getElementById('res-severity');
    sev.innerText = (analysis.severity || "Medium").toUpperCase();
    sev.className = `severity-tag severity-${(analysis.severity || 'medium').toLowerCase()}`;
    
    // Render Escalation Path
    const escalationContainer = document.getElementById('escalation-path');
    const path = department.escalation_path || [];
    escalationContainer.innerHTML = '';
    if (path.length) {
        path.forEach((step, index) => {
            escalationContainer.innerHTML += `
                <div class="path-step">
                    <div class="step-num">${index + 1}</div>
                    <span>${step}</span>
                </div>
            `;
        });
    } else {
        escalationContainer.innerHTML = '<p class="text-muted">No specific escalation path found.</p>';
    }

    // Render Legal Rights
    const rightsContainer = document.getElementById('legal-rights-list');
    const rights = outputs.key_legal_rights || [];
    rightsContainer.innerHTML = '';
    if (rights.length) {
        rights.forEach(right => {
            rightsContainer.innerHTML += `
                <div class="right-item">
                    <i class="fa-solid fa-circle-check"></i>
                    <span>${right}</span>
                </div>
            `;
        });
    } else {
        rightsContainer.innerHTML = '<p class="text-muted">General legal rights applicable.</p>';
    }

    renderDepartment('central');
    renderDocument('letter');
}

function renderDepartment(type) {
    const dept = pipelineResult.department;
    const data = type === 'central' ? dept.central_details : dept.state_details;
    
    document.getElementById('dept-name').innerText = type === 'central' ? dept.department_name : (data.organization || "State Authority");
    document.getElementById('dept-helpline').innerText = data.helpline || "Contact State Portal";
    
    const portal = document.getElementById('dept-portal');
    portal.href = data.portal && data.portal !== 'N/A' ? data.portal : "#";
    portal.innerText = data.portal && data.portal !== 'N/A' ? "Visit Official Website" : "Portal Not Available";
}

function renderDocument(type) {
    const outputs = pipelineResult.outputs;
    let content = "";

    if (type === 'letter') content = outputs.formal_letter;
    else if (type === 'email') {
        const e = outputs.email;
        content = `To: ${e.to}\nSubject: ${e.subject}\n\n${e.body}`;
    } else {
        content = outputs.twitter_post || "Twitter post generation in progress...";
    }

    document.getElementById('doc-content').innerText = content;
}

async function sendFollowup() {
    const input = document.getElementById('followup-input');
    const question = input.value;
    if (!question.trim() || !currentSessionId) return;

    appendChatMessage('complaint-chat-history', 'user', question);
    input.value = '';

    try {
        const res = await fetch(`${API_BASE}/complaint/followup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                question: question,
                user_id: userId
            })
        });
        const data = await res.json();
        appendChatMessage('complaint-chat-history', 'bot', data.answer);
    } catch (err) {
        appendChatMessage('complaint-chat-history', 'bot', "AI Expert is currently offline.");
    }
}

async function sendRagQuery() {
    const input = document.getElementById('rag-input');
    const question = input.value;
    if (!question.trim()) return;

    appendChatMessage('rag-chat-history', 'user', question);
    input.value = '';

    try {
        const res = await fetch(`${API_BASE}/rag/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: question })
        });
        const data = await res.json();
        let answer = data.answer;
        if (data.sources && data.sources.length) {
            answer += `\n\n📚 Legal Sources: ${data.sources.join(', ')}`;
        }
        appendChatMessage('rag-chat-history', 'bot', answer);
    } catch (err) {
        appendChatMessage('rag-chat-history', 'bot', "Legal Database is unreachable.");
    }
}

function appendChatMessage(containerId, role, text) {
    const container = document.getElementById(containerId);
    const msg = document.createElement('div');
    msg.className = `message ${role}`;
    msg.innerText = text;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}

async function loadHistory() {
    const container = document.getElementById('history-container');
    container.innerHTML = '<div class="loader" style="border-top-color: var(--primary)"></div>';
    
    try {
        const res = await fetch(`${API_BASE}/history/${userId}`);
        const data = await res.json();
        
        container.innerHTML = '';
        if (!data.history || !data.history.length) {
            container.innerHTML = '<div class="card" style="grid-column: 1/-1;"><p>No records found in your complaint box.</p></div>';
            return;
        }

        data.history.forEach(item => {
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <h3 style="color: var(--primary)">${item.category.replace(/_/g, ' ')}</h3>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">Submitted on: ${item.date.slice(0, 10)}</p>
                <p style="color: #475569">${item.complaint_text.slice(0, 120)}...</p>
                <button class="primary-btn" style="margin-top:1.5rem; padding: 0.8rem;" onclick="viewHistoryItem('${item.session_id}')">View Full Report</button>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        container.innerHTML = '<p>Error loading history.</p>';
    }
}

async function viewHistoryItem(sid) {
    try {
        const res = await fetch(`${API_BASE}/session/${sid}`);
        pipelineResult = await res.json();
        currentSessionId = sid;
        resultsNav.classList.remove('hidden');
        renderResults();
        switchTab('results');
    } catch (err) { alert("Failed to load details"); }
}

function copyDoc() {
    const text = document.getElementById('doc-content').innerText;
    navigator.clipboard.writeText(text);
    alert("Copied to clipboard!");
}

function downloadDoc() {
    const text = document.getElementById('doc-content').innerText;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `NyayaVaani_Grievance_Report.txt`;
    a.click();
}
