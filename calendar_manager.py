from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Optional, Tuple
import os
import json
import logging

logger = logging.getLogger(__name__)

class CalendarManager:
    def __init__(self):
        self.calendar_id = os.getenv("GOOGLE_CALENDAR_ID")
        self.timezone = pytz.timezone(os.getenv("BARBER_SHOP_TIMEZONE", "Asia/Beirut"))
        self.service = self._authenticate()
        
        # Business hours configuration
        self.business_hours = {
            "monday": {"start": "09:00", "end": "20:00"},
            "tuesday": {"start": "09:00", "end": "20:00"},
            "wednesday": {"start": "09:00", "end": "20:00"},
            "thursday": {"start": "09:00", "end": "20:00"},
            "friday": {"start": "09:00", "end": "20:00"},
            "saturday": {"start": "09:00", "end": "20:00"},
            "sunday": {"start": None, "end": None}  # Closed
        }
        
        # Service duration mapping (in minutes)
        self.service_durations = {
            "haircut": 30,
            "beard trim": 15,
            "hair wash": 10,
            "full service": 45,
            "default": 30
        }
    
    def _authenticate(self):
        """Authenticate with Google Calendar API using service account"""
        try:
            # Prefer explicit path var; fall back to JSON string
            credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
            credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")

            if credentials_path and os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
            elif credentials_json:
                credentials_info = json.loads(credentials_json)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=['https://www.googleapis.com/auth/calendar']
                )
            else:
                logger.error("Google credentials not found")
                return None
            
            service = build('calendar', 'v3', credentials=credentials)
            logger.info("Successfully authenticated with Google Calendar")
            return service
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Calendar: {str(e)}")
            return None
    
    def check_availability(self, date: str, duration_minutes: int = 30) -> List[Dict]:
        """Check available time slots for a given date"""
        if not self.service:
            logger.error("Calendar service not available")
            return []
        
        try:
            # Parse the requested date
            requested_date = datetime.strptime(date, "%Y-%m-%d").date()
            day_name = requested_date.strftime("%A").lower()
            
            # Check if shop is open on this day
            if not self.business_hours[day_name]["start"]:
                logger.info(f"Shop closed on {day_name}")
                return []
            
            # Get business hours for the day
            start_time = datetime.strptime(self.business_hours[day_name]["start"], "%H:%M").time()
            end_time = datetime.strptime(self.business_hours[day_name]["end"], "%H:%M").time()
            
            # Create datetime objects in shop timezone
            start_datetime = self.timezone.localize(
                datetime.combine(requested_date, start_time)
            )
            end_datetime = self.timezone.localize(
                datetime.combine(requested_date, end_time)
            )
            
            # Get existing events for the day
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=start_datetime.isoformat(),
                timeMax=end_datetime.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Generate available slots
            available_slots = self._generate_available_slots(
                start_datetime, end_datetime, events, duration_minutes
            )
            
            logger.info(f"Found {len(available_slots)} available slots for {date}")
            return available_slots
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return []
    
    def _generate_available_slots(self, start_datetime: datetime, end_datetime: datetime, 
                                 existing_events: List[Dict], duration_minutes: int) -> List[Dict]:
        """Generate list of available time slots"""
        available_slots = []
        slot_duration = timedelta(minutes=duration_minutes)
        current_time = start_datetime
        
        # Convert existing events to datetime objects
        busy_periods = []
        for event in existing_events:
            event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))
            
            # Convert to shop timezone if needed
            if event_start.tzinfo is None:
                event_start = self.timezone.localize(event_start)
            if event_end.tzinfo is None:
                event_end = self.timezone.localize(event_end)
                
            busy_periods.append((event_start, event_end))
        
        # Generate slots every 15 minutes
        while current_time + slot_duration <= end_datetime:
            slot_end = current_time + slot_duration
            
            # Check if this slot conflicts with any existing event
            is_available = True
            for busy_start, busy_end in busy_periods:
                if (current_time < busy_end and slot_end > busy_start):
                    is_available = False
                    break
            
            if is_available:
                available_slots.append({
                    "start_time": current_time.strftime("%H:%M"),
                    "end_time": slot_end.strftime("%H:%M"),
                    "datetime": current_time.isoformat(),
                    "formatted_time": current_time.strftime("%I:%M %p")
                })
            
            # Move to next 15-minute slot
            current_time += timedelta(minutes=15)
        
        return available_slots
    
    def book_appointment(self, customer_name: str, phone: str, service: str, 
                        date: str, time: str) -> Tuple[bool, str, Optional[Dict]]:
        """Book an appointment in Google Calendar"""
        if not self.service:
            return False, "Calendar service not available", None
        
        try:
            # Parse date and time
            appointment_date = datetime.strptime(date, "%Y-%m-%d").date()
            appointment_time = datetime.strptime(time, "%H:%M").time()
            
            # Create datetime in shop timezone
            start_datetime = self.timezone.localize(
                datetime.combine(appointment_date, appointment_time)
            )
            
            # Calculate end time based on service
            service_key = service.lower().replace(" ", "_")
            duration = self.service_durations.get(service_key, self.service_durations["default"])
            end_datetime = start_datetime + timedelta(minutes=duration)
            
            # Check if slot is still available
            available_slots = self.check_availability(date, duration)
            slot_available = any(
                slot["start_time"] == time for slot in available_slots
            )
            
            if not slot_available:
                return False, "This time slot is no longer available", None
            
            # Create event
            event = {
                'summary': f'{service} - {customer_name}',
                'description': f'Customer: {customer_name}\nPhone: {phone}\nService: {service}',
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': str(self.timezone),
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': str(self.timezone),
                },
                # 'attendees': [
                #     {'email': customer_name.lower().replace(' ', '') + '@example.com', 'displayName': customer_name}
                # ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'sms', 'minutes': 60},  # 1 hour before
                        {'method': 'popup', 'minutes': 15},  # 15 minutes before
                    ],
                },
            }
            
            # Insert event
            created_event = self.service.events().insert(
                calendarId=self.calendar_id, 
                body=event
            ).execute()
            
            appointment_details = {
                "event_id": created_event['id'],
                "customer_name": customer_name,
                "phone": phone,
                "service": service,
                "date": date,
                "time": time,
                "formatted_datetime": start_datetime.strftime("%A, %B %d, %Y at %I:%M %p"),
                "calendar_link": created_event.get('htmlLink', '')
            }
            
            logger.info(f"Successfully booked appointment for {customer_name} on {date} at {time}")
            return True, "Appointment booked successfully", appointment_details
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {str(e)}")
            return False, "Failed to book appointment due to calendar error", None
        except Exception as e:
            logger.error(f"Error booking appointment: {str(e)}")
            return False, "Failed to book appointment", None
    
    def cancel_appointment(self, event_id: str) -> Tuple[bool, str]:
        """Cancel an appointment"""
        if not self.service:
            return False, "Calendar service not available"
        
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Successfully cancelled appointment {event_id}")
            return True, "Appointment cancelled successfully"
            
        except HttpError as e:
            logger.error(f"Error cancelling appointment: {str(e)}")
            return False, "Failed to cancel appointment"
    
    def get_upcoming_appointments(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming appointments for the next N days"""
        if not self.service:
            return []
        
        try:
            now = datetime.now(self.timezone)
            future = now + timedelta(days=days_ahead)
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now.isoformat(),
                timeMax=future.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            appointments = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                start_dt = datetime.fromisoformat(start)
                
                appointments.append({
                    "event_id": event['id'],
                    "summary": event.get('summary', ''),
                    "description": event.get('description', ''),
                    "start_time": start_dt.strftime("%Y-%m-%d %H:%M"),
                    "formatted_time": start_dt.strftime("%A, %B %d at %I:%M %p")
                })
            
            return appointments
            
        except Exception as e:
            logger.error(f"Error getting upcoming appointments: {str(e)}")
            return []
    
    def find_next_available_slots(self, days_to_check: int = 7, num_slots: int = 3) -> List[Dict]:
        """Find the next available appointment slots"""
        available_slots = []
        current_date = datetime.now(self.timezone).date()
        
        for i in range(days_to_check):
            check_date = current_date + timedelta(days=i)
            date_str = check_date.strftime("%Y-%m-%d")
            
            # Skip if it's today and past business hours
            if i == 0:
                current_time = datetime.now(self.timezone).time()
                day_name = check_date.strftime("%A").lower()
                if (self.business_hours[day_name]["end"] and 
                    current_time > datetime.strptime(self.business_hours[day_name]["end"], "%H:%M").time()):
                    continue
            
            day_slots = self.check_availability(date_str)
            
            for slot in day_slots[:2]:  # Take first 2 slots per day
                slot["date"] = date_str
                slot["formatted_date"] = check_date.strftime("%A, %B %d")
                available_slots.append(slot)
                
                if len(available_slots) >= num_slots:
                    return available_slots
        
        return available_slots
