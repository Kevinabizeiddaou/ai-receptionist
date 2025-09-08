import redis
import json
import uuid
from typing import Dict, Optional
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            # Fallback to in-memory storage for development
            self.redis_client = None
            self._memory_store = {}
    
    def create_session(self, call_sid: str, caller_number: str) -> str:
        """Create a new session for the call"""
        session_id = f"session_{call_sid}"
        
        session_data = {
            "session_id": session_id,
            "call_sid": call_sid,
            "caller_number": caller_number,
            "created_at": datetime.now().isoformat(),
            "conversation_state": "greeting",
            "conversation_history": [],
            "customer_name": None,
            "appointment_details": {},
            "last_activity": datetime.now().isoformat()
        }
        
        self._store_session(session_id, session_data)
        logger.info(f"Created session {session_id} for caller {caller_number}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data"""
        try:
            if self.redis_client:
                data = self.redis_client.get(session_id)
                if data:
                    return json.loads(data)
            else:
                return self._memory_store.get(session_id)
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {str(e)}")
        
        return None
    
    def update_session(self, session_id: str, updates: Dict) -> bool:
        """Update session data"""
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"Session {session_id} not found for update")
                return False
            
            # Update fields
            session_data.update(updates)
            session_data["last_activity"] = datetime.now().isoformat()
            
            self._store_session(session_id, session_data)
            return True
            
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {str(e)}")
            return False
    
    def add_to_conversation_history(self, session_id: str, role: str, message: str):
        """Add message to conversation history"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                if "conversation_history" not in session_data:
                    session_data["conversation_history"] = []
                
                session_data["conversation_history"].append({
                    "role": role,
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Keep only last 10 messages to manage memory
                session_data["conversation_history"] = session_data["conversation_history"][-10:]
                
                self._store_session(session_id, session_data)
                
        except Exception as e:
            logger.error(f"Error adding to conversation history: {str(e)}")
    
    def end_session(self, session_id: str):
        """End and cleanup session"""
        try:
            session_data = self.get_session(session_id)
            if session_data:
                session_data["ended_at"] = datetime.now().isoformat()
                session_data["conversation_state"] = "ended"
                
                # Store final session data with longer TTL for analytics
                self._store_session(session_id, session_data, ttl=86400)  # 24 hours
                
                logger.info(f"Ended session {session_id}")
                
        except Exception as e:
            logger.error(f"Error ending session {session_id}: {str(e)}")
    
    def _store_session(self, session_id: str, session_data: Dict, ttl: int = 3600):
        """Store session data with TTL"""
        try:
            if self.redis_client:
                self.redis_client.setex(
                    session_id, 
                    ttl,  # 1 hour default TTL
                    json.dumps(session_data, default=str)
                )
            else:
                # In-memory fallback
                self._memory_store[session_id] = session_data
                
        except Exception as e:
            logger.error(f"Error storing session {session_id}: {str(e)}")
    
    def cleanup_expired_sessions(self):
        """Cleanup expired sessions (for in-memory storage)"""
        if not self.redis_client and hasattr(self, '_memory_store'):
            current_time = datetime.now()
            expired_sessions = []
            
            for session_id, session_data in self._memory_store.items():
                last_activity = datetime.fromisoformat(session_data.get("last_activity", ""))
                if current_time - last_activity > timedelta(hours=1):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self._memory_store[session_id]
                logger.info(f"Cleaned up expired session {session_id}")
