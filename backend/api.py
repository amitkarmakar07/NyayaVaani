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

            system_prompt = f"""You are the NyayaVaani Strategy Expert. 
You help Indian citizens understand their civic grievance, escalation paths, and drafted legal documents.
Context of their problem:
State: {session.get('state')}
Original Complaint: {session.get('complaint_text')}
Pipeline Analysis: {json.dumps(session.get('pipeline_result', {}))}

FORMATTING RULES:
1. If the user asks a question UNRELATED to their complaint or civic/legal issues, refuse politely.
2. Keep answers concise. Avoid unnecessary filler sentences.
3. Use markdown only when it genuinely helps: **bold** for key terms, bullet lists for steps or options.
4. Do NOT bold entire sentences or headings. Bold only 2-4 key words at most per response.
5. Do NOT add blank lines between every sentence. Keep paragraphs compact.
6. If listing steps, use a numbered list. If listing options, use bullet points.
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

        # Detect conversational / personal questions — skip RAG retrieval for these
        conversational_keywords = [
            "hello", "hi ", "hey ", "namaste", "good morning", "good evening",
            "how are you", "what is your name", "who are you", "what can you do",
            "my name is", "what is my name", "tell me about yourself",
            "thank you", "thanks", "bye", "goodbye"
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

        # Build prompt with memory
        system_msg = """You are NyayaVaani's Legal Assistant — an expert in Indian government laws and citizen rights.
You remember the conversation history, so you can answer follow-up questions in context.

FORMATTING RULES:
1. For legal questions: ONLY use information from the provided document excerpts.
2. Always cite the Act name and section number inline when you reference law, e.g. *(RTI Act 2005, Section 7)*.
3. Use simple language a common Indian citizen can understand.
4. Structure: provide a short, direct answer first, followed by a compact list if details or options are needed.
5. Do NOT include any "Next Step" section or sentence at the end. End directly after providing the answer.
6. Bold only key legal terms or time limits (2-4 words max). Do NOT bold full sentences.
7. For greetings or personal questions (e.g. "what is my name?"): respond naturally and conversationally without legal citations.
8. If legal information is not in the provided documents, say: "This detail is not in my documents. Please verify at the official government portal."
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