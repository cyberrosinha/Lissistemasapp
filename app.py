import streamlit as st
import pandas as pd
from PIL import Image
import io
import os
import datetime
from streamlit_drawable_canvas import st_canvas

# Bibliotecas para criar o PDF
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Folha de Obra - LIS SISTEMAS", layout="centered")

st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #212529;
        color: white;
        border-radius: 4px;
        padding: 12px;
        font-weight: bold;
        text-transform: uppercase;
        border: none;
    }
    .stButton>button:hover { background-color: #495057; color: white; }
    h3, h4 { color: #343a40; }
    </style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
if os.path.exists("logo.png"):
    st.image("logo.png", width=200)
else:
    st.title("LIS SISTEMAS, LDA")

st.markdown("### Folha de Obra Digital")
st.divider()

# --- 1. DADOS DO CLIENTE ---
st.markdown("#### 1. Dados do Cliente")
col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Cliente / Empresa")
    email = st.text_input("Email")
with col2:
    nome_contacto = st.text_input("Nome")
    tipo_servico = st.selectbox("Tipo de Serviço", ["Assistência", "Instalação"])
st.divider()

# --- 2. PRODUTOS / EQUIPAMENTOS ---
st.markdown("#### 2. Produtos e Equipamentos")
if 'df_produtos' not in st.session_state:
    st.session_state.df_produtos = pd.DataFrame([{"Qtd": 1, "Descrição do Produto": ""} for _ in range(2)])

tabela_produtos = st.data_editor(
    st.session_state.df_produtos,
    num_rows="dynamic",
    use_container_width=True,
    key="editor_produtos",
    column_config={
        "Qtd": st.column_config.NumberColumn("Qtd", min_value=1, step=1, width="small"),
        "Descrição do Produto": st.column_config.TextColumn("Descrição do Produto / Equipamento", width="large")
    }
)
st.divider()

# --- 3. DESCRIÇÃO DO PEDIDO ---
st.markdown("#### 3. Descrição do Pedido")
descricao = st.text_area("Descrição inicial do pedido / avaria")
st.divider()

# --- 4. INTERVENÇÃO E TEMPOS ---
st.markdown("#### 4. Intervenção e Tempos")
col_t, col_hi, col_hf, col_km = st.columns(4)
tecnico = col_t.text_input("Técnico")
hora_inicio = col_hi.time_input("Hora Início", datetime.time(9, 0))
hora_fim = col_hf.time_input("Hora Fim", datetime.time(10, 0))
deslocacao = col_km.number_input("Deslocação (Km)", min_value=0)
st.divider()

# --- 5. MATERIAIS E PREÇOS ---
st.markdown("#### 5. Materiais Aplicados")
if 'df_materiais' not in st.session_state:
    st.session_state.df_materiais = pd.DataFrame([{"Quantidade": 1, "Produto": "", "Preço": 0.00} for _ in range(3)])

tabela_materiais = st.data_editor(
    st.session_state.df_materiais,
    num_rows="dynamic",
    use_container_width=True,
    key="editor_materiais",
    column_config={
        "Quantidade": st.column_config.NumberColumn("Quantidade", min_value=1, step=1, width="small"),
        "Produto": st.column_config.TextColumn("Produto", width="large"),
        "Preço": st.column_config.NumberColumn("Preço Unitário (€)", min_value=0.0, step=0.01, format="%.2f")
    }
)

# Cálculo automático do total
total_materiais = 0.0
for index, row in tabela_materiais.iterrows():
    if str(row["Produto"]).strip() != "":
        total_materiais += float(row["Quantidade"]) * float(row["Preço"])

st.markdown(f"<h5 style='text-align: right; color: #d9534f;'>Total: {total_materiais:.2f} €</h5>", unsafe_allow_html=True)
st.divider()

# --- 6. TAREFAS E OBSERVAÇÕES ---
st.markdown("#### 6. Tarefas Realizadas e Observações Detalhadas")
tarefas = st.text_area("Descreva os trabalhos executados")
st.divider()

# --- 7. ASSINATURA DIGITAL ---
st.markdown("#### 7. Assinatura do Cliente")
st.caption("Assine dentro do quadro abaixo.")

canvas_result = st_canvas(
    fill_color="rgba(255, 255, 255, 1)",
    stroke_width=2,
    stroke_color="#000000",
    background_color="#f8f9fa",
    height=200,
    width=400,
    drawing_mode="freedraw",
    key="canvas",
)

st.info("Ao assinar, declaro que os trabalhos acima descritos foram executados a meu inteiro agrado e dou conformidade à quantidade de horas e materiais registados.")
st.divider()

# --- BOTÃO GERAR PDF ---
if st.button("Concluir e Gerar Folha de Obra"):
    # Assinatura
    img_assinatura_pdf = None
    if canvas_result.image_data is not None:
        img_array = canvas_result.image_data
        img_pil = Image.fromarray(img_array.astype('uint8'), 'RGBA')
        fundo_branco = Image.new("RGB", img_pil.size, (255, 255, 255))
        fundo_branco.paste(img_pil, mask=img_pil.split()[3])
        
        buffer_img = io.BytesIO()
        fundo_branco.save(buffer_img, format='PNG')
        buffer_img.seek(0)
        img_assinatura_pdf = RLImage(buffer_img, width=150, height=75)

    # Configuração do PDF
    buffer_pdf = io.BytesIO()
    doc = SimpleDocTemplate(buffer_pdf, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    
    estilos = getSampleStyleSheet()
    estilo_rodape = ParagraphStyle(name='Rodape', parent=estilos['Normal'], alignment=TA_CENTER, fontSize=8, textColor=colors.dimgrey)
    estilo_legal = ParagraphStyle(name='Legal', parent=estilos['Normal'], alignment=TA_JUSTIFY, fontSize=8, textColor=colors.black)

    # Cabeçalho
    dados_cabecalho = []
    texto_titulo = Paragraph("<b>LIS SISTEMAS, LDA</b><br/>FOLHA DE OBRA", estilos['Heading2'])
    
    if os.path.exists("logo.png"):
        img_logo_pdf = RLImage("logo.png", width=120, height=75)
        dados_cabecalho = [[img_logo_pdf, texto_titulo]]
    else:
        dados_cabecalho = [[texto_titulo]]

    t_cabecalho = Table(dados_cabecalho, colWidths=[150, 350] if os.path.exists("logo.png") else [500])
    t_cabecalho.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    elementos.append(t_cabecalho)
    
    elementos.append(Paragraph(f"<b>Data:</b> {datetime.date.today().strftime('%d/%m/%Y')}", estilos['Normal']))
    elementos.append(Spacer(1, 15))

    # Tabela Dados do Cliente
    dados_cliente = [
        [f"Cliente: {cliente}", f"Nome: {nome_contacto}"],
        [f"Email: {email}", f"Serviço: {tipo_servico}"]
    ]
    t_cliente = Table(dados_cliente, colWidths=[260, 260])
    t_cliente.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey)]))
    elementos.append(t_cliente)
    elementos.append(Spacer(1, 10))

    # Produtos e Equipamentos
    dados_produtos_pdf = [["Qtd", "Produtos e Equipamentos"]]
    for index, row in tabela_produtos.iterrows():
        if str(row["Descrição do Produto"]).strip() != "":
            dados_produtos_pdf.append([str(row["Qtd"]), str(row["Descrição do Produto"])])
    
    if len(dados_produtos_pdf) > 1:
        t_produtos_pdf = Table(dados_produtos_pdf, colWidths=[40, 480])
        t_produtos_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
        ]))
        elementos.append(t_produtos_pdf)
    elementos.append(Spacer(1, 15))

    # Descrição do Pedido
    elementos.append(Paragraph(f"<b>Descrição do Pedido:</b> {descricao}", estilos['Normal']))
    elementos.append(Spacer(1, 15))

    # Intervenção e Tempos
    dados_tempos = [
        ["Técnico", "Hora Início", "Hora Fim", "Deslocação (Km)"],
        [tecnico, str(hora_inicio.strftime('%H:%M')), str(hora_fim.strftime('%H:%M')), str(deslocacao)]
    ]
    t_tempos = Table(dados_tempos, colWidths=[200, 100, 100, 120])
    t_tempos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))
    elementos.append(t_tempos)
    elementos.append(Spacer(1, 15))

    # Materiais Aplicados
    dados_materiais_pdf = [["Qtd", "Produto", "Preço Unit.", "Subtotal"]]
    for index, row in tabela_materiais.iterrows():
        if str(row["Produto"]).strip() != "":
            qtd = float(row["Quantidade"])
            preco = float(row["Preço"])
            subtotal = qtd * preco
            dados_materiais_pdf.append([str(int(qtd)), str(row["Produto"]), f"{preco:.2f} €", f"{subtotal:.2f} €"])
    
    if len(dados_materiais_pdf) > 1:
        dados_materiais_pdf.append(["", "", "Total:", f"{total_materiais:.2f} €"])
        t_materiais_pdf = Table(dados_materiais_pdf, colWidths=[40, 320, 80, 80])
        t_materiais_pdf.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('FONTNAME', (2, -1), (-1, -1), 'Helvetica-Bold')
        ]))
        elementos.append(t_materiais_pdf)
    elementos.append(Spacer(1, 15))

    # Tarefas Realizadas
    elementos.append(Paragraph(f"<b>Tarefas Realizadas e Observações:</b><br/>{tarefas}", estilos['Normal']))
    elementos.append(Spacer(1, 30))

    # Assinatura
    if img_assinatura_pdf:
        dados_assinatura = [[Paragraph("<b>Assinatura do cliente:</b>", estilos['Normal']), img_assinatura_pdf]]
        t_assinatura = Table(dados_assinatura, colWidths=[150, 370])
        elementos.append(t_assinatura)
        elementos.append(Spacer(1, 5))
        
    # Texto Legal
    texto_declaracao = "Ao assinar, declaro que os trabalhos acima descritos foram executados a meu inteiro agrado e dou conformidade à quantidade de horas e materiais registados."
    elementos.append(Paragraph(texto_declaracao, estilo_legal))

    # Rodapé com Morada
    elementos.append(Spacer(1, 40)) 
    morada = "Rua Pinhal Cotelo, 175 C - 2410-480 Leiria - Tlf.: 244 815 262<br/>geral@lissistemas.pt - www.lissistemas.pt"
    elementos.append(Paragraph(morada, estilo_rodape))

    # Construção final
    doc.build(elementos)
    buffer_pdf.seek(0)

    st.success("Folha de Obra gerada com sucesso.")
    
    # Prevenção para nome de ficheiro caso o cliente esteja vazio
    nome_ficheiro = cliente.replace(' ', '_') if cliente.strip() else "Sem_Nome"
    
    st.download_button(
        label="Descarregar PDF",
        data=buffer_pdf,
        file_name=f"FO_{nome_ficheiro}.pdf",
        mime="application/pdf"
    )