import datetime
import calendar
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Scheduler Engine PRO v5",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS avançada para cartões modernos e a matriz do calendário visual
st.markdown("""
    <style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #FFFFFF;
        border-left: 5px solid #2563EB;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        margin-bottom: 15px;
    }
    .calendar-grid {
        display: block;
        margin-bottom: 20px;
    }
    .calendar-row {
        display: table;
        width: 100%;
        table-layout: fixed;
    }
    .calendar-cell {
        display: table-cell;
        text-align: center;
        padding: 6px 2px;
        font-size: 11px;
        border: 1px solid #E5E7EB;
        font-weight: 600;
    }
    .day-normal { background-color: #F9FAFB; color: #1F2937; }
    .day-allocated { background-color: #DBEAFE; color: #1E40AF; border: 2px solid #2563EB !important; }
    .day-holiday { background-color: #FEE2E2; color: #991B1B; }
    .day-blocked { background-color: #E5E7EB; color: #6B7280; }
    .day-header { background-color: #F3F4F6; color: #374151; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. MOTOR DE FERIADOS FLEXÍVEL (GAUSS + REGIONAIS DINÂMICOS)
# =============================================================================
class BrazilHolidaysPure:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, str] = None):
        self.year = year
        self.custom_holidays = custom_holidays if custom_holidays else {}
        self.holidays_dict = self._generate_holidays()

    def _calcula_pascoa(self, ano: int) -> datetime.date:
        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        mes = (h + l - 7 * m + 114) // 31
        dia = ((h + l - 7 * m + 114) % 31) + 1
        return datetime.date(ano, mes, dia)

    def _generate_holidays(self) -> Dict[datetime.date, str]:
        pascoa = self._calcula_pascoa(self.year)
        carnaval = pascoa - datetime.timedelta(days=47)
        sexta_santa = pascoa - datetime.timedelta(days=2)
        corpus_christi = pascoa + datetime.timedelta(days=60)
        
        base_holidays = {
            datetime.date(self.year, 1, 1): "Ano Novo",
            datetime.date(self.year, 4, 21): "Tiradentes / Aniv. de Brasília",
            datetime.date(self.year, 5, 1): "Dia do Trabalho",
            datetime.date(self.year, 9, 7): "Independência do Brasil",
            datetime.date(self.year, 10, 12): "Nossa Sra. Aparecida",
            datetime.date(self.year, 10, 28): "Dia do Servidor Público",
            datetime.date(self.year, 11, 2): "Finados",
            datetime.date(self.year, 11, 15): "Proclamação da República",
            datetime.date(self.year, 11, 30): "Dia do Evangélico (Feriado no DF)",
            datetime.date(self.year, 12, 25): "Natal",
            carnaval: "Carnaval",
            sexta_santa: "Sexta-feira Santa",
            corpus_christi: "Corpus Christi"
        }
        base_holidays.update(self.custom_holidays)
        return base_holidays

    def get(self, d: datetime.date, default: str = "") -> str:
        return self.holidays_dict.get(d, default)

# =============================================================================
# 3. GERENCIADOR DO CALENDÁRIO OPERACIONAL
# =============================================================================
class CalendarManager:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, str] = None):
        self.year = year
        self.br_holidays = BrazilHolidaysPure(year=self.year, custom_holidays=custom_holidays)
        self.start_date = datetime.date(year, 1, 1)
        self.end_date = datetime.date(year, 12, 31)
        self.total_days = (self.end_date - self.start_date).days + 1
        
    def date_to_idx(self, d: datetime.date) -> int:
        return (d - self.start_date).days
        
    def idx_to_date(self, idx: int) -> datetime.date:
        return self.start_date + datetime.timedelta(days=idx)
        
    def get_day_properties(self, idx: int, config: Dict[str, bool]) -> Dict[str, Any]:
        current_date = self.idx_to_date(idx)
        is_weekend = current_date.weekday() in (5, 6)
        holiday_name = self.br_holidays.get(current_date, "")
        is_holiday = holiday_name != ""
        
        is_blocked = False
        if config.get("block_weekends") and is_weekend:
            is_blocked = True
        if config.get("block_holidays") and is_holiday:
            is_blocked = True
            
        return {
            "date": current_date,
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "is_blocked": is_blocked,
            "name": holiday_name if is_holiday else "Dia Operacional",
            "weekday": current_date.weekday()
        }

    def contar_dias_uteis_entre(self, start_idx: int, end_idx: int, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> int:
        if start_idx >= end_idx:
            return 0
        dias_uteis = 0
        for idx in range(start_idx + 1, end_idx + 1):
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions:
                dias_uteis += 1
        return dias_uteis

# =============================================================================
# 4. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA AVANÇADA (V5)
# =============================================================================
class PurePythonScheduleEngine:
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr
        self.cal_config = cal_config
        self.tasks: List[Dict[str, Any]] = []
        self.manual_exclusions: List[datetime.date] = []

    def load_matrix(self, tasks_list: List[Dict[str, Any]]):
        self.tasks = tasks_list

    def apply_global_blocks(self, manual_exclusions: List[datetime.date]):
        self.manual_exclusions = manual_exclusions

    def _validar_parcial(self, alocacao: Dict[str, int]) -> bool:
        for t_id, idx in alocacao.items():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or props["date"] in self.manual_exclusions:
                return False

        # Avalia as regras extraídas diretamente da tabela do usuário
        for t in self.tasks:
            t_id = t["Código ID"]
            if t_id in alocacao:
                idx_atual = alocacao[t_id]
                
                # Regra 1: Deslocamento por Dias Úteis Vinculados
                base_id = t.get("Id da Atividade Base")
                if pd.notna(base_id) and str(base_id).strip() != "" and str(base_id) in alocacao:
                    idx_base = alocacao[str(base_id)]
                    offset_esperado = t.get("Dias Úteis de Intervalo")
                    try:
                        offset_esperado = int(offset_esperado) if pd.notna(offset_esperado) else 0
                    except:
                        offset_esperado = 0
                        
                    if offset_esperado > 0:
                        dias_uteis_reais = self.cal_mgr.contar_dias_uteis_entre(idx_base, idx_atual, self.cal_config, self.manual_exclusions)
                        if dias_uteis_reais != offset_esperado:
                            return False
                            
                # Regra 2: Deadline Fixo de data Limite (Se houver)
                deadline_val = t.get("Prazo Limite (AAAA-MM-DD)")
                if pd.notna(deadline_val) and isinstance(deadline_val, (datetime.date, datetime.datetime)):
                    idx_limite = self.cal_mgr.date_to_idx(deadline_val if isinstance(deadline_val, datetime.date) else deadline_val.date())
                    if idx_atual > idx_limite:
                        return False
        return True

    def _avaliar_custo(self, alocacao: Dict[str, int]) -> int:
        custo = 0
        for idx in alocacao.values():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_weekend"] or props["is_holiday"]:
                custo += 50
        return custo

    def solve(self) -> Tuple[str, Dict[str, datetime.date]]:
        solucao_otima = {}
        melhor_custo = float('inf')
        task_ids = [str(t["Código ID"]) for t in self.tasks if pd.notna(t["Código ID"])]
        
        if not task_ids:
            return "INFEASIBLE", {}

        horizonte_busca = min(120, self.cal_mgr.total_days)

        def backtrack(task_index: int, alocacao_atual: Dict[str, int]):
            nonlocal solucao_otima, melhor_custo
            
            if not self._validar_parcial(alocacao_atual):
                return
                
            if task_index == len(task_ids):
                custo_atual = self._avaliar_custo(alocacao_atual)
                if custo_atual < melhor_custo:
                    melhor_custo = custo_atual
                    solucao_otima = alocacao_atual.copy()
                return

            t_id = task_ids[task_index]
            
            for idx in range(horizonte_busca):
                alocacao_atual[t_id] = idx
                if self._avaliar_custo(alocacao_atual) < melhor_custo:
                    backtrack(task_index + 1, alocacao_atual)
                del alocacao_atual[t_id]

        backtrack(0, {})
        
        if solucao_otima:
            results = {t_id: self.cal_mgr.idx_to_date(idx) for t_id, idx in solucao_otima.items()}
            return "SUCCESS", results
        return "INFEASIBLE", {}

# =============================================================================
# 5. INTERFACE INTERATIVA DO USUÁRIO (STREAMLIT UX DESIGN)
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Engine de Planejamento Operacional Inteligente</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Planilha Dinâmica Interativa com Cálculo Automático de Dias Úteis e Prazos Regulares</div>', unsafe_allow_html=True)
    
    if "custom_holidays" not in st.session_state:
        st.session_state.custom_holidays = {}

    # Configurações na Barra Lateral
    st.sidebar.header("⚙️ Painel de Controle")
    ano_corrente = st.sidebar.number_input("Ano de Exercício", min_value=2024, max_value=2030, value=2026)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Civis/DF", value=True)
    }

    st.sidebar.subheader("🏛️ Adicionar Feriado Estadual/Regional")
    with st.sidebar.container():
        f_name = st.text_input("Nome do Feriado", placeholder="Ex: Feriado Distrital")
        f_date = st.date_input("Data do Feriado", datetime.date(ano_corrente, 11, 30))
        if st.sidebar.button("➕ Injetar Feriado", use_container_width=True):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.sidebar.success(f"'{f_name}' salvo!")
                st.rerun()

    st.sidebar.subheader("🚫 Bloqueios Manuais do Usuário")
    manual_dates = st.sidebar.date_input("Marcar indisponibilidade avulsa", value=[])
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO
    # -------------------------------------------------------------------------
    tab_planilha, tab_analise, tab_calendario_visual = st.tabs([
        "📊 1. Upload & Edição da Planilha", 
        "🚀 2. Processamento & Cronograma Gerado", 
        "📅 3. Visão Anual do Calendário"
    ])

    with tab_planilha:
        st.subheader("📁 Carregamento da Matriz de Atividades")
        st.markdown("""
        Suba uma planilha contendo a estrutura de cronograma ou utilize a **matriz padrão editável** abaixo. 
        Você pode alterar valores, adicionar linhas e configurar dependências diretamente nas células!
        """)
        
        uploaded_file = st.file_uploader("Arraste ou selecione seu arquivo (.csv, .xlsx)", type=["csv", "xlsx"])
        
        # Define os dados padrão se não houver arquivo carregado
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_base = pd.read_csv(uploaded_file)
                else:
                    df_base = pd.read_excel(uploaded_file)
                st.toast("Tabela acoplada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler o arquivo: {e}. Carregando modelo padrão.")
                uploaded_file = None

        if uploaded_file is None:
            # Planilha Estrutural Modelo Base
            data_default = {
                "Código ID": ["T1", "T2", "T3"],
                "Descrição do Compromisso": ["Abertura do Processo de Auditoria", "Análise de Riscos e Relatório Inicial", "Homologação e Entrega dos Resultados"],
                "Id da Atividade Base": ["", "T1", "T2"],
                "Dias Úteis de Intervalo": [0, 15, 10],
                "Prazo Limite (AAAA-MM-DD)": [None, None, datetime.date(ano_corrente, 12, 15)]
            }
            df_base = pd.DataFrame(data_default)

        st.markdown("#### 📝 Modifique os dados na tabela abaixo em tempo real:")
        # O DATA EDITOR torna a planilha 100% interativa
        df_edited = st.data_editor(
            df_base, 
            use_container_width=True, 
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código ID", help="Identificador único (Ex: T1, T2)", required=True),
                "Dias Úteis de Intervalo": st.column_config.NumberColumn("Dias Úteis de Intervalo", min_value=0, max_value=90, step=1),
                "Prazo Limite (AAAA-MM-DD)": st.column_config.DateColumn("Prazo Limite", format="DD/MM/YYYY")
            }
        )
        
        # Converte a planilha editada em lista de dicionários para a Engine de cálculo
        tasks_matrix = df_edited.to_dict(orient="records")

    # EXECUÇÃO DO MOTOR MATEMÁTICO COM BASE NA PLANILHA EDITADA
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.load_matrix(tasks_matrix)
    engine.apply_global_blocks(manual_dates)
    status, sol_dates = engine.solve()

    with tab_analise:
        st.subheader("🏁 Resultados Estruturados pelo Motor")
        
        if status == "SUCCESS":
            st.success("🎯 Solução ideal encontrada! Todas as amarrações da planilha foram respeitadas e os finais de semana/feriados foram pulados com sucesso.")
            
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                # Procura a descrição da tarefa na lista editada
                desc_task = next((t["Descrição do Compromisso"] for t in tasks_matrix if str(t["Código ID"]) == t_id), "Compromisso")
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <span style="color:#2563EB; font-weight:bold; font-size:11px;">CÓDIGO DA LINHA: {t_id}</span>
                        <h4 style="margin:2px 0;">📌 {desc_task}</h4>
                        <h2 style="color:#1E3A8A; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                        <span style="font-size:11px; color:#6B7280;">Dia da semana: {["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][date_val.weekday()]}</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("### 📊 Tabela Geral Consolidadora Resultante")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                desc = next((t["Descrição do Compromisso"] for t in tasks_matrix if str(t["Código ID"]) == t_id), "")
                cronograma_data.append({
                    "Código ID": t_id,
                    "Descrição do Compromisso": desc,
                    "Data Calculada": d_val.strftime('%d/%m/%Y'),
                    "Dia da Semana": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][d_val.weekday()],
                })
            df_final = pd.DataFrame(cronograma_data)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            csv_buffer = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Cronograma Final Atualizado (.CSV)",
                data=csv_buffer,
                file_name=f"cronograma_calculado_{ano_corrente}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.error("❌ Conflito de Regras na Planilha. Verifique se você configurou os intervalos de Dias Úteis corretamente ou se alguma data Limite inserida nas células está inviabilizando o fluxo.")

    with tab_calendario_visual:
        st.subheader("📅 Mapa de Ocupação e Disponibilidade")
        
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Dia Livre</div>
            <div><span style="background-color: #DBEAFE; padding: 2px 10px; border: 1px solid #2563EB; border-radius:3px;"></span> <b>Alocado pela Planilha</b></div>
            <div><span style="background-color: #FEE2E2; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Feriado Ativo</div>
            <div><span style="background-color: #E5E7EB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Bloqueio / Fim de Semana</div>
        </div>
        """, unsafe_allow_html=True)

        m_idx = 1
        for row_m in range(4):
            cols_meses = st.columns(3)
            for col_mes in cols_meses:
                if m_idx <= 12:
                    with col_mes:
                        nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][m_idx - 1]
                        st.markdown(f"##### **{nome_mes}**")
                        
                        html_cal = '<div class="calendar-grid"><div class="calendar-row">'
                        for sem in ["D", "S", "T", "Q", "Q", "S", "S"]:
                            html_cal += f'<div class="calendar-cell day-header">{sem}</div>'
          