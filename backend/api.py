"""
FastAPI Backend — NyayaVaani API
All endpoints for complaint processing, RAG chatbot, history
"""

import uuid
import json
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from src.crew import run_complaint_pipeline, run_followup
from src.rag.retriever import get_rag
from src.voice.whisper_stt import transcribe_audio
from src.memory.session_memory import save_session, get_session, update_conversation, get_user_history

app = FastAPI(
    title="NyayaVaani API",
    description="AI-powered civic grievance assistant for Indian citizens",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ─── Request/Response Models ─────────────────────────────────────

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


# ─── Endpoints ───────────────────────────────────────────────────

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


@app.post("/complaint/process")
async def process_complaint(request: ComplaintTextRequest):
    """
    Main endpoint — process a complaint through all 3 agents.
    Returns department info + letter + email + SMS.
    """
    try:
        session_id = str(uuid.uuid4())
        logger.info(f"Processing complaint. Session: {session_id}")

        result = run_complaint_pipeline(
            complaint_text=request.complaint_text,
            user_state=request.user_state,
            user_name=request.user_name,
            user_address=request.user_address,
            user_contact=request.user_contact
        )

        # Save to memory
        save_session(
            session_id=session_id,
            user_id=request.user_id,
            complaint_text=request.complaint_text,
            state=request.user_state,
            pipeline_result=result
        )

        return {
            "session_id": session_id,
            **result
        }

    except Exception as e:
        import traceback
        logger.error(f"Complaint processing failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/complaint/followup")
async def followup_question(request: FollowupRequest):
    """Handle follow-up questions with memory context."""
    try:
        session = get_session(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        conversation = session.get("conversation", [])

        # Add user message
        conversation.append({"role": "user", "content": request.question})

        # Get answer
        answer = run_followup(
            question=request.question,
            conversation_history=conversation,
            original_complaint=session
        )

        # Add assistant message
        conversation.append({"role": "assistant", "content": answer})

        # Save updated conversation
        update_conversation(request.session_id, conversation)

        return {
            "answer": answer,
            "session_id": request.session_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Followup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rag/chat")
async def rag_chatbot(request: RAGChatRequest):
    """
    Standalone RAG chatbot for legal questions.
    Tab 2 in frontend.
    """
    try:
        rag = get_rag()
        result = rag.answer_question(request.question, department=request.department)
        return result
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