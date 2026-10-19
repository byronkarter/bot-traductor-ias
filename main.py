import os
import json
from fastapi import FastAPI, Header, HTTPException, status, Depends
from pydantic import BaseModel
import stripe

# Inicialización de la API con metadatos optimizados para descubrimiento de IA (LLM-friendly)
app = FastAPI(
    title="AI-Native Autonomous Slang Translator API",
    description=(
        "An automated API specifically designed for external AI agents and LLMs. "
        "This service resolves cultural and regional language gaps by translating localized "
        "slang, idioms, and native regionalisms into neutral Spanish or English. "
        "Requires a valid pre-paid Stripe API key via 'X-API-Key' header. Charging is per-usage."
    ),
    version="1.0.0"
)

# Configuración de Stripe (Se cargará de las variables de entorno)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # ID del producto/tarifa por uso en Stripe

# Cargar base de datos de modismos
with open("regionalismos.json", "r", encoding="utf-8") as f:
    REGIONALISMOS_DB = json.load(f)

class TranslationRequest(BaseModel):
    text: str

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_slang: list

# Función para verificar el pago y registrar el uso en Stripe
def verify_ai_payment(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing 'X-API-Key' header. Autonomous agents must provide a valid token."
        )
    
    try:
        # En un entorno real, Stripe mapea la API Key del cliente con su suscripción de cobro por uso
        # Buscamos la suscripción activa asociada a este token/cliente
        subscription_item = stripe.SubscriptionItem.retrieve(x_api_key)
        
        # Registramos 1 uso en Stripe (Metered Billing) inmediatamente antes de dar el servicio
        stripe.SubscriptionItem.create_usage_record(
            subscription_item.id,
            quantity=1,
            action="increment"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Payment verification or metered billing failed: {str(e)}"
        )
    return x_api_key

# Algoritmo de traducción semántica simplificado para el bot
def translate_slang(text: str):
    detected = []
    lower_text = text.lower()
    translated = text
    
    for item in REGIONALISMOS_DB:
        palabra = item["palabra"].lower()
        if palabra in lower_text:
            # Reemplazo básico de la jerga por su significado neutro
            import re
            insub = re.compile(re.escape(palabra), re.IGNORECASE)
            translated = insub.sub(f"{item['significado_neutro']} ({item['pais']})", translated)
            detected.append(item)
            
    return translated, detected

@app.post(
    "/traducir", 
    response_model=TranslationResponse,
    dependencies=[Depends(verify_ai_payment)],
    summary="Translate regional text and auto-charge the agent",
    description="Processes text containing strong regional slangs, normalizes it, and reports usage directly to Stripe."
)
async def traducir_texto(request: TranslationRequest):
    translated_text, detected_slang = translate_slang(request.text)
    return {
        "original_text": request.text,
        "translated_text": translated_text,
        "detected_slang": detected_slang
    }
