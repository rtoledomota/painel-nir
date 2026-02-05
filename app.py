import io
import unicodedata
import pandas as pd
import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Painel NIR - Censo Diário", layout="wide")

SHEET_ID = "1wA--gbvOmHWcUvMBTldVC8HriI3IXfQoEvQEskCKGDk"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Folha1"

st_autorefresh(interval=60_000, key="nir_autorefresh")

def _remover_acentos(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")

def _norm(s: str) -> str:
    return _remover_acentos((s or "").strip().upper())

@st.cache_data(ttl=30)
def baixar_csv_como_matriz(url: str) -> list[list[str]]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()

    # Lê como “matriz” para não quebrar quando linhas têm tamanhos diferentes
    df = pd.read_csv(io.StringIO(r.text), header=None, dtype=str, engine="python")
    df = df.fillna("")
    return df.values.tolist()

def achar_linha(rows: list[list[str]], texto: str) -> int | None:
    alvo = _norm(texto)
    for i, row in enumerate(rows):
        for cell in row:
            if alvo == _norm(cell):
                return i
    return None

def slice_rows(rows: list[list[str]], start: int, end: int) -> list[list[str]]:
    bloco = rows[start:end]
    # remove linhas totalmente vazias
    return [r for r in bloco if any(str(c).strip() for c in r)]

def to_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)

def montar_altas(rows: list[list[str]], i_altas: int, i_vagas: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_altas, i_vagas)
    if len(bloco) < 2:
        return pd.DataFrame()

    header = bloco[0][:4]
    data = [r[:4] for r in bloco[1:]]
    df = pd.DataFrame(data, columns=header)

    # padroniza nomes
    rename = {
        "ALTAS HOSPITAL": "HOSPITAL",
        "SETOR": "SETOR",
        "ALTAS DO DIA (ATÉ 19H)": "ALTAS_DO_DIA_ATE_19H",
        "ALTAS PREVISTAS 24H": "ALTAS_PREVISTAS_24H",
    }
    df = df.rename(columns={c: rename.get(c, c) for c in df.columns})

    # remove linhas “sem números” (no seu CSV aparecem várias com vazio)
    if "ALTAS_DO_DIA_ATE_19H" in df.columns:
        df["ALTAS_DO_DIA_ATE_19H"] = to_int_series(df["ALTAS_DO_DIA_ATE_19H"])
    if "ALTAS_PREVISTAS_24H" in df.columns:
        df["ALTAS_PREVISTAS_24H"] = to_int_series(df["ALTAS_PREVISTAS_24H"])

    # mantém apenas linhas em que há hospital + setor
    df = df[(df["HOSPITAL"].astype(str).str.strip() != "") & (df["SETOR"].astype(str).str.strip() != "")]

    return df

def montar_vagas(rows: list[list[str]], i_vagas: int, i_cir: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_vagas + 1, i_cir)  # pula o título
    if not bloco:
        return pd.DataFrame()

    # Padrão observado: [HOSPITAL, SETOR, VAGAS, ...]
    data = []
    for r in bloco:
        hosp = (r[0] if len(r) > 0 else "").strip()
        setor = (r[1] if len(r) > 1 else "").strip()
        vagas = (r[2] if len(r) > 2 else "").strip()
        if hosp or setor or vagas:
            data.append([hosp, setor, vagas])

    df = pd.DataFrame(data, columns=["HOSPITAL", "SETOR", "VAGAS_RESERVADAS"])
    df["VAGAS_RESERVADAS"] = to_int_series(df["VAGAS_RESERVADAS"])
    df = df[(df["HOSPITAL"] != "") & (df["SETOR"] != "")]
    return df

def montar_cirurgias(rows: list[list[str]], i_cir: int, i_transf: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_cir + 1, i_transf)  # pula o título
    if not bloco:
        return pd.DataFrame()

    # Padrão observado (linha 23):
    # [HOSPITAL, "CIRURGIAS PROGRAMADAS - PROXIMO DIA", "16", ...]
    data = []
    for r in bloco:
        hosp = (r[0] if len(r) > 0 else "").strip()
        desc = (r[1] if len(r) > 1 else "").strip()
        val = (r[2] if len(r) > 2 else "").strip()
        if hosp or desc or val:
            data.append([hosp, desc, val])

    df = pd.DataFrame(data, columns=["HOSPITAL", "DESCRICAO", "VALOR"])
    df["VALOR"] = to_int_series(df["VALOR"])

    # remove linhas vazias
    df = df[(df["HOSPITAL"] != "") | (df["DESCRICAO"] != "") | (df["VALOR"] != 0)]
    return df

def montar_transferencias(rows: list[list[str]], i_transf: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_transf + 1, len(rows))  # até o fim
    if not bloco:
        return pd.DataFrame()

    # Padrões possíveis:
    # - ["CROSS", ...]
    # - ["PLATAFORMA", ...]
    # - ["TOTAL", "0", ...]
    data = []
    for r in bloco:
        desc = (r[0] if len(r) > 0 else "").strip()
        val = (r[1] if len(r) > 1 else "").strip()  # no TOTAL aparece "0" na coluna 2
        if desc == "":
            continue
        data.append([desc, val])

    df = pd.DataFrame(data, columns=["DESCRICAO", "VALOR"])
    df["VALOR"] = to_int_series(df["VALOR"])
    return df

def render_df(titulo: str, df: pd.DataFrame):
    st.subheader(titulo)
    if df is None or df.empty:
        st.info("Sem dados para exibir.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)

st.title("Painel NIR – Censo Diário")

if st.button("Atualizar agora"):
    st.cache_data.clear()

rows = baixar_csv_como_matriz(CSV_URL)

# encontra marcadores
i_altas = achar_linha(rows, "ALTAS HOSPITAL")
i_vagas = achar_linha(rows, "VAGAS RESERVADAS")
i_cir = achar_linha(rows, "CIRURGIAS PROGRAMADAS - PROXIMO DIA")
i_transf = achar_linha(rows, "TRANSFERENCIAS/SAÍDAS")

# fallback: se algum não achar, tenta versões normalizadas
if i_altas is None:
    i_altas = achar_linha(rows, "ALTAS")
if i_transf is None:
    i_transf = achar_linha(rows, "TRANSFERENCIAS/SAIDAS")
if i_cir is None:
    i_cir = achar_linha(rows, "CIRURGIAS PROGRAMADAS")

# validações
missing = []
if i_altas is None: missing.append("ALTAS HOSPITAL")
if i_vagas is None: missing.append("VAGAS RESERVADAS")
if i_cir is None: missing.append("CIRURGIAS PROGRAMADAS - PROXIMO DIA")
if i_transf is None: missing.append("TRANSFERENCIAS/SAÍDAS")

if missing:
    st.error("Não encontrei estes marcadores no CSV: " + ", ".join(missing))
    st.stop()

# monta dfs
df_altas = montar_altas(rows, i_altas, i_vagas)
df_vagas = montar_vagas(rows, i_vagas, i_cir)
df_cir = montar_cirurgias(rows, i_cir, i_transf)
df_transf = montar_transferencias(rows, i_transf)

# layout dashboard
c1, c2 = st.columns(2)
with c1:
    render_df("ALTAS", df_altas)
with c2:
    render_df("VAGAS RESERVADAS", df_vagas)

c3, c4 = st.columns(2)
with c3:
    render_df("CIRURGIAS PROGRAMADAS (PRÓXIMO DIA)", df_cir)
with c4:
    render_df("TRANSFERÊNCIAS/SAÍDAS", df_transf)

st.caption("Fonte: Google Sheets (Folha1). Atualização automática a cada 60s.")
