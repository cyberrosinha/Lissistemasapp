import streamlit as st
import pandas as pd
import os
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

# --- 2. FUNÇÃO PARA GERAR O PDF ---
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

# --- 3. LAYOUT PRINCIPAL DO FORMULÁRIO ---
if os.path.exists("logo.png"):
    st.image("logo.png", width=200)

st.title("Folha de Obra Digital")
st.divider()

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
    st.session_state.df_materiais = pd.DataFrame([{"Quantidade": 1, "Produto": "", "Preço Unitário (EUR)": 0.00} for _ in range(3)])
tabela_materiais = st.data_editor(st.session_state.df_materiais, num_rows="dynamic", use_container_width=True)

total_materiais = 0.0
for index, row in tabela_materiais.iterrows():
    if str(row["Produto"]).strip() != "":
        total_materiais += float(row["Quantidade"]) * float(row["Preço Unitário (EUR)"])
st.markdown(f"<h4 style='text-align: right; color: #d9534f;'>Total: {total_materiais:.2f} EUR</h4>", unsafe_allow_html=True)
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

# --- BOTÃO DE CONCLUIR ---
if st.button("CONCLUIR E GERAR FOLHA DE OBRA", type="primary", use_container_width=True):
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
    
    # 1. Guardar no Supabase
    try:
        supabase.table("folhas_obra").insert(dados_obra).execute()
        st.success("Obra guardada com sucesso na Base de Dados!")
    except Exception as err:
        st.error(f"Erro ao guardar na base de dados: {err}")

    # 2. Gerar PDF
    buffer_pdf = gerar_pdf_obra(dados_obra)
    nome_ficheiro = f"FO_{cliente.replace(' ', '_') if cliente.strip() else 'Sem_Nome'}.pdf"
    
    # 3. Enviar PDF por Email Automático
    try:
        remetente = st.secrets.get("EMAIL_REMETENTE")
        password = st.secrets.get("EMAIL_PASSWORD")
        servidor_smtp = st.secrets.get("SMTP_SERVER")
        porta_smtp = int(st.secrets.get("SMTP_PORT", 587))
        
        if remetente and password and servidor_smtp:
            destinatario = "service@lissistemas.pt"
            
            msg = MIMEMultipart()
            msg['From'] = remetente
            msg['To'] = destinatario
            msg['Subject'] = f"Nova Folha de Obra Concluída: {cliente}"
            
            corpo_email = f"A folha de obra do cliente {cliente} foi concluída pelo técnico {tecnico}.\n\nO ficheiro PDF segue em anexo."
            msg.attach(MIMEText(corpo_email, 'plain'))
            
            anexo = MIMEBase('application', 'octet-stream')
            anexo.set_payload(buffer_pdf.getvalue())
            encoders.encode_base64(anexo)
            anexo.add_header('Content-Disposition', f'attachment; filename="{nome_ficheiro}"')
            msg.attach(anexo)
            
            servidor = smtplib.SMTP(servidor_smtp, porta_smtp)
            servidor.starttls()
            servidor.login(remetente, password)
            servidor.send_message(msg)
            servidor.quit()
            
            st.success("Email com o PDF enviado com sucesso para service@lissistemas.pt!")
        else:
            st.warning("A obra foi guardada, mas as configurações de email estão incompletas nos Secrets.")
    except Exception as e:
        st.warning("A obra foi guardada, mas ocorreu um erro ao enviar o email. Verifica as credenciais nos Secrets.")

    # 4. Botão de Download Manual
    st.download_button(
        label="DESCARREGAR PDF",
        data=buffer_pdf,
        file_name=nome_ficheiro,
        mime="application/pdf"
    )

# --- 4. GESTÃO E HISTÓRICO DE OBRAS (NO FUNDO DA PÁGINA) ---
st.divider()
st.markdown("### Histórico de Obras Guardadas")

try:
    resposta = supabase.table("folhas_obra").select("*").order("id", desc=True).execute()
    obras = resposta.data
except Exception as err:
    st.error(f"Erro ao carregar o histórico: {err}")
    obras = []

if len(obras) > 0:
    opcoes = {f"Obra #{obra['id']} - {obra['cliente']} (Estado: {obra['estado']})": obra for obra in obras}
    escolha = st.selectbox("Selecione uma obra para ver detalhes, editar ou apagar:", list(opcoes.keys()))

    if escolha:
        obra_sel = opcoes[escolha]
        id_obra = obra_sel['id']
        
        meu_pdf_gerado = gerar_pdf_obra(obra_sel)
        
        with st.expander(f"Ver Detalhes da Obra #{id_obra}", expanded=True):
            col_info, col_acoes = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Data:** {obra_sel['created_at'][:10]}")
                st.write(f"**Técnico:** {obra_sel['tecnico']}")
                st.write(f"**Serviço:** {obra_sel['tipo_servico']}")
                st.write(f"**Descrição/Avaria:** {obra_sel['descricao']}")
                st.write(f"**Tarefas Realizadas:** {obra_sel['tarefas']}")
                st.write(f"**Total de Materiais:** {obra_sel['total_materiais']} EUR")
                
                st.markdown("**Visualizar PDF:**")
                base64_pdf = base64.b64encode(meu_pdf_gerado.getvalue()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="400" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
                
                st.download_button(
                    label="Descarregar Ficheiro PDF",
                    data=meu_pdf_gerado,
                    file_name=f"Folha_Obra_{obra_sel['id']}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_{id_obra}"
                )

            with col_acoes:
                st.markdown("**Atualizar Estado**")
                novo_estado = st.selectbox(
                    "Mudar para:",
                    ["Pendente", "Concluído", "Faturado", "Cancelado"],
                    index=["Pendente", "Concluído", "Faturado", "Cancelado"].index(obra_sel['estado']) if obra_sel['estado'] in ["Pendente", "Concluído", "Faturado", "Cancelado"] else 0,
                    key=f"estado_{id_obra}"
                )
                if st.button("Guardar Novo Estado", type="primary"):
                    supabase.table("folhas_obra").update({"estado": novo_estado}).eq("id", id_obra).execute()
                    st.success("Estado atualizado!")
                    st.rerun() 

                st.markdown("**Apagar Registo**")
                if st.button("Apagar Obra"):
                    supabase.table("folhas_obra").delete().eq("id", id_obra).execute()
                    st.warning("Obra apagada com sucesso!")
                    st.rerun()
else:
    st.info("Ainda não existem obras na base de dados.")

