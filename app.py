import io
import unicodedata
import pandas as pd
import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Painel NIR - Censo Diário", layout="wide")

CSV_URL = "https://docs.google.com/spreadsheets/d/1wA--gbvOmHWcUvMBTldVC8HriI3IXfQoEvQEskCKGDk/gviz/tq?tqx=out:csv&sheet=Folha1"

st_autorefresh(interval=60_000, key="nir_autorefresh")  # 60s

TITULOS = [
    "ALTAS",
    "VAGAS RESERVADAS",
    "CIRURGIAS PROGRAMADAS (PRÓXIMO DIA)",
    "TRANSFERÊNCIAS/SAÍDAS",
    "CIRURGIAS PROGRAMADAS",  # fallback sem parênteses
    "TRANSFERENCIAS SAIDAS",  # fallback sem barra/acentos
]

def remover_acentos(s: str) -> str:
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')

def normalizar(s: str) -> str:
    return remover_acentos((s or "").strip().upper())

@st.cache_data(ttl=30)
def baixar_linhas_csv(url: str) -> list[list[str]]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    raw = r.text.splitlines()
    df_raw = pd.read_csv(io.StringIO("\n".join(raw)), header=None, dtype=str, engine="python")
    df_raw = df_raw.fillna("")
    return df_raw.values.tolist()

def achar_linha_titulo(rows, titulo):
    titulo_norm = normalizar(titulo)
    for i, row in enumerate(rows):
        for cell in row:
            cell_norm = normalizar(cell)
            # Procura por substring ou palavras-chave
            if titulo_norm in cell_norm or any(word in cell_norm for word in titulo_norm.split()):
                return i
    return None

def extrair_bloco(rows, start_idx, end_idx):
    bloco = rows[start_idx:end_idx]
    bloco = [r for r in bloco if any(str(c).strip() for c in r)]
    if len(bloco) < 1:
        return pd.DataFrame()

    # Para blocos pequenos (<=3 linhas), tratar como dados sem cabeçalho separado
    if len(bloco) <= 3:
        max_cols = max(len(r) for r in bloco) if bloco else 0
        df = pd.DataFrame(bloco, columns=[f'Col{i+1}' for i in range(max_cols)])
    else:
        # Lógica para blocos maiores: procurar cabeçalho
        header_i = None
        for i in range(len(bloco)):
            filled = sum(1 for c in bloco[i] if str(c).strip())
            if filled >= 2:
                header_i = i
                break
        if header_i is None or header_i + 1 >= len(bloco):
            # Se não encontrou cabeçalho, tratar como dados sem cabeçalho
            max_cols = max(len(r) for r in bloco) if bloco else 0
            df = pd.DataFrame(bloco, columns=[f'Col{i+1}' for i in range(max_cols)])
        else:
            header = [str(c).strip() for c in bloco[header_i] if str(c).strip() != ""]
            data_rows = bloco[header_i + 1 :]
            clean_rows = []
            for r in data_rows:
                vals = [str(c).strip() for c in r]
                vals = vals[: len(header)]
                if any(v for v in vals):
                    clean_rows.append(vals)
            df = pd.DataFrame(clean_rows, columns=header)
    
    # Resolver nomes de colunas duplicados
    if df.empty:
        return df
    cols = df.columns.tolist()
    seen = set()
    new_cols = []
    for col in cols:
        if col in seen:
            counter = 1
            new_col = f"{col}_{counter}"
            while new_col in seen:
                counter += 1
                new_col = f"{col}_{counter}"
            new_cols.append(new_col)
            seen.add(new_col)
        else:
            new_cols.append(col)
            seen.add(col)
    df.columns = new_cols
    
    return df

def render_tabela(titulo, df):
    st.subheader(titulo)
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)

st.title("Painel NIR – Censo Diário")

col_btn, _ = st.columns([1, 6])
with col_btn:
    if st.button("Atualizar agora"):
        st.cache_data.clear()

try:
    rows = baixar_linhas_csv(CSV_URL)
except Exception:
    st.error("Não foi possível carregar a planilha (CSV). Verifique se o link continua acessível sem login.")
    st.stop()

idxs = {}
for t in TITULOS:
    i = achar_linha_titulo(rows, t)
    if i is not None:
        idxs[normalizar(t)] = i

ordem = ["ALTAS", "VAGAS RESERVADAS", "CIRURGIAS PROGRAMADAS (PRÓXIMO DIA)", "TRANSFERÊNCIAS/SAÍDAS"]
if "TRANSFERÊNCIAS/SAÍDAS" not in idxs and "TRANSFERENCIAS SAIDAS" in idxs:
    ordem[-1] = "TRANSFERENCIAS SAIDAS"
if "CIRURGIAS PROGRAMADAS (PRÓXIMO DIA)" not in idxs and "CIRURGIAS PROGRAMADAS" in idxs:
    ordem[2] = "CIRURGIAS PROGRAMADAS"

faltando = [t for t in ordem if normalizar(t) not in idxs]
if faltando:
    st.warning("Não encontrei os títulos de todas as tabelas no CSV. Confirme se na Folha1 existem exatamente estes títulos em uma célula: " + ", ".join(faltando))
    st.info("Dica: os títulos são procurados ignorando maiúsculas/acentos. Se ainda não encontrar, me envie os títulos exatos que aparecem na planilha (ex.: 'ALTAS', 'VAGAS RESERVADAS').")

posicoes = [(t, idxs[normalizar(t)]) for t in ordem if normalizar(t) in idxs]
posicoes.sort(key=lambda x: x[1])

blocos = {}
for j, (titulo, start) in enumerate(posicoes):
    end = posicoes[j + 1][1] if j + 1 < len(posicoes) else len(rows)
    blocos[titulo] = extrair_bloco(rows, start + 1, end)

c1, c2 = st.columns(2)
with c1:
    render_tabela("ALTAS", blocos.get("ALTAS", pd.DataFrame()))
with c2:
    render_tabela("VAGAS RESERVADAS", blocos.get("VAGAS RESERVADAS", pd.DataFrame()))

c3, c4 = st.columns(2)
with c3:
    render_tabela("CIRURGIAS PROGRAMADAS (PRÓXIMO DIA)", blocos.get(ordem[2], pd.DataFrame()))
with c4:
    render_tabela("TRANSFERÊNCIAS/SAÍDAS", blocos.get(ordem[-1], pd.DataFrame()))

st.caption("Fonte: Google Sheets (Folha1). Atualização automática a cada 60s.")
