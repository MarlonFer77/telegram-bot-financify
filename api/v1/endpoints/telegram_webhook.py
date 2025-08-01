from fastapi import APIRouter, Request, Depends, Response
from sqlalchemy.orm import Session
from database.database import get_db
from database import crud
from services import gemini_service, telegram_service
from PIL import Image
import datetime
import calendar
import io

router = APIRouter()

async def handle_log_transaction(db: Session, message_text: str, db_user, chat_id: int):
    extracted_data = await gemini_service.extract_transaction_data_from_text(message_text)
    if "error" in extracted_data:
        reply_text = "Desculpe, não consegui extrair os dados da transação. Tente ser mais específico, como 'Gastei 50 no mercado'."
    else:
        try:
            transaction_payload = {
                'description': extracted_data.get('descricao'),
                'amount': float(extracted_data.get('valor')),
                'type': extracted_data.get('tipo', 'despesa'),
                'category': extracted_data.get('categoria'),
                'transaction_date': datetime.date.fromisoformat(extracted_data.get('data'))
            }
            crud.create_transaction(db=db, transaction_data=transaction_payload, user_id=db_user.id)
            reply_text = f"✅ Transação registrada!\n*- Categoria:* {transaction_payload['category']}\n*- Valor:* R$ {transaction_payload['amount']:.2f}"
        except Exception as e:
            print(f"Erro ao salvar transação: {e}")
            reply_text = "Ocorreu um erro ao salvar sua transação."
    await telegram_service.send_message(chat_id, reply_text)

async def handle_query_spending(db: Session, message_text: str, db_user, chat_id: int):
    params = await gemini_service.extract_query_params(message_text)
    if "error" in params or not params.get("start_date"):
        reply_text = "Não consegui entender o período da sua pergunta. Tente algo como 'este mês' ou 'em julho'."
    else:
        try:
            start_date = datetime.date.fromisoformat(params["start_date"])
            end_date = datetime.date.fromisoformat(params["end_date"])
            category = params.get("category")

            # Aplica o filtro de categoria na chamada da função
            results = crud.get_user_spending_by_category_for_period(db, user_id=db_user.id, start_date=start_date, end_date=end_date, category=category)
            
            if not results:
                reply_text = "Não encontrei nenhum gasto para sua consulta."
            else:
                # Lógica para criar um título mais amigável
                meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
                
                # Verifica se o período é um mês completo
                is_full_month = start_date.day == 1 and calendar.monthrange(start_date.year, start_date.month)[1] == end_date.day
                
                if is_full_month:
                    period_name = meses[start_date.month - 1]
                else:
                    period_name = f"de {start_date.strftime('%d/%m')} a {end_date.strftime('%d/%m')}"

                # Monta a resposta baseado se foi uma consulta geral ou específica
                if category:
                    # Resposta para uma categoria específica
                    total_categoria = results[0].total
                    reply_text = f"📊 *Gastos com {category} em {period_name}*\n\n"
                    reply_text += f"*- Total:* R$ {total_categoria:.2f}"
                else:
                    # Resposta para todas as categorias no período
                    total_geral = sum(item.total for item in results)
                    reply_text = f"📊 *Resumo de Gastos de {period_name}*\n\n"
                    for item in results:
                        reply_text += f"*- {item.category}:* R$ {item.total:.2f}\n"
                    reply_text += f"\n*Total Geral:* R$ {total_geral:.2f}"

        except Exception as e:
            print(f"Erro ao processar consulta: {e}")
            reply_text = "Ocorreu um erro ao processar sua consulta."
    await telegram_service.send_message(chat_id, reply_text)

