import os
import json
import re
from fastapi import FastAPI, Header, HTTPException, status, Depends
from pydantic import BaseModel, Field
from solana.rpc.api import Client

app = FastAPI(
    title="AI-Native Autonomous Slang Translator API",
    description=(
        "An automated API designed for external AI agents and LLMs. "
        "This service resolves cultural language gaps by translating localized "
        "slang and native regionalisms into neutral Spanish. "
        "Monetization is fully machine-to-machine with robust on-chain validation."
    ),
    version="2.4.0"
)

# CONFIGURACIÓN DE SEGURIDAD Y BLOCKCHAIN REAL
BINANCE_SOLANA_WALLET = os.getenv("BINANCE_SOL_WALLET")
PRECIO_POR_TRADUCCION_USDC = 0.005
USDC_MINT_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOLANA_NETWORK_ID = "solana-mainnet-beta"

# Nodo oficial RPC para conectar con la red principal de Solana
solana_client = Client("https://solana.com")

# Registro en memoria para evitar firmas reutilizadas (Idempotencia)
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

# FUNCIÓN CRÍTICA DE AUDITORÍA ON-CHAIN SOLICITADA POR EL AGENTE
def verify_m2m_crypto_payment(x_tx_hash: str = Header(None, description="The unique Solana transaction signature in Base58 format confirming the 0.005 USDC payment.")):
    if not BINANCE_SOLANA_WALLET or "example" in BINANCE_SOLANA_WALLET.lower():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server misconfiguration: Production destination wallet missing.")

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
                f"The transaction must transfer SPL token mint {USDC_MINT_ADDRESS}. "
                "Once confirmed, re-send this request with the unique transaction signature in the 'X-Tx-Hash' header."
            )
        }
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=invoice_details)
    
    # 1. COMPROBACIÓN DE IDEMPOTENCIA (Evita firmas reutilizadas)
    if x_tx_hash in PROCESSED_TRANSACTIONS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Transaction signature already used and settled.")
    
    # 2. VALIDACIÓN PROFUNDA DIRECTAMENTE EN LA BLOCKCHAIN DE SOLANA
    try:
        tx_response = solana_client.get_transaction(x_tx_hash, max_supported_transaction_version=0)
        if not tx_response or tx_response.value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transaction signature not found on solana-mainnet-beta.")
        
        meta = tx_response.value.transaction.meta
        transaction_data = tx_response.value.transaction.transaction
        
        if meta.err is not None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target transaction failed on-chain.")

        # EXTRACCIÓN Y VERIFICACIÓN DE PASES DE TOKEN (Token Balances)
        # Verificamos que el balance final de tu billetera aumentó en 5000 unidades (0.005 USDC) 
        # y que el Mint interactuado pertenece al USDC real.
        usdc_transfer_valid = False
        
        post_token_balances = meta.post_token_balances
        pre_token_balances = meta.pre_token_balances
        
        for post_bal in post_token_balances:
            # Validamos si la cuenta destino coincide con tu wallet y el mint es USDC
            if post_bal.owner == BINANCE_SOLANA_WALLET and post_bal.mint == USDC_MINT_ADDRESS:
                # Buscamos el balance previo para calcular la diferencia exacta
                pre_amount = 0
                for pre_bal in pre_token_balances:
                    if pre_bal.owner == BINANCE_SOLANA_WALLET and pre_bal.mint == USDC_MINT_ADDRESS:
                        pre_amount = int(pre_bal.ui_token_amount.amount)
                        break
                
                post_amount = int(post_bal.ui_token_amount.amount)
                diff = post_amount - pre_amount
                
                # 5000 unidades atómicas = 0.005 USDC debido a los 6 decimales
                if diff >= 5000:
                    usdc_transfer_valid = True
                    break

        if not usdc_transfer_valid:
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Transaction does not contain a valid 0.005 USDC transfer to the destination wallet.")
            
        # Si la transacción pasa todos los escudos criptográficos, bloqueamos el hash
        PROCESSED_TRANSACTIONS.add(x_tx_hash)
        
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"On-chain transaction forensic analysis failed: {str(e)}")
        
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
        402: { "model": PaymentRequiredResponse, "description": "Payment Required. Returns structured 'detail' node with on-chain challenge requirements." },
        400: { "model": GenericErrorResponse, "description": "Bad Request. Transaction signature not found or transaction failed on-chain." },
        409: { "model": GenericErrorResponse, "description": "Conflict. The transaction signature has already been spent." },
        422: { "model": GenericErrorResponse, "description": "Unprocessable Entity. Cryptographic forensic analysis failed." }
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
