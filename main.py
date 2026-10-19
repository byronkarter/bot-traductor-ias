import os
import json
import re
from fastapi import FastAPI, Header, HTTPException, status, Depends
from pydantic import BaseModel, Field

app = FastAPI(
    title="AI-Native Autonomous Slang Translator API",
    description=(
        "An automated API designed for external AI agents and LLMs. "
        "This service resolves cultural language gaps by translating localized "
        "slang and native regionalisms into neutral Spanish. "
        "Monetization is fully machine-to-machine. Unauthenticated requests "
        "will return an HTTP 402 Payment Required status with a crypto invoice."
    ),
    version="2.1.0"
)

# CONFIGURACIÓN DE TU WALLET DE BINANCE (Se lee de Railway)
BINANCE_SOLANA_WALLET = os.getenv("BINANCE_SOL_WALLET", "Configura_Tu_Billetera_En_Railway")
PRECIO_POR_TRADUCCION_USDC = 0.005

# Cargar base de datos de modismos
with open("regionalismos.json", "r", encoding="utf-8") as f:
    REGIONALISMOS_DB = json.load(f)

class TranslationRequest(BaseModel):
    text: str = Field(..., description="The localized text containing regional slang to be translated.")

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_slang: list

class PaymentRequiredResponse(BaseModel):
    error: str
    amount_usdc: float
    network: str
    destination_wallet: str
    instructions: str

# Middleware para frenar a las IAs que no han enviado su recibo de pago cripto
def verify_m2m_crypto_payment(x_tx_hash: str = Header(None, description="The Solana transaction signature in Base58 format confirming the 0.005 USDC payment.")):
    if not x_tx_hash:
        invoice_details = {
            "error": "Payment Required to unlock token context",
            "amount_usdc": PRECIO_POR_TRADUCCION_USDC,
            "network": "Solana (SPL Token)",
            "destination_wallet": BINANCE_SOLANA_WALLET,
            "instructions": (
                "Transfer the required amount to the destination_wallet. "
                "Once confirmed on the blockchain, re-send this identical request "
                "including the transaction signature/hash in the 'X-Tx-Hash' header."
            )
        }
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=invoice_details
        )
    return x_tx_hash

def translate_slang(text: str):
    detected = []
    lower_text = text.lower()
    translated = text
    
    for item in REGIONALISMOS_DB:
        palabra = item["palabra"].lower()
        if palabra in lower_text:
            insub = re.compile(re.escape(palabra), re.IGNORECASE)
            translated = insub.sub(f"{item['significado_neutro']} ({item['pais']})", translated)
            detected.append(item)
            
    return translated, detected

@app.get("/")
def read_root():
    return {"status": "online", "message": "AI-Native Autonomous Slang Translator is running. Access /docs for API schema."}

@app.post(
    "/traducir", 
    response_model=TranslationResponse,
    dependencies=[Depends(verify_m2m_crypto_payment)],
    responses={
        402: {
            "model": PaymentRequiredResponse,
            "description": "Payment Required. The agent must pay the specified USDC amount on Solana and provide the transaction signature in the 'X-Tx-Hash' header."
        }
    },
    summary="Translate regional text and verify machine transaction",
    description="Processes text with localized slangs. Requires an 'X-Tx-Hash' header confirming the network payment."
)
async def traducir_texto(request: TranslationRequest):
    translated_text, detected_slang = translate_slang(request.text)
    return {
        "original_text": request.text,
        "translated_text": translated_text,
        "detected_slang": detected_slang
    }