async def handle_query_balance(db: Session, db_user, chat_id: int):
    balance_data = crud.get_user_balance(db, user_id=db_user.id)

    receitas = balance_data['total_receitas']
    despesas = balance_data['total_despesas']
    saldo = balance_data['saldo']

    reply_text = f"💰 *Seu Saldo Atual*\n\n"
    reply_text += f"📈 *Total de Receitas:* R$ {receitas:.2f}\n"
    reply_text += f"📉 *Total de Despesas:* R$ {despesas:.2f}\n"
    reply_text += "--------------------\n"
    reply_text += f"🏦 *Saldo Restante:* R$ {saldo:.2f}"

    await telegram_service.send_message(chat_id, reply_text)

async def handle_receipt_image(db: Session, message: dict, db_user, chat_id: int):
    # Pega o file_id da foto de maior resolução
    file_id = message["photo"][-1]["file_id"]
    
    # 1. Baixa a imagem
    image_bytes = await telegram_service.download_telegram_file(file_id)
    if not image_bytes:
        await telegram_service.send_message(chat_id, "❌ Desculpe, não consegui baixar a imagem do comprovante. Tente novamente.")
        return

    # 2. Extrai os dados com a IA de Visão
    extracted_data = await gemini_service.extract_data_from_receipt_image(image_bytes)

    # 3. Salva a transação (lógica similar à de texto)
    if "error" in extracted_data:
        reply_text = f"Não consegui ler os dados do comprovante. Por favor, digite manualmente (ex: 'gastei {extracted_data.get('valor', 'XX')} em {extracted_data.get('descricao', 'YYY')}')"
    else:
        try:
            transaction_payload = {
                'description': extracted_data.get('descricao', 'Compra de comprovante'),
                'amount': float(extracted_data.get('valor')),
                'type': 'despesa', # Comprovantes são sempre despesas
                'category': extracted_data.get('categoria', 'Outros'),
                'transaction_date': datetime.date.fromisoformat(extracted_data.get('data'))
            }
            crud.create_transaction(db=db, transaction_data=transaction_payload, user_id=db_user.id)
            reply_text = f"✅ Gasto do comprovante registrado!\n*- Categoria:* {transaction_payload['category']}\n*- Valor:* R$ {transaction_payload['amount']:.2f}"
        except Exception as e:
            print(f"Erro ao salvar transação da imagem: {e}")
            reply_text = "Ocorreu um erro ao salvar a transação do seu comprovante."
    
    await telegram_service.send_message(chat_id, reply_text)

async def handle_delete_transaction_start(db: Session, db_user, chat_id: int):
    """Inicia o processo de exclusão, listando as últimas transações."""
    recent_transactions = crud.get_recent_transactions(db, user_id=db_user.id, limit=5)
    if not recent_transactions:
        await telegram_service.send_message(chat_id, "Você ainda não tem nenhuma transação para excluir.")
        return

    buttons = []
    text = "Qual transação você gostaria de excluir?\n\n"
    for t in recent_transactions:
        tipo_emoji = "📉" if t.type == 'despesa' else '📈'
        # Formata o texto da transação
        text += f"{tipo_emoji} *{t.description}* - R$ {t.amount:.2f} em {t.transaction_date.strftime('%d/%m')}\n"
        # Cria um botão para cada transação com um callback_data único
        buttons.append([
            {"text": f"❌ Excluir: {t.description[:20]}", "callback_data": f"delete_transaction_{t.id}"}
        ])
    
    reply_markup = {"inline_keyboard": buttons}
    await telegram_service.send_message(chat_id, text, reply_markup)

async def handle_reset_data_start(chat_id: int):
    """Pede confirmação para resetar os dados."""
    text = "⚠️ *Atenção!* Você tem certeza que deseja apagar TODAS as suas receitas e despesas?\n\n*Essa ação não pode ser desfeita.*"
    buttons = [
        [
            {"text": "Sim, apagar tudo", "callback_data": "confirm_reset_yes"},
            {"text": "Não, cancelar", "callback_data": "confirm_reset_no"}
        ]
    ]
    reply_markup = {"inline_keyboard": buttons}
    await telegram_service.send_message(chat_id, text, reply_markup)

