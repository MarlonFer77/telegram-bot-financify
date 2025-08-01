import httpx
from core import config

API_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

async def send_message(chat_id: int, text: str, reply_markup: dict | None = None):
    """
    Envia uma mensagem de texto para um chat específico no Telegram.
    Pode incluir um teclado de botões inline (reply_markup).
    """
    payload = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{API_URL}/sendMessage", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"Erro ao enviar mensagem para o Telegram: {e.response.text}")

async def download_telegram_file(file_id: str) -> bytes | None:
    """
    Baixa um arquivo do Telegram usando seu file_id.
    """
    async with httpx.AsyncClient() as client:
        try:
            # 1. Obter o file_path
            get_file_url = f"{API_URL}/getFile"
            response = await client.post(get_file_url, json={"file_id": file_id})
            response.raise_for_status()
            file_path = response.json()["result"]["file_path"]

            # 2. Baixar o arquivo usando o file_path
            file_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
            download_response = await client.get(file_url)
            download_response.raise_for_status()
            
            return download_response.content # Retorna os bytes da imagem
        except httpx.HTTPStatusError as e:
            print(f"Erro ao baixar arquivo do Telegram: {e.response.text}")
            return None