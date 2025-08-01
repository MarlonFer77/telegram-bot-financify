from database.database import SessionLocal
from database import crud
from services import gemini_service, telegram_service

async def analyze_users_spending():
    """
    Tarefa que roda periodicamente para analisar e notificar os usuários.
    """
    print("--- Iniciando tarefa de análise de gastos ---")
    db = SessionLocal()
    try:
        all_users = crud.get_all_users(db)
        for user in all_users:
            print(f"Analisando usuário: {user.first_name} ({user.telegram_id})")

            summary = crud.get_spending_summary_last_90_days(db, user_id=user.id)
            if not summary:
                print("  -> Sem dados suficientes para análise.")
                continue

            insight = await gemini_service.generate_spending_insight(summary)

            if insight:
                print(f"  -> Insight encontrado: {insight}")
                await telegram_service.send_message(user.telegram_id, insight)
            else:
                print("  -> Nenhum insight notável encontrado.")
    finally:
        db.close()
    print("--- Tarefa de análise de gastos finalizada ---")