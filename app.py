import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Painel NIR - Censo Diário", layout="wide")

# URLs dos CSVs publicados (ajuste com as URLs reais das abas)
URL_ALTAS = "https://docs.google.com/spreadsheets/d/SEU_ID/gviz/tq?tqx=out:csv&sheet=ALTAS"
URL_VAGAS = "https://docs.google.com/spreadsheets/d/SEU_ID/gviz/tq?tqx=out:csv&sheet=VAGAS_RESERVADAS"
URL_CIRURGIAS = "https://docs.google.com/spreadsheets/d/SEU_ID/gviz/tq?tqx=out:csv&sheet=CIRURGIAS_PROGRAMADAS"
URL_TRANSFERENCIAS = "https://docs.google.com/spreadsheets/d/SEU_ID/gviz/tq?tqx=out:csv&sheet=TRANSFERENCIAS_SAIDAS"

st_autorefresh(interval=60_000, key="nir_autorefresh")  # 60s

@st.cache_data(ttl=30)
def carregar(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    return df

st.title("Painel NIR – Censo Diário")

col1, col2 = st.columns([1, 6])
with col1:
    if st.button("Atualizar agora"):
        st.cache_data.clear()

# Seção 1: ALTAS
st.header("📊 ALTAS")
df_altas = carregar(URL_ALTAS)
if not df_altas.empty:
    # Card com total (sem cálculo complexo)
    total_altas_realizadas = df_altas.get("altas_do_dia_ate_19h_", pd.Series([0])).sum()
    total_altas_previstas = df_altas.get("altas_previstas_24h", pd.Series([0])).sum()
    c1, c2 = st.columns(2)
    c1.metric("Total Realizadas (até 19h)", int(total_altas_realizadas))
    c2.metric("Total Previstas (24h)", int(total_altas_previstas))
st.dataframe(df_altas, use_container_width=True, hide_index=True)

# Seção 2: VAGAS RESERVADAS
st.header("🏥 VAGAS RESERVADAS")
df_vagas = carregar(URL_VAGAS)
if not df_vagas.empty:
    # Card com total de vagas
    total_vagas = df_vagas.select_dtypes(include=[int, float]).sum().sum()  # Soma todos os números
    st.metric("Total de Vagas Reservadas", int(total_vagas))
st.dataframe(df_vagas, use_container_width=True, hide_index=True)

# Seção 3: CIRURGIAS PROGRAMADAS
st.header("🩺 CIRURGIAS PROGRAMADAS")
df_cirurgias = carregar(URL_CIRURGIAS)
if not df_cirurgias.empty:
    # Card com total
    total_cirurgias = df_cirurgias.select_dtypes(include=[int, float]).sum().sum()
    st.metric("Total Programadas (Próximo Dia)", int(total_cirurgias))
st.dataframe(df_cirurgias, use_container_width=True, hide_index=True)

# Seção 4: TRANSFERÊNCIAS SAIDAS
st.header("📤 TRANSFERÊNCIAS/SAÍDAS")
df_transferencias = carregar(URL_TRANSFERENCIAS)
if not df_transferencias.empty:
    # Card com total
    total_transferencias = df_transferencias.select_dtypes(include=[int, float]).sum().sum()
    st.metric("Total de Transferências/Saídas", int(total_transferencias))
st.dataframe(df_transferencias, use_container_width=True, hide_index=True)

st.caption("Fonte: Google Sheets (CSVs publicados). Atualiza automaticamente a cada 60 segundos.")
