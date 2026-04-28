"""
Session Memory — SQLite based long-term memory
Stores complaint history and conversation per user
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict
from loguru import logger

from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

from config import config

os.makedirs("db", exist_ok=True)

engine = create_engine(f"sqlite:///{config.SQLITE_DB}", echo=False)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


class ComplaintSession(Base):
    __tablename__ = "complaint_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True)
    user_id = Column(String(64), index=True)
    complaint_text = Column(Text)
    department_category = Column(String(100))
    department_name = Column(String(200))
    state = Column(String(100))
    analysis_json = Column(Text)
    department_json = Column(Text)
    outputs_json = Column(Text)
    conversation_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


Base.metadata.create_all(engine)


def save_session(
    session_id: str,
    user_id: str,
    complaint_text: str,
    state: str,
    pipeline_result: dict
) -> bool:
    """Save a complaint session to DB."""
    try:
        db = SessionLocal()
        analysis = pipeline_result.get("analysis", {})
        session = ComplaintSession(
            session_id=session_id,
            user_id=user_id,
            complaint_text=complaint_text,
            department_category=analysis.get("department_category", ""),
            department_name=pipeline_result.get("department", {}).get("department_name", ""),
            state=state,
            analysis_json=json.dumps(pipeline_result.get("analysis", {})),
            department_json=json.dumps(pipeline_result.get("department", {})),
            outputs_json=json.dumps(pipeline_result.get("outputs", {})),
            conversation_json="[]"
        )
        db.merge(session)
        db.commit()
        db.close()
        logger.success(f"Session saved: {session_id}")
        return True
    except Exception as e:
        logger.error(f"Session save failed: {e}")
        return False


def update_conversation(session_id: str, conversation: List[Dict]) -> bool:
    """Update conversation history for a session."""
    try:
        db = SessionLocal()
        session = db.query(ComplaintSession).filter_by(session_id=session_id).first()
        if session:
            session.conversation_json = json.dumps(conversation)
            session.updated_at = datetime.utcnow()
            db.commit()
        db.close()
        return True
    except Exception as e:
        logger.error(f"Conversation update failed: {e}")
        return False


def get_session(session_id: str) -> Optional[Dict]:
    """Load a specific session."""
    try:
        db = SessionLocal()
        session = db.query(ComplaintSession).filter_by(session_id=session_id).first()
        db.close()
        if not session:
            return None
        return {
            "session_id": session.session_id,
            "complaint_text": session.complaint_text,
            "department_category": session.department_category,
            "department_name": session.department_name,
            "state": session.state,
            "analysis": json.loads(session.analysis_json or "{}"),
            "department": json.loads(session.department_json or "{}"),
            "outputs": json.loads(session.outputs_json or "{}"),
            "conversation": json.loads(session.conversation_json or "[]"),
            "created_at": str(session.created_at)
        }
    except Exception as e:
        logger.error(f"Session load failed: {e}")
        return None


def get_user_history(user_id: str, limit: int = 10) -> List[Dict]:
    """Get recent complaint sessions for a user."""
    try:
        db = SessionLocal()
        sessions = (
            db.query(ComplaintSession)
            .filter_by(user_id=user_id)
            .order_by(ComplaintSession.created_at.desc())
            .limit(limit)
            .all()
        )
        db.close()
        return [
            {
                "session_id": s.session_id,
                "complaint_text": s.complaint_text[:100] + "...",
                "department": s.department_name,
                "category": s.department_category,
                "date": str(s.created_at)
            }
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"History load failed: {e}")
        return []