import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
from PIL import Image
import pandas as pd
import io
from parser import parse_mmd_file
from database import init_db, insert_error, get_errors, delete_error
from loguru import logger
import config
from api_utils import get_openrouter_client, encode_image_to_base64
from text_utils import is_table, count_words, count_differing_words
from document_utils import parse_doc_name, get_documents_data
from image_utils import load_pdf_page_as_image, crop_and_highlight_bbox

# Load environment variables from .env file

# Initialize database
init_db()

# Page config
st.set_page_config(page_title=config.PAGE_TITLE, layout=config.PAGE_LAYOUT)

# ============================================================================
# Authentication
# ============================================================================

def check_password():
    """Returns `True` if the user had the correct password."""
    
    # Return True if password is correct
    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        # Show login form centered
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            # Display logos
            logo_col1, logo_col2 = st.columns(2)
            try:
                with logo_col1:
                    wallis_logo = Image.open("public/konica-logo.png")
                    # Convert to base64 and embed directly in HTML to bypass Streamlit's media storage
                    wallis_base64 = encode_image_to_base64(wallis_logo)
                    st.markdown(
                        f'<img src="data:image/jpeg;base64,{wallis_base64}" style="width:100%; height:auto;" />',
                        unsafe_allow_html=True
                    )
                with logo_col2:
                    konica_logo = Image.open("public/wallis-logo.png")
                    # Convert to base64 and embed directly in HTML to bypass Streamlit's media storage
                    konica_base64 = encode_image_to_base64(konica_logo)
                    st.markdown(
                        f'<img src="data:image/jpeg;base64,{konica_base64}" style="width:100%; height:auto;" />',
                        unsafe_allow_html=True
                    )
            except FileNotFoundError:
                st.info("Logos não encontrados")
            
            st.markdown("---")
            
            # Use separate keys for login form to avoid conflicts
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            
            login_button = st.button("Login", type="primary", use_container_width=True)
            
            if login_button:
                logger.info(f"Username: {username}, Password: {password}")
                logger.info(f"Config.AUTH_USERNAME: {config.AUTH_USERNAME}, Config.AUTH_PASSWORD: {config.AUTH_PASSWORD}")
                if username == config.AUTH_USERNAME and password == config.AUTH_PASSWORD:
                    st.session_state["password_correct"] = True
                    # Clear login form keys
                    if "login_username" in st.session_state:
                        del st.session_state["login_username"]
                    if "login_password" in st.session_state:
                        del st.session_state["login_password"]
                    st.rerun()
                else:
                    st.session_state["password_correct"] = False
                    st.error("😕 Username/password incorretos")
            
            if "password_correct" in st.session_state and not st.session_state["password_correct"]:
                st.error("😕 Username/password incorretos")
        
        return False
    else:
        # Password correct
        return True

# Check authentication before showing the app
if not check_password():
    st.stop()  # Do not continue if password is not correct


# Logout button in sidebar
if st.sidebar.button("🚪 Logout", use_container_width=True):
    # Clear authentication
    if "password_correct" in st.session_state:
        del st.session_state["password_correct"]
    if "username" in st.session_state:
        del st.session_state["username"]
    st.rerun()

if "last_bbox_id" not in st.session_state:
    st.session_state.last_bbox_id = None

if "temp_text" not in st.session_state:
    st.session_state.temp_text = None

if "button_accept" not in st.session_state:
    st.session_state.button_accept = None
if "previous_year" not in st.session_state:
    st.session_state.previous_year = None
if "previous_month" not in st.session_state:
    st.session_state.previous_month = None
if "previous_day" not in st.session_state:
    st.session_state.previous_day = None
if "previous_page" not in st.session_state:
    st.session_state.previous_page = None


# Text processing functions are now imported from text_utils

# Get all documents from year folders
parsed_docs_dir = config.PARSED_DOCS_DIR
year_dirs = sorted([d for d in parsed_docs_dir.iterdir() if d.is_dir()])

if not year_dirs:
    st.error("Nenhum diretório de documentos encontrado em parsed_docs/")
    st.stop()

# Extract all documents from year folders
documents_data = get_documents_data()

if not documents_data:
    st.error("Nenhum documento válido encontrado")
    st.stop()

