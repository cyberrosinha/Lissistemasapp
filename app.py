import streamlit as st
import pandas as pd
import io
import datetime
import base64
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client

# Bibliotecas para Email e PDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- 1. CONFIGURAÇÃO DA PÁGINA E BASE DE DADOS ---
st.set_page_config(page_title="LIS SISTEMAS - Gestão de Obras", layout="centered")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase: Client = init_supabase()
except Exception as e:
    st.error("Erro de ligação à Base de Dados. Verifica os Secrets.")

# --- 2. FUNÇÃO MESTRA PARA GERAR O PDF ---
def gerar_pdf_obra(dados):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    estilos = getSampleStyleSheet()
    
    elementos.append(Paragraph("<b>LIS SISTEMAS, LDA - FOLHA DE OBRA</b>", estilos['Heading2']))
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph(f"<b>Cliente:</b> {dados.get('cliente', '')}", estilos['Normal']))
    elementos.append(Paragraph(f"<b>Email:</b> {dados.get('email', '')}", estilos['Normal']))
    elementos.append(Paragraph(f"<b>Serviço:</b> {dados.get('tipo_servico', '')}", estilos['Normal']))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(f"<b>Técnico:</b> {dados.get('tecnico', '')} | <b>Horário:</b> {dados.get('hora_inicio', '')} - {dados.get('hora_fim', '')}", estilos['Normal']))
    elementos.append(Paragraph(f"<b>Deslocação:</b> {dados.get('deslocacao', 0)} Km", estilos['Normal']))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("<b>Descrição da Avaria:</b>", estilos['Normal']))
    elementos.append(Paragraph(f"{dados.get('descricao', '')}", estilos['Normal']))
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("<b>Tarefas Realizadas:</b>", estilos['Normal']))
    elementos.append(Paragraph(f"{dados.get('tarefas', '')}", estilos['Normal']))
    elementos.append(Spacer(1, 15))
    elementos.append(Paragraph(f"<b>Total de Materiais:</b> {dados.get('total_materiais', 0)} EUR", estilos['Heading3']))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer

st.title("Gestão de Obras - LIS SISTEMAS")

# --- 3. CRIAR OS SEPARADORES (TABS) ---
tab_nova, tab_gestao = st.tabs(["Nova Folha de Obra", "Painel de Gestão (Histórico)"])

# ==========================================
# TAB 1: NOVA FOLHA DE OBRA (Para o Técnico)
# ==========================================
with tab_nova:
    st.markdown("### 1. Dados do Cliente")
    col1, col2 = st.columns(2)
    with col1:
        cliente = st.text_input("Cliente / Empresa")
        email = st.text_input("Email")
    with col2:
        nome_contacto = st.text_input("Nome")
        tipo_servico = st.selectbox("Tipo de Serviço", ["Assistência", "Instalação"])
    
    st.markdown("### 2. Pedido e Intervenção")
    descricao = st.text_area("Descrição da avaria")
    
    col_t, col_hi, col_hf, col_km = st.columns(4)
    tecnico = col_t.text_input("Técnico")
    hora_inicio = col_hi.time_input("Hora Início", datetime.time(9, 0))
    hora_fim = col_hf.time_input("Hora Fim", datetime.time(10, 0))
    deslocacao = col_km.number_input("Km", min_value=0)
    
    st.markdown("### 3. Materiais e Trabalhos")
    tarefas = st.text_area("Trabalhos executados")
    total_materiais = st.number_input("Valor Total de Materiais Aplicados (EUR)", min_value=0.0, step=0.5)
    
    st.markdown("### 4. Assinatura do Cliente")
    st_canvas(fill_color="rgba(255, 255, 255, 1)", stroke_width=2, background_color="#f8f9fa", height=150, width=400, key="canvas")

    if st.button("CONCLUIR, GRAVAR E ENVIAR EMAIL", type="primary", use_container_width=True):
        dados_obra = {
            "cliente": cliente, "email": email, "nome_contacto": nome_contacto,
            "tipo_servico": tipo_servico, "descricao": descricao, "tecnico": tecnico,
            "hora_inicio": str(hora_inicio.strftime('%H:%M')), "hora_fim": str(hora_fim.strftime('%H:%M')),
            "deslocacao": float(deslocacao), "total_materiais": float(total_materiais),
            "tarefas": tarefas, "estado": "Pendente"
        }
        
        # 1. Guardar no Supabase
        try:
            supabase.table("folhas_obra").insert(dados_obra).execute()
            st.success("Obra guardada na Base de Dados!")
        except Exception as e:
            st.error(f"Erro na base de dados: {e}")

        # 2. Gerar PDF e tentar enviar Email
        buffer_pdf = gerar_pdf_obra(dados_obra)
        nome_ficheiro = f"FO_{cliente.replace(' ', '_')}.pdf"
        
        try:
            remetente = st.secrets.get("EMAIL_REMETENTE")
            password = st.secrets.get("EMAIL_PASSWORD")
            smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(st.secrets.get("SMTP_PORT", 587))
            
            if remetente and password:
                msg = MIMEMultipart()
                msg['From'] = remetente
                msg['To'] = remetente # Envia para o próprio escritório
                msg['Subject'] = f"Nova Folha de Obra: {cliente}"
                msg.attach(MIMEText(f"A folha de obra do cliente {cliente} foi concluída.", 'plain'))
                
                anexo = MIMEBase('application', 'octet-stream')
                anexo.set_payload(buffer_pdf.getvalue())
                encoders.encode_base64(anexo)
                anexo.add_header('Content-Disposition', f'attachment; filename="{nome_ficheiro}"')
                msg.attach(anexo)
                
                servidor = smtplib.SMTP(smtp_server, smtp_port)
                servidor.starttls() 
                servidor.login(remetente, password)
                servidor.send_message(msg)
                servidor.quit()
                st.success("Email enviado para o escritório!")
        except Exception as e:
            st.warning("A obra foi guardada, mas ocorreu um erro a enviar o email (verifica os Secrets).")
            
        st.download_button("DESCARREGAR PDF DA OBRA AGORA", data=buffer_pdf, file_name=nome_ficheiro, mime="application/pdf")

