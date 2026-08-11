import streamlit as st
import pandas as pd
import os
import io
import datetime
import base64
from PIL import Image as PILImage
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client

# Bibliotecas para Email e PDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- 1. CONFIGURAÇÃO DA PÁGINA E BASE DE DADOS ---
st.set_page_config(page_title="LIS SISTEMAS - Gestão de Obras", layout="centered")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase: Client = init_supabase()
except Exception as e:
    st.error("Erro de ligação à Base de Dados. Verifica os Secrets.")

# --- 2. FUNÇÃO PARA GERAR O PDF PROFISSIONAL COM LOGÓTIPO ---
def gerar_pdf_obra(dados, assinatura_buffer, assinou):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )
    elementos = []
    
    # Estilos de Texto do ReportLab
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('Titulo', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.HexColor("#0F172A"))
    estilo_normal = ParagraphStyle('Normal', fontName='Helvetica', fontSize=10, leading=14, textColor=colors.HexColor("#334155"))
    estilo_bold = ParagraphStyle('Negrito', fontName='Helvetica-Bold', fontSize=10, leading=14, textColor=colors.HexColor("#0F172A"))
    estilo_total = ParagraphStyle('Total', fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=colors.HexColor("#DC2626"))
    estilo_disclaimer = ParagraphStyle('Disclaimer', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor("#64748B"))

    # 1. Cabeçalho com Logótipo
    logo_cell = ""
    if os.path.exists("logo.png"):
        try:
            logo_cell = RLImage("logo.png", width=130, height=50)
        except Exception:
            logo_cell = Paragraph("<b>LIS SISTEMAS</b>", estilo_titulo)
    else:
        logo_cell = Paragraph("<b>LIS SISTEMAS</b>", estilo_titulo)

    header_text = Paragraph("<b>FOLHA DE OBRA DIGITAL</b><br/><font size=9 color='#64748B'>LIS SISTEMAS, LDA</font>", estilo_titulo)
    
    tabela_header = Table([[logo_cell, header_text]], colWidths=[200, 320])
    tabela_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elementos.append(tabela_header)
    elementos.append(Spacer(1, 10))

    # Função Auxiliar para Criar Barras de Secção
    def criar_cabecalho_seccao(texto):
        p = Paragraph(f"<b>{texto.upper()}</b>", ParagraphStyle('SecBar', fontName='Helvetica-Bold', fontSize=9, textColor=colors.white))
        t = Table([[p]], colWidths=[520])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#1E293B")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    # 2. Dados do Cliente
    elementos.append(criar_cabecalho_seccao("1. Dados do Cliente & Serviço"))
    elementos.append(Spacer(1, 6))
    
    dados_cliente = [
        [Paragraph(f"<b>Cliente / Empresa:</b> {dados.get('cliente', '')}", estilo_normal), Paragraph(f"<b>Responsável:</b> {dados.get('nome_contacto', '')}", estilo_normal)],
        [Paragraph(f"<b>Email:</b> {dados.get('email', '')}", estilo_normal), Paragraph(f"<b>Tipo de Serviço:</b> {dados.get('tipo_servico', '')}", estilo_normal)],
    ]
    t_cliente = Table(dados_cliente, colWidths=[260, 260])
    t_cliente.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_cliente)
    elementos.append(Spacer(1, 10))

    # 3. Intervenção e Tempos
    elementos.append(criar_cabecalho_seccao("2. Intervenção e Tempos"))
    elementos.append(Spacer(1, 6))
    
    dados_intervencao = [
        [Paragraph(f"<b>Técnico Responsável:</b> {dados.get('tecnico', '')}", estilo_normal), Paragraph(f"<b>Horário:</b> {dados.get('hora_inicio', '')} às {dados.get('hora_fim', '')}", estilo_normal)],
        [Paragraph(f"<b>Deslocação:</b> {dados.get('deslocacao', 0)} Km", estilo_normal), Paragraph("", estilo_normal)]
    ]
    t_intervencao = Table(dados_intervencao, colWidths=[260, 260])
    t_intervencao.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
    ]))
    elementos.append(t_intervencao)
    elementos.append(Spacer(1, 10))

    # 4. Descrição e Trabalhos
    elementos.append(criar_cabecalho_seccao("3. Descrição do Pedido e Trabalhos Executados"))
    elementos.append(Spacer(1, 6))
    
    elementos.append(Paragraph("<b>Descrição da Avaria / Pedido Inicial:</b>", estilo_bold))
    elementos.append(Paragraph(f"{dados.get('descricao', '') or 'N/A'}", estilo_normal))
    elementos.append(Spacer(1, 8))
    elementos.append(Paragraph("<b>Tarefas Realizadas e Observações:</b>", estilo_bold))
    elementos.append(Paragraph(f"{dados.get('tarefas', '') or 'N/A'}", estilo_normal))
    elementos.append(Spacer(1, 12))

    # 5. Resumo Financeiro
    elementos.append(criar_cabecalho_seccao("4. Resumo de Materiais"))
    elementos.append(Spacer(1, 6))
    
    total_val = float(dados.get('total_materiais', 0.0))
    p_total = Paragraph(f"<b>Total de Materiais Aplicados:</b> {total_val:.2f} EUR", estilo_total)
    p_disc = Paragraph("* Não inclui IVA. A todos os valores acrescentar a taxa legal em vigor.", estilo_disclaimer)
    
    t_totais = Table([[p_total], [p_disc]], colWidths=[520])
    t_totais.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elementos.append(t_totais)
    elementos.append(Spacer(1, 15))

    # 6. Assinatura e Validação
    elementos.append(criar_cabecalho_seccao("5. Conformidade e Assinatura"))
    elementos.append(Spacer(1, 8))
    
    p_decl = Paragraph("Com a assinatura do presente documento, valido o descrito nesta folha de obra e declaro a conformidade das horas e dos materiais registados.", estilo_disclaimer)
    elementos.append(p_decl)
    elementos.append(Spacer(1, 10))

    data_str = datetime.date.today().strftime('%d / %m / %Y')
    p_data = Paragraph(f"<b>Data da Folha de Obra:</b><br/>{data_str}", estilo_normal)
    
    if assinou and assinatura_buffer:
        img_ass = RLImage(assinatura_buffer, width=170, height=65)
        t_ass = Table([[p_data, img_ass]], colWidths=[260, 260])
        t_ass.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elementos.append(t_ass)
    else:
        p_linha = Paragraph("<b>Assinatura do Cliente:</b><br/><br/>________________________________________", estilo_normal)
        t_ass = Table([[p_data, p_linha]], colWidths=[260, 260])
        t_ass.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        elementos.append(t_ass)

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
    nome_contacto = st.text_input("Responsável")
    tipo_servico = st.selectbox("Tipo de Serviço", ["Assistência", "Instalação"])