# Get unique years, months, days
all_years = sorted(set(d['year'] for d in documents_data))
all_months = sorted(set(d['month'] for d in documents_data))
all_days = sorted(set(d['day'] for d in documents_data))

# Navigation buttons in sidebar
if "current_view" not in st.session_state:
    st.session_state.current_view = "anotacao"

nav_anotacao = st.sidebar.button("📝 Anotação", use_container_width=True, type="primary" if st.session_state.current_view == "anotacao" else "secondary", key="nav_anotacao")
if nav_anotacao:
    st.session_state.current_view = "anotacao"
    st.rerun()

nav_estatisticas = st.sidebar.button("📊 Estatísticas", use_container_width=True, type="primary" if st.session_state.current_view == "estatisticas" else "secondary", key="nav_estatisticas")
if nav_estatisticas:
    st.session_state.current_view = "estatisticas"
    st.rerun()

st.sidebar.markdown("---")

# Sidebar for document selection
st.sidebar.title("Diário do Governo")

# Initialize session state for date selection
if 'selected_year' not in st.session_state:
    st.session_state.selected_year = all_years[0] if all_years else None
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = all_months[0] if all_months else None
if 'selected_day' not in st.session_state:
    st.session_state.selected_day = all_days[0] if all_days else None

# Year dropdown
selected_year = st.sidebar.selectbox(
    "Ano",
    options=all_years,
    index=all_years.index(st.session_state.selected_year) if st.session_state.selected_year in all_years else 0,
    key="year_select"
)

# Filter documents by year
filtered_by_year = [d for d in documents_data if d['year'] == selected_year]
available_months = sorted(set(d['month'] for d in filtered_by_year))

# Month dropdown with month names
if available_months:
    # Update selected_month if it's not available for current year
    if st.session_state.selected_month not in available_months:
        st.session_state.selected_month = available_months[0]
    
    selected_month = st.sidebar.selectbox(
        "Mês",
        options=available_months,
        index=available_months.index(st.session_state.selected_month) if st.session_state.selected_month in available_months else 0,
        format_func=lambda x: config.MONTH_NAMES.get(x, str(x)),
        key="month_select"
    )
else:
    selected_month = None
    st.sidebar.warning("Nenhum mês disponível para o ano selecionado")

# Filter documents by year and month
if selected_month:
    filtered_by_month = [d for d in filtered_by_year if d['month'] == selected_month]
    available_days = sorted(set(d['day'] for d in filtered_by_month))
    
    # Day dropdown
    if available_days:
        # Update selected_day if it's not available for current month
        if st.session_state.selected_day not in available_days:
            st.session_state.selected_day = available_days[0]
        
        selected_day = st.sidebar.selectbox(
            "Dia",
            options=available_days,
            index=available_days.index(st.session_state.selected_day) if st.session_state.selected_day in available_days else 0,
            key="day_select"
        )
    else:
        selected_day = None
        st.sidebar.warning("Nenhum dia disponível para o mês selecionado")
else:
    selected_day = None

# Find the matching document
selected_doc = None
if selected_year and selected_month and selected_day:
    matching_docs = [d for d in documents_data if d['year'] == selected_year and d['month'] == selected_month and d['day'] == selected_day]
    if matching_docs:
        selected_doc = matching_docs[0]
        selected_dir = selected_doc['path']  # Year folder
        document_name = selected_doc['name']  # Document name (DR_DD_MM_YYYY)
        # For database operations, use the year (to match existing database format)
        document_name_db = str(selected_year)
        # Update session state
        st.session_state.selected_year = selected_year
        st.session_state.selected_month = selected_month
        st.session_state.selected_day = selected_day
    else:
        st.sidebar.error("Documento não encontrado")
        st.stop()
else:
    st.sidebar.error("Selecione ano, mês e dia")
    st.stop()

# Find PDF and MMD files using the document name
# Use the regular PDF (not the layouts PDF which has boxes drawn on it)
pdf_path = selected_dir / f"{document_name}.pdf"
mmd_path = selected_dir / f"{document_name}_det.mmd"

if not pdf_path.exists() or not mmd_path.exists():
    st.error(f"Ficheiros PDF ou MMD em falta para {document_name}")
    st.stop()

