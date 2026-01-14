"""Chat endpoint"""
from fastapi import APIRouter, HTTPException
from models import ChatRequest, ChatResponse
from services.ollama_client import get_ollama_client

router = APIRouter(tags=["Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Direct chat with the AI model"""
    client = get_ollama_client()

    context = ""
    for msg in request.history:
        context += f"{msg.role.upper()}: {msg.content}\n"

    full_prompt = f"{context}USER: {request.message}\nASSISTANT:"

    try:
        result = await client.generate(
            model=request.model,
            prompt=full_prompt,
            system_prompt="Sen MİNNAL AI ADMİN yardımcısısın. Medya Takip Merkezi (MTM) platformu içerisinde genel bir AI asistanı olarak görev yapıyorsun. Kullanıcıyla normal bir sohbet kur, her şeyi bir haber merkezi formatında analiz etmeye zorlama. Yardımsever, zeki ve özgün yanıtlar ver.",
            json_schema={"response": {"type": "string", "description": "The assistant's response"}},
            keep_alive="10m"
        )

        return ChatResponse(
            response=result["result"]["response"],
            response_time_ms=result["response_time_ms"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
