from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import Response, HTMLResponse, JSONResponse
from twilio.twiml.voice_response import VoiceResponse
from twilio.request_validator import RequestValidator
import os
from typing import Optional
import logging
import uuid

from ai_agent import AIAgent, ConversationState, CustomerIntent
from session_manager import SessionManager
from speech_processor import SpeechProcessor

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mounir Cutzz AI Receptionist", version="1.0.0")

ai_agent = AIAgent()
session_manager = SessionManager()
speech_processor = SpeechProcessor()

# Twilio configuration
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")

def validate_twilio_request(request: Request) -> bool:
    """Validate that the request is from Twilio"""
    if not TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN not set - skipping validation")
        return True
    
    validator = RequestValidator(TWILIO_AUTH_TOKEN)
    url = str(request.url)
    signature = request.headers.get("X-Twilio-Signature", "")
    
    # Get form data for validation
    form_data = {}
    if hasattr(request, '_body'):
        # Parse form data from body
        body = request._body.decode()
        for pair in body.split('&'):
            if '=' in pair:
                key, value = pair.split('=', 1)
                form_data[key] = value
    
    return validator.validate(url, form_data, signature)

@app.get("/demo", response_class=HTMLResponse)
async def demo_page():
    html = """
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
      <meta charset=\"UTF-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
      <title>AI Receptionist Demo</title>
      <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        #log { border: 1px solid #ddd; padding: 12px; height: 320px; overflow-y: auto; }
        .msg { margin: 8px 0; }
        .user { color: #0b6; }
        .bot { color: #06b; }
        button { margin-right: 8px; }
      </style>
    </head>
    <body>
      <h2>AI Receptionist - Browser Demo</h2>
      <div>
        <button id=\"startBtn\">Start talking</button>
        <button id=\"stopBtn\" disabled>Stop</button>
      </div>
      <div id=\"log\"></div>
      <script>
        const log = document.getElementById('log');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        let sessionId = null;

        function addMsg(text, cls) {
          const div = document.createElement('div');
          div.className = 'msg ' + cls;
          div.textContent = text;
          log.appendChild(div);
          log.scrollTop = log.scrollHeight;
        }

        async function sendToAI(text) {
          const res = await fetch('/demo/ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text, session_id: sessionId })
          });
          const data = await res.json();
          if (data.session_id) sessionId = data.session_id;
          if (data.response) {
            addMsg('Assistant: ' + data.response, 'bot');
            if ('speechSynthesis' in window) {
              const utter = new SpeechSynthesisUtterance(data.response);
              window.speechSynthesis.speak(utter);
            }
          }
          if (data.booking_details) {
            addMsg('Booking confirmed: ' + data.booking_details.formatted_datetime, 'bot');
          }
        }

        let recognition = null;
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
          const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
          recognition = new SR();
          recognition.lang = 'en-US';
          recognition.interimResults = false;
          recognition.continuous = true;

          recognition.onresult = (event) => {
            for (let i = event.resultIndex; i < event.results.length; i++) {
              if (event.results[i].isFinal) {
                const text = event.results[i][0].transcript;
                addMsg('You: ' + text, 'user');
                sendToAI(text);
              }
            }
          };

          recognition.onend = () => {
            startBtn.disabled = false;
            stopBtn.disabled = true;
          };
        } else {
          addMsg('Speech recognition not supported in this browser. Use Chrome.', 'bot');
        }

        startBtn.onclick = () => {
          if (!recognition) return;
          startBtn.disabled = true;
          stopBtn.disabled = false;
          recognition.start();
          if (!sessionId) addMsg('Say hello to start...', 'bot');
        };
        stopBtn.onclick = () => {
          if (!recognition) return;
          recognition.stop();
        };
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.post("/demo/ai")
async def demo_ai(request: Request):
    try:
        data = await request.json()
        user_text = data.get("text", "").strip()
        provided_session_id = data.get("session_id")

        if not user_text:
            return JSONResponse({"error": "No text provided"}, status_code=400)

        session_id = provided_session_id
        if not session_id:
            # Create a new session seeded for web
            call_sid = f"web_{uuid.uuid4().hex[:12]}"
            session_id = session_manager.create_session(call_sid, "web")

        session_data = session_manager.get_session(session_id) or {}

        # Add user's message to history
        session_manager.add_to_conversation_history(session_id, "user", user_text)

        current_state = ConversationState(session_data.get("conversation_state", "greeting"))
        conversation_history = session_data.get("conversation_history", [])

        detected_language = speech_processor.detect_language(user_text)
        session_manager.update_session(session_id, {"detected_language": detected_language})

        intent, extracted_info = ai_agent.analyze_intent(user_text, conversation_history)
        ai_response, next_state, updated_session = ai_agent.generate_response(
            user_text, intent, extracted_info, current_state, session_data
        )

        session_manager.update_session(session_id, {
            "conversation_state": next_state.value,
            **updated_session
        })
        session_manager.add_to_conversation_history(session_id, "assistant", ai_response)

        payload = {
            "response": ai_response,
            "next_state": next_state.value,
            "session_id": session_id
        }

        # If a booking was just confirmed, surface details
        updated = session_manager.get_session(session_id) or {}
        if updated.get("booking_confirmed") and updated.get("booking_details"):
            payload["booking_details"] = updated["booking_details"]

        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error in /demo/ai: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "Mounir Cutzz AI Receptionist",
        "features": {
            "ai_agent": True,
            "calendar_integration": True,
            "speech_processing": speech_processor.tts_available,
            "session_management": True
        }
    }

@app.post("/webhook/voice")
async def handle_incoming_call(request: Request):
    """Handle incoming voice calls from Twilio"""
    try:
        # Validate Twilio request
        if not validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")
        
        # Get call information
        form_data = await request.form()
        caller_number = form_data.get("From", "Unknown")
        call_sid = form_data.get("CallSid", "Unknown")
        
        logger.info(f"Incoming call from {caller_number}, CallSid: {call_sid}")
        
        session_id = session_manager.create_session(call_sid, caller_number)
        
        # Create TwiML response
        response = VoiceResponse()
        
        welcome_text = (
            "مرحبا بكم في صالون منير كتز. أهلا وسهلا! "
            "Welcome to Mounir Cutzz barber shop. How can I help you today?"
        )
        
        # Use custom TTS if available, otherwise fall back to Twilio
        if speech_processor.tts_available:
            # Generate custom audio for welcome message
            audio_data = speech_processor.synthesize_speech(welcome_text, "english")
            if audio_data:
                # For production, you'd upload this to a CDN and use the URL
                # For now, use Twilio's built-in TTS with optimized text
                response.say(welcome_text, voice="alice", language="en")
            else:
                response.say(welcome_text, voice="alice", language="en")
        else:
            response.say(welcome_text, voice="alice", language="en")
        
        gather = response.gather(
            input="speech",
            action=f"/webhook/process-speech?session_id={session_id}",
            method="POST",
            speech_timeout="auto",  # Auto-detect end of speech
            timeout="10",
            language="en-US",
            hints="appointment, booking, haircut, beard, hours, price, availability",  # Speech recognition hints
            partial_result_callback=f"/webhook/partial-speech?session_id={session_id}"  # Optional: handle partial results
        )
        
        # Fallback if no input
        response.say("I didn't hear anything. Please call back when you're ready to speak.")
        response.hangup()
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {str(e)}")
        
        # Return error TwiML
        response = VoiceResponse()
        response.say("Sorry, we're experiencing technical difficulties. Please try calling back later.")
        response.hangup()
        
        return Response(content=str(response), media_type="application/xml")

@app.post("/webhook/process-speech")
async def process_speech_input(request: Request):
    """Process speech input from caller using AI agent and enhanced speech processing"""
    try:
        form_data = await request.form()
        speech_result = form_data.get("SpeechResult", "")
        call_sid = form_data.get("CallSid", "Unknown")
        confidence = float(form_data.get("Confidence", "0"))
        
        recording_url = form_data.get("RecordingUrl")
        
        session_id = request.query_params.get("session_id")
        if not session_id:
            session_id = f"session_{call_sid}"
        
        logger.info(f"Speech received - CallSid: {call_sid}, Text: '{speech_result}', Confidence: {confidence}")
        
        response = VoiceResponse()
        
        final_text = speech_result
        final_confidence = confidence
        
        # If confidence is low or no speech result, try custom transcription
        if (not speech_result or confidence < 0.6) and recording_url:
            logger.info("Low confidence or no speech result, trying custom transcription")
            custom_text, custom_confidence = await speech_processor.process_twilio_recording(
                recording_url, ACCOUNT_SID, TWILIO_AUTH_TOKEN
            )
            
            if custom_text and custom_confidence > confidence:
                final_text = custom_text
                final_confidence = custom_confidence
                logger.info(f"Using custom transcription: '{final_text}' (confidence: {final_confidence})")
        
        if not final_text or final_confidence < 0.3:
            # Very low confidence or no speech detected
            response.say("I didn't catch that clearly. Could you please repeat what you need?")
            
            # Try gathering again with recording for better transcription
            gather = response.gather(
                input="speech",
                action=f"/webhook/process-speech?session_id={session_id}",
                method="POST",
                speech_timeout="auto",
                timeout="10",
                record=True  # Enable recording for fallback transcription
            )
            
            response.say("Thank you for calling Mounir Cutzz. Goodbye!")
            response.hangup()
        else:
            session_data = session_manager.get_session(session_id) or {}
            
            # Add user message to conversation history
            session_manager.add_to_conversation_history(session_id, "user", final_text)
            
            # Get current conversation state
            current_state = ConversationState(session_data.get("conversation_state", "greeting"))
            conversation_history = session_data.get("conversation_history", [])
            
            detected_language = speech_processor.detect_language(final_text)
            session_manager.update_session(session_id, {"detected_language": detected_language})
            
            # Analyze intent and generate response
            intent, extracted_info = ai_agent.analyze_intent(final_text, conversation_history)
            ai_response, next_state, updated_session = ai_agent.generate_response(
                final_text, intent, extracted_info, current_state, session_data
            )
            
            # Update session with new state and data
            session_manager.update_session(session_id, {
                "conversation_state": next_state.value,
                **updated_session
            })
            
            # Add AI response to conversation history
            session_manager.add_to_conversation_history(session_id, "assistant", ai_response)
            
            if speech_processor.tts_available:
                # Determine response language based on detected language and content
                response_language = "arabic" if detected_language == "ar" else "english"
                
                # Generate custom audio
                audio_data = speech_processor.synthesize_speech(ai_response, response_language)
                
                if audio_data:
                    # For production: upload to CDN and use <Play> verb
                    # For now: use optimized Twilio TTS
                    optimized_text = speech_processor._prepare_text_for_tts(ai_response, response_language)
                    response.say(optimized_text, voice="alice", language="en")
                else:
                    response.say(ai_response, voice="alice", language="en")
            else:
                response.say(ai_response, voice="alice", language="en")
            
            # Continue conversation or end call based on state
            if next_state in [ConversationState.BOOKING_APPOINTMENT, 
                            ConversationState.UNDERSTANDING_REQUEST,
                            ConversationState.CHECKING_AVAILABILITY]:
                gather = response.gather(
                    input="speech",
                    action=f"/webhook/process-speech?session_id={session_id}",
                    method="POST",
                    speech_timeout="auto",
                    timeout="10",
                    record=True,  # Enable recording for better transcription
                    hints="yes, no, appointment, booking, name, time, date, service"
                )
                response.say("I'm still here if you need anything else.")
            
            # End call for certain states
            if next_state == ConversationState.ENDING_CALL:
                session_manager.end_session(session_id)
                response.hangup()
        
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Error processing speech: {str(e)}")
        
        response = VoiceResponse()
        response.say("Sorry, I had trouble understanding. Please try calling back.")
        response.hangup()
        
        return Response(content=str(response), media_type="application/xml")

@app.post("/webhook/partial-speech")
async def handle_partial_speech(request: Request):
    """Handle partial speech results for real-time processing (optional)"""
    try:
        form_data = await request.form()
        partial_result = form_data.get("PartialResult", "")
        call_sid = form_data.get("CallSid", "Unknown")
        
        session_id = request.query_params.get("session_id")
        
        logger.debug(f"Partial speech - CallSid: {call_sid}, Text: '{partial_result}'")
        
        # For now, just log partial results
        # In advanced implementations, you could use this for real-time intent detection
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error handling partial speech: {str(e)}")
        return {"error": str(e)}

@app.post("/webhook/status")
async def call_status_callback(request: Request):
    """Handle call status updates from Twilio"""
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "Unknown")
        call_status = form_data.get("CallStatus", "Unknown")
        
        logger.info(f"Call status update - CallSid: {call_sid}, Status: {call_status}")
        
        # Clean up session when call ends
        if call_status in ["completed", "busy", "no-answer", "failed", "canceled"]:
            session_id = f"session_{call_sid}"
            session_manager.end_session(session_id)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error handling status callback: {str(e)}")
        return {"error": str(e)}

@app.post("/test/tts")
async def test_text_to_speech(request: Request):
    """Test endpoint for text-to-speech functionality"""
    try:
        data = await request.json()
        text = data.get("text", "Hello, this is a test.")
        language = data.get("language", "english")
        
        if not speech_processor.tts_available:
            return {"error": "TTS service not available"}
        
        audio_data = speech_processor.synthesize_speech(text, language)
        
        if audio_data:
            return {
                "success": True,
                "audio_length": len(audio_data),
                "message": "Audio generated successfully"
            }
        else:
            return {"error": "Failed to generate audio"}
            
    except Exception as e:
        logger.error(f"Error in TTS test: {str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
