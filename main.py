from fastapi import FastAPI
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException


app = FastAPI()

# ANTIGO app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
def home():
    return FileResponse("static/index.html")

# conexão com Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

def conectar_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )
    client = gspread.authorize(creds)
    sheet = client.open("uphiplc_db")
    return sheet

# 🔥 agora sim pode usar
try:
    sheet = conectar_sheets()
    membros_sheet = sheet.worksheet("membros")
    mov_sheet = sheet.worksheet("movimentacoes")
    mensalidades_sheet = sheet.worksheet("mensalidades")
    print("✅ Conectado ao Google Sheets")
except Exception as e:
    print("❌ Erro ao conectar:", e)

# 📌 criar membro
@app.post("/membros")
def criar_membro(nome_completo: str, telefone: str = ""):
    if not nome_completo.strip():
        raise HTTPException(status_code=400, detail="Nome é obrigatório")

    novo_id = str(uuid.uuid4())

    membros_sheet.append_row([
        novo_id,
        nome_completo,
        telefone,
        "true"
    ])

    return {"message": "Membro criado", "id": novo_id}

# 📌 listar membros
@app.get("/membros")
def listar_membros():
    return membros_sheet.get_all_records()

# 📌 registrar movimentação
@app.post("/movimentacoes")
def criar_mov(tipo: str, valor: float, membro_id: str = "", descricao: str = "", mes_referencia: str = ""):
    novo_id = str(uuid.uuid4())

    mov_sheet.append_row([
        novo_id,
        tipo,
        membro_id,
        valor,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        descricao,
        mes_referencia
    ])

    return {"message": "Movimentação registrada"}

# 📌 listar movimentações
@app.get("/movimentacoes")
def listar_mov(mes: int = None, ano: int = None):
    dados = mov_sheet.get_all_records()
    filtrados = []

    for mov in dados:
        try:
            tipo = mov.get("tipo")

            # 🔹 MENSALIDADE → usa mês de referência
            if tipo == "mensalidade" and mov.get("mes_referencia"):
                mes_ref, ano_ref = mov["mes_referencia"].split("/")

                if ano and int(ano_ref) != ano:
                    continue

                if mes and int(mes_ref) != mes:
                    continue

                filtrados.append(mov)

            # 🔹 OUTROS → usa data real
            else:
                data = datetime.strptime(mov["data"], "%Y-%m-%d %H:%M:%S")

                if ano and data.year != ano:
                    continue

                if mes and data.month != mes:
                    continue

                filtrados.append(mov)

        except Exception as e:
            continue

    return filtrados

@app.get("/")
def home():
    return {"status": "ok"}

@app.get("/saldo")
def saldo():
    dados = mov_sheet.get_all_records()

    total = 0

    for mov in dados:
        if mov["tipo"] in ["mensalidade", "entrada"]:
            total += float(mov["valor"])
        elif mov["tipo"] == "retirada":
            total -= float(mov["valor"])

    return {"saldo": total}

@app.get("/saldo-mensal")
def saldo_mensal(mes: int, ano: int):
    dados = mov_sheet.get_all_records()

    total = 0

    for mov in dados:

        # 🔹 CASO 1: mensalidade (usa mes_referencia)
        if mov["tipo"] == "mensalidade" and mov.get("mes_referencia"):
            mes_ref, ano_ref = mov["mes_referencia"].split("/")

            if int(mes_ref) == mes and int(ano_ref) == ano:
                total += float(mov["valor"])

        # 🔹 CASO 2: entrada/retirada (usa data)
        else:
            data = datetime.strptime(mov["data"], "%Y-%m-%d %H:%M:%S")

            if data.month == mes and data.year == ano:
                if mov["tipo"] in ["entrada"]:
                    total += float(mov["valor"])
                elif mov["tipo"] == "retirada":
                    total -= float(mov["valor"])

    return {"saldo_mensal": total}

@app.post("/mensalidade/pagar")
def pagar_mensalidade(membro_id: str, mes: int, ano: int, valor: float):
    novo_id = str(uuid.uuid4())

    # 🔹 buscar nome do membro
    membros = membros_sheet.get_all_records()
    nome_membro = next(
        (m["nome_completo"] for m in membros if m["id"] == membro_id),
        "Membro"
    )

    # 🔹 formatar mês (opcional mas MUITO melhor)
    nomes_mes = ["Jan","Fev","Mar","Abr","Mai","Jun",
                 "Jul","Ago","Set","Out","Nov","Dez"]

    mes_formatado = nomes_mes[mes - 1]

    descricao = f"Mensalidade - {nome_membro} ({mes_formatado}/{ano})"

    # 🔹 salva mensalidade
    mensalidades_sheet.append_row([
        novo_id,
        membro_id,
        mes,
        ano,
        "true",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ])

    # 🔹 salva movimentação financeira
    mov_sheet.append_row([
        str(uuid.uuid4()),
        "mensalidade",
        membro_id,
        valor,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        descricao,
        f"{mes}/{ano}"
    ])

    return {"message": "Mensalidade registrada"}

@app.get("/mensalidades/{membro_id}")
def listar_mensalidades(membro_id: str, ano: int):
    dados = mensalidades_sheet.get_all_records()

    pagos = [
        m for m in dados
        if m["membro_id"] == membro_id and int(m["ano"]) == ano
    ]

    return pagos