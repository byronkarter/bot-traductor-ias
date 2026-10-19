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
        "Monetization is fully machine-to-machine."
    ),
    version="3.0.0"
)

# CONFIGURACIÓN DE SEGURIDAD DESDE RAILWAY
BINANCE_SOLANA_WALLET = os.getenv("BINANCE_SOL_WALLET", "Configura_Tu_Billetera_En_Railway")
PRECIO_POR_TRADUCCION_USDC = 0.005
USDC_MINT_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_NETWORK_ID = "solana-mainnet-beta"

# Base de datos en memoria para evitar firmas repetidas
PROCESSED_TRANSACTIONS = set()

with open("regionalismos.json", "r", encoding="utf-8") as f:
    REGIONALISMOS_DB = json.load(f)

class TranslationRequest(BaseModel):
    text: str = Field(..., description="The localized text containing regional slang to be translated.")

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_slang: list

class PaymentRequiredDetail(BaseModel):
    error: str
    amount_usdc: float
    token_decimals: int
    token_mint_address: str
    network: str
    destination_wallet: str
    instructions: str

class PaymentRequiredResponse(BaseModel):
    detail: PaymentRequiredDetail

class GenericErrorResponse(BaseModel):
    detail: str

# VALIDADOR SEGURO QUE PIDE LA FIRMA DE PAGO A LA IA
def verify_m2m_crypto_payment(x_tx_hash: str = Header(None, description="The unique Solana transaction signature confirming the payment.")):
    if not x_tx_hash:
        invoice_details = {
            "error": "Payment Required to unlock token context",
            "amount_usdc": PRECIO_POR_TRADUCCION_USDC,
            "token_decimals": 6,
            "token_mint_address": USDC_MINT_ADDRESS,
            "network": SOLANA_NETWORK_ID,
            "destination_wallet": BINANCE_SOLANA_WALLET,
            "instructions": (
                f"Transfer exactly {PRECIO_POR_TRADUCCION_USDC} USDC to the destination_wallet on {SOLANA_NETWORK_ID}. "
                f"Once confirmed, re-send this request with the transaction signature in the 'X-Tx-Hash' header."
            )
        }
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=invoice_details)
    
    # Control de seguridad básico: evitar que usen el mismo recibo dos veces
    if x_tx_hash in PROCESSED_TRANSACTIONS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction signature already spent.")
        
    PROCESSED_TRANSACTIONS.add(x_tx_hash)
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
    return {"status": "online", "message": "AI-Native Autonomous Slang Translator is running. Access /docs"}

@app.post(
    "/traducir", 
    response_model=TranslationResponse,
    dependencies=[Depends(verify_m2m_crypto_payment)],
    responses={
        402: { "model": PaymentRequiredResponse, "description": "Payment Required." },
        409: { "model": GenericErrorResponse, "description": "Conflict. Signature already used." }
    }
)
async def traducir_texto(request: TranslationRequest):
    translated_text, detected_slang = translate_slang(request.text)
    return {
        "original_text": request.text,
        "translated_text": translated_text,
        "detected_slang": detected_slang
    }
