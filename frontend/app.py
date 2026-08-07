"""
NyayaVaani — Streamlit Frontend
Tab 1: Complaint Assistant (Voice/Text → Agent Pipeline)
Tab 2: Legal Chatbot (RAG)
"""

import uuid
import requests
import streamlit as st
from streamlit_mic_recorder import mic_recorder

API_BASE = "http://localhost:8000"

# ─── Page Config ─────────────────────────────────────────────────
st.set_page_config(
    page_title="NyayaVaani — Civic Grievance Assistant",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Custom CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main Layout */
    .stApp {
        background-color: #ffffff;
    }
    
    /* Header & Branding */
    .main-header {
        background: linear-gradient(135deg, #FF8C00, #FF5722);
        color: white;
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(255, 87, 34, 0.2);
    }
    
    .nv-title {
        font-size: 3rem !important;
        font-weight: 800 !important;
        background: linear-gradient(90deg, #FF8C00, #FF5722);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    /* Cards & Components */
    .dept-card {
        background: #fff7ed;
        border-left: 5px solid #FF8C00;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }
    
    .rights-card {
        background: #fdf2f2;
        border-left: 5px solid #ef4444;
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
    }
    
    /* Formal Letter Styling (Normal Font) */
    .letter-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 2.5rem;
        border-radius: 16px;
        font-family: 'Inter', 'Segoe UI', Roboto, sans-serif !important;
        font-size: 1.1rem;
        line-height: 1.8;
        color: #1e293b;
        white-space: pre-wrap;
        margin-bottom: 1.5rem;
    }
    
    .severity-critical { color: #dc2626; font-weight: bold; }
    .severity-high { color: #ea580c; font-weight: bold; }
    .severity-medium { color: #f59e0b; font-weight: bold; }
    .severity-low { color: #16a34a; font-weight: bold; }
    
    /* Chat bubbles */
    .chat-user { 
        background: #fff7ed; 
        padding: 1rem; 
        border-radius: 15px 15px 0 15px; 
        margin: 0.5rem 0;
        border: 1px solid #ffedd5;
        text-align: right;
    }
    .chat-bot { 
        background: #f1f5f9; 
        padding: 1rem; 
        border-radius: 15px 15px 15px 0; 
        margin: 0.5rem 0;
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Init ───────────────────────────────────────────
def init_session():
    defaults = {
        "user_id": str(uuid.uuid4()),
        "session_id": None,
        "pipeline_result": None,
        "conversation": [],
        "rag_history": [],
        "user_profile": None
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ─── Sidebar — User Profile ───────────────────────────────────────
with st.sidebar:
    st.markdown('<h1 class="nv-title" style="font-size: 2rem !important;">NyayaVaani</h1>', unsafe_allow_html=True)
    st.caption("Naagrik ki awaaz, AI ki taakat")
    st.divider()

    st.subheader("👤 Your Profile")
    user_name = st.text_input("Full Name", placeholder="Ramesh Kumar")
    user_state = st.selectbox("State", [
        "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi",
        "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
        "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab",
        "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh",
        "Uttarakhand", "West Bengal"
    ])
    user_address = st.text_area("Address", placeholder="123, Main Street, City - PIN", height=80)
    user_contact = st.text_input("Contact Number", placeholder="9876543210")

    if st.button("💾 Save Profile", use_container_width=True):
        st.session_state.user_profile = {
            "name": user_name or "Citizen",
            "state": user_state,
            "address": user_address or "Not provided",
            "contact": user_contact or "Not provided"
        }
        st.success("Profile saved!")

    st.divider()

    # History
    if st.button("📋 View My Complaints", use_container_width=True):
        try:
            res = requests.get(f"{API_BASE}/history/{st.session_state.user_id}", timeout=10)
            if res.ok:
                history = res.json().get("history", [])
                if history:
                    for item in history[:5]:
                        with st.expander(f"🗂 {item['category']} — {item['date'][:10]}"):
                            st.write(item["complaint_text"])
                            st.caption(f"Dept: {item['department']}")
                else:
                    st.info("No past complaints found.")
        except Exception:
            st.error("Could not load history.")


# ─── Header ──────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1 style="font-size: 3.5rem; font-weight: 900; margin-bottom: 0;">NyayaVaani</h1>
    <p style="margin:0; opacity:0.9; font-size: 1.2rem;">AI-Powered Civic Grievance Assistant for Every Indian Citizen</p>
</div>
""", unsafe_allow_html=True)


# ─── Main Tabs ───────────────────────────────────────────────────
tab1, tab2 = st.tabs(["🎙️ Complaint Assistant", "📚 Legal Chatbot (RAG)"])


# ════════════════════════════════════════════════════════════════
# TAB 1 — COMPLAINT ASSISTANT
# ════════════════════════════════════════════════════════════════
with tab1:

    profile = st.session_state.get("user_profile") or {
        "name": user_name or "Citizen",
        "state": user_state,
        "address": user_address or "Not provided",
        "contact": user_contact or "Not provided"
    }

    # Input section
    st.subheader("📢 Tell us your problem")
    
    # Large area for input
    complaint_text = st.text_area(
        "Describe your problem in detail:",
        placeholder="Example: My electricity bill is 3 times higher than usual. I complained to WBSEDCL last month but they haven't responded...",
        height=350,
        key="main_complaint_input"
    )

    # Voice alternative
    with st.expander("🎙️ Use Voice Instead"):
        st.info("🎙️ Click the mic and speak your complaint in Hindi or English")
        audio = mic_recorder(
            start_prompt="🎙️ Start Speaking",
            stop_prompt="⏹️ Stop Recording",
            key="complaint_mic"
        )
        if audio and audio.get("bytes"):
            with st.spinner("Transcribing audio..."):
                try:
                    files = {"audio": ("audio.webm", audio["bytes"], "audio/webm")}
                    res = requests.post(f"{API_BASE}/transcribe", files=files, timeout=30)
                    if res.ok:
                        result = res.json()
                        st.session_state.voice_transcript = result.get("text", "")
                        lang = result.get("language", "unknown")
                        st.success(f"✅ Transcribed ({lang.upper()})")
                        st.info(f"**Transcription:** {st.session_state.voice_transcript}")
                        if st.button("Use this transcript"):
                             st.session_state.main_complaint_input = st.session_state.voice_transcript
                             st.rerun()
                    else:
                        st.error("Transcription failed. Try typing instead.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # Process button
    if st.button("🚀 Find My Rights & Generate Complaint", type="primary", use_container_width=True):
        if not complaint_text.strip():
            st.warning("Please provide your complaint first.")
        else:
            with st.spinner("🤖 AI agents are analyzing your complaint..."):
                progress = st.progress(0)

                try:
                    st.caption("Agent 1: Understanding your complaint...")
                    progress.progress(25)

                    payload = {
                        "complaint_text": complaint_text,
                        "user_state": profile["state"],
                        "user_name": profile["name"],
                        "user_address": profile["address"],
                        "user_contact": profile["contact"],
                        "user_id": st.session_state.user_id
                    }

                    st.caption("Agent 2: Finding department & helplines...")
                    progress.progress(55)

                    res = requests.post(
                        f"{API_BASE}/complaint/process",
                        json=payload,
                        timeout=180
                    )

                    st.caption("Agent 3: Writing your complaint letter...")
                    progress.progress(85)

                    if res.ok:
                        result = res.json()
                        st.session_state.pipeline_result = result
                        st.session_state.session_id = result.get("session_id")
                        st.session_state.conversation = []
                        progress.progress(100)
                        st.success("✅ Done! See your results below.")
                    else:
                        st.error(f"Processing failed: {res.text}")
                        progress.empty()

                except requests.Timeout:
                    st.error("Request timed out. The AI is taking too long. Please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")

    # ─── Results ─────────────────────────────────────────────────
    if st.session_state.pipeline_result:
        result = st.session_state.pipeline_result
        analysis = result.get("analysis", {})
        department = result.get("department", {})
        outputs = result.get("outputs", {})
        rag_meta = result.get("rag_meta", {})

        st.divider()

        # Problem Summary
        col1, col2, col3 = st.columns(3)
        severity = analysis.get("severity", "medium")
        with col1:
            st.metric("Problem Category", analysis.get("department_category", "N/A").replace("_", " ").title())
        with col2:
            st.metric("Severity", severity.upper())
        with col3:
            st.metric("Action Type", analysis.get("action_type", "N/A").replace("_", " ").title())

        # Department Info
        st.subheader("🏛️ Department Details")
        central = department.get("central_details", {})
        state_det = department.get("state_details", {})

        col_c, col_s = st.columns(2)

        with col_c:
            st.markdown(f"""
<div class="dept-card">
<b>🏢 Central Department</b><br>
<b>{department.get('department_name', 'N/A')}</b><br><br>
📞 <b>Helpline:</b> {central.get('helpline', 'N/A')}<br>
🌐 <b>Portal:</b> {central.get('portal', 'N/A')}<br>
📧 <b>Email:</b> {central.get('email', 'N/A')}<br>
⏰ <b>Response Deadline:</b> {central.get('response_deadline', '30 days')}<br>
⬆️ <b>Escalation:</b> {central.get('escalation', 'N/A')}
</div>
""", unsafe_allow_html=True)

        with col_s:
            st.markdown(f"""
<div class="dept-card">
<b>📍 {profile['state']} State Department</b><br>
<b>{state_det.get('organization', 'State Department')}</b><br><br>
📞 <b>State Helpline:</b> {state_det.get('helpline', 'Check state portal')}<br>
🌐 <b>State Portal:</b> {state_det.get('portal', 'N/A')}<br>
🔗 <b>Source:</b> {state_det.get('source', 'SerpAPI Search')}
</div>
""", unsafe_allow_html=True)

        # Escalation Path
        escalation_path = department.get("escalation_path", [])
        if escalation_path:
            st.subheader("📈 Escalation Path")
            for i, step in enumerate(escalation_path):
                st.markdown(f"**Step {i+1}:** {step}")

        # Legal Rights
        key_rights = outputs.get("key_legal_rights", [])
        if key_rights:
            st.subheader("⚖️ Your Legal Rights")
            st.markdown(f"""<div class="rights-card">
{"<br>".join(f"✅ {r}" for r in key_rights)}
<br><br><small>📚 Sources: {', '.join(rag_meta.get('sources', []))}</small>
</div>""", unsafe_allow_html=True)

        # 3 Outputs
        st.subheader("📄 Your Complaint Documents")

        out_tab1, out_tab2, out_tab3 = st.tabs(["📜 Formal Letter", "📧 Email", "💬 SMS/WhatsApp"])

        with out_tab1:
            letter = outputs.get("formal_letter", "Not generated")
            st.markdown(f'<div class="letter-box">{letter}</div>', unsafe_allow_html=True)
            st.download_button(
                "⬇️ Download Letter as TXT",
                data=letter,
                file_name="complaint_letter.txt",
                mime="text/plain",
                use_container_width=True
            )

        with out_tab2:
            email_data = outputs.get("email", {})
            st.markdown(f"**To:** `{email_data.get('to', 'N/A')}`")
            st.markdown(f"**Subject:** {email_data.get('subject', 'N/A')}")
            st.text_area("Email Body", email_data.get("body", "Not generated"), height=300)
            full_email = f"To: {email_data.get('to','')}\nSubject: {email_data.get('subject','')}\n\n{email_data.get('body','')}"
            st.download_button("⬇️ Download Email Draft", data=full_email,
                               file_name="complaint_email.txt", mime="text/plain",
                               use_container_width=True)

        with out_tab3:
            sms = outputs.get("sms", "Not generated")
            st.text_area("SMS / WhatsApp Message", sms, height=150)
            st.caption(f"Character count: {len(sms)}/320")

        # Suggested Attachments
        attachments = outputs.get("suggested_attachments", [])
        if attachments:
            st.subheader("📎 Documents to Attach")
            for a in attachments:
                st.markdown(f"- {a}")

        # ─── Follow-up Chat ──────────────────────────────────────
        st.divider()
        st.subheader("💬 Ask Follow-up Questions")

        # Display chat history
        for msg in st.session_state.conversation:
            role_class = "chat-user" if msg["role"] == "user" else "chat-bot"
            icon = "👤" if msg["role"] == "user" else "⚖️"
            st.markdown(
                f'<div class="{role_class}">{icon} {msg["content"]}</div>',
                unsafe_allow_html=True
            )

        followup_q = st.text_input(
            "Ask anything about your complaint...",
            placeholder="What if they don't respond in 30 days?",
            key="followup_input"
        )

        if st.button("Send ➤", key="followup_btn"):
            if followup_q and st.session_state.session_id:
                st.session_state.conversation.append({"role": "user", "content": followup_q})
                with st.spinner("Thinking..."):
                    try:
                        res = requests.post(
                            f"{API_BASE}/complaint/followup",
                            json={
                                "session_id": st.session_state.session_id,
                                "question": followup_q,
                                "user_id": st.session_state.user_id
                            },
                            timeout=180
                        )
                        if res.ok:
                            answer = res.json().get("answer", "")
                            st.session_state.conversation.append({"role": "assistant", "content": answer})
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════════════
# TAB 2 — RAG LEGAL CHATBOT
# ════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("📚 Legal Rights Chatbot")
    st.caption("Ask any question about Indian civic laws, your rights, or government procedures")

    # Display RAG chat history
    for msg in st.session_state.rag_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">👤 {msg["content"]}</div>', unsafe_allow_html=True)
        else:
            with st.container():
                st.markdown(f'<div class="chat-bot">⚖️ {msg["content"]}</div>', unsafe_allow_html=True)
                if msg.get("sources"):
                    st.caption(f"📚 Sources: {', '.join(msg['sources'])}")
                confidence = msg.get("confidence", "")
                if confidence == "low":
                    st.warning("⚠️ Limited information in documents. Please verify with official sources.")

    # Input
    rag_question = st.text_input(
        "Ask your legal question:",
        placeholder="What are my rights if my RTI application is not answered?",
        key="rag_input"
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        ask_btn = st.button("🔍 Ask", type="primary", use_container_width=True, key="rag_ask")
    with col2:
        if st.button("🗑️ Clear", use_container_width=True, key="rag_clear"):
            st.session_state.rag_history = []
            st.rerun()

    if ask_btn and rag_question:
        st.session_state.rag_history.append({"role": "user", "content": rag_question})

        with st.spinner("🔍 Searching legal documents..."):
            try:
                res = requests.post(
                    f"{API_BASE}/rag/chat",
                    json={"question": rag_question},
                    timeout=180
                )
                if res.ok:
                    data = res.json()
                    st.session_state.rag_history.append({
                        "role": "assistant",
                        "content": data.get("answer", ""),
                        "sources": data.get("sources", []),
                        "confidence": data.get("confidence", "")
                    })
                    st.rerun()
                else:
                    st.error("Failed to get answer.")
            except Exception as e:
                st.error(f"Error: {e}")

    # Sample questions
    st.divider()
    st.caption("💡 Try asking:")
    sample_qs = [
        "What is RTI Act and how to file it?",
        "What are my rights if bank transaction fails?",
        "How to escalate if government ignores my complaint?",
        "What is the Consumer Protection Act 2019?",
        "How to file a police complaint if FIR is refused?"
    ]
    cols = st.columns(2)
    for i, q in enumerate(sample_qs):
        with cols[i % 2]:
            if st.button(q, key=f"sample_{i}", use_container_width=True):
                st.session_state.rag_history.append({"role": "user", "content": q})
                with st.spinner("Searching..."):
                    try:
                        res = requests.post(f"{API_BASE}/rag/chat", json={"question": q}, timeout=180)
                        if res.ok:
                            data = res.json()
                            st.session_state.rag_history.append({
                                "role": "assistant",
                                "content": data.get("answer", ""),
                                "sources": data.get("sources", []),
                                "confidence": data.get("confidence", "")
                            })
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")