import uuid
import json
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
from fastapi import BackgroundTasks
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.rag.retriever import get_rag
from src.nyayavaani_crew.crew import NyayaVaaniCrew
from src.voice.whisper_stt import transcribe_audio
from src.memory.session_memory import save_session, get_session, update_conversation, get_user_history

from config import Config
from langfuse import observe, propagate_attributes
from langfuse.langchain import CallbackHandler

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

def process_bg_task(job_id: str, request: ComplaintTextRequest, session_id: str):
    try:
        inputs = {
            "complaint_text": request.complaint_text,
            "user_state": request.user_state,
            "user_name": request.user_name,
            "user_address": request.user_address,
            "user_contact": request.user_contact
        }
        
        # Crew execution
        crew_instance = NyayaVaaniCrew()
        crew_obj = crew_instance.crew()
        result = crew_obj.kickoff(inputs=inputs)
        
     
        try:
            analysis_dict = crew_obj.tasks[0].output.pydantic.model_dump() if getattr(crew_obj.tasks[0].output, "pydantic", None) else {}
            dept_dict = crew_obj.tasks[1].output.pydantic.model_dump() if getattr(crew_obj.tasks[1].output, "pydantic", None) else {}
            writer_dict = crew_obj.tasks[3].output.pydantic.model_dump() if getattr(crew_obj.tasks[3].output, "pydantic", None) else {}
            social_dict = crew_obj.tasks[4].output.pydantic.model_dump() if getattr(crew_obj.tasks[4].output, "pydantic", None) else {}
            
            outputs_dict = {**writer_dict, **social_dict}
        except Exception as e:
            logger.error(f"Failed to extract pydantic models: {e}")
            analysis_dict, dept_dict, outputs_dict = {}, {}, {}

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
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        jobs[job_id] = {"status": "error", "error": str(e)}

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
    """Handle follow-up questions with memory context."""
    with propagate_attributes(session_id=request.session_id, user_id=request.user_id):
        try:
            session = get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            conversation = session.get("conversation", [])

            conversation.append({"role": "user", "content": request.question})

            try:
                llm = ChatGoogleGenerativeAI(model=Config.LLM_MODEL, google_api_key=Config.GOOGLE_API_KEY, temperature=0.7)
                system_prompt = f"""You are the NyayaVaani Strategy Expert. 
You help Indian citizens understand their civic grievance, escalation paths, and drafted legal documents.
Context of their problem:
State: {session.get('state')}
Original Complaint: {session.get('complaint_text')}
Pipeline Analysis: {json.dumps(session.get('pipeline_result', {}))}

STRICT RULES:
1. If the user asks a question UNRELATED to their complaint or civic/legal issues, you MUST refuse to answer. Do not respond to general knowledge, coding, or casual talk.
2. Answers must be SHORT and CONCISE, but still provide a proper, direct solution.
3. DO NOT use any markdown formatting like stars (**), asterisks (*), or hashes (#). Output plain text only.
"""
                
                messages = [SystemMessage(content=system_prompt)]
                for msg in conversation[:-1]:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
                
                messages.append(HumanMessage(content=request.question))
                
                langfuse_handler = CallbackHandler()
                response = llm.invoke(messages, config={"callbacks": [langfuse_handler]})
                
                content = response.content
                if isinstance(content, list):
                    content = content[0].get("text", "") if len(content) > 0 else str(content)
                answer = str(content)
            except Exception as e:
                logger.error(f"LLM Error in followup: {e}")
                answer = "Sorry, my AI thought process was interrupted. Could you ask that again?"

            conversation.append({"role": "assistant", "content": answer})

            update_conversation(request.session_id, conversation)

            return {
                "answer": answer,
                "session_id": request.session_id
            }

        except HTTPException:
            raise
        except Exception as e:
            error_msg = str(e)
            if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
                friendly_msg = "AI quota limit reached. Please try later."
            else:
                friendly_msg = error_msg
                
            logger.error(f"Followup failed: {e}")
            raise HTTPException(status_code=500, detail=friendly_msg)


@app.post("/rag/chat")
@observe(name="rag_chatbot")
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
        error_msg = str(e)
        if "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            friendly_msg = "Legal AI quota limit reached. Please try later."
        else:
            friendly_msg = error_msg
            
        logger.error(f"RAG chat failed: {e}")
        raise HTTPException(status_code=500, detail=friendly_msg)


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