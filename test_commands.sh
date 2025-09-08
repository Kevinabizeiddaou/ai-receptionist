#!/bin/bash

# Test Commands for AI Phone Receptionist
# Run these in your terminal after starting the server with: uvicorn main:app --reload

echo "🧪 AI Phone Receptionist Test Commands"
echo "======================================"
echo ""

echo "1. Health Check:"
echo "curl http://localhost:8000/"
echo ""

echo "2. Test AI Agent Response:"
echo "curl -X POST http://localhost:8000/test/ai \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"message\": \"What are your hours?\", \"language\": \"en\"}'"
echo ""

echo "3. Test Speech Processing:"
echo "curl -X POST http://localhost:8000/test/speech \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"text\": \"I want to book an appointment for tomorrow at 2pm\", \"language\": \"en\"}'"
echo ""

echo "4. Test Calendar Availability:"
echo "curl http://localhost:8000/test/availability?date=2024-01-15"
echo ""

echo "5. Test Text-to-Speech:"
echo "curl -X POST http://localhost:8000/test/tts \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"text\": \"Hello, welcome to Mounir Cutzz!\", \"language\": \"english\"}'"
echo ""

echo "6. Simulate Full Call:"
echo "curl -X POST http://localhost:8000/test/simulate-call \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{"
echo "    \"caller\": \"+1234567890\","
echo "    \"messages\": ["
echo "      \"Hello, I want to book an appointment\","
echo "      \"Tomorrow at 2pm please\","
echo "      \"Yes, my name is John Smith\""
echo "    ]"
echo "  }'"
echo ""

echo "7. Check Active Sessions:"
echo "curl http://localhost:8000/test/sessions"
echo ""

echo "💡 Usage:"
echo "1. Copy and paste these commands into your terminal"
echo "2. Make sure your server is running: uvicorn main:app --reload"
echo "3. Start with the health check, then try the AI agent test"
echo "4. Use the simulate-call endpoint to test complete conversations"
