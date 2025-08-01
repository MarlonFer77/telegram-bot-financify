# main.py

from fastapi import FastAPI
from database import models
from database.database import engine
from api.v1.endpoints import telegram_webhook
from apscheduler.schedulers.asyncio import AsyncIOScheduler # <-- Importe
from background_tasks import analyze_users_spending # <-- Importe

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Financify Bot API",
    description="Backend para o bot de gestão financeira pessoal.",
    version="1.0.0" 
)

scheduler = AsyncIOScheduler() 

@app.on_event("startup")
async def startup_event():
    """
    Inicia o agendador de tarefas quando a aplicação é iniciada.
    """
    # scheduler.add_job(analyze_users_spending, 'cron', day_of_week='sun', hour=21)
    scheduler.add_job(analyze_users_spending, 'interval', seconds=60)
    scheduler.start()
    print("Agendador iniciado. A análise de gastos rodará todo domingo às 21h.")

app.include_router(telegram_webhook.router, prefix="/api/v1", tags=["Telegram"])

@app.get("/")
def read_root():
    return {"status": "Financify Bot API is running!"}