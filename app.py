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

# Paleta aproximada dos logos (ajuste fino se quiser)
PRIMARY = "#163A9A"        # azul
PRIMARY_DARK = "#0B2B6B"
ACCENT_GREEN = "#22A34A"   # verde
SCS_PURPLE = "#4B3FA6"     # roxo
SCS_CYAN = "#33C7D6"       # ciano

BG = "#F6F8FB"
CARD_BG = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#0F172A"
MUTED = "#64748B"

# Logos no repositório (ajuste extensão se necessário)
LOGO_LEFT_PATH = Path("assets/logo_esquerda.png")
LOGO_RIGHT_PATH = Path("assets/logo_direita.png")

# Google Sheets
SHEET_ID = "1wA--gbvOmHWcUvMBTldVC8HriI3IXfQoEvQEskCKGDk"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Folha1"

# Auto refresh
REFRESH_SECONDS = 60
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="nir_autorefresh")

# ======================
# CSS (responsivo automático: TV/desktop vs celular)
# ======================
st.markdown(
    f"""
    <style>
      .stApp {{
        background: {BG};
        color: {TEXT};
      }}

      .nir-top {{
        border-radius: 16px;
        padding: 14px 16px;
        border: 1px solid rgba(255,255,255,0.15);
        background: linear-gradient(90deg, {PRIMARY_DARK}, {PRIMARY} 45%, {SCS_PURPLE});
        color: white;
      }}
      .nir-top-title {{
        font-weight: 950;
        letter-spacing: 0.2px;
        line-height: 1.1;
      }}
      .nir-top-sub {{
        margin-top: 4px;
        opacity: 0.92;
      }}

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

      div[data-testid="stDataFrame"] {{
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid {BORDER};
      }}

      /* Celular */
      @media (max-width: 768px) {{
        .block-container {{
          padding-top: 0.8rem;
          padding-left: 0.9rem;
          padding-right: 0.9rem;
        }}
        .nir-top-title {{ font-size: 16px; }}
        .nir-top-sub {{ font-size: 12px; }}
        .nir-card-title {{ font-size: 12px; }}
        .nir-card-value {{ font-size: 22px; }}
        .nir-section-title {{ font-size: 14px; }}
        .nir-pill {{ font-size: 11px; }}
      }}

      /* TV / FullHD / Desktop */
      @media (min-width: 1200px) {{
        .block-container {{
          padding-top: 1.4rem;
          padding-left: 1.6rem;
          padding-right: 1.6rem;
        }}
        .nir-top-title {{ font-size: 24px; }}
        .nir-top-sub {{ font-size: 14px; }}
        .nir-card-title {{ font-size: 13px; }}
        .nir-card-value {{ font-size: 32px; }}
        .nir-section-title {{ font-size: 16px; }}
        .nir-pill {{ font-size: 12px; }}
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


def achar_linha_exata(rows: list[list[str]], texto: str) -> int | None:
    alvo = _norm(texto)
    for i, row in enumerate(rows):
        for cell in row:
            if _norm(cell) == alvo:
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


# ======================
# Parsing determinístico do CSV
# ======================
def montar_altas(rows: list[list[str]], i_altas_header: int, i_vagas_title: int) -> pd.DataFrame:
    bloco = slice_rows(rows, i_altas_header, i_vagas_title)
    if len(bloco) < 2:
        return pd.DataFrame()

    header = bloco[0][:4]
    data = [r[:4] for r in bloco[1:]]

    df = pd.DataFrame(data, columns=header).rename(
        columns={
            "ALTAS HOSPITAL": "HOSPITAL",
            "SETOR": "SETOR",
            "ALTAS DO DIA (ATÉ 19H)": "REALIZADAS_ATÉ_19H",
            "ALTAS PREVISTAS 24H": "PREVISTAS_24H",
        }
    )

    df["REALIZADAS_ATÉ_19H"] = to_int_series(df["REALIZADAS_ATÉ_19H"])
    df["PREVISTAS_24H"] = to_int_series(df["PREVISTAS_24H"])
    df = df[(df["HOSPITAL"].astype(str).str.strip() != "") & (df["SETOR"].astype(str).str.strip() != "")]
    return df


def montar_vagas(rows: list[list[str]], i_vagas_title: int, i_cir_title: int) 