import sys
import os
import uuid
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger
from fastapi import BackgroundTasks
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.rag.retriever import get_rag
from src.nyayavaani_crew.crew import NyayaVaaniCrew
from src.voice.whisper_stt import transcribe_audio
from src.memory.session_memory import save_session, get_session, update_conversation, get_user_history
from src.security import NyayaVaaniGuardrail, InputGuardrail

from config import Config
from langfuse import observe, propagate_attributes
from langfuse.langchain import CallbackHandler
from src.telemetry import setup_telemetry

setup_telemetry()

app = FastAPI(
    title="NyayaVaani API",
    description="AI-powered civic grievance assistant for Indian citizens",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RAG-Session-ID"]
)

@app.get("/")
async def serve_index():
    return FileResponse("frontend/index.html")

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


class ComplaintTextRequest(BaseModel):
    complaint_text: str
    user_state: str
    user_name: str = "Citizen"
    user_address: str = "Not provided"
    user_contact: str = "Not provided"
    user_id: str = "anonymous"

class FollowupRequest(BaseModel):
    session_id: str
    question: str
    user_id: str = "anonymous"

class RAGChatRequest(BaseModel):
    question: str
    department: Optional[str] = None
    session_id: Optional[str] = None

# In-memory RAG conversation store: { session_id: [HumanMessage|AIMessage, ...] }
rag_sessions: dict = {}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "NyayaVaani"}


@app.post("/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None)
):
    """Transcribe voice audio to text using Whisper."""
    try:
        audio_bytes = await audio.read()
        result = transcribe_audio(audio_bytes, language=language)
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        logger.error(f"Transcription endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


jobs = {}

import time

@observe(name="CrewAI Multi-Agent Civic Grievance Workflow")
async def process_bg_task(job_id: str, request: ComplaintTextRequest, session_id: str):
    import asyncio

    # 🛡️ Guardrails Input Validation (Jailbreak, Off-topic, PII)
    guardrail = await NyayaVaaniGuardrail.validate_input_async(request.complaint_text)
    if not guardrail["is_safe"]:
        logger.warning(f"Job {job_id} blocked by Guardrails: {guardrail['warning_message']}")
        jobs[job_id] = {
            "status": "error",
            "error": guardrail["warning_message"]
        }
        return

    inputs = {
        "complaint_text": request.complaint_text,
        "user_state": request.user_state,
        "user_name": request.user_name,
        "user_address": request.user_address,
        "user_contact": request.user_contact
    }
    
    for attempt in range(2):
        try:
            crew_instance = NyayaVaaniCrew()
            crew_obj = crew_instance.crew()
            result = await asyncio.to_thread(crew_obj.kickoff, inputs=inputs)
            
            try:
                analysis_dict = crew_obj.tasks[0].output.pydantic.model_dump() if getattr(crew_obj.tasks[0].output, "pydantic", None) else {}
                dept_dict = crew_obj.tasks[1].output.pydantic.model_dump() if getattr(crew_obj.tasks[1].output, "pydantic", None) else {}
                writer_dict = crew_obj.tasks[3].output.pydantic.model_dump() if getattr(crew_obj.tasks[3].output, "pydantic", None) else {}
                social_dict = crew_obj.tasks[4].output.pydantic.model_dump() if getattr(crew_obj.tasks[4].output, "pydantic", None) else {}
                
                outputs_dict = {**writer_dict, **social_dict}
            except Exception as e:
                logger.error(f"Failed to extract pydantic models: {e}")
                analysis_dict, dept_dict, outputs_dict = {}, {}, {}

            # 🛡️ Guardrails Output Check (Toxicity & Safety)
            output_check = await NyayaVaaniGuardrail.validate_output_async(json.dumps(outputs_dict))
            if not output_check["is_safe"]:
                logger.warning(f"Job {job_id} output flagged by safety guardrails.")
                outputs_dict["safety_warning"] = output_check["warning_message"]

            final_result = {
                "analysis": analysis_dict,
                "department": dept_dict,
                "outputs": outputs_dict
            }
                
            save_session(
                session_id=session_id,
                user_id=request.user_id,
                complaint_text=request.complaint_text,
                state=request.user_state,
                pipeline_result=final_result
            )
            
            jobs[job_id] = {"status": "completed", "result": final_result}
            break
        except Exception as e:
            err_str = str(e)
            if ("RateLimitError" in err_str or "429" in err_str or "TPM" in err_str) and attempt == 0:
                logger.warning(f"Job {job_id} encountered Groq TPM rate limit. Waiting 30 seconds for quota reset (attempt 1)...")
                await asyncio.sleep(30)
                continue
            else:
                if "RateLimitError" in err_str or "429" in err_str or "TPM" in err_str:
                    clean_error = "AI Provider Rate Limit: The free-tier token quota was briefly reached. Please wait 15 seconds and try again."
                else:
                    clean_error = f"Error processing grievance: {err_str}"
                logger.error(f"Job {job_id} failed: {clean_error}")
                jobs[job_id] = {"status": "error", "error": clean_error}

@app.post("/complaint/process")
async def process_complaint(request: ComplaintTextRequest, background_tasks: BackgroundTasks):
    """
    Async endpoint — processes complaint in background.
    """
    job_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    logger.info(f"Accepted job {job_id}. Session: {session_id}")
    
    jobs[job_id] = {"status": "processing"}
    background_tasks.add_task(process_bg_task, job_id, request, session_id)
    
    return {"job_id": job_id, "session_id": session_id, "status": "processing"}

@app.get("/complaint/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.post("/complaint/followup")
@observe(name="followup_question")
async def followup_question(request: FollowupRequest):
    """Handle follow-up questions with streaming memory context."""
    with propagate_attributes(session_id=request.session_id, user_id=request.user_id):
        try:
            # 🛡️ Guardrails Input Validation (PII, Jailbreak, Off-topic)
            guardrail = await NyayaVaaniGuardrail.validate_input_async(request.question)
            if not guardrail["is_safe"]:
                async def generate_guardrail_warning():
                    yield guardrail["warning_message"]

                return StreamingResponse(generate_guardrail_warning(), media_type="text/plain")

            session = get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            conversation = session.get("conversation", [])
            conversation.append({"role": "user", "content": request.question})

            analysis = session.get("analysis", {})
            department = session.get("department", {})
            outputs = session.get("outputs", {})

            # Fetch statutory legal context for the follow-up question
            rag_context = ""
            try:
                rag = get_rag()
                rag_res = rag.retrieve_and_rerank(request.question)
                if rag_res.get("chunks"):
                    rag_context = "\nApplicable Statutory Laws & Context:\n" + "\n".join([f"- {c['source']} (Page {c['page']}): {c['content']}" for c in rag_res["chunks"][:2]])
            except Exception as e:
                logger.warning(f"Followup RAG lookup skipped: {e}")

            system_prompt = f"""You are the NyayaVaani Strategy Expert — an expert in Indian civic grievances, municipal escalation paths, and citizen legal rights.
You help citizens understand their complaint analysis, escalation paths, nodal officer contact details, and drafted legal documents.

CONTEXT OF CITIZEN'S PROBLEM:
- State: {session.get('state', 'Not specified')}
- Original Complaint: {session.get('complaint_text', '')}

EXTRACTED COMPLAINT ANALYSIS:
{json.dumps(analysis, indent=2)}

DEPARTMENT & HELPLINE CONTACT DETAILS:
{json.dumps(department, indent=2)}

DRAFTED COMPLAINT DOCUMENTS & LEGAL RIGHTS:
{json.dumps(outputs, indent=2)}
{rag_context}

RESPONSE & FORMATTING RULES:
1. Provide clear, accurate, and direct answers using the problem context and statutory legal documents above.
2. If the user asks for next steps, helplines, or who to contact, provide the exact department names, phone numbers, email addresses, or official portals from the context.
3. If the user asks to refine, edit, rewrite, shorten, or format the complaint letter, email, or tweet, provide the updated/refined version directly.
4. STRICT PRIVACY RULE: NEVER include the citizen's mobile phone number or personal contact number inside any letter body, email body, or tweet body text.
5. TWITTER HANDLE RULE: NEVER mention or tag any personal individual Twitter accounts or handles of politicians (e.g., @MamataOfficial, @ArvindKejriwal). Use ONLY official institutional/department handles (e.g., @BBMPOFFICIAL, @DelhiPolice, @ConsumerFeed).
6. If legal rights or acts apply, cite the exact statutory act and section inline.
7. Keep answers concise and practical. Bold key terms (2-4 words max). Use numbered lists for steps.
"""
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=Config.OPENAI_API_KEY, temperature=0.7)
            
            messages = [SystemMessage(content=system_prompt)]
            for msg in conversation[:-1]:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    messages.append(AIMessage(content=msg["content"]))
            
            messages.append(HumanMessage(content=request.question))

            async def generate_followup_stream():
                langfuse_handler = CallbackHandler()
                full_response = ""
                try:
                    async for chunk in llm.astream(messages, config={"callbacks": [langfuse_handler]}):
                        token = chunk.content
                        if isinstance(token, list):
                            token = token[0].get("text", "") if len(token) > 0 else ""
                        token_str = str(token)
                        if token_str:
                            full_response += token_str
                            yield token_str
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    yield "\n[An error occurred while streaming response.]"

                # 🛡️ Guardrails Output Toxicity Check
                output_check = await NyayaVaaniGuardrail.validate_output_async(full_response)
                if not output_check["is_safe"]:
                    full_response = output_check["cleaned_text"]

                conversation.append({"role": "assistant", "content": full_response})
                update_conversation(request.session_id, conversation)

            return StreamingResponse(generate_followup_stream(), media_type="text/plain")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Followup failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/chat")
@observe(name="rag_chatbot")
async def rag_chatbot(request: RAGChatRequest):
    """
    Streaming RAG chatbot with conversation memory and smart source filtering.
    """
    try:
        # 🛡️ Guardrails Input Validation (PII, Jailbreak, Off-topic)
        guardrail = await NyayaVaaniGuardrail.validate_input_async(request.question)
        if not guardrail["is_safe"]:
            async def generate_guardrail_warning():
                yield guardrail["warning_message"]

            response = StreamingResponse(generate_guardrail_warning(), media_type="text/plain")
            if request.session_id:
                response.headers["X-RAG-Session-ID"] = request.session_id
            return response

        rag = get_rag()

        # Load or create conversation history for this session
        session_id = request.session_id or str(uuid.uuid4())
        history: list = rag_sessions.get(session_id, [])

        # Load active complaint session context from DB if present
        db_session = get_session(session_id)
        complaint_context = ""
        if db_session:
            analysis = db_session.get("analysis", {})
            department = db_session.get("department", {})
            outputs = db_session.get("outputs", {})
            complaint_context = f"""
ACTIVE CITIZEN CASE FILE & COMPLAINT DETAILS:
- State: {db_session.get('state', 'N/A')}
- Original Complaint Text: {db_session.get('complaint_text', '')}
- Extracted Problem Summary: {analysis.get('problem_summary', 'N/A')}
- Department Category & Severity: {analysis.get('department_category', 'N/A')} | Severity: {analysis.get('severity', 'N/A')}
- Assigned Nodal Authority: {department.get('department_name', 'N/A')}
- Central Helpline: {department.get('central_details', {}).get('helpline', 'N/A')} | State Helpline: {department.get('state_details', {}).get('helpline', 'N/A')}
- Official Portal: {department.get('central_details', {}).get('portal', 'N/A')}
- Key Legal Rights Identified: {', '.join(outputs.get('key_legal_rights', []))}
"""

        # Detect conversational / personal / case file / next step questions
        conversational_keywords = [
            "hello", "hi ", "hey ", "namaste", "good morning", "good evening",
            "how are you", "what is your name", "who are you", "what can you do",
            "my name is", "what is my name", "tell me about yourself",
            "thank you", "thanks", "bye", "goodbye", "what is my problem", "my problem",
            "my case", "my complaint", "what issue", "what did i report",
            "what to do next", "what are my next steps", "next step", "what next",
            "what should i do", "how to proceed", "guidance", "where to submit"
        ]
        question_lower = request.question.lower().strip()
        is_conversational = any(kw in question_lower for kw in conversational_keywords)

        context = ""
        sources = set()

        if not is_conversational:
            retrieval = rag.retrieve_and_rerank(request.question, request.department)
            chunks = retrieval["chunks"]
            for i, chunk in enumerate(chunks):
                context += f"\n--- Source {i+1}: {chunk['source']} (Page {chunk['page']}) ---\n"
                context += chunk["content"] + "\n"
                if chunk.get("source"):
                    sources.add(chunk["source"])

        # Build prompt with memory and active case file
        system_msg = f"""You are NyayaVaani's Legal Assistant — an expert in Indian government laws, citizen rights, and case files.
You remember conversation history and have access to the citizen's active complaint case file.

FORMATTING RULES:
1. If the citizen asks about their problem, case file, or next steps (e.g. "what to do next?", "what is my problem?", "summarize my case"): use the ACTIVE CITIZEN CASE FILE & COMPLAINT DETAILS below to give clear, actionable, step-by-step guidance.
2. For legal questions: use information from the provided document excerpts and cite the Act name and section number inline.
3. STRICT PRIVACY RULE: NEVER include the citizen's mobile phone number or contact number in any letter body, email body, or tweet body.
4. TWITTER HANDLE RULE: NEVER mention or tag any personal individual Twitter accounts or handles of politicians (e.g., @MamataOfficial, @ArvindKejriwal). Use ONLY official institutional/department handles (e.g., @BBMPOFFICIAL, @DelhiPolice, @ConsumerFeed).
5. Use simple language a common Indian citizen can understand.
6. Structure: provide a short, direct answer first, followed by a compact list of next action steps if needed.
7. Bold key terms (2-4 words max). Do NOT bold full sentences.
8. For greetings or personal questions: respond naturally and conversationally without legal citations.
9. If no active case file is found and legal information is missing, invite the user to file a complaint or ask a specific legal query.
{complaint_context}
"""

        if context:
            system_msg += f"\nRelevant Legal Documents for this question:\n{context}"

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}")
        ])

        llm = ChatOpenAI(model="gpt-4o-mini", api_key=Config.OPENAI_API_KEY, temperature=0.3)
        chain = answer_prompt | llm

        async def generate_rag_stream():
            langfuse_handler = CallbackHandler()
            full_answer = ""
            try:
                async for chunk in chain.astream(
                    {"question": request.question, "history": history},
                    config={"callbacks": [langfuse_handler]}
                ):
                    token = chunk.content
                    if isinstance(token, list):
                        token = token[0].get("text", "") if len(token) > 0 else ""
                    token_str = str(token)
                    if token_str:
                        full_answer += token_str
                        yield token_str
            except Exception as e:
                logger.error(f"RAG streaming error: {e}")
                yield "\n[Error generating legal response.]"

            # 🛡️ Guardrails Output Toxicity Check
            output_check = await NyayaVaaniGuardrail.validate_output_async(full_answer)
            if not output_check["is_safe"]:
                full_answer = output_check["cleaned_text"]

            # Save turn to memory
            history.append(HumanMessage(content=request.question))
            history.append(AIMessage(content=full_answer))
            rag_sessions[session_id] = history[-20:]

            # Only show sources if:
            # 1. We actually retrieved legal docs (not a conversational turn)
            # 2. AND the LLM answer actually cites at least one of those sources
            if sources and not is_conversational:
                cited = {s for s in sources if s.lower().replace(" ", "") in full_answer.lower().replace(" ", "")}
                if cited:
                    yield f"\n\n📚 **Legal Sources:** {', '.join(cited)}"

        response = StreamingResponse(generate_rag_stream(), media_type="text/plain")
        response.headers["X-RAG-Session-ID"] = session_id
        return response

    except Exception as e:
        logger.error(f"RAG chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{user_id}")
async def get_history(user_id: str):
    """Get complaint history for a user."""
    history = get_user_history(user_id)
    return {"history": history}


@app.get("/session/{session_id}")
async def get_session_details(session_id: str):
    """Get full session details."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)