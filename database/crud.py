from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime

from . import models

# --- Funções para Usuários ---

def get_user_by_telegram_id(db: Session, telegram_id: int):
    """
    Busca um usuário específico pelo seu ID do Telegram.
    """
    return db.query(models.User).filter(models.User.telegram_id == telegram_id).first()

def create_user(db: Session, telegram_id: int, first_name: str):
    """
    Cria um novo usuário no banco de dados.
    """
    db_user = models.User(telegram_id=telegram_id, first_name=first_name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Funções para Transações ---

def create_transaction(db: Session, transaction_data: dict, user_id: int):
    """
    Cria uma nova transação associada a um usuário.
    'transaction_data' é um dicionário com chaves como:
    'description', 'amount', 'type', 'category', 'transaction_date'
    """
    db_transaction = models.Transaction(**transaction_data, user_id=user_id)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def get_user_transactions_for_period(db: Session, user_id: int, start_date: datetime.date, end_date: datetime.date):
    """
    Busca todas as transações de um usuário em um determinado período.
    """
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.transaction_date >= start_date,
        models.Transaction.transaction_date <= end_date
    ).all()

def get_user_spending_by_category_for_period(db: Session, user_id: int, start_date: datetime.date, end_date: datetime.date, category: str | None = None):
    """
    Agrupa os gastos de um usuário por categoria em um determinado período.
    Se uma categoria específica for fornecida, filtra apenas por ela.
    """
    # Inicia a query base
    query = db.query(
        models.Transaction.category, 
        func.sum(models.Transaction.amount).label("total")
    ).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.type == 'despesa',
        models.Transaction.transaction_date >= start_date,
        models.Transaction.transaction_date <= end_date
    )

    # Adiciona o filtro de categoria APENAS se ele for fornecido
    if category:
        query = query.filter(models.Transaction.category == category)

    # Agrupa por categoria e retorna todos os resultados
    return query.group_by(models.Transaction.category).all()

def get_user_balance(db: Session, user_id: int):
    """
    Calcula o saldo total de um usuário.
    Saldo = Total de Receitas - Total de Despesas.
    """
    # Calcula o somatório de todas as receitas
    total_receitas = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.type == 'receita'
    ).scalar()

    # Calcula o somatório de todas as despesas
    total_despesas = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.type == 'despesa'
    ).scalar()

    # .scalar() retorna None se não houver transações, então tratamos como 0.0
    total_receitas = total_receitas or 0.0
    total_despesas = total_despesas or 0.0

    saldo = total_receitas - total_despesas
    
    return {
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "saldo": saldo
    }

def get_recent_transactions(db: Session, user_id: int, limit: int = 5):
    """
    Busca as transações mais recentes de um usuário.
    """
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id
    ).order_by(models.Transaction.id.desc()).limit(limit).all()

def delete_transaction_by_id(db: Session, transaction_id: int, user_id: int):
    """
    Deleta uma transação específica pelo seu ID, garantindo que ela pertence ao usuário.
    Retorna o número de linhas deletadas (1 se sucesso, 0 se falha).
    """
    db_transaction = db.query(models.Transaction).filter(
        models.Transaction.id == transaction_id,
        models.Transaction.user_id == user_id
    )
    
    deleted_count = db_transaction.delete()
    db.commit()
    return deleted_count

def delete_all_user_transactions(db: Session, user_id: int):
    """
    Deleta TODAS as transações de um usuário.
    Retorna o número de linhas deletadas.
    """
    deleted_count = db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id
    ).delete()
    
    db.commit()
    return deleted_count

def get_all_users(db: Session):
    """
    Retorna todos os usuários cadastrados no banco de dados.
    """
    return db.query(models.User).all()

def get_spending_summary_last_90_days(db: Session, user_id: int):
    """
    Retorna um resumo de gastos dos últimos 90 dias, agrupado por categoria e mês.
    """
    ninety_days_ago = datetime.date.today() - datetime.timedelta(days=90)
    
    # Usamos func.strftime para extrair o ano e o mês (ex: '2025-07')
    results = db.query(
        func.strftime('%Y-%m', models.Transaction.transaction_date).label('month'),
        models.Transaction.category,
        func.sum(models.Transaction.amount).label('total')
    ).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.type == 'despesa',
        models.Transaction.transaction_date >= ninety_days_ago
    ).group_by('month', models.Transaction.category).order_by('month', models.Transaction.category).all()
    
    # Formata os resultados em um dicionário mais fácil de processar
    summary = {}
    for r in results:
        if r.month not in summary:
            summary[r.month] = []
        summary[r.month].append({"category": r.category, "total": r.total})
        
    return summary