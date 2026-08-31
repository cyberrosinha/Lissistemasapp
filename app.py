import streamlit as st
import pandas as pd
import os
import io
import json
import ast
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

def carregar_json_safe(texto, default_val):
    if not texto:
        return default_val
    if isinstance(texto, list):
        return texto
    try:
        return json.loads(texto)
    except Exception:
        try:
            return ast.literal_eval(texto)
        except Exception:
            return default_val

# --- FUNÇÃO PARA ENVIAR O PDF POR EMAIL ---
def enviar_email_pdf(cliente, tecnico, buffer_pdf, nome_ficheiro):
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
            msg['Subject'] = f"Folha de Obra: {cliente}"
            
            corpo_email = f"A folha de obra do cliente {cliente} foi registada/atualizada pelo técnico {tecnico}.\n\nO ficheiro PDF segue em anexo."
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
            
            return True, "Email com o PDF enviado com sucesso para service@lissistemas.pt!"
        return False, "Faltam as credenciais de Email nos Secrets."
    except Exception as e:
        return False, f"Ocorreu um erro ao enviar o email: {str(e)}"

# --- 2. FUNÇÃO PARA GERAR O PDF PROFISSIONAL COM LOGÓTIPO E TABELAS ---
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

    header_text = Paragraph("<b>FOLHA DE OBRA</b>", estilo_titulo)
    
    tabela_header = Table([[logo_cell, header_text]], colWidths=[200, 320])
    tabela_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    elementos.append(tabela_header)
    elementos.append(Spacer(1, 10))

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

    sec_num = 4

    # 5. TABELA DE PRODUTOS E EQUIPAMENTOS
    produtos_list = carregar_json_safe(dados.get('produtos'), [])
    produtos_validos = [p for p in produtos_list if str(p.get("Descrição do Produto / Equipamento", "")).strip() != ""]

    if produtos_validos:
        elementos.append(criar_cabecalho_seccao(f"{sec_num}. Produtos e Equipamentos"))
        elementos.append(Spacer(1, 6))
        
        t_data_prod = [[Paragraph("<b>Qtd</b>", estilo_bold), Paragraph("<b>Descrição do Produto / Equipamento</b>", estilo_bold)]]
        for p in produtos_validos:
            qtd = str(p.get("Qtd", "1"))
            desc = str(p.get("Descrição do Produto / Equipamento", ""))
            t_data_prod.append([Paragraph(qtd, estilo_normal), Paragraph(desc, estilo_normal)])
            
        t_prod = Table(t_data_prod, colWidths=[50, 470])
        t_prod.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elementos.append(t_prod)
        elementos.append(Spacer(1, 12))
        sec_num += 1

    # 6. TABELA DE MATERIAIS APLICADOS
    materiais_list = carregar_json_safe(dados.get('materiais'), [])
    materiais_validos = [m for m in materiais_list if str(m.get("Produto", "")).strip() != ""]

    if materiais_validos:
        elementos.append(criar_cabecalho_seccao(f"{sec_num}. Materiais Aplicados"))
        elementos.append(Spacer(1, 6))
        
        t_data_mat = [[
            Paragraph("<b>Qtd</b>", estilo_bold), 
            Paragraph("<b>Produto</b>", estilo_bold),
            Paragraph("<b>Preço Unit.</b>", estilo_bold),
            Paragraph("<b>Total</b>", estilo_bold)
        ]]
        
        for m in materiais_validos:
            try:
                qtd = float(m.get("Quantidade", 0))
            except:
                qtd = 0.0
            prod = str(m.get("Produto", ""))
            try:
                preco = float(m.get("Preço Unitário (€)", 0))
            except:
                preco = 0.0
            subtotal = qtd * preco
            
            t_data_mat.append([
                Paragraph(f"{qtd:g}", estilo_normal),
                Paragraph(prod, estilo_normal),
                Paragraph(f"{preco:.2f} €", estilo_normal),
                Paragraph(f"{subtotal:.2f} €", estilo_normal)
            ])
            
        t_mat = Table(t_data_mat, colWidths=[50, 310, 80, 80])
        t_mat.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elementos.append(t_mat)
        elementos.append(Spacer(1, 12))
        sec_num += 1

    # 7. Resumo Financeiro
    elementos.append(criar_cabecalho_seccao(f"{sec_num}. Resumo de Materiais"))
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
    sec_num += 1

    # 8. Assinatura e Validação
    elementos.append(criar_cabecalho_seccao(f"{sec_num}. Conformidade e Assinatura"))
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

