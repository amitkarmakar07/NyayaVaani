const API_BASE = "http://localhost:8000";
let userId = localStorage.getItem('nyayavani_user_id') || crypto.randomUUID();
localStorage.setItem('nyayavani_user_id', userId);

let currentSessionId = null;
let pipelineResult = null;
let userProfile = JSON.parse(localStorage.getItem('nyayavani_profile')) || null;

// DOM Elements
const navLinks = document.querySelectorAll('.nav-links li');
const tabs = document.querySelectorAll('.tab-content');
const processBtn = document.getElementById('process-btn');
const resultsNav = document.getElementById('nav-results');

// Initial Setup
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

    // Process Complaint
    processBtn.addEventListener('click', runPipeline);

    // Document Tabs
    document.querySelectorAll('.doc-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.doc-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDocument(btn.getAttribute('data-doc'));
        });
    });

    // Dept Tabs
    document.querySelectorAll('.dept-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.dept-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderDepartment(btn.getAttribute('data-dept'));
        });
    });

    // Chat Inputs
    document.getElementById('send-followup').addEventListener('click', sendFollowup);
    document.getElementById('send-rag').addEventListener('click', sendRagQuery);
    
    // Sample Questions
    document.querySelectorAll('.sample-q').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('rag-input').value = btn.innerText;
            sendRagQuery();
        });
    });

    // Actions
    document.getElementById('copy-doc').addEventListener('click', copyDoc);
    document.getElementById('download-doc').addEventListener('click', downloadDoc);
});

function switchTab(tabId) {
    navLinks.forEach(l => l.classList.remove('active'));
    tabs.forEach(t => t.classList.remove('active'));

    const activeLink = document.querySelector(`.nav-links li[data-tab="${tabId}"]`);
    const activeTab = document.getElementById(tabId);

    if (activeLink) activeLink.classList.add('active');
    if (activeTab) activeTab.classList.add('active');

    if (tabId === 'history') loadHistory();
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
    alert('Profile updated successfully!');
    switchTab('complaint');
}

function updateProfileUI() {
    document.getElementById('display-name').innerText = userProfile.name;
    document.getElementById('display-state').innerText = userProfile.state;
    document.querySelectorAll('.user-name-span').forEach(el => el.innerText = userProfile.name);
    
    // Fill inputs if they exist
    if (document.getElementById('user_name')) {
        document.getElementById('user_name').value = userProfile.name;
        document.getElementById('user_state').value = userProfile.state;
        document.getElementById('user_address').value = userProfile.address;
        document.getElementById('user_contact').value = userProfile.contact;
    }
}

async function runPipeline() {
    const text = document.getElementById('complaint_text').value;
    if (!text.trim()) return alert("Please describe your problem.");

    if (!userProfile) {
        alert("Please save your profile in the Dashboard first.");
        return switchTab('dashboard');
    }

    const loader = processBtn.querySelector('.loader');
    const btnText = processBtn.querySelector('span');

    processBtn.disabled = true;
    loader.classList.remove('hidden');
    btnText.innerText = "AI is working...";

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

        pipelineResult = await res.json();
        currentSessionId = pipelineResult.session_id;

        // Unlock Results
        resultsNav.classList.remove('hidden');
        renderResults();
        switchTab('results');

    } catch (err) {
        alert("Error: " + err.message);
    } finally {
        processBtn.disabled = false;
        loader.classList.add('hidden');
        btnText.innerText = "Analyze & Generate Complaint";
    }
}

function renderResults() {
    const analysis = pipelineResult.analysis;
    const outputs = pipelineResult.outputs;

    document.getElementById('res-category').innerText = (analysis.department_category || "N/A").replace(/_/g, ' ');
    
    const sev = document.getElementById('res-severity');
    sev.innerText = analysis.severity || "Medium";
    sev.className = `severity-tag severity-${(analysis.severity || 'medium').toLowerCase()}`;
    
    document.getElementById('res-action').innerText = (analysis.action_type || "Grievance").replace(/_/g, ' ');

    // Department
    renderDepartment('central');

    // Escalation
    const escList = document.getElementById('escalation-list');
    escList.innerHTML = '';
    (pipelineResult.department.escalation_path || []).forEach(step => {
        const li = document.createElement('li');
        li.innerText = step;
        escList.appendChild(li);
    });

    // Rights
    const rightsList = document.getElementById('rights-list');
    rightsList.innerHTML = '';
    (outputs.key_legal_rights || []).forEach(right => {
        const div = document.createElement('div');
        div.className = 'right-item';
        div.innerHTML = `<strong>✅</strong> ${right}`;
        rightsList.appendChild(div);
    });
    document.getElementById('res-sources').innerText = (pipelineResult.rag_meta.sources || []).join(', ');

    // Document
    renderDocument('letter');
}

function renderDepartment(type) {
    const dept = pipelineResult.department;
    const data = type === 'central' ? dept.central_details : dept.state_details;
    
    document.getElementById('dept-name').innerText = type === 'central' ? dept.department_name : (data.organization || "State Dept");
    document.getElementById('dept-helpline').innerText = data.helpline || "N/A";
    document.getElementById('dept-email').innerText = data.email || "N/A";
    
    const portal = document.getElementById('dept-portal');
    portal.innerText = data.portal && data.portal !== 'N/A' ? "Visit Portal" : "N/A";
    portal.href = data.portal || "#";
}

function renderDocument(type) {
    const outputs = pipelineResult.outputs;
    let content = "";

    if (type === 'letter') content = outputs.formal_letter;
    else if (type === 'email') {
        const e = outputs.email;
        content = `To: ${e.to}\nSubject: ${e.subject}\n\n${e.body}`;
    } else {
        content = outputs.sms;
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
        appendChatMessage('complaint-chat-history', 'bot', "Sorry, I couldn't process that.");
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
            answer += `\n\n📚 *Sources: ${data.sources.join(', ')}*`;
        }
        appendChatMessage('rag-chat-history', 'bot', answer);
    } catch (err) {
        appendChatMessage('rag-chat-history', 'bot', "I'm having trouble connecting to the legal database.");
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
    container.innerHTML = '<div class="loader"></div>';
    
    try {
        const res = await fetch(`${API_BASE}/history/${userId}`);
        const data = await res.json();
        
        container.innerHTML = '';
        if (!data.history || !data.history.length) {
            container.innerHTML = '<div class="card"><p>No history found.</p></div>';
            return;
        }

        data.history.forEach(item => {
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <h3>${item.category.replace(/_/g, ' ')}</h3>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">${item.date.slice(0, 10)}</p>
                <p>${item.complaint_text.slice(0, 100)}...</p>
                <button class="secondary-btn" style="margin-top:1rem" onclick="viewHistoryItem('${item.session_id}')">View Full Analysis</button>
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
    a.download = `NyayaVaani_Complaint.txt`;
    a.click();
}