st.divider()

st.markdown("### 2. Produtos e Equipamentos")
if 'df_produtos' not in st.session_state:
    st.session_state.df_produtos = pd.DataFrame([{"Qtd": 1.0, "Descrição do Produto / Equipamento": ""} for _ in range(2)])
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
deslocacao = col_km.number_input("Deslocação (Km)", min_value=0.0, step=0.5)
st.divider()

st.markdown("### 5. Materiais Aplicados")
if 'df_materiais' not in st.session_state:
    st.session_state.df_materiais = pd.DataFrame([{"Quantidade": 1.0, "Produto": "", "Preço Unitário (€)": 0.00} for _ in range(3)])
tabela_materiais = st.data_editor(st.session_state.df_materiais, num_rows="dynamic", use_container_width=True)

total_materiais = 0.0
for index, row in tabela_materiais.iterrows():
    if str(row["Produto"]).strip() != "":
        total_materiais += float(row["Quantidade"]) * float(row["Preço Unitário (€)"])

st.markdown(f"<h4 style='text-align: right; color: #d9534f;'>Total: {total_materiais:.2f} €</h4>", unsafe_allow_html=True)
st.markdown("<p style='text-align: right; color: gray; font-size: 12px;'>* Não inclui IVA. A todos os valores acrescentar a taxa legal em vigor.</p>", unsafe_allow_html=True)
st.divider()

st.markdown("### 6. Tarefas Realizadas e Observações Detalhadas")
tarefas = st.text_area("Descreva os trabalhos executados")
st.divider()

st.markdown("### 7. Assinatura do Cliente")
st.caption("Assine dentro do quadro abaixo (Opcional).")
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 1)", stroke_width=2, stroke_color="#000000",
    background_color="#f8f9fa", height=200, width=400, drawing_mode="freedraw", key="canvas"
)
st.info("Com a assinatura do presente documento, valido o descrito nesta folha de obra e declaro a conformidade das horas e dos materiais registados.")
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
    
    assinou = False
    assinatura_buffer = None
    if canvas_result.json_data is not None and len(canvas_result.json_data.get("objects", [])) > 0:
        assinou = True
        try:
            img_data = canvas_result.image_data
            pil_img = PILImage.fromarray(img_data.astype('uint8'), 'RGBA')
            bg = PILImage.new("RGB", pil_img.size, (255,255,255))
            bg.paste(pil_img, mask=pil_img.split()[3])
            assinatura_buffer = io.BytesIO()
            bg.save(assinatura_buffer, format="PNG")
            assinatura_buffer.seek(0)
        except Exception:
            assinou = False

    # 1. Guardar no Supabase
    try:
        supabase.table("folhas_obra").insert(dados_obra).execute()
        st.success("Obra guardada com sucesso na Base de Dados!")
    except Exception as err:
        st.error(f"Erro ao guardar na base de dados: {err}")

    # 2. Gerar PDF
    buffer_pdf = gerar_pdf_obra(dados_obra, assinatura_buffer, assinou)
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
    except Exception:
        st.warning("A obra foi guardada, mas ocorreu um erro ao enviar o email automático. Verifica as credenciais nos Secrets.")

    # 4. Botão de Download Manual
    st.download_button(
        label="DESCARREGAR PDF",
        data=buffer_pdf,
        file_name=nome_ficheiro,
        mime="application/pdf"
    )

