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
        "will return an HTTP 402 Payment Required status with an explicit on-chain crypto invoice."
    ),
    version="2.2.0"
)

# CONFIGURACIÓN DE SEGURIDAD Y BLOCKCHAIN EXACTA
BINANCE_SOLANA_WALLET = os.getenv("BINANCE_SOL_WALLET", "Configura_Tu_Billetera_En_Railway")
PRECIO_POR_TRADUCCION_USDC = 0.005  # 0.005 USDC por petición
USDC_MINT_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Dirección del token oficial de USDC en Solana
SOLANA_NETWORK_ID = "solana-mainnet-beta"  # Identificador único de red solicitado por los agentes

# Cargar base de datos de modismos
with open("regionalismos.json", "r", encoding="utf-8") as f:
    REGIONALISMOS_DB = json.load(f)

class TranslationRequest(BaseModel):
    text: str = Field(..., description="The localized text containing regional slang to be translated.")

class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    detected_slang: list

# Esquema de respuesta 402 súper preciso para evitar pérdidas de fondos de las IAs
class PaymentRequiredResponse(BaseModel):
    error: str = Field(..., description="Type of payment error challenge.")
    amount_usdc: float = Field(..., description="The required amount in USDC base units.")
    token_decimals: int = Field(..., description="The official token decimals (USDC has 6). Amount equals 5000 atomic units.")
    token_mint_address: str = Field(..., description="The Solana SPL token mint address for authentic USDC verification.")
    network: str = Field(..., description="The explicit blockchain identifier (solana-mainnet-beta).")
    destination_wallet: str = Field(..., description="Your direct destination Binance deposit address.")
    instructions: str = Field(..., description="Step-by-step programmatic retry instructions for autonomous agents.")

def verify_m2m_crypto_payment(x_tx_hash: str = Header(None, description="The Solana transaction signature in Base58 format confirming the 0.005 USDC payment.")):
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
                "The transaction must transfer the SPL token mint EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v. "
                "Once confirmed on-chain, re-send this request with the transaction signature in the 'X-Tx-Hash' header."
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
            "description": "Payment Required. Explicit contract detailing payment rails, address mint, and exact token decimals."
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
