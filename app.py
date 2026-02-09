import io
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ======================
# CONFIG GERAL
# ======================
st.set_page_config(page_title="Painel NIR - Censo Diário", layout="wide")

PRIMARY = "#163A9A"
PRIMARY_DARK = "#0B2B6B"
ACCENT_GREEN = "#22A34A"
SCS_PURPLE = "#4B3FA6"
SCS_CYAN = "#33C7D6"

BG = "#F6F8FB"
CARD_BG = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#0F172A"
MUTED = "#64748B"

LOGO_LEFT_PATH = Path("assets/logo_esquerda.png")
LOGO_RIGHT_PATH = Path("assets/logo_direita.png")

SHEET_ID = "1wA--gbvOmHWcUvMBTldVC8HriI3IXfQoEvQEskCKGDk"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Folha1"

REFRESH_SECONDS = 60
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="nir_autorefresh")

# ======================
# CSS (responsivo automático + ajustes estéticos)
# ======================
st.markdown(
    f"""
    <style>
      .stApp {{
        background: {BG};
        color: {TEXT};
      }}

      /* Header */
      .nir-top {{
        border-radius: 16px;
        padding: 16px 18px;
        border: 1px solid rgba(255,255,255,0.15);
        background: linear-gradient(90deg, {PRIMARY_DARK}, {PRIMARY} 45%, {SCS_PURPLE});
        color: white;
        text-align: center; /* centraliza */
      }}
      .nir-top-title {{
        font-weight: 980;
        letter-spacing: 0.2px;
        line-height: 1.05;
        margin: 0 auto;
      }}
      .nir-top-sub {{
        margin-top: 6px;
        opacity: 0.92;
        margin-left: auto;
        margin-right: auto;
      }}

      /* Wrapper para padronizar altura dos logos */
      .nir-logo-wrap {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
      }}

      /* Cards */
      .nir-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 1px 0 rgba(16,24,40,0.02);
      }}
      .nir-card-title {{
        color: {MUTED};
        font-weight: 800;
        margin-bottom: 6px;
      }}
      .nir-card-value {{
        font-weight: 950;
        margin: 0;
        line-height: 1.0;
      }}

      /* Seções */
      .nir-section-title {{
        font-weight: 950;
        margin-bottom: 6px;
        color: {TEXT};
        display: flex;
        align-items: center;
        justify-content: space-between;
      }}
      .nir-pill {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-weight: 900;
        border: 1px solid {BORDER};
        color: {TEXT};
        background: #F8FAFC;
        white-space: nowrap;
      }}

      /* Dataframes */
      div[data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid {BORDER};
      }}

      /* ===== Celular ===== */
      @media (max-width: 768px) {{
        .block-container {{
          padding-top: 0.8rem;
          padding-left: 0.9rem;
          padding-right: 0.9rem;
        }}
        .nir-top-title {{ font-size: 18px; }}
        .nir-top-sub {{ font-size: 12px; }}
        .nir-card-title {{ font-size: 12px; }}
        .nir-card-value {{ font-size: 22px; }}
        .nir-section-title {{ font-size: 14px; }}
        .nir-pill {{ font-size: 11px; }}

        /* logos mesma altura no celular */
        .nir-logo-wrap img {{
          height: 56px !important;
          width: auto !important;
          object-fit: contain !important;
        }}
      }}

      /* ===== TV/Full HD e Desktop ===== */
      @media (min-width: 1200px) {{
        .block-container {{
          padding-top: 1.4rem;
          padding-left: 1.6rem;
          padding-right: 1.6rem;
        }}
        .nir-top-title {{ font-size: 34px; }}  /* título maior */
        .nir-top-sub {{ font-size: 15px; }}
        .nir-card-title {{ font-size: 13px; }}
        .nir-card-value {{ font-size: 32px; }}
        .nir-section-title {{ font-size: 16px; }}
        .nir-pill {{ font-size: 12px; }}

        /* logos mesma altura na TV */
        .nir-logo-wrap img {{
          height: 96px !important;
          width: auto !important;
          object-fit: contain !important;
        }}
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ======================
# Helpers
# ======================
def _remover_acentos(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _norm(s: str) -> str:
    return _remover_acentos((s or "").strip().upper())


def to_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(0).astype(int)


@st.cache_data(ttl=30)
def baixar_csv_como_matriz(url: str) -> list[list[str]]:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), header=None, dtype=str, engine="python").fillna("")
    return df.values.tolist()


def achar_linha_por_substring(rows: list[list[str]], substring: str) -> int | None:
    alvo = _norm(substring)
    for i, row in enumerate(rows):
        for cell in row:
            if alvo in _norm(cell):
                return i
    return None


def slice_rows(rows: list[list[str]], start: int, end: int) -> list[list[str]]:
    bloco = rows[start:end]
    return [r for r in bloco if any(str(c).strip() for c in r)]


def safe_df_for_display(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    cols = list(df.columns)
    seen: dict[str, int] = {}
    new_cols = []
    for c in cols:
        key = str(c).strip()
        if key in seen:
            seen[key] += 1
            new_cols.append(f"{key}_{seen[key]}")
        else:
            seen[key] = 0
            new_cols.append(key)
    df.columns = new_cols

    return df


def render_metric_card(title: str, value: int, color: str):
    st.markdown(
        f"""
        <div class="nir-card">
          <div class="nir-card-title">{title}</div>
          <div class="nir-card-value" style="color:{color}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, pill: str):
    st.markdown(
        f"""
        <div class="nir-section-title">
          <div>{title}</div>
          <span class="nir-pill">{pill}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_df(df: pd.DataFrame):
    df = safe_df_for_display(df)
    if df.empty:
        st.info("Sem dados para exibir.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_logo(path: Path):
    if path.exists():
        st.image(str(path), use_container_width=True)
    else:
        st.caption(f"Arquivo não encontrado: {path.as_posix()}")


def find_col_by_contains(df: pd.DataFrame, contains_norm: str) -> str | None:
    target = _norm(contains_norm)
    for c in df.columns:
        if target in _norm(str(c)):
            return c
    return None


# ======================
# Parsing do CSV (3 blocos)
# ======================
def montar_altas(rows: list[list[str]], i_altas_header: int, i_vagas_title: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_altas_header, i_vagas_title)
    if len(bloco) < 2:
        return pd.DataFrame()

    raw_header = [str(c).strip() for c in bloco[0]]
    header = []
    for h in raw_header:
        if h != "":
            header.append(h)
        else:
            break

    if len(header) < 2:
        return pd.DataFrame()

    data = []
    for r in bloco[1:]:
        row = [str(c).strip() for c in r[: len(header)]]
        if any(v != "" for v in row):
            data.append(row)

    df = pd.DataFrame(data, columns=header)

    rename = {
        "ALTAS HOSPITAL": "HOSPITAL",
        "SETOR": "SETOR",
    }
    df = df.rename(columns={c: rename.get(str(c).strip(), str(c).strip()) for c in df.columns})

    col_realizadas = find_col_by_contains(df, "ALTAS DO DIA")
    col_previstas = find_col_by_contains(df, "ALTAS PREVISTAS")
    if col_realizadas:
        df[col_realizadas] = to_int_series(df[col_realizadas])
    if col_previstas:
        df[col_previstas] = to_int_series(df[col_previstas])

    if "HOSPITAL" in df.columns and "SETOR" in df.columns:
        df = df[(df["HOSPITAL"].astype(str).str.strip() != "") & (df["SETOR"].astype(str).str.strip() != "")]
    return df


def montar_vagas(rows: list[list[str]], i_vagas_title: int, i_transf_title: int) -> pd.DataFrame:
    """
    Correção: preserva a 2ª linha (ex.: UTI) mesmo quando HOSPITAL vem vazio.
    Regra: mantém linhas com SETOR ou VAGAS, e faz forward-fill do HOSPITAL.
    """
    bloco = slice_rows(rows, i_vagas_title + 1, i_transf_title)
    if not bloco:
        return pd.DataFrame()

    data = []
    for r in bloco:
        hosp = (r[0] if len(r) > 0 else "").strip()
        setor = (r[1] if len(r) > 1 else "").strip()
        vagas = (r[2] if len(r) > 2 else "").strip()

        if setor == "" and vagas == "":
            continue

        data.append([hosp, setor, vagas])

    df = pd.DataFrame(data, columns=["HOSPITAL", "SETOR", "VAGAS_RESERVADAS"])

    df["HOSPITAL"] = df["HOSPITAL"].replace("", pd.NA).ffill().fillna("")
    df["VAGAS_RESERVADAS"] = to_int_series(df["VAGAS_RESERVADAS"])
    df = df[df["SETOR"].astype(str).str.strip() != ""]

    return df


def montar_transferencias(rows: list[list[str]], i_transf_title: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_transf_title + 1, len(rows))
    if not bloco:
        return pd.DataFrame()

    data = []
    for r in bloco:
        desc = (r[0] if len(r) > 0 else "").strip()
        val = (r[1] if len(r) > 1 else "").strip()
        if desc:
            data.append([desc, val])

    df = pd.DataFrame(data, columns=["DESCRIÇÃO", "TOTAL"])
    df["TOTAL"] = to_int_series(df["TOTAL"])
    return df


# ======================
# HEADER COM LOGOS (altura padronizada por CSS)
# ======================
top_l, top_c, top_r = st.columns([1.2, 5.6, 1.2])

with top_l:
    st.markdown("<div class='nir-logo-wrap'>", unsafe_allow_html=True)
    render_logo(LOGO_LEFT_PATH)
    st.markdown("</div>", unsafe_allow_html=True)

with top_c:
    st.markdown(
        f"""
        <div class="nir-top">
          <div class="nir-top-title">Painel NIR – Censo Diário</div>
          <div class="nir-top-sub">Atualização automática a cada {REFRESH_SECONDS}s • Fonte: Google Sheets</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with top_r:
    st.markdown("<div class='nir-logo-wrap'>", unsafe_allow_html=True)
    render_logo(LOGO_RIGHT_PATH)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")

# Controles
b1, b2, b3 = st.columns([1.3, 3.7, 2.0])
with b1:
    if st.button("Atualizar agora"):
        st.cache_data.clear()
with b3:
    st.caption(f"Última renderização: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

st.markdown("")

# ======================
# LOAD + PARSE
# ======================
try:
    rows = baixar_csv_como_matriz(CSV_URL)
except Exception:
    st.error("Não foi possível carregar o CSV da planilha. Verifique permissões/publicação do Google Sheets.")
    st.stop()

i_altas_header = achar_linha_por_substring(rows, "ALTAS")
i_vagas_title = achar_linha_por_substring(rows, "VAGAS RESERVADAS")
i_transf_title = achar_linha_por_substring(rows, "TRANSFERENCIAS")

missing = []
if i_altas_header is None:
    missing.append("ALTAS")
if i_vagas_title is None:
    missing.append("VAGAS RESERVADAS")
if i_transf_title is None:
    missing.append("TRANSFERENCIAS")

if missing:
    st.error("Não encontrei estes marcadores no CSV: " + ", ".join(missing))
    st.stop()

df_altas = montar_altas(rows, i_altas_header, i_vagas_title)
df_vagas = montar_vagas(rows, i_vagas_title, i_transf_title)
df_transf = montar_transferencias(rows, i_transf_title)

# ======================
# MÉTRICAS
# ======================
col_realizadas = find_col_by_contains(df_altas, "ALTAS DO DIA") if not df_altas.empty else None
col_previstas = find_col_by_contains(df_altas, "ALTAS PREVISTAS") if not df_altas.empty else None

total_realizadas = int(df_altas[col_realizadas].sum()) if col_realizadas else 0
total_previstas = int(df_altas[col_previstas].sum()) if col_previstas else 0
total_vagas = int(df_vagas["VAGAS_RESERVADAS"].sum()) if not df_vagas.empty else 0
total_transf = int(df_transf["TOTAL"].sum()) if not df_transf.empty else 0

m1, m2, m3, m4 = st.columns(4)
with m1:
    render_metric_card("Altas realizadas (até 19h)", total_realizadas, PRIMARY)
with m2:
    render_metric_card("Altas previstas (24h)", total_previstas, ACCENT_GREEN)
with m3:
    render_metric_card("Vagas reservadas (dia seguinte)", total_vagas, SCS_PURPLE)
with m4:
    render_metric_card("Transferências/Saídas (total)", total_transf, SCS_CYAN)

st.markdown("")

# ======================
# TABELAS
# ======================
c1, c2 = st.columns(2)
with c1:
    st.markdown("<div class='nir-card'>", unsafe_allow_html=True)
    render_section_header("ALTAS", f"{len(df_altas)} linhas")
    render_df(df_altas)
    st.markdown("</div>", unsafe_allow_html=True)

with c2:
    st.markdown("<div class='nir-card'>", unsafe_allow_html=True)
    render_section_header("VAGAS RESERVADAS - MAPA CIRÚRGICO (DIA SEGUINTE)", f"{len(df_vagas)} linhas")
    render_df(df_vagas)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("")

st.markdown("<div class='nir-card'>", unsafe_allow_html=True)
render_section_header("TRANSFERÊNCIAS/SAÍDAS", f"{len(df_transf)} linhas")
render_df(df_transf)
st.markdown("</div>", unsafe_allow_html=True)

st.caption("Fonte: Google Sheets (Folha1).")
