from openai import OpenAI
from typing import Dict, List, Optional, Tuple
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
import os
import re

from calendar_manager import CalendarManager

logger = logging.getLogger(__name__)

class ConversationState(Enum):
    GREETING = "greeting"
    UNDERSTANDING_REQUEST = "understanding_request"
    BOOKING_APPOINTMENT = "booking_appointment"
    CHECKING_AVAILABILITY = "checking_availability"
    CONFIRMING_DETAILS = "confirming_details"
    PROVIDING_INFO = "providing_info"
    ENDING_CALL = "ending_call"

class CustomerIntent(Enum):
    BOOK_APPOINTMENT = "book_appointment"
    CHECK_AVAILABILITY = "check_availability"
    ASK_HOURS = "ask_hours"
    ASK_SERVICES = "ask_services"
    ASK_PRICES = "ask_prices"
    ASK_LOCATION = "ask_location"
    CANCEL_APPOINTMENT = "cancel_appointment"
    OTHER = "other"

class AIAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.calendar_manager = CalendarManager()
        self.shop_info = {
            "name": "Mounir Cutzz",
            "location": "Lebanon",
            "hours": "Monday to Saturday, 9 AM to 8 PM. Closed on Sundays",
            "services": [
                "Haircut - $15",
                "Beard trim - $8", 
                "Hair wash - $5",
                "Full service (haircut + beard + wash) - $25"
            ],
            "phone": "+961 XX XXX XXX",
            "languages": ["Arabic", "English"]
        }
        
    def analyze_intent(self, user_message: str, conversation_history: List[Dict]) -> Tuple[CustomerIntent, Dict]:
        """Analyze customer intent using OpenAI"""
        try:
            system_prompt = f"""
            You are an AI assistant for {self.shop_info['name']} barber shop in Lebanon.
            Analyze the customer's message and determine their intent.
            
            Available intents:
            - book_appointment: Customer wants to book an appointment
            - check_availability: Customer asking about available times
            - ask_hours: Customer asking about opening hours
            - ask_services: Customer asking about services offered
            - ask_prices: Customer asking about prices
            - ask_location: Customer asking about location/address
            - cancel_appointment: Customer wants to cancel existing appointment
            - other: General inquiry or unclear intent
            
            Extract information like dates (today, tomorrow, Monday, etc.), times, services, and names.
            
            Respond with JSON format:
            {{
                "intent": "intent_name",
                "confidence": 0.95,
                "extracted_info": {{
                    "preferred_date": "YYYY-MM-DD format if mentioned",
                    "preferred_time": "HH:MM format if mentioned", 
                    "service_type": "exact service name if mentioned",
                    "customer_name": "if mentioned"
                }}
            }}
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Customer message: {user_message}"}
            ]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.3,
                max_tokens=200
            )
            
            result = json.loads(response.choices[0].message.content)
            intent = CustomerIntent(result["intent"])
            extracted_info = result.get("extracted_info", {})

            # Fallback: extract customer name from common patterns if model missed it
            if not extracted_info.get("customer_name"):
                # Patterns: "my name is Kevin", "I'm Kevin", "I am Kevin", "this is Kevin"
                name_patterns = [
                    r"my\s+name\s+is\s+([A-Za-z][A-Za-z\-\'\s]{1,40})",
                    r"i\s*'?m\s+([A-Za-z][A-Za-z\-\'\s]{1,40})",
                    r"i\s+am\s+([A-Za-z][A-Za-z\-\'\s]{1,40})",
                    r"this\s+is\s+([A-Za-z][A-Za-z\-\'\s]{1,40})",
                ]
                lower_msg = user_message.lower()
                for pat in name_patterns:
                    m = re.search(pat, lower_msg, re.IGNORECASE)
                    if m:
                        # Extract original-cased name by slicing from original text around match span
                        start, end = m.span(1)
                        extracted_name = user_message[start:end].strip().split()[0]
                        extracted_info["customer_name"] = extracted_name
                        break
            
            # Process relative dates
            extracted_info = self._process_extracted_dates(extracted_info, user_message)
            
            logger.info(f"Intent analysis: {intent.value}, confidence: {result.get('confidence', 0)}")
            return intent, extracted_info
            
        except Exception as e:
            logger.error(f"Error analyzing intent: {str(e)}")
            return CustomerIntent.OTHER, {}
    
    def _process_extracted_dates(self, extracted_info: Dict, user_message: str) -> Dict:
        """Process relative date references like 'today', 'tomorrow', 'Monday'"""
        today = datetime.now().date()
        print(today)
        if not extracted_info.get("preferred_date"):
            # Check for relative date keywords
            message_lower = user_message.lower()
            
            if "today" in message_lower:
                extracted_info["preferred_date"] = today.strftime("%Y-%m-%d")
            elif "tomorrow" in message_lower:
                tomorrow = today + timedelta(days=1)
                extracted_info["preferred_date"] = tomorrow.strftime("%Y-%m-%d")
            elif any(day in message_lower for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
                # Find next occurrence of the mentioned day
                days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                for day in days:
                    if day in message_lower:
                        target_day = days.index(day)
                        current_day = today.weekday()
                        days_ahead = (target_day - current_day) % 7
                        if days_ahead == 0:  # Same day, assume next week
                            days_ahead = 7
                        target_date = today + timedelta(days=days_ahead)
                        extracted_info["preferred_date"] = target_date.strftime("%Y-%m-%d")
                        break

        # If a date was extracted but it's in the past, adjust to this year or next
        try:
            if extracted_info.get("preferred_date"):
                parsed = datetime.strptime(extracted_info["preferred_date"], "%Y-%m-%d").date()
                if parsed < today:
                    # Move to current year keeping month/day
                    adjusted = parsed.replace(year=today.year)
                    if adjusted < today:
                        adjusted = adjusted.replace(year=today.year + 1)
                    extracted_info["preferred_date"] = adjusted.strftime("%Y-%m-%d")
        except Exception:
            # If parsing fails, keep original
            pass
        
        return extracted_info
    
    def generate_response(self, 
                         user_message: str, 
                         intent: CustomerIntent, 
                         extracted_info: Dict,
                         conversation_state: ConversationState,
                         session_data: Dict) -> Tuple[str, ConversationState, Dict]:
        """Generate appropriate response based on intent and state"""
        
        try:
            # If we have any booking-related info or are already booking, continue booking flow
            booking_keys = {"customer_name", "preferred_date", "preferred_time", "service_type"}
            has_booking_info = any(k in extracted_info and extracted_info.get(k) for k in booking_keys)
            has_booking_context = bool(session_data.get("appointment_details"))

            if conversation_state == ConversationState.BOOKING_APPOINTMENT or has_booking_info or has_booking_context:
                return self._handle_appointment_booking(extracted_info, conversation_state, session_data)

            # If we are checking availability, keep that flow regardless of intent classification
            if conversation_state == ConversationState.CHECKING_AVAILABILITY and intent != CustomerIntent.BOOK_APPOINTMENT:
                return self._handle_availability_check(extracted_info, session_data)
            # Handle calendar-related intents
            if intent == CustomerIntent.CHECK_AVAILABILITY:
                return self._handle_availability_check(extracted_info, session_data)
            elif intent == CustomerIntent.BOOK_APPOINTMENT:
                return self._handle_appointment_booking(extracted_info, conversation_state, session_data)
            
            # Build context for other intents
            context = self._build_context(intent, extracted_info, conversation_state, session_data)
            
            system_prompt = f"""
            You are the AI receptionist for {self.shop_info['name']} barber shop in Lebanon.
            
            Shop Information:
            - Hours: {self.shop_info['hours']}
            - Services: {', '.join(self.shop_info['services'])}
            - Location: Lebanon
            
            Guidelines:
            - Be friendly, professional, and helpful
            - Keep responses concise (1-2 sentences max for phone calls)
            - Use simple, clear language
            - If booking appointment, ask for name, preferred date/time, and service
            - Always confirm important details
            - Speak naturally as if on a phone call
            - Mix Arabic greetings when appropriate (مرحبا، أهلا وسهلا)
            
            Current context: {context}
            Customer intent: {intent.value}
            Conversation state: {conversation_state.value}
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Determine next state and update session data
            next_state, updated_session = self._determine_next_state(
                intent, conversation_state, extracted_info, session_data
            )
            
            logger.info(f"Generated response: {ai_response[:50]}...")
            return ai_response, next_state, updated_session
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            fallback_response = "I apologize, I'm having trouble processing your request. Could you please repeat that?"
            return fallback_response, conversation_state, session_data
    
    def _handle_availability_check(self, extracted_info: Dict, session_data: Dict) -> Tuple[str, ConversationState, Dict]:
        """Handle availability checking requests"""
        date = extracted_info.get("preferred_date")
        
        if not date:
            # Ask for date
            next_slots = self.calendar_manager.find_next_available_slots(days_to_check=7, num_slots=3)
            if next_slots:
                slots_text = ", ".join([f"{slot['formatted_date']} at {slot['formatted_time']}" for slot in next_slots[:3]])
                response = f"I can check availability for you. Our next available slots are: {slots_text}. Which date works for you?"
            else:
                response = "Let me check our availability. Which date are you interested in?"
            
            return response, ConversationState.CHECKING_AVAILABILITY, session_data
        
        # Check availability for specific date
        available_slots = self.calendar_manager.check_availability(date)
        
        if available_slots:
            # Show first few available slots
            slots_text = ", ".join([slot["formatted_time"] for slot in available_slots[:5]])
            formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d")
            response = f"For {formatted_date}, we have availability at: {slots_text}. Would you like to book one of these times?"
            
            updated_session = session_data.copy()
            updated_session["checked_date"] = date
            updated_session["available_slots"] = available_slots
            
            return response, ConversationState.BOOKING_APPOINTMENT, updated_session
        else:
            # No availability, suggest alternatives
            next_slots = self.calendar_manager.find_next_available_slots(days_to_check=7, num_slots=3)
            if next_slots:
                slots_text = ", ".join([f"{slot['formatted_date']} at {slot['formatted_time']}" for slot in next_slots[:3]])
                response = f"Sorry, we're fully booked that day. Our next available appointments are: {slots_text}. Would any of these work?"
            else:
                response = "Sorry, we're fully booked that day. Let me check other dates for you."
            
            return response, ConversationState.CHECKING_AVAILABILITY, session_data
    
    def _handle_appointment_booking(self, extracted_info: Dict, conversation_state: ConversationState, session_data: Dict) -> Tuple[str, ConversationState, Dict]:
        """Handle appointment booking process"""
        updated_session = session_data.copy()
        appointment_details = updated_session.get("appointment_details", {})
        
        # Update appointment details with extracted info
        if extracted_info.get("customer_name"):
            appointment_details["customer_name"] = extracted_info["customer_name"]
        if extracted_info.get("preferred_date"):
            appointment_details["preferred_date"] = extracted_info["preferred_date"]
        if extracted_info.get("preferred_time"):
            appointment_details["preferred_time"] = extracted_info["preferred_time"]
        if extracted_info.get("service_type"):
            appointment_details["service_type"] = extracted_info["service_type"]
        
        updated_session["appointment_details"] = appointment_details
        
        # Check what information we still need
        missing_info = []
        if not appointment_details.get("customer_name"):
            missing_info.append("name")
        if not appointment_details.get("preferred_date"):
            missing_info.append("date")
        if not appointment_details.get("preferred_time"):
            missing_info.append("time")
        if not appointment_details.get("service_type"):
            missing_info.append("service")
        
        if missing_info:
            # Ask for missing information
            if "name" in missing_info:
                response = "I'd be happy to book an appointment for you. May I have your name please?"
            elif "service" in missing_info:
                services = "haircut, beard trim, hair wash, or full service"
                response = f"What service would you like? We offer {services}."
            elif "date" in missing_info:
                next_slots = self.calendar_manager.find_next_available_slots(days_to_check=7, num_slots=3)
                if next_slots:
                    slots_text = ", ".join([f"{slot['formatted_date']}" for slot in next_slots[:3]])
                    response = f"Which date works for you? We have availability on {slots_text}."
                else:
                    response = "Which date would you prefer for your appointment?"
            elif "time" in missing_info:
                if appointment_details.get("preferred_date"):
                    available_slots = self.calendar_manager.check_availability(appointment_details["preferred_date"])
                    if available_slots:
                        slots_text = ", ".join([slot["formatted_time"] for slot in available_slots[:5]])
                        response = f"What time works best? We have: {slots_text}."
                    else:
                        response = "What time would you prefer? I'll check if it's available."
                else:
                    response = "What time would you prefer for your appointment?"
            
            return response, ConversationState.BOOKING_APPOINTMENT, updated_session
        
        # We have all information, try to book
        success, message, booking_details = self.calendar_manager.book_appointment(
            customer_name=appointment_details["customer_name"],
            phone=session_data.get("caller_number", "Unknown"),
            service=appointment_details["service_type"],
            date=appointment_details["preferred_date"],
            time=appointment_details["preferred_time"]
        )
        
        if success:
            updated_session["booking_confirmed"] = True
            updated_session["booking_details"] = booking_details
            response = f"Perfect! I've booked your {appointment_details['service_type']} appointment for {booking_details['formatted_datetime']}. You'll receive a confirmation. Is there anything else I can help you with?"
            return response, ConversationState.ENDING_CALL, updated_session
        else:
            response = f"I'm sorry, {message}. Let me check other available times for you."
            return response, ConversationState.CHECKING_AVAILABILITY, updated_session

    def _build_context(self, intent: CustomerIntent, extracted_info: Dict, 
                      state: ConversationState, session_data: Dict) -> str:
        """Build context string for the AI"""
        context_parts = []
        
        if session_data.get("customer_name"):
            context_parts.append(f"Customer name: {session_data['customer_name']}")
        
        if session_data.get("appointment_details"):
            details = session_data["appointment_details"]
            context_parts.append(f"Appointment being discussed: {details}")
        
        if extracted_info:
            context_parts.append(f"Extracted info: {extracted_info}")
        
        return "; ".join(context_parts) if context_parts else "New conversation"
    
    def _determine_next_state(self, intent: CustomerIntent, current_state: ConversationState,
                             extracted_info: Dict, session_data: Dict) -> Tuple[ConversationState, Dict]:
        """Determine next conversation state and update session data"""
        
        updated_session = session_data.copy()
        
        # Update session with extracted information
        if extracted_info.get("customer_name"):
            updated_session["customer_name"] = extracted_info["customer_name"]
        
        if intent == CustomerIntent.BOOK_APPOINTMENT:
            return ConversationState.BOOKING_APPOINTMENT, updated_session
        elif intent == CustomerIntent.CHECK_AVAILABILITY:
            return ConversationState.CHECKING_AVAILABILITY, updated_session
        elif intent in [CustomerIntent.ASK_HOURS, CustomerIntent.ASK_SERVICES, 
                       CustomerIntent.ASK_PRICES, CustomerIntent.ASK_LOCATION]:
            return ConversationState.PROVIDING_INFO, updated_session
        elif intent == CustomerIntent.OTHER:
            if current_state == ConversationState.GREETING:
                return ConversationState.UNDERSTANDING_REQUEST, updated_session
        
        # Default: stay in current state
        return current_state, updated_session
    
    def get_shop_info_response(self, intent: CustomerIntent) -> str:
        """Get predefined responses for shop information"""
        responses = {
            CustomerIntent.ASK_HOURS: f"We're open {self.shop_info['hours']}. Would you like to book an appointment?",
            CustomerIntent.ASK_SERVICES: f"We offer: {', '.join(self.shop_info['services'])}. What service interests you?",
            CustomerIntent.ASK_LOCATION: "We're located in Lebanon. Would you like directions or to book an appointment?",
            CustomerIntent.ASK_PRICES: f"Our services are: {', '.join(self.shop_info['services'])}. Which service would you like?"
        }
        return responses.get(intent, "How can I help you today?")