# Construção do cabeçalho em linha (Logótipo à esquerda + Texto à direita)
img_html = ""
if os.path.exists("logo.png"):
    with open("logo.png", "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    img_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-height: 55px; margin-right: 20px; object-fit: contain;" />'
else:
    img_html = '''<div style="display: flex; align-items: center; justify-content: center; width: 50px; height: 50px; background: linear-gradient(135deg, #1e293b, #0f172a); color: white; border-radius: 10px; margin-right: 20px; flex-shrink: 0;">
        <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"></path>
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1"></rect>
          <path d="M9 12h6"></path>
          <path d="M9 16h6"></path>
        </svg>
    </div>'''

custom_header = f"""
<div style="display: flex; flex-direction: row; align-items: center; justify-content: flex-start; margin-bottom: 2rem;">
    {img_html}
    <h1 style="margin: 0; padding: 0; font-size: 2.2rem; font-weight: 700; color: #0f172a; line-height: 1;">Folha de Obra</h1>
</div>
"""
st.markdown(custom_header, unsafe_allow_html=True)

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
        try:
            total_materiais += float(row["Quantidade"]) * float(row["Preço Unitário (€)"])
        except:
            pass

st.markdown(f"<h4 style='text-align: right; color: #d9534f;'>Total: {total_materiais:.2f} €</h4>", unsafe_allow_html=True)
st.markdown("<p style='text-align: right; color: gray; font-size: 12px;'>* Não inclui IVA. A todos os valores acrescentar a taxa legal em vigor.</p>", unsafe_allow_html=True)
st.divider()

st.markdown("### 6. Tarefas Realizadas e Observações Detalhadas")
tarefas = st.text_area("Descreva os trabalhos executados")
st.divider()

st.markdown("### 7. Assinatura do Cliente")
st.caption("Assine dentro do quadro abaixo (Opcional).")
canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 1)",
    stroke_width=2,
    stroke_color="#000000",
    background_color="#ffffff",
    height=180,
    width=380,
    drawing_mode="freedraw",
    key="canvas_principal",
    update_streamlit=True,
    display_toolbar=True
)
st.info("Com a assinatura do presente documento, valido o descrito nesta folha de obra e declaro a conformidade das horas e dos materiais registados.")
st.divider()

# --- BOTÃO DE CONCLUIR ---
if st.button("CONCLUIR E GERAR FOLHA DE OBRA", type="primary", use_container_width=True):
    assinou = False
    assinatura_buffer = None
    assinatura_b64 = ""
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
            assinatura_b64 = base64.b64encode(assinatura_buffer.getvalue()).decode('utf-8')
        except Exception:
            assinou = False

    prod_dict = tabela_produtos.to_dict('records')
    mat_dict = tabela_materiais.to_dict('records')

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
        "estado": "Pendente",
        "produtos": json.dumps(prod_dict),
        "materiais": json.dumps(mat_dict),
        "assinatura": assinatura_b64
    }

    # 1. Guardar no Supabase
    try:
        supabase.table("folhas_obra").insert(dados_obra).execute()
        st.success("Obra guardada com sucesso na Base de Dados!")
    except Exception as err:
        if "column" in str(err).lower() or "schema" in str(err).lower() or "pgrst" in str(err).lower():
            st.warning("⚠️ Aviso: As colunas 'produtos', 'materiais' ou 'assinatura' não foram encontradas no teu Supabase! A gravar apenas os dados básicos...")
            dados_base = {k: v for k, v in dados_obra.items() if k not in ["produtos", "materiais", "assinatura"]}
            try:
                supabase.table("folhas_obra").insert(dados_base).execute()
                st.success("Obra guardada (sem as tabelas/assinaturas) com sucesso!")
            except Exception as err2:
                st.error(f"Erro ao guardar na base de dados: {err2}")
        else:
            st.error(f"Erro ao guardar na base de dados: {err}")

    # 2. Gerar PDF
    buffer_pdf = gerar_pdf_obra(dados_obra, assinatura_buffer, assinou)
    nome_ficheiro = f"FO_{cliente.replace(' ', '_') if cliente.strip() else 'Sem_Nome'}.pdf"
    
    # 3. Enviar PDF por Email (Usando a nova função)
    sucesso, msg_email = enviar_email_pdf(cliente, tecnico, buffer_pdf, nome_ficheiro)
    if sucesso:
        st.success(msg_email)
    else:
        st.warning(msg_email)

    # 4. Botão de Download Manual
    st.download_button(
        label="DESCARREGAR PDF",
        data=buffer_pdf,
        file_name=nome_ficheiro,
        mime="application/pdf"
    )

