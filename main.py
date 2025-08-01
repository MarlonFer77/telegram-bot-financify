# main.py

from fastapi import FastAPI
from database import models
from database.database import get_db
from database.database import engine
from api.v1.endpoints import telegram_webhook
from background_tasks import analyze_users_spending #
from core import config
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Financify Bot API",
    description="Backend para o bot de gestão financeira pessoal.",
    version="1.0.0" 
)

app.include_router(telegram_webhook.router, prefix="/api/v1", tags=["Telegram"])

@app.get("/")
def read_root():
    return {"status": "Financify Bot API is running!"}

@app.post("/trigger-analysis/{secret_key}")
async def trigger_analysis_endpoint(secret_key: str, db: Session = Depends(get_db)):
    if secret_key != config.CRON_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Chave secreta inválida.")

    print("--- Análise de gastos acionada por Cron Job externo ---")
    await analyze_users_spending()
    return {"status": "Análise concluída"}