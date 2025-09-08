import boto3
from openai import OpenAI
import tempfile
import os
import logging
from typing import Optional, Tuple
import httpx
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class SpeechProcessor:
    def __init__(self):
        # Initialize OpenAI client for Whisper STT
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize AWS Polly for TTS
        try:
            self.polly_client = boto3.client(
                'polly',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
            # Test Polly connection
            self.polly_client.describe_voices()
            logger.info("Successfully connected to AWS Polly")
            self.tts_available = True
        except (ClientError, NoCredentialsError) as e:
            logger.warning(f"AWS Polly not available: {str(e)}. Falling back to Twilio TTS")
            self.polly_client = None
            self.tts_available = False
        
        # Voice configuration
        self.voice_config = {
            "english": {
                "voice_id": "Joanna",  # Natural US English voice
                "language_code": "en-US"
            },
            "arabic": {
                "voice_id": "Zeina",   # Arabic voice
                "language_code": "arb"
            }
        }
    
    async def transcribe_audio(self, audio_url: str, language: str = "en") -> Tuple[Optional[str], float]:
        """
        Transcribe audio using OpenAI Whisper
        
        Args:
            audio_url: URL to the audio file from Twilio
            language: Language code for transcription
            
        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        try:
            # Download audio file from Twilio
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url)
                response.raise_for_status()
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
            
            # Transcribe with Whisper
            with open(temp_file_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json",
                    temperature=0.2
                )
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            transcribed_text = transcript.text.strip()
            confidence = getattr(transcript, 'confidence', 0.8)  # Whisper doesn't always return confidence
            
            logger.info(f"Transcribed audio: '{transcribed_text}' (confidence: {confidence})")
            return transcribed_text, confidence
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return None, 0.0
    
    def synthesize_speech(self, text: str, language: str = "english") -> Optional[bytes]:
        """
        Convert text to speech using AWS Polly
        
        Args:
            text: Text to convert to speech
            language: Language for synthesis ("english" or "arabic")
            
        Returns:
            Audio data as bytes, or None if failed
        """
        if not self.tts_available:
            logger.warning("TTS not available, falling back to Twilio TTS")
            return None
        
        try:
            voice_config = self.voice_config.get(language, self.voice_config["english"])
            
            # Clean and prepare text for TTS
            cleaned_text = self._prepare_text_for_tts(text, language)
            
            response = self.polly_client.synthesize_speech(
                Text=cleaned_text,
                OutputFormat='mp3',
                VoiceId=voice_config["voice_id"],
                LanguageCode=voice_config["language_code"],
                Engine='neural'  # Use neural engine for more natural speech
            )
            
            # Get audio stream
            audio_data = response['AudioStream'].read()
            
            logger.info(f"Synthesized speech for text: '{text[:50]}...' in {language}")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error synthesizing speech: {str(e)}")
            return None
    
    def _prepare_text_for_tts(self, text: str, language: str) -> str:
        """
        Prepare text for TTS by cleaning and adding SSML if needed
        
        Args:
            text: Raw text to clean
            language: Target language
            
        Returns:
            Cleaned text ready for TTS
        """
        # Remove excessive punctuation
        cleaned_text = text.replace("...", ".")
        cleaned_text = cleaned_text.replace("!!", "!")
        cleaned_text = cleaned_text.replace("??", "?")
        
        # Handle mixed language content
        if language == "english" and any(ord(char) > 127 for char in text):
            # Text contains non-ASCII characters (likely Arabic)
            # Split into segments and handle appropriately
            segments = self._split_mixed_language_text(cleaned_text)
            return self._create_ssml_for_mixed_content(segments)
        
        # Add pauses for better speech flow
        cleaned_text = cleaned_text.replace(". ", ". <break time='0.5s'/> ")
        cleaned_text = cleaned_text.replace("? ", "? <break time='0.5s'/> ")
        cleaned_text = cleaned_text.replace("! ", "! <break time='0.5s'/> ")
        
        # Wrap in SSML if contains breaks
        if "<break" in cleaned_text:
            cleaned_text = f"<speak>{cleaned_text}</speak>"
        
        return cleaned_text
    
    def _split_mixed_language_text(self, text: str) -> list:
        """Split text into language segments"""
        segments = []
        current_segment = ""
        current_lang = "english"
        
        for char in text:
            if ord(char) > 127:  # Non-ASCII (likely Arabic)
                if current_lang == "english" and current_segment:
                    segments.append(("english", current_segment.strip()))
                    current_segment = ""
                current_lang = "arabic"
            else:  # ASCII (likely English)
                if current_lang == "arabic" and current_segment:
                    segments.append(("arabic", current_segment.strip()))
                    current_segment = ""
                current_lang = "english"
            
            current_segment += char
        
        # Add final segment
        if current_segment.strip():
            segments.append((current_lang, current_segment.strip()))
        
        return segments
    
    def _create_ssml_for_mixed_content(self, segments: list) -> str:
        """Create SSML for mixed language content"""
        ssml_parts = ["<speak>"]
        
        for lang, text in segments:
            if lang == "arabic":
                ssml_parts.append(f'<lang xml:lang="ar">{text}</lang>')
            else:
                ssml_parts.append(f'<lang xml:lang="en-US">{text}</lang>')
            
            # Add pause between segments
            ssml_parts.append('<break time="0.3s"/>')
        
        ssml_parts.append("</speak>")
        return "".join(ssml_parts)
    
    def detect_language(self, text: str) -> str:
        """
        Detect the primary language of the text
        
        Args:
            text: Text to analyze
            
        Returns:
            Language code ("en" for English, "ar" for Arabic)
        """
        # Simple heuristic: count Arabic vs Latin characters
        arabic_chars = sum(1 for char in text if 0x0600 <= ord(char) <= 0x06FF)
        latin_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        if arabic_chars > latin_chars:
            return "ar"
        else:
            return "en"
    
    def get_supported_voices(self) -> dict:
        """Get list of available voices for each language"""
        if not self.tts_available:
            return {}
        
        try:
            response = self.polly_client.describe_voices()
            voices = {}
            
            for voice in response['Voices']:
                lang_code = voice['LanguageCode']
                if lang_code not in voices:
                    voices[lang_code] = []
                
                voices[lang_code].append({
                    'id': voice['Id'],
                    'name': voice['Name'],
                    'gender': voice['Gender'],
                    'engine': voice.get('SupportedEngines', [])
                })
            
            return voices
            
        except Exception as e:
            logger.error(f"Error getting supported voices: {str(e)}")
            return {}
    
    async def process_twilio_recording(self, recording_url: str, account_sid: str, auth_token: str) -> Tuple[Optional[str], float]:
        """
        Process a Twilio recording URL with authentication
        
        Args:
            recording_url: Twilio recording URL
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            
        Returns:
            Tuple of (transcribed_text, confidence_score)
        """
        try:
            # Download recording with Twilio authentication
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    recording_url,
                    auth=(account_sid, auth_token)
                )
                response.raise_for_status()
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name
            
            # Transcribe the recording
            with open(temp_file_path, "rb") as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    temperature=0.2
                )
            
            # Clean up
            os.unlink(temp_file_path)
            
            transcribed_text = transcript.text.strip()
            confidence = getattr(transcript, 'confidence', 0.8)
            
            logger.info(f"Processed Twilio recording: '{transcribed_text}' (confidence: {confidence})")
            return transcribed_text, confidence
            
        except Exception as e:
            logger.error(f"Error processing Twilio recording: {str(e)}")
            return None, 0.0