@router.post("/webhook/telegram")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    # --- Processa Cliques em Botões (Callback Query) ---
    if "callback_query" in data:
        callback_query = data["callback_query"]
        callback_data = callback_query["data"]
        chat_id = callback_query["message"]["chat"]["id"]
        user_id = callback_query["from"]["id"]
        
        # Busca o usuário que clicou no botão
        db_user = crud.get_user_by_telegram_id(db, telegram_id=user_id)
        if not db_user: # Segurança: não faz nada se o usuário não for encontrado
            return Response(status_code=200)

        # Lógica de exclusão de transação
        if callback_data.startswith("delete_transaction_"):
            transaction_id = int(callback_data.split("_")[2])
            deleted_count = crud.delete_transaction_by_id(db, transaction_id=transaction_id, user_id=db_user.id)
            await telegram_service.send_message(chat_id, "✅ Transação excluída com sucesso!" if deleted_count > 0 else "❌ Erro ao excluir.")
        
        # Lógica de reset da conta
        elif callback_data == "confirm_reset_yes":
            crud.delete_all_user_transactions(db, user_id=db_user.id)
            await telegram_service.send_message(chat_id, "✅ Todos os seus dados foram apagados.")
        elif callback_data == "confirm_reset_no":
            await telegram_service.send_message(chat_id, "Operação cancelada.")
        
        return Response(status_code=200)

    # --- Processa Mensagens Normais (Texto, Foto, etc.) ---
    if "message" not in data:
        return Response(status_code=200)
    
    message = data["message"]
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    first_name = message["from"]["first_name"]

    # Busca ou cria o usuário ANTES de qualquer outra lógica
    db_user = crud.get_user_by_telegram_id(db, telegram_id=user_id)
    if not db_user:
        db_user = crud.create_user(db, telegram_id=user_id, first_name=first_name)

    # Lida com mensagens de foto
    if "photo" in message:
        await telegram_service.send_message(chat_id, "🔍 Entendi! Processando a imagem do seu comprovante...")
        await handle_receipt_image(db, message, db_user, chat_id)
        return Response(status_code=200)
    
    # Lida com mensagens de texto
    if "text" in message:
        message_text = message["text"]

        # Lida com comandos diretos primeiro
        if message_text.startswith('/'):
            command = message_text.split()[0].lower()
            if command in ['/start', '/ajuda']:
                reply_text = f"Olá, {db_user.first_name}! Sou seu assistente financeiro.\nUse os comandos do menu ou simplesmente me diga o que você gastou."
                await telegram_service.send_message(chat_id, reply_text)
            elif command == '/saldo':
                await handle_query_balance(db, db_user, chat_id)
            elif command == '/gastos':
                await handle_query_spending(db, "meus gastos este mês", db_user, chat_id)
            elif command == '/excluir':
                await handle_delete_transaction_start(db, db_user, chat_id)
            elif command == '/resetar':
                await handle_reset_data_start(chat_id)
            return Response(status_code=200)

        # Se não for comando, usa a IA
        intent = await gemini_service.classify_user_intent(message_text)
        if intent == "log_transaction":
            await handle_log_transaction(db, message_text, db_user, chat_id)
        elif intent == "query_spending":
            await handle_query_spending(db, message_text, db_user, chat_id)
        elif intent == "query_balance":
            await handle_query_balance(db, db_user, chat_id)
        elif intent == "delete_transaction":
            await handle_delete_transaction_start(db, db_user, chat_id)
        elif intent == "reset_data":
            await handle_reset_data_start(chat_id)
        elif intent == "greeting":
            await telegram_service.send_message(chat_id, f"Olá, {db_user.first_name}! Como posso ajudar?")
        else: # unknown
            await telegram_service.send_message(chat_id, "Desculpe, não entendi. Use os comandos do menu ou tente descrever um gasto.")
        
        return Response(status_code=200)

    # Fallback para outros tipos de mensagem (ex: áudio, sticker)
    await telegram_service.send_message(chat_id, "Não sei o que fazer com essa mensagem. 🤔")
    return Response(status_code=200)