# --- 4. GESTÃO, EDIÇÃO E HISTÓRICO DE OBRAS ---
st.divider()
st.markdown("### Histórico de Obras Guardadas")

try:
    resposta = supabase.table("folhas_obra").select("*").order("id", desc=True).execute()
    obras_todas = resposta.data
except Exception as err:
    st.error(f"Erro ao carregar o histórico: {err}")
    obras_todas = []

if len(obras_todas) > 0:
    st.markdown("**Filtros do Histórico**")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        clientes_unicos = ["Todos"] + sorted(list(set([o['cliente'] for o in obras_todas if o.get('cliente')])))
        filtro_cliente = st.selectbox("Filtrar por Cliente:", clientes_unicos)
        
    with f_col2:
        filtro_servico = st.selectbox("Filtrar por Serviço:", ["Todos", "Assistência", "Instalação"])

    with f_col3:
        filtro_estado = st.selectbox("Filtrar por Estado:", ["Todos", "Pendente", "Oferta", "Faturado", "Cancelado"])

    obras = obras_todas
    if filtro_cliente != "Todos":
        obras = [o for o in obras if o.get('cliente') == filtro_cliente]
    if filtro_servico != "Todos":
        obras = [o for o in obras if o.get('tipo_servico') == filtro_servico]
    if filtro_estado != "Todos":
        obras = [o for o in obras if o.get('estado') == filtro_estado]

    if len(obras) > 0:
        opcoes = {f"Obra #{obra['id']} - {obra['cliente']} (Estado: {obra['estado']})": obra for obra in obras}
        escolha = st.selectbox("Selecione uma obra para ver detalhes, editar ou apagar:", list(opcoes.keys()))

        if escolha:
            obra_sel = opcoes[escolha]
            id_obra = obra_sel['id']
            
            ass_b64 = obra_sel.get('assinatura')
            ass_buf = None
            tem_assinatura = False
            if ass_b64:
                try:
                    ass_buf = io.BytesIO(base64.b64decode(ass_b64))
                    tem_assinatura = True
                except Exception:
                    ass_buf = None
                    tem_assinatura = False

            meu_pdf_gerado = gerar_pdf_obra(obra_sel, ass_buf, tem_assinatura)
            
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
                    st.markdown("**Ações Rápidas**")
                    
                    # --- NOVO BOTÃO PARA REENVIAR EMAIL APÓS EDIÇÃO ---
                    if st.button("📧 Reenviar PDF por Email", key=f"btn_reenviar_{id_obra}", use_container_width=True):
                        nome_f = f"FO_{obra_sel.get('cliente', 'Sem_Nome').replace(' ', '_')}.pdf"
                        sucesso_envio, msg_envio = enviar_email_pdf(obra_sel.get('cliente', ''), obra_sel.get('tecnico', ''), meu_pdf_gerado, nome_f)
                        if sucesso_envio:
                            st.success(msg_envio)
                        else:
                            st.error(msg_envio)
                            
                    st.markdown("---")
                    
                    st.markdown("**Atualizar Estado**")
                    status_opcoes = ["Pendente", "Oferta", "Faturado", "Cancelado"]
                    estado_atual = obra_sel.get('estado', 'Pendente')
                    idx_st = status_opcoes.index(estado_atual) if estado_atual in status_opcoes else 0
                    
                    novo_estado = st.selectbox(
                        "Mudar para:",
                        status_opcoes,
                        index=idx_st,
                        key=f"estado_{id_obra}"
                    )
                    if st.button("Guardar Novo Estado", type="primary", key=f"btn_st_{id_obra}", use_container_width=True):
                        supabase.table("folhas_obra").update({"estado": novo_estado}).eq("id", id_obra).execute()
                        st.success("Estado atualizado!")
                        st.rerun() 

                    st.markdown("---")
                    st.markdown("**Apagar Registo**")
                    if st.button("Apagar Obra", key=f"del_{id_obra}", use_container_width=True):
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

                    st.markdown("**Editar Produtos e Equipamentos:**")
                    raw_prod = obra_sel.get('produtos')
                    prod_list = carregar_json_safe(raw_prod, [{"Qtd": 1.0, "Descrição do Produto / Equipamento": ""} for _ in range(2)])
                    edit_df_prod = pd.DataFrame(prod_list)
                    edit_tab_prod = st.data_editor(edit_df_prod, num_rows="dynamic", use_container_width=True, key=f"edit_prod_editor_{id_obra}")

                    st.markdown("**Editar Materiais Aplicados:**")
                    raw_mat = obra_sel.get('materiais')
                    mat_list = carregar_json_safe(raw_mat, [{"Quantidade": 1.0, "Produto": "", "Preço Unitário (€)": 0.00} for _ in range(3)])
                    edit_df_mat = pd.DataFrame(mat_list)
                    edit_tab_mat = st.data_editor(edit_df_mat, num_rows="dynamic", use_container_width=True, key=f"edit_mat_editor_{id_obra}")

                    edit_total_mat = 0.0
                    for idx, r in edit_tab_mat.iterrows():
                        if str(r.get("Produto", "")).strip() != "":
                            try:
                                edit_total_mat += float(r.get("Quantidade", 0)) * float(r.get("Preço Unitário (€)", 0))
                            except Exception:
                                pass
                    st.caption(f"Total recalculado dos materiais: {edit_total_mat:.2f} €")

                    st.markdown("**Editar Assinatura:**")
                    ativar_assinatura = st.checkbox("Substituir / Adicionar Assinatura", key=f"chk_ass_{id_obra}")
                    
                    edit_canvas_result = None
                    if ativar_assinatura:
                        st.caption("Assine no quadro abaixo:")
                        edit_canvas_result = st_canvas(
                            fill_color="rgba(255, 255, 255, 1)",
                            stroke_width=2,
                            stroke_color="#000000",
                            background_color="#ffffff",
                            height=180,
                            width=380,
                            drawing_mode="freedraw",
                            key=f"edit_canvas_{id_obra}",
                            update_streamlit=True,
                            display_toolbar=True
                        )

                    if st.button("Guardar Alterações da Obra", key=f"btn_save_{id_obra}", type="primary", use_container_width=True):
                        nova_ass_b64 = obra_sel.get('assinatura', '')
                        if ativar_assinatura and edit_canvas_result is not None and edit_canvas_result.json_data is not None and len(edit_canvas_result.json_data.get("objects", [])) > 0:
                            try:
                                img_d = edit_canvas_result.image_data
                                p_img = PILImage.fromarray(img_d.astype('uint8'), 'RGBA')
                                bg_img = PILImage.new("RGB", p_img.size, (255,255,255))
                                bg_img.paste(p_img, mask=p_img.split()[3])
                                b_buf = io.BytesIO()
                                bg_img.save(b_buf, format="PNG")
                                b_buf.seek(0)
                                nova_ass_b64 = base64.b64encode(b_buf.getvalue()).decode('utf-8')
                            except Exception:
                                pass

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
                            "total_materiais": float(edit_total_mat),
                            "produtos": json.dumps(edit_tab_prod.to_dict('records')),
                            "materiais": json.dumps(edit_tab_mat.to_dict('records')),
                            "assinatura": nova_ass_b64
                        }

                        # Edição Supabase (COM AVISOS CASO AS COLUNAS NÃO EXISTAM)
                        try:
                            supabase.table("folhas_obra").update(dados_editados).eq("id", id_obra).execute()
                            st.success("Obra atualizada com sucesso!")
                            st.rerun()
                        except Exception as err:
                            if "column" in str(err).lower() or "schema" in str(err).lower() or "pgrst" in str(err).lower():
                                st.warning("⚠️ Aviso: Faltam colunas na Base de Dados. A guardar apenas os dados básicos...")
                                dados_edit_base = {k: v for k, v in dados_editados.items() if k not in ["produtos", "materiais", "assinatura"]}
                                supabase.table("folhas_obra").update(dados_edit_base).eq("id", id_obra).execute()
                                st.success("Obra atualizada (sem as tabelas/assinatura) com sucesso!")
                                st.rerun()
                            else:
                                st.error(f"Erro ao atualizar obra: {err}")
    else:
        st.info("Nenhuma obra encontrada com os filtros selecionados.")
else:
    st.info("Ainda não existem obras na base de dados.")
