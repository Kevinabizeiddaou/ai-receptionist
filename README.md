# Mounir Cutzz AI Phone Receptionist

An AI-powered phone receptionist system for Mounir Cutzz barber shop in Lebanon.

## Features

- 🎯 **Bilingual Support**: Arabic and English
- 📞 **Twilio Voice Integration**: Handle incoming calls
- 🤖 **AI Agent**: OpenAI GPT-4o-mini powered conversations
- 📅 **Google Calendar**: Automatic appointment booking
- 🗣️ **Speech Processing**: Whisper STT + AWS Polly TTS
- 📱 **SMS Confirmations**: Automatic booking confirmations

## Quick Start

1. **Clone and Setup**
   \`\`\`bash
   git clone <repository>
   cd ai-phone-receptionist
   cp .env.example .env

   # Edit .env with your credentials

   \`\`\`

2. **Run with Docker**
   \`\`\`bash
   docker-compose up -d
   \`\`\`

3. **Configure Twilio Webhook**
   - Set webhook URL to: `https://your-domain.com/webhook/voice`
   - Set status callback URL to: `https://your-domain.com/webhook/status`

## Environment Variables

See `.env.example` for required configuration.

## API Endpoints

- `GET /` - Health check
- `POST /webhook/voice` - Twilio voice webhook
- `POST /webhook/process-speech` - Speech processing
- `POST /webhook/status` - Call status callbacks

## Development

\`\`\`bash
pip install -r requirements.txt
uvicorn main:app --reload
\`\`\`

## Architecture

\`\`\`
Phone Call → Twilio → FastAPI → AI Agent → Google Calendar
↓
Speech Processing (STT/TTS)