# --- 4. GESTÃO, EDIÇÃO E HISTÓRICO DE OBRAS (NO FUNDO DA PÁGINA) ---
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
        
        meu_pdf_gerado = gerar_pdf_obra(obra_sel, None, False)
        
        with st.expander(f"Ver Detalhes e Gerir Obra #{id_obra}", expanded=True):
            col_info, col_acoes = st.columns([2, 1])
            
            with col_info:
                st.write(f"**Data:** {obra_sel['created_at'][:10]}")
                st.write(f"**Cliente / Empresa:** {obra_sel.get('cliente', '')}")
                st.write(f"**Responsável:** {obra_sel.get('nome_contacto', '')}")
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
                if st.button("Guardar Novo Estado", type="primary", key=f"btn_st_{id_obra}"):
                    supabase.table("folhas_obra").update({"estado": novo_estado}).eq("id", id_obra).execute()
                    st.success("Estado atualizado!")
                    st.rerun() 

                st.markdown("---")
                st.markdown("**Apagar Registo**")
                if st.button("Apagar Obra", key=f"del_{id_obra}"):
                    supabase.table("folhas_obra").delete().eq("id", id_obra).execute()
                    st.warning("Obra apagada com sucesso!")
                    st.rerun()

            # FORMULÁRIO DE EDIÇÃO EM LARGURA TOTAL
            st.divider()
            with st.expander("Editar Todos os Dados desta Obra", expanded=False):
                ecol1, ecol2 = st.columns(2)
                with ecol1:
                    edit_cliente = st.text_input("Cliente / Empresa", value=obra_sel.get('cliente', ''), key=f"edit_cli_{id_obra}")
                    edit_email = st.text_input("Email", value=obra_sel.get('email', ''), key=f"edit_email_{id_obra}")
                    edit_tec = st.text_input("Técnico", value=obra_sel.get('tecnico', ''), key=f"edit_tec_{id_obra}")
                    edit_hi = st.text_input("Hora Início", value=str(obra_sel.get('hora_inicio', '09:00')), key=f"edit_hi_{id_obra}")
                with ecol2:
                    edit_resp = st.text_input("Responsável", value=obra_sel.get('nome_contacto', ''), key=f"edit_resp_{id_obra}")
                    edit_servico = st.selectbox("Tipo de Serviço", ["Assistência", "Instalação"], index=["Assistência", "Instalação"].index(obra_sel.get('tipo_servico', 'Assistência')) if obra_sel.get('tipo_servico') in ["Assistência", "Instalação"] else 0, key=f"edit_serv_{id_obra}")
                    edit_km = st.number_input("Deslocação (Km)", value=float(obra_sel.get('deslocacao', 0.0)), step=0.5, key=f"edit_km_{id_obra}")
                    edit_hf = st.text_input("Hora Fim", value=str(obra_sel.get('hora_fim', '10:00')), key=f"edit_hf_{id_obra}")

                edit_desc = st.text_area("Descrição da avaria", value=obra_sel.get('descricao', ''), key=f"edit_desc_{id_obra}")
                edit_tar = st.text_area("Trabalhos executados", value=obra_sel.get('tarefas', ''), key=f"edit_tar_{id_obra}")
                edit_mat = st.number_input("Total de Materiais (€)", value=float(obra_sel.get('total_materiais', 0.0)), step=0.5, key=f"edit_mat_{id_obra}")
                
                if st.button("Guardar Alterações da Obra", key=f"btn_save_{id_obra}", type="primary", use_container_width=True):
                    dados_editados = {
                        "cliente": edit_cliente,
                        "nome_contacto": edit_resp,
                        "email": edit_email,
                        "tipo_servico": edit_servico,
                        "tecnico": edit_tec,
                        "hora_inicio": edit_hi,
                        "hora_fim": edit_hf,
                        "deslocacao": float(edit_km),
                        "descricao": edit_desc,
                        "tarefas": edit_tar,
                        "total_materiais": float(edit_mat)
                    }
                    supabase.table("folhas_obra").update(dados_editados).eq("id", id_obra).execute()
                    st.success("Obra atualizada com sucesso!")
                    st.rerun()
else:
    st.info("Ainda não existem obras na base de dados.")
