import streamlit as st
import pandas as pd
from PIL import Image
import io
import os
import datetime
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client

# Bibliotecas para criar o PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# --- 1. LIGAÇÃO À BASE DE DADOS SUPABASE ---
st.set_page_config(page_title="LIS SISTEMAS - Gestão de Obras", layout="centered")

@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_supabase()
except Exception as e:
    st.error("⚠️ Erro a ler as passwords do Supabase. Verifica os Secrets no Streamlit!")

# --- 2. LAYOUT E INTERFACE ---
if os.path.exists("logo.png"):
    st.image("logo.png", width=200)

st.title("Folha de Obra Digital")
st.divider()

# TAB 1: CRIAR NOVA OBRA
st.markdown("### 1. Dados do Cliente")
col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Cliente / Empresa")
    email = st.text_input("Email")
with col2:
    nome_contacto = st.text_input("Nome")
    tipo_servico = st.selectbox("Tipo de Serviço", ["Assistência", "Instalação"])
st.divider()

st.markdown("### 2. Produtos e Equipamentos")
if 'df_produtos' not in st.session_state:
    st.session_state.df_produtos = pd.DataFrame([{"Qtd": 1, "Descrição do Produto / Equipamento": ""} for _ in range(2)])
tabela_produtos = st.data_editor(st.session_state.df_produtos, num_rows="dynamic", use_container_width=True)
st.divider()

st.markdown("### 3. Descrição do Pedido")
descricao = st.text_area("Descrição inicial do pedido / avaria")
st.divider()

st.markdown("### 4. Intervenção e Tempos")
col_t, col_hi, col_hf, col_km = st.columns(4)
tecnico = col_t.text_input("Técnico")
hora_inicio = col_hi.time_input("Hora Início", datetime.time(9, 0))
hora_fim = col_hf.time_input("Hora Fim", datetime.time(10, 0))
deslocacao = col_km.number_input("Deslocação (Km)", min_value=0)
st.divider()

st.markdown("### 5. Materiais Aplicados")
if 'df_materiais' not in st.session_state:
    st.session_state.df_materiais = pd.DataFrame([{"Quantidade": 1, "Produto": "", "Preço": 0.00} for _ in range(3)])
tabela_materiais = st.data_editor(st.session_state.df_materiais, num_rows="dynamic", use_container_width=True)

total_materiais = 0.0
for index, row in tabela_materiais.iterrows():
    if str(row["Produto"]).strip() != "":
        total_materiais += float(row["Quantidade"]) * float(row["Preço"])
st.markdown(f"<h4 style='text-align: right; color: #d9534f;'>Total: {total_materiais:.2f} €</h4>", unsafe_allow_html=True)
st.divider()

st.markdown("### 6. Tarefas Realizadas e Observações Detalhadas")
tarefas = st.text_area("Descreva os trabalhos executados")
st.divider()

st.markdown("### 7. Assinatura do Cliente")
st.caption("Assine dentro do quadro abaixo.")
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 1)", stroke_width=2, stroke_color="#000000",
    background_color="#f8f9fa", height=200, width=400, drawing_mode="freedraw", key="canvas"
)
st.info("Ao assinar, declaro que os trabalhos acima descritos foram executados a meu inteiro agrado e dou conformidade à quantidade de horas e materiais registados.")
st.divider()

# --- 3. BOTÃO DE CONCLUIR (GRAVA E GERA PDF) ---
if st.button("CONCLUIR E GERAR FOLHA DE OBRA", type="primary", use_container_width=True):
    # 1. Enviar para o Supabase
    try:
        dados_obra = {
            "cliente": cliente,
            "email": email,
            "nome_contacto": nome_contacto,
            "tipo_servico": tipo_servico,
            "descricao": descricao,
            "tecnico": tecnico,
            "hora_inicio": str(hora_inicio.strftime('%H:%M')),
            "hora_fim": str(hora_fim.strftime('%H:%M')),
            "deslocacao": float(deslocacao),
            "total_materiais": float(total_materiais),
            "tarefas": tarefas,
            "estado": "Pendente"
        }
        supabase.table("folhas_obra").insert(dados_obra).execute()
        st.success("✅ Obra guardada com sucesso na Base de Dados!")
    except Exception as err:
        st.error(f"Erro ao guardar na base de dados: {err}")

    # 2. Gerar PDF (Apenas o visual básico para garantir o download)
    buffer_pdf = io.BytesIO()
    doc = SimpleDocTemplate(buffer_pdf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    estilos = getSampleStyleSheet()
    
    elementos.append(Paragraph("<b>LIS SISTEMAS, LDA - FOLHA DE OBRA</b>", estilos['Heading2']))
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph(f"<b>Cliente:</b> {cliente} | <b>Data:</b> {datetime.date.today().strftime('%d/%m/%Y')}", estilos['Normal']))
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph(f"<b>Técnico:</b> {tecnico} | <b>Total Materiais:</b> {total_materiais:.2f} €", estilos['Normal']))
    
    doc.build(elementos)
    buffer_pdf.seek(0)
    
    nome_ficheiro = cliente.replace(' ', '_') if cliente.strip() else "Sem_Nome"
    st.download_button(
        label="📄 DESCARREGAR PDF",
        data=buffer_pdf,
        file_name=f"FO_{nome_ficheiro}.pdf",
        mime="application/pdf"
    )

# --- 4. LISTA DE HISTÓRICO RÁPIDA NO FUNDO DA PÁGINA ---
st.divider()
st.markdown("### 🗄️ Histórico de Obras Guardadas")
if st.button("Atualizar Lista de Obras"):
    try:
        resposta = supabase.table("folhas_obra").select("*").order("id", desc=True).limit(5).execute()
        if len(resposta.data) > 0:
            df_historico = pd.DataFrame(resposta.data)
            st.dataframe(df_historico[["created_at", "cliente", "tecnico", "estado"]], use_container_width=True)
        else:
            st.info("Ainda não tens obras guardadas.")
    except Exception as err:
        st.error("Erro ao carregar o histórico.")