# Parse MMD file
if 'parsed_data' not in st.session_state or st.session_state.get('current_doc') != document_name:
    with st.spinner("A processar ficheiro MMD..."):
        st.session_state.parsed_data = parse_mmd_file(str(mmd_path))
        st.session_state.current_doc = document_name

parsed_data = st.session_state.parsed_data

# Page selection
pages = sorted(parsed_data.keys())
if not pages:
    st.error("Nenhuma página encontrada no ficheiro MMD")
    st.stop()

# Get current page index or default to 0
current_page_index = 0
if st.session_state.previous_page and st.session_state.previous_page in pages:
    current_page_index = pages.index(st.session_state.previous_page)

selected_page = st.sidebar.selectbox(
    "Página",
    options=pages,
    index=current_page_index,
    key="page_select"
)

# Initialize previous values if not set (before checking for changes)
if st.session_state.previous_year is None:
    st.session_state.previous_year = selected_year
if st.session_state.previous_month is None:
    st.session_state.previous_month = selected_month
if st.session_state.previous_day is None:
    st.session_state.previous_day = selected_day

# Check if sidebar selections changed and reset bbox if needed
sidebar_changed = (
    st.session_state.previous_year != selected_year or
    st.session_state.previous_month != selected_month or
    st.session_state.previous_day != selected_day or
    st.session_state.previous_page != selected_page
)


if sidebar_changed:
    logger.info("Sidebar changed")
    # Reset bbox to 1 and clear text state
    st.session_state.bbox_num = 1
    st.session_state.temp_text = None
    if "ground_truth" in st.session_state:
        st.session_state["ground_truth"] = None
    st.session_state.last_bbox_id = None
    
    # Clear all per-bbox session state to ensure text boxes update correctly
    keys_to_clear = [key for key in st.session_state.keys() if any(
        key.startswith(prefix) for prefix in [
            "llm_corrected_text_",
            "combined_correction_",
            "use_llm_suggestion_",
            "use_combined_suggestion_",
            "obtained_text_",
            "ground_truth_",
            "ferramentas_correcao_",
            "checkbox_inteligente_",
            "checkbox_regras_",
            "apply_corrections_",
            "accept_obtained_text_",
            "use_llm_text_",
            "llm_corrected_display_",
            "combined_correction_display_",
            "submit_error_"
        ]
    )]
    for key in keys_to_clear:
        del st.session_state[key]
    
    # Update previous values
    st.session_state.previous_year = selected_year
    st.session_state.previous_month = selected_month
    st.session_state.previous_day = selected_day
    st.session_state.previous_page = selected_page
    logger.info("Sidebar changed")

# Get bounding boxes for selected page
bboxes_data = parsed_data[selected_page]

# Initialize bbox_num in session state if not exists
if 'bbox_num' not in st.session_state:
    st.session_state.bbox_num = 1

# Bounding box number input in sidebar
logger.info(f"Bbox num: {st.session_state.bbox_num}")
st.sidebar.number_input(
    "Caixa",
    min_value=1,
    max_value=len(bboxes_data),
    step=1,
    key="bbox_num"
)
logger.info(f"Bbox num after input: {st.session_state.bbox_num}")

# Load PDF page as image
try:
    img, img_metadata = load_pdf_page_as_image(pdf_path, selected_page)
except Exception as e:
    st.error(f"Erro ao carregar PDF: {e}")
    st.stop()

# Check for navigation actions that need to happen before widgets are created
# This prevents the "cannot modify after widget instantiated" error
if 'next_bbox' in st.session_state and st.session_state.next_bbox:
    if st.session_state.bbox_num < len(bboxes_data):
        st.session_state.bbox_num += 1
    st.session_state.next_bbox = False