# ==========================================
# TAB 2: PAINEL DE GESTÃO (Histórico)
# ==========================================
with tab_gestao:
    st.markdown("### Histórico e Edição")
    
    try:
        resposta = supabase.table("folhas_obra").select("*").order("id", desc=True).execute()
        obras = resposta.data
    except Exception as err:
        obras = []

    if len(obras) > 0:
        # Seletor da obra a visualizar
        opcoes = {f"#{obra['id']} | Cliente: {obra['cliente']} | Estado: {obra['estado']}": obra for obra in obras}
        escolha = st.selectbox("Selecione uma obra:", list(opcoes.keys()))

        if escolha:
            obra_sel = opcoes[escolha]
            id_obra = obra_sel['id']
            
            # Recriamos o PDF no momento para o utilizador visualizar/descarregar
            meu_pdf_gerado = gerar_pdf_obra(obra_sel)
            
            col_info, col_acoes = st.columns([2, 1])
            
            # DADOS E VISUALIZAÇÃO DO PDF
            with col_info:
                st.markdown(f"#### Detalhes: {obra_sel['cliente']}")
                st.write(f"**Técnico:** {obra_sel['tecnico']} | **Serviço:** {obra_sel['tipo_servico']}")
                st.write(f"**Data de Criação:** {obra_sel['created_at'][:10]}")
                
                with st.expander("VISUALIZAR PDF DESTA OBRA"):
                    # Mostrar o PDF diretamente dentro da página
                    base64_pdf = base64.b64encode(meu_pdf_gerado.getvalue()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    st.download_button(
                        label="Descarregar Ficheiro",
                        data=meu_pdf_gerado,
                        file_name=f"Folha_Obra_{obra_sel['id']}.pdf",
                        mime="application/pdf"
                    )

            # AÇÕES (MUDAR ESTADO E APAGAR)
            with col_acoes:
                st.markdown("#### Ações")
                
                # Mudar Estado
                novo_estado = st.selectbox(
                    "Mudar Estado:",
                    ["Pendente", "Concluído", "Faturado", "Cancelado"],
                    index=["Pendente", "Concluído", "Faturado", "Cancelado"].index(obra_sel['estado']) if obra_sel['estado'] in ["Pendente", "Concluído", "Faturado", "Cancelado"] else 0
                )
                if st.button("Guardar Estado", use_container_width=True):
                    supabase.table("folhas_obra").update({"estado": novo_estado}).eq("id", id_obra).execute()
                    st.success("Estado alterado!")
                    st.rerun()
                
                st.divider()
                
                # Apagar Registo
                if st.button("Apagar Obra", use_container_width=True):
                    supabase.table("folhas_obra").delete().eq("id", id_obra).execute()
                    st.warning("Obra eliminada para sempre!")
                    st.rerun()
    else:
        st.info("Ainda não existem obras na base de dados.")
