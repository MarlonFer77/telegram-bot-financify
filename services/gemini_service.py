import google.generativeai as genai
import json
import datetime
from core import config
from PIL import Image
import io

# Configura a API do Gemini com sua chave
genai.configure(api_key=config.GEMINI_API_KEY)
MODEL_CONFIG = genai.GenerativeModel('gemini-2.5-flash')

async def classify_user_intent(text: str) -> str:
    """
    Classifica a intenção do usuário.
    """
    prompt = f"""
    Analise o texto do usuário e classifique sua intenção principal em uma das seguintes categorias:
    - "log_transaction": O usuário está tentando registrar uma despesa ou receita (ex: "gastei 50", "recebi 1000").
    - "query_spending": O usuário está fazendo uma pergunta sobre seus gastos (ex: "quanto gastei?", "quais meus gastos com comida?").
    - "query_balance": O usuário quer saber seu saldo total (ex: "qual meu saldo?", "ver saldo", "quanto dinheiro eu tenho?").
    - "delete_transaction": O usuário quer apagar uma transação específica (ex: "apagar último gasto", "excluir a compra de ontem").
    - "reset_data": O usuário quer apagar todos os seus dados (ex: "resetar conta", "começar do zero", "apagar tudo").
    - "greeting": O usuário está apenas cumprimentando (ex: "oi", "olá", "bom dia").
    - "unknown": A intenção não é clara ou não se encaixa nas categorias acima.

    Retorne a resposta EXCLUSIVAMENTE em formato JSON, como no exemplo: {{"intent": "log_transaction"}}

    Texto do usuário: "{text}"
    """
    try:
        response = await MODEL_CONFIG.generate_content_async(
            [prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        data = json.loads(response.text)
        return data.get("intent", "unknown")
    except Exception as e:
        print(f"Erro ao classificar intenção: {e}")
        return "unknown"


async def extract_transaction_data_from_text(text: str) -> dict:
    """
    Envia o texto do usuário para a IA do Gemini e retorna os dados extraídos da transação.
    (Esta função permanece, mas podemos simplificar o prompt já que a intenção já foi classificada)
    """
    prompt = f"""
    Você é um assistente que extrai dados de uma transação financeira.
    A data de hoje é {datetime.date.today().strftime('%Y-%m-%d')}.

    Extraia valor, descrição, categoria e data do texto a seguir.
    As categorias válidas são: ["Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Educação", "Trabalho", "Compras", "Outros"].
    O tipo é "despesa", a menos que o usuário diga "recebi", "ganhei", etc.

    Retorne a resposta EXCLUSIVAMENTE em formato JSON.
    Exemplo de sucesso: {{"tipo": "despesa", "valor": 50.00, "descricao": "almoço", "categoria": "Alimentação", "data": "2025-07-30"}}
    Exemplo de erro: {{"error": "Dados insuficientes."}}

    Texto do usuário: "{text}"
    """
    try:
        response = await MODEL_CONFIG.generate_content_async(
            [prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Erro ao extrair dados de transação: {e}")
        return {"error": "Houve um problema ao extrair os dados."}


async def extract_query_params(text: str) -> dict:
    """
    Extrai parâmetros de uma pergunta sobre gastos.
    """
    prompt = f"""
    Você é um assistente que extrai parâmetros de uma pergunta.
    A data de hoje é {datetime.date.today().strftime('%Y-%m-%d')}.

    Analise a pergunta do usuário e extraia a "categoria" e um período de tempo ("start_date" e "end_date" no formato YYYY-MM-DD).
    - Se o usuário mencionar um mês (ex: "julho", "mês passado"), retorne o primeiro e último dia daquele mês.
    - Se o usuário mencionar "este mês", use o mês atual.
    - Se o usuário mencionar "hoje", use a data de hoje para start e end date.
    - Se a categoria não for mencionada, retorne o campo "category" como nulo (null).

    Retorne a resposta EXCLUSIVAMENTE em formato JSON.
    Exemplo 1: "quanto gastei com transporte em julho?" -> {{"category": "Transporte", "start_date": "2025-07-01", "end_date": "2025-07-31"}}
    Exemplo 2: "meus gastos este mês" -> {{"category": null, "start_date": "2025-07-01", "end_date": "2025-07-31"}}

    Texto do usuário: "{text}"
    """
    try:
        response = await MODEL_CONFIG.generate_content_async(
            [prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Erro ao extrair parâmetros de consulta: {e}")
        return {"error": "Não entendi os parâmetros da sua pergunta."}

async def extract_data_from_receipt_image(image_bytes: bytes) -> dict:
    """
    Envia a imagem de um comprovante para a IA do Gemini e extrai os dados.
    """
    prompt = """
    Você é um especialista em ler comprovantes e notas fiscais.
    Analise a imagem deste comprovante e extraia as seguintes informações:
    - "valor": O valor total da compra. Deve ser um número.
    - "descricao": O nome do estabelecimento ou uma breve descrição da compra.
    - "data": A data da transação no formato YYYY-MM-DD. Se não encontrar, use a data de hoje.

    Sugira também uma "categoria" para esta despesa com base no estabelecimento.
    As categorias válidas são: ["Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Educação", "Trabalho", "Compras", "Outros"].
    O tipo da transação é sempre "despesa".

    Retorne a resposta EXCLUSIVAMENTE em formato JSON.
    """
    try:
        receipt_image = Image.open(io.BytesIO(image_bytes))
        
        response = await MODEL_CONFIG.generate_content_async(
            [prompt, receipt_image],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"Erro ao processar imagem com Gemini: {e}")
        return {"error": "Não foi possível ler os dados do comprovante."}
    
async def generate_spending_insight(spending_summary: dict) -> str | None:
    """
    Analisa um resumo de gastos e gera um insight financeiro proativo.
    Retorna uma string com o insight ou None se nada for notável.
    """
    # Converte o dicionário de resumo em uma string formatada para o prompt
    summary_str = json.dumps(spending_summary, indent=2, ensure_ascii=False)
    
    prompt = f"""
    Você é um assistente financeiro proativo e amigável. Sua tarefa é analisar o resumo de gastos de um usuário dos últimos 3 meses e gerar UM ÚNICO insight útil e conciso.

    Analise os dados a seguir:
    {summary_str}

    Regras para o insight:
    1.  Compare os gastos do mês mais recente com a média dos meses anteriores.
    2.  Procure por aumentos ou diminuições significativas em categorias específicas.
    3.  Se encontrar algo notável, escreva uma mensagem curta e amigável para o usuário.
    4.  Comece a mensagem com um emoji. Ex: 💡, 📈, ⚠️.
    5.  Se não houver nada de interessante ou se os dados forem insuficientes, retorne EXATAMENTE a string "NO_INSIGHT".

    Exemplo de um bom insight:
    "💡 Notei que seus gastos com 'Alimentação' este mês foram de R$ 850, um pouco acima da sua média de R$ 700 dos últimos meses. Vale a pena ficar de olho!"

    Exemplo de quando não há nada a dizer:
    "NO_INSIGHT"

    Analise os dados fornecidos e gere sua resposta.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = await model.generate_content_async([prompt])
        
        insight = response.text.strip()
        
        if "NO_INSIGHT" in insight or not insight:
            return None
        return insight
        
    except Exception as e:
        print(f"Erro ao gerar insight: {e}")
        return None