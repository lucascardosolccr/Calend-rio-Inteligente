import datetime
import calendar
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Scheduler Engine PRO v5.3",
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
# 2. MODELOS DE DADOS HISTÓRICOS E ESTRUTURAS
# =============================================================================
class Task:
    def __init__(self, id: str, name: str):
        self.id = id
        self.name = name

class Restriction:
    def __init__(self, type: str, params: Dict[str, Any]):
        self.type = type
        self.params = params

# =============================================================================
# 3. MOTOR DE FERIADOS FLEXÍVEL (GAUSS + REGIONAIS DINÂMICOS)
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
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL
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
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA CONSOLIDADO (V5.3)
# =============================================================================
class PurePythonScheduleEngine:
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr
        self.cal_config = cal_config
        self.tasks: List[Task] = []
        self.restrictions: List[Restriction] = []
        self.manual_exclusions: List[datetime.date] = []

    def add_tasks(self, tasks: List[Task]):
        self.tasks = tasks

    def apply_global_blocks(self, manual_exclusions: List[datetime.date]):
        self.manual_exclusions = manual_exclusions

    def apply_restrictions(self, restrictions: List[Restriction]):
        self.restrictions = restrictions

    def _validar_parcial(self, alocacao: Dict[str, int]) -> bool:
        for t_id, idx in alocacao.items():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or props["date"] in self.manual_exclusions:
                return False

        for r in self.restrictions:
            if r.type == "deadline":
                t_id = r.params["task_id"]
                if t_id in alocacao:
                    idx_atual = alocacao[t_id]
                    if r.params.get("before"):
                        idx_limite = self.cal_mgr.date_to_idx(r.params["before"])
                        if idx_atual >= idx_limite: return False
                    if r.params.get("after"):
                        idx_limite = self.cal_mgr.date_to_idx(r.params["after"])
                        if idx_atual <= idx_limite: return False
                        
            elif r.type == "dependency":
                t_a = r.params["task_a"]
                t_b = r.params["task_b"]
                if t_a in alocacao and t_b in alocacao:
                    min_gap = r.params.get("min_gap", 0)
                    if alocacao[t_b] < alocacao[t_a] + min_gap:
                        return False
                        
            elif r.type == "working_day_offset":
                t_base = r.params["task_base"]
                t_target = r.params["task_target"]
                if t_base in alocacao and t_target in alocacao:
                    idx_base = alocacao[t_base]
                    idx_target = alocacao[t_target]
                    offset_esperado = r.params["offset"]
                    
                    dias_uteis_reais = self.cal_mgr.contar_dias_uteis_entre(idx_base, idx_target, self.cal_config, self.manual_exclusions)
                    if dias_uteis_reais != offset_esperado:
                        return False
        return True

    def _avaliar_custo(self, alocacao: Dict[str, int]) -> int:
        custo = 0
        for idx in alocacao.values():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_weekend"] or props["is_holiday"]:
                custo += 50
        return custo

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]]]:
        solucao_otima = {}
        melhor_custo = float('inf')
        task_ids = [t.id for t in self.tasks]
        
        if not task_ids:
            return "SUCCESS", {}, []

        horizonte_busca = min(180, self.cal_mgr.total_days)

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
            alternatives = []
            for t_id in task_ids:
                score_calculado = max(0, 100 - melhor_custo)
                alternatives.append({
                    "task_id": t_id,
                    "score": score_calculado,
                    "justification": f"Alocação ideal com Score de Confiança de {score_calculado}%. Amarrada sob conformidade estrita de regras logísticas."
                })
            return "SUCCESS", results, alternatives
            
        return "INFEASIBLE", {}, []

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO (STREAMLIT UX DESIGN MASTER)
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Scheduler Engine PRO v5.3</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Código Mestre Consolidado: Restauração Total de Históricos e Lógica de Planilha Inteligente Integrada</div>', unsafe_allow_html=True)
    
    if "custom_holidays" not in st.session_state:
        st.session_state.custom_holidays = {}

    # Estado das tarefas e restrições históricas acopladas nativamente na estrutura
    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Descrição do Compromisso": "Homologação e Abertura do Processo", "Tipo de Vínculo": "Livre", "Atividade Base": "", "Valor Técnico": 0},
            {"Código ID": "T2", "Descrição do Compromisso": "Análise de Metas e Dashboard CILAES", "Tipo de Vínculo": "Deslocamento Dias Úteis", "Atividade Base": "T1", "Valor Técnico": 10},
            {"Código ID": "T3", "Descrição do Compromisso": "Entrega do Relatório Final de Fechamento", "Tipo de Vínculo": "Data Limite (Antes de)", "Atividade Base": "", "Valor Técnico": 45}
        ])

    if "restrictions_manuais" not in st.session_state:
        st.session_state.restrictions_manuais = []

    # Barra Lateral
    st.sidebar.header("⚙️ Configurações Centrais")
    ano_corrente = st.sidebar.number_input("Ano do Exercício", min_value=2024, max_value=2030, value=2026)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Ativos", value=True)
    }

    st.sidebar.subheader("🏛️ Cadastrar Feriado Regional")
    with st.sidebar.container():
        f_name = st.text_input("Nome do Feriado", placeholder="Ex: Feriado Distrital")
        f_date = st.date_input("Data do Evento", datetime.date(ano_corrente, 11, 30))
        if st.sidebar.button("➕ Injetar Feriado Regional", use_container_width=True):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.sidebar.success(f"'{f_name}' registrado!")
                st.rerun()

    st.sidebar.subheader("🚫 Indisponibilidades Manuais")
    manual_dates = st.sidebar.date_input("Adicionar datas avulsas bloqueadas", value=[])
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # Abas Estruturais Clássicas
    tab_compromissos, tab_visualizacao, tab_calendario_visual = st.tabs([
        "📋 1. Entrada de Escopo & Planilha Editável", 
        "📊 2. Painel Analítico & Métricas Visuais", 
        "📅 3. Calendário Visual Anual"
    ])

    with tab_compromissos:
        st.subheader("📁 Central de Carga e Upload")
        uploaded_file = st.file_uploader("Suba seu arquivo (.csv, .xlsx) para popular a grade operacional:", type=["csv", "xlsx"])
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_up = pd.read_csv(uploaded_file)
                else:
                    df_up = pd.read_excel(uploaded_file)
                
                # Normalização inteligente para evitar quebras em cargas parciais
                for col_req in ["Código ID", "Descrição do Compromisso", "Tipo de Vínculo", "Atividade Base", "Valor Técnico"]:
                    if col_req not in df_up.columns:
                        df_up[col_req] = "" if col_req != "Valor Técnico" else 0
                
                st.session_state.df_planilha = df_up
                st.success("Planilha integrada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao processar arquivo: {e}")

        st.markdown("---")
        
        col_grade, col_form = st.columns([3, 2], gap="large")
        
        with col_grade:
            st.markdown("#### 📝 Matriz de Atividades Interativa (Edição Direta)")
            df_edited = st.data_editor(
                st.session_state.df_planilha,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "Código ID": st.column_config.TextColumn("Código ID", required=True),
                    "Descrição do Compromisso": st.column_config.TextColumn("Descrição do Compromisso", width="medium"),
                    "Tipo de Vínculo": st.column_config.SelectboxColumn(
                        "Tipo de Vínculo",
                        options=["Livre", "Deslocamento Dias Úteis", "Data Limite (Antes de)", "Data Limite (Após de)"],
                        required=True
                    ),
                    "Atividade Base": st.column_config.TextColumn("Atividade Base"),
                    "Valor Técnico": st.column_config.NumberColumn("Valor (Dias / Deslocamento)", min_value=0, max_value=365)
                }
            )
            st.session_state.df_planilha = df_edited

        with col_form:
            st.markdown("#### ⛓️ Regras de Amarração Secundárias (Formulário Clássico)")
            rest_type = st.selectbox("Selecione o Modelo de Regra Manual", [
                "Deslocamento por Dias Úteis Exatos", 
                "Prazo Limite (Deadline)", 
                "Dependência Sequencial Simples"
            ])
            
            if rest_type == "Deslocamento por Dias Úteis Exatos":
                t_base_f = st.selectbox("Atividade Base", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])], key="bf")
                t_target_f = st.selectbox("Atividade Destino", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])], key="tf")
                num_dias = st.number_input("Dias Úteis de Intervalo", min_value=1, value=10)
                if st.button("Vincular Regra de Dias Úteis", use_container_width=True):
                    st.session_state.restrictions_manuais.append(Restriction(type="working_day_offset", params={"task_base": t_base_f, "task_target": t_target_f, "offset": num_dias}))
                    st.rerun()

            elif rest_type == "Prazo Limite (Deadline)":
                t_id_f = st.selectbox("Escolha o Alvo", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])])
                choice = st.radio("Critério", ["Deve ocorrer APÓS", "Deve ocorrer ANTES"])
                d_val = st.date_input("Data Limite", datetime.date(ano_corrente, 6, 1))
                if st.button("Vincular Prazo Manual", use_container_width=True):
                    param_key = "after" if "APÓS" in choice else "before"
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, param_key: d_val}))
                    st.rerun()
                    
            elif rest_type == "Dependência Sequencial Simples":
                t_a = st.selectbox("Antecessora (A)", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])], key="da")
                t_b = st.selectbox("Sucessora (B)", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])], key="db")
                min_g = st.number_input("Intervalo Mínimo Corrido (Dias)", min_value=0, value=2)
                if st.button("Vincular Cadeia Sequencial", use_container_width=True):
                    st.session_state.restrictions_manuais.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                    st.rerun()

            if st.session_state.restrictions_manuais:
                st.markdown("---")
                st.markdown("**Regras Manuais Ativas:**")
                for idx, r in enumerate(st.session_state.restrictions_manuais):
                    st.caption(f"• Regra {idx+1}: {r.type.upper()} -> {r.params}")
                if st.button("🗑️ Limpar Restrições de Formulário", use_container_width=True):
                    st.session_state.restrictions_manuais = []
                    st.rerun()

    # COMPILAÇÃO UNIFICADA DE REGRAS (PLANILHA + FORMULÁRIO)
    engine_tasks = []
    engine_restrictions = list(st.session_state.restrictions_manuais)

    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Descrição do Compromisso", "Tarefa Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]):
            continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        
        v_tipo = row.get("Tipo de Vínculo", "Livre")
        v_base = str(row.get("Atividade Base", "")).strip()
        try:
            v_val = int(row.get("Valor Técnico", 0))
        except:
            v_val = 0
            
        if v_tipo == "Deslocamento Dias Úteis" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Data Limite (Antes de)":
            target_date = cal_mgr.start_date + datetime.timedelta(days=v_val if v_val > 0 else 30)
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": target_date}))
        elif v_tipo == "Data Limite (Após de)":
            target_date = cal_mgr.start_date + datetime.timedelta(days=v_val if v_val > 0 else 1)
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "after": target_date}))

    # EXECUÇÃO DO MOTOR TRADICIONAL RESTAURADO
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards = engine.solve()

    with tab_visualizacao:
        if status == "SUCCESS":
            st.success("🎯 Agenda estruturada com sucesso! Todas as condicionais históricas e de planilha foram resolvidas.")
            
            # Recuperação Total: Renderização dos Cartões Métricos Originais com Score e Justificativa
            col_m1, col_m2 = st.columns(2)
            for i, card in enumerate(alt_cards):
                target_col = col_m1 if i % 2 == 0 else col_m2
                t_id = card["task_id"]
                date_val = sol_dates.get(t_id)
                t_obj = next((t for t in engine_tasks if t.id == t_id), None)
                
                if t_obj and date_val:
                    with target_col:
                        st.markdown(f"""
                        <div class="metric-card">
                            <span style="color:#2563EB; font-weight:bold; font-size:11px;">CÓDIGO: {t_id} | CONFIDANÇA: {card['score']}%</span>
                            <h4 style="margin:2px 0;">📌 {t_obj.name}</h4>
                            <h2 style="color:#1E3A8A; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:11.5px; color:#4B5563; margin:4px 0;"><b>Justificativa:</b> {card['justification']}</p>
                            <span style="font-size:11px; color:#6B7280;">Dia da semana: {["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][date_val.weekday()]}</span>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📊 Tabela Geral Consolidadora")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    cronograma_data.append({
                        "Código ID": t_id,
                        "Descrição do Compromisso": t_item.name,
                        "Data Determinada": d_val.strftime('%d/%m/%Y'),
                        "Dia da Semana": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][d_val.weekday()],
                    })
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                
                csv_buffer = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar Planilha Otimizada (.CSV)",
                    data=csv_buffer,
                    file_name=f"cronograma_operacional_{ano_corrente}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.error("❌ Bloqueio Logístico: Conflito estrutural de regras. O motor determinou ser logicamente impossível alocar os compromissos com os critérios fornecidos.")

    with tab_calendario_visual:
        st.subheader("📅 Mapa Analítico de Disponibilidade")
        
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Dia Útil Livre</div>
            <div><span style="background-color: #DBEAFE; padding: 2px 10px; border: 1px solid #2563EB; border-radius:3px;"></span> <b>Tarefa Alocada</b></div>
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
                        html_cal += '</div>'
                        
                        cal_obj = calendar.Calendar(firstweekday=6)
                        weeks = cal_obj.monthdayscalendar(ano_corrente, m_idx)
                        
                        for week in weeks:
                            html_cal += '<div class="calendar-row">'
                            for day in week:
                                if day == 0:
                                    html_cal += '<div class="calendar-cell day-blocked"></div>'
                                else:
                                    d_verif = datetime.date(ano_corrente, m_idx, day)
                                    idx_verif = cal_mgr.date_to_idx(d_verif)
                                    props = cal_mgr.get_day_properties(idx_verif, cal_config)
                                    
                                    cell_class = "day-normal"
                                    title_hover = props["name"]
                                    
                                    if d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"Alocado: {', '.join(t_codes)}"
                                    elif props["is_holiday"]:
                                        cell_class = "day-holiday"
                                    elif props["is_blocked"] or d_verif in manual_dates:
                                        cell_class = "day-blocked"
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{day}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

if __name__ == "__main__":
    main()