# Annotation view
if st.session_state.current_view == "anotacao":
    # Get the current bounding box coordinates AFTER the widget has processed the value
    current_bbox_num = st.session_state.bbox_num
    current_bbox, _ = bboxes_data[current_bbox_num - 1] if current_bbox_num <= len(bboxes_data) else (None, None)

    # Crop image to show only the selected bounding box
    if current_bbox:
        display_img = crop_and_highlight_bbox(img, current_bbox, img_metadata)
    else:
        display_img = img
    
    # Get the text for selected bounding box - use current session state value
    selected_bbox_text = bboxes_data[current_bbox_num - 1][1] if current_bbox_num <= len(bboxes_data) else ""
    logger.info(f"Selected bbox text: {selected_bbox_text}")
    # Check if this is a table
    is_table_bbox = is_table(selected_bbox_text)
    
    # Initialize ground_truth in session state if needed or update when bbox changes
    if st.session_state.last_bbox_id != current_bbox_num:
        st.session_state["ground_truth"] = selected_bbox_text
        st.session_state.last_bbox_id = current_bbox_num
        # Reset temp_text when changing bbox (LLM results are kept per bbox)
        st.session_state.temp_text = None

    # Main section - Image on left, text boxes on right
    col1, col2 = st.columns([1, 1])

    with col1:
        # Get bounding box coordinates
        if current_bbox:
            x_coord, y_coord = current_bbox[0], current_bbox[1]
            st.subheader(f"Pagina {selected_page} - Caixa {current_bbox_num} - X: {x_coord} Y: {y_coord}")
        else:
            st.subheader(f"Pagina {selected_page} - Caixa {current_bbox_num}")
        # Convert PIL Image to base64 and embed directly in HTML to bypass Streamlit's media storage
        img_base64 = encode_image_to_base64(display_img)
        st.markdown(
            f'<img src="data:image/jpeg;base64,{img_base64}" style="width:100%; height:auto;" />',
            unsafe_allow_html=True
        )

    with col2:
        # If it's a table, only show the image (already displayed in col1)
        if is_table_bbox:
            pass
        else:
            # Obtained text (non-editable) - only for non-tables
            st.text_area(
                "Texto obtido",
                value=selected_bbox_text,
                height=150,
                disabled=True)
                #key=f"obtained_text_{current_bbox_num}")
            
            if st.button("Aceitar texto obtido", key=f"accept_obtained_text_{current_bbox_num}", type="secondary", width='stretch'):
                # Move to next box
                if st.session_state.bbox_num < len(bboxes_data):
                    st.session_state.next_bbox = True
                    logger.info(f"Moving to next bbox")
                    st.rerun()
                else:
                    st.info("Já está na última caixa delimitadora")
            
            # Ferramentas section after "Texto obtido" (outside form)
            st.write("**Ferramentas**")
            
            # Initialize checkboxes state
            if f"ferramentas_correcao_inteligente_{current_bbox_num}" not in st.session_state:
                st.session_state[f"ferramentas_correcao_inteligente_{current_bbox_num}"] = False
            if f"ferramentas_correcao_regras_{current_bbox_num}" not in st.session_state:
                st.session_state[f"ferramentas_correcao_regras_{current_bbox_num}"] = False
            
            # Ferramentas in one row: checkboxes and apply button
            ferramentas_col1, ferramentas_col2, ferramentas_col3 = st.columns([2, 2, 2])
            
            with ferramentas_col1:
                correcao_inteligente = st.checkbox(
                    "🤖 Inteligente",
                    value=st.session_state[f"ferramentas_correcao_inteligente_{current_bbox_num}"],
                    key=f"checkbox_inteligente_{current_bbox_num}"
                )
            
            with ferramentas_col2:
                correcao_regras = st.checkbox(
                    "📝 Regras",
                    value=st.session_state[f"ferramentas_correcao_regras_{current_bbox_num}"],
                    key=f"checkbox_regras_{current_bbox_num}"
                )
            
            with ferramentas_col3:
                # Apply button
                apply_button = st.button("Aplicar Correções", type="primary", width='stretch', key=f"apply_corrections_{current_bbox_num}")
            
            # Update session state
            st.session_state[f"ferramentas_correcao_inteligente_{current_bbox_num}"] = correcao_inteligente
            st.session_state[f"ferramentas_correcao_regras_{current_bbox_num}"] = correcao_regras
            
            if apply_button:
                if correcao_inteligente or correcao_regras:
                    # Start with current text
                    if st.session_state.temp_text is not None:
                        working_text = st.session_state.temp_text
                    else:
                        working_text = st.session_state["ground_truth"]
                    
                    # Apply intelligent correction first if selected
                    if correcao_inteligente:
                        client = get_openrouter_client()
                        if client is not None:
                            try:
                                # Convert image to base64
                                img_base64 = encode_image_to_base64(display_img)
                                
                                with st.spinner("A processar..."):
                                    # Call OpenRouter API with image (using vision model)
                                    response = client.chat.completions.create(
                                        model=config.DEFAULT_VISION_MODEL,
                                        messages=[
                                            {
                                                "role": "user",
                                                "content": [
                                                    {
                                                        "type": "text",
                                                        "text": config.PROMPT_IMAGE
                                                    },
                                                    {
                                                        "type": "image_url",
                                                        "image_url": {
                                                            "url": f"data:image/jpeg;base64,{img_base64}"
                                                        }
                                                    }
                                                ]
                                            }
                                        ],
                                        temperature=config.LLM_TEMPERATURE,
                                    )
                                    
                                    # Extract text from response
                                    llm_corrected_text = response.choices[0].message.content.strip()
                                    logger.info(f"Texto obtido com LLM: {llm_corrected_text}")
                                    
                                    # Store in session state
                                    st.session_state[f"llm_corrected_text_{current_bbox_num}"] = llm_corrected_text
                                    
                                    # Use corrected text for further processing
                                    working_text = llm_corrected_text
                            except Exception as e:
                                st.error(f"Erro ao processar imagem com LLM: {str(e)}")
                                logger.error(f"Erro ao processar imagem com LLM: {str(e)}")
                                st.exception(e)
                        else:
                            st.error("OpenRouter API key não encontrada")
                    
                    # Apply rules correction if selected
                    if correcao_regras:
                        for old, new in config.RULES_DICT.items():
                            working_text = working_text.replace(old, new)
                        logger.info(f"Working text after rule correction: {working_text}")
                    
                    # Store the combined correction result for display in "Sugestão de Correção"
                    st.session_state[f"combined_correction_{current_bbox_num}"] = working_text
                    
                    # Update temp_text with the corrected result
                    st.session_state.temp_text = working_text
                    st.success("Correções aplicadas com sucesso!")
                    st.rerun()
                else:
                    st.warning("Por favor selecione pelo menos uma ferramenta de correção")
            
            # Display combined correction suggestion if available
            combined_correction_key = f"combined_correction_{current_bbox_num}"
            
            if combined_correction_key in st.session_state and st.session_state[combined_correction_key]:
                
                # Combined Correction Suggestion Text box (LLM + Rules or either one)
                st.text_area(
                    "Sugestão de Correção",
                    value=st.session_state[combined_correction_key],
                    height=150,
                    disabled=True,
                    key=f"combined_correction_display_{current_bbox_num}"
                )
                
                # Button to use combined correction suggestion
                if st.button("Aceitar sugestão de correção", key=f"use_combined_suggestion_{current_bbox_num}", type="primary"):
                    # Update temp_text with the combined correction
                    st.session_state.temp_text = st.session_state[combined_correction_key]
                    st.success("Sugestão copiada para 'Texto Correto'!")
                    # Move to next box
                    if st.session_state.bbox_num < len(bboxes_data):
                        st.session_state.next_bbox = True
                    else:
                        st.info("Já está na última caixa delimitadora")
                    st.rerun()

            # Form for error submission
            with st.form("error_form", clear_on_submit=True):
                # Ground truth (editable) - use session state value only
                # Pre-fill with corrected text if available
                if st.session_state.temp_text is not None:
                    ground_truth_default = st.session_state.temp_text
                else:
                    ground_truth_default = selected_bbox_text

                ground_truth = st.text_area(
                    "Texto Corrigido",
                    value=ground_truth_default, 
                    height=150,
                    disabled=False,
                    #key=f"ground_truth_{current_bbox_num}")
                )
                # Error type and Error submission in same row
                action_col1, action_col2 = st.columns([2, 2])
                
                with action_col1:
                    # Error type
                    error_type = st.selectbox(
                        "Tipo de Erro",
                        options=config.ERROR_TYPES,
                        format_func=lambda x: config.ERROR_TYPE_LABELS.get(x, x),
                        key="error_type"
                    )
                
                with action_col2:
                    # Red "Submeter Erro" button
                    st.markdown("""
                        <style>
                        .submit-error-btn > button {
                            background-color: #dc3545 !important;
                            color: white !important;
                            border-radius: 8px !important;
                            padding: 0.5rem 2rem !important;
                            font-weight: bold !important;
                            width: 100% !important;
                        }
                        .submit-error-btn > button:hover {
                            background-color: #c82333 !important;
                            box-shadow: 0 4px 8px rgba(220, 53, 69, 0.3) !important;
                        }
                        </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown('<div class="submit-error-btn">', unsafe_allow_html=True)
                    submitted = st.form_submit_button("Submeter Erro", width='stretch', key=f"submit_error_{current_bbox_num}")
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # Handle submit error button
                if submitted:
                    if not ground_truth.strip():
                        st.error("Por favor forneça o texto correto")
                    else:
                        insert_error(
                            document_name=document_name_db,  # Use year format for database
                            page_number=selected_page,
                            bbox_number=st.session_state.bbox_num,
                            text_with_error=selected_bbox_text,
                            ground_truth=ground_truth,
                            error_type=error_type
                        )
                        st.success("Erro submetido com sucesso!")
                        st.rerun()

    # Show existing errors for this document/page (outside columns)
    st.divider()
    st.subheader("Erros Existentes")

    # Database stores document_name as year (e.g., "1939"), not full document name
    errors = get_errors(document_name_db)
    page_errors = [e for e in errors if e['page_number'] == selected_page]

    if page_errors:
        # Display errors with delete buttons
        for idx, err in enumerate(page_errors):
            col1, col2 = st.columns([10, 1])
            
            with col1:
                error_type_pt = config.ERROR_TYPE_LABELS.get(err['error_type'], err['error_type'])
                st.markdown(f"**Caixa #{err['bbox_number']}** - {error_type_pt}")
                st.markdown(f"**Texto com Erro:** {err['text_with_error'][:100]}{'...' if len(err['text_with_error']) > 100 else ''}")
                st.markdown(f"**Texto Correto:** {err['ground_truth'][:100]}{'...' if len(err['ground_truth']) > 100 else ''}")
            
            with col2:
                if st.button("🗑️", key=f"delete_{err['id']}", help="Eliminar este erro"):
                    delete_error(err['id'])
                    st.success("Erro eliminado!")
                    st.rerun()
            
            if idx < len(page_errors) - 1:
                st.divider()
    else:
        st.info("Ainda não foram submetidos erros para esta página.")

# Statistics view
elif st.session_state.current_view == "estatisticas":
    st.header("Estatísticas de Anotação")
    
    # Get all errors
    all_errors = get_errors()
    
    if not all_errors:
        st.info("Ainda não existem anotações registadas.")
    else:
        # Overall statistics
        col1, col2, col3, col4 = st.columns(4)
        
        total_errors = len(all_errors)
        minor_errors = len([e for e in all_errors if e['error_type'] == 'minor'])
        major_errors = len([e for e in all_errors if e['error_type'] == 'major'])
        unique_documents = len(set(e['document_name'] for e in all_errors))
        
        with col1:
            st.metric("Total de Erros", total_errors)
        with col2:
            st.metric("Erros Menores", minor_errors)
        with col3:
            st.metric("Erros Maiores", major_errors)
        with col4:
            st.metric("Documentos", unique_documents)
        
        # Calculate word error statistics
        with st.spinner("A calcular estatísticas de erros de palavras..."):
            # Get unique document names that have errors
            documents_with_errors = set(error['document_name'] for error in all_errors)
            
            # Count total OCR words only from documents with errors
            total_ocr_words = 0
            for doc_name in documents_with_errors:
                doc_dir = parsed_docs_dir / doc_name
                if doc_dir.exists() and doc_dir.is_dir():
                    mmd_file_list = list(doc_dir.glob("DR_*_det.mmd"))
                    if mmd_file_list:
                        try:
                            parsed_doc_data = parse_mmd_file(str(mmd_file_list[0]))
                            for page_num, bboxes in parsed_doc_data.items():
                                for bbox, text in bboxes:
                                    total_ocr_words += count_words(text)
                        except Exception as e:
                            st.warning(f"Não foi possível processar {doc_name}: {e}")
            
            # Count error words
            minor_error_words = 0
            major_error_words = 0
            total_error_words = 0
            
            for error in all_errors:
                error_word_count = count_differing_words(
                    error['text_with_error'], 
                    error['ground_truth']
                )
                total_error_words += error_word_count
                if error['error_type'] == 'minor':
                    minor_error_words += error_word_count
                else:
                    major_error_words += error_word_count
            
            # Calculate percentages
            minor_error_pct = (minor_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
            major_error_pct = (major_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
            total_error_pct = (total_error_words / total_ocr_words * 100) if total_ocr_words > 0 else 0
        
        # Word error statistics section
        st.subheader("Estatísticas de Erros de Palavras")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Total de Palavras OCR", f"{total_ocr_words:,}")
        with col2:
            st.metric("Total de Palavras com Erro", f"{total_error_words:,}", f"{total_error_pct:.3f}%")
        with col3:
            st.metric("Palavras com Erro Menor", f"{minor_error_words:,}", f"{minor_error_pct:.3f}%")
        with col4:
            st.metric("Palavras com Erro Maior", f"{major_error_words:,}", f"{major_error_pct:.3f}%")
        with col5:
            accuracy = (1 - total_error_pct / 100) * 100 if total_ocr_words > 0 else 100
            st.metric("Precisão", f"{accuracy:.3f}%")
        
        st.divider()
        
        # Errors by document
        st.subheader("Erros por Documento")
        doc_stats = {}
        for error in all_errors:
            doc_name = error['document_name']
            if doc_name not in doc_stats:
                doc_stats[doc_name] = {'total': 0, 'minor': 0, 'major': 0}
            doc_stats[doc_name]['total'] += 1
            doc_stats[doc_name][error['error_type']] += 1
        
        # Display as table
        doc_df = pd.DataFrame([
            {
                'Documento': doc,
                'Total': stats['total'],
                'Menores': stats['minor'],
                'Maiores': stats['major']
            }
            for doc, stats in sorted(doc_stats.items())
        ])
        st.dataframe(doc_df, width='stretch', hide_index=True)
        
        st.divider()
        
        # Errors per page for selected document
        st.subheader(f"Erros por Página - {selected_dir.name}")
        doc_errors = [e for e in all_errors if e['document_name'] == selected_dir.name]
        
        if doc_errors:
            page_stats = {}
            for error in doc_errors:
                page_num = error['page_number']
                if page_num not in page_stats:
                    page_stats[page_num] = {'total': 0, 'minor': 0, 'major': 0}
                page_stats[page_num]['total'] += 1
                page_stats[page_num][error['error_type']] += 1
            
            page_df = pd.DataFrame([
                {
                    'Página': page,
                    'Total': stats['total'],
                    'Menores': stats['minor'],
                    'Maiores': stats['major']
                }
                for page, stats in sorted(page_stats.items())
            ])
            st.dataframe(page_df, width='stretch', hide_index=True)
            
            # Bar chart of errors per page
            if len(page_df) > 0:
                st.subheader("Erros por Página (Gráfico)")
                st.bar_chart(page_df.set_index('Página')[['Menores', 'Maiores']], height=400)
        else:
            st.info(f"Ainda não existem erros registados para o documento {selected_dir.name}.")
        
        st.divider()
        
        # Recent errors
        st.subheader("Erros Recentes")
        recent_errors = sorted(all_errors, key=lambda x: x['created_at'], reverse=True)[:10]
        
        for error in recent_errors:
            error_type_pt = config.ERROR_TYPE_LABELS.get(error['error_type'], error['error_type']).lower()
            with st.expander(f"{error['document_name']} - Página {error['page_number']}, Caixa {error['bbox_number']} ({error_type_pt})"):
                st.write(f"**Texto com Erro:** {error['text_with_error'][:200]}{'...' if len(error['text_with_error']) > 200 else ''}")
                st.write(f"**Texto Correto:** {error['ground_truth'][:200]}{'...' if len(error['ground_truth']) > 200 else ''}")
                st.caption(f"Submetido: {error['created_at']}")
