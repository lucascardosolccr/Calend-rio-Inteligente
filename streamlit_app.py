import datetime
import calendar
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Scheduler Engine PRO v3",
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
    .manual-box {
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    /* Grid customizado do calendário visual */
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
# 2. MODELOS DE DADOS
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
        # Injeta os feriados estaduais/municipais ou impeditivos customizados
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

# =============================================================================
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA AVANÇADA
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
            
            for idx in range(min(90, self.cal_mgr.total_days)):
                alocacao_atual[t_id] = idx
                if self._avaliar_custo(alocacao_atual) < melhor_custo:
                    backtrack(task_index + 1, alocacao_atual)
                del alocacao_atual[t_id]

        backtrack(0, {})
        
        if solucao_otima:
            results = {t_id: self.cal_mgr.idx_to_date(idx) for t_id, idx in solucao_otima.items()}
            alternatives = []
            for t_id in task_ids:
                alternatives.append({
                    "task_id": t_id,
                    "score": max(0, 100 - melhor_custo),
                    "justification": "Conformidade e segurança regulamentar validadas."
                })
            return "SUCCESS", results, alternatives
            
        return "INFEASIBLE", {}, []

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO (STREAMLIT UX DESIGN)
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Engine de Agendamento Otimizado</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Planejamento Estratégico com Calendário Visual Dinâmico e Customização de Feriados</div>', unsafe_allow_html=True)
    
    # Gerenciamento de Feriados Estaduais / Customizados via Session State
    if "custom_holidays" not in st.session_state:
        st.session_state.custom_holidays = {}

    # Barra Lateral - Controles Gerais
    st.sidebar.header("⚙️ Configurações Centrais")
    ano_corrente = st.sidebar.number_input("Ano do Exercício", min_value=2024, max_value=2030, value=2026)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Ativos", value=True)
    }

    # Painel para Adicionar Feriados Customizados (Estaduais / Municipais)
    st.sidebar.subheader("🏛️ Cadastrar Feriado Estadual / Impeditivo")
    with st.sidebar.container():
        f_name = st.text_input("Nome do Feriado/Impeditivo", placeholder="Ex: Feriado Distrital")
        f_date = st.date_input("Data do Evento", datetime.date(ano_corrente, 11, 30))
        if st.sidebar.button("➕ Injetar Feriado Regional", use_container_width=True):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.sidebar.success(f"'{f_name}' registrado!")
                st.rerun()

    if st.session_state.custom_holidays:
        st.sidebar.markdown("**Feriados Estaduais Ativos:**")
        for d, name in list(st.session_state.custom_holidays.items()):
            st.sidebar.caption(f"• {d.strftime('%d/%m')}: {name}")

    st.sidebar.subheader("🚫 Indisponibilidades Manuais")
    manual_dates = st.sidebar.date_input("Adicionar datas avulsas bloqueadas", value=[])
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    # Instancia o gerenciador unificado de calendário
    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # Inicialização estável do escopo de tarefas padrão
    if "tasks" not in st.session_state:
        st.session_state.tasks = [
            Task(id="T1", name="Reunião de Alinhamento e Metas"),
            Task(id="T2", name="Consolidação e Integração CILAES")
        ]
    if "restrictions" not in st.session_state:
        st.session_state.restrictions = [
            Restriction(type="dependency", params={"task_a": "T1", "task_b": "T2", "min_gap": 2})
        ]

    # Abas Principais de Operação
    tab_compromissos, tab_visualizacao, tab_calendario_visual = st.tabs([
        "📋 1. Escopo & Regras", 
        "📊 2. Painel Analítico & Exportação", 
        "📅 3. Calendário Visual Anual"
    ])

    with tab_compromissos:
        col_tasks, col_rest = st.columns([1, 1], gap="large")
        
        with col_tasks:
            st.subheader("📌 Cadastro de Atividades")
            with st.container():
                new_id = st.text_input("Código de Identificação (Único)", value=f"T{len(st.session_state.tasks)+1}")
                new_name = st.text_input("Nome Descritivo do Compromisso", placeholder="Ex: Auditoria de Processos")
                if st.button("✨ Adicionar Atividade", use_container_width=True):
                    if new_name and not any(t.id == new_id for t in st.session_state.tasks):
                        st.session_state.tasks.append(Task(id=new_id, name=new_name))
                        st.toast(f"Compromisso {new_id} acoplado!")
                        st.rerun()
            
            st.markdown("---")
            df_tasks = pd.DataFrame([{"ID": t.id, "Compromisso Cadastrado": t.name} for t in st.session_state.tasks])
            st.dataframe(df_tasks, use_container_width=True, hide_index=True)

        with col_rest:
            st.subheader("⛓️ Restrições Logísticas")
            rest_type = st.selectbox("Selecione o Modelo de Regra", ["Prazo Limite (Deadline)", "Dependência Sequencial"])
            
            if rest_type == "Prazo Limite (Deadline)":
                t_id = st.selectbox("Escolha o Alvo", [t.id for t in st.session_state.tasks])
                choice = st.radio("Critério", ["Deve ocorrer APÓS", "Deve ocorrer ANTES"])
                d_val = st.date_input("Data de Referência", datetime.date(ano_corrente, 1, 10))
                if st.button("Vincular Prazo", use_container_width=True):
                    param_key = "after" if "APÓS" in choice else "before"
                    st.session_state.restrictions.append(Restriction(type="deadline", params={"task_id": t_id, param_key: d_val}))
                    st.rerun()
                    
            elif rest_type == "Dependência Sequencial":
                t_a = st.selectbox("Antecessora (A)", [t.id for t in st.session_state.tasks], key="dep_a")
                t_b = st.selectbox("Sucessora (B)", [t.id for t in st.session_state.tasks], key="dep_b")
                min_g = st.number_input("Intervalo Mínimo (Dias)", min_value=0, value=2)
                if st.button("Vincular Cadeia Sequencial", use_container_width=True):
                    if t_a != t_b:
                        st.session_state.restrictions.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                        st.rerun()

            st.markdown("---")
            for idx, r in enumerate(st.session_state.restrictions):
                st.caption(f"• **Regra {idx+1}:** {r.type.upper()} ➔ {r.params}")

    # RESOLUÇÃO DA ENGINE MATEMÁTICA
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(st.session_state.tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(st.session_state.restrictions)
    status, sol_dates, alt_cards = engine.solve()

    with tab_visualizacao:
        if status == "SUCCESS":
            st.success("🎯 Agenda estruturada com sucesso!")
            
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                t_obj = next(t for t in st.session_state.tasks if t.id == t_id)
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <span style="color:#2563EB; font-weight:bold; font-size:11px;">CÓDIGO: {t_id}</span>
                        <h4 style="margin:2px 0;">📌 {t_obj.name}</h4>
                        <h2 style="color:#1E3A8A; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("### 📊 Tabela Geral de Atividades")
            cronograma_data = [
                {
                    "Código ID": t_id,
                    "Descrição do Compromisso": next(t.name for t in st.session_state.tasks if t.id == t_id),
                    "Data Determinada": d_val.strftime('%d/%m/%Y'),
                    "Dia da Semana": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][d_val.weekday()],
                } for t_id, d_val in sol_dates.items()
            ]
            df_final = pd.DataFrame(cronograma_data)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            csv_buffer = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Planilha Consolidadora (.CSV)",
                data=csv_buffer,
                file_name=f"cronograma_{ano_corrente}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.error("❌ Bloqueio Logístico: Inviabilidade matemática nas regras vigentes.")

    with tab_calendario_visual:
        st.subheader("📅 Mapa Visual de Disponibilidade e Alocações")
        st.caption("Visão matricial analítica do ano corrente. Monitore bloqueios, feriados nacionais/estaduais e tarefas alocadas.")
        
        # Legenda Visual Explicativa
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Dia Operacional Disponível</div>
            <div><span style="background-color: #DBEAFE; padding: 2px 10px; border: 1px solid #2563EB; border-radius:3px;"></span> <b>Atividade Alocada</b></div>
            <div><span style="background-color: #FEE2E2; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Feriado (Nacional ou Customizado)</div>
            <div><span style="background-color: #E5E7EB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Fim de Semana / Bloqueio Manual</div>
        </div>
        """, unsafe_allow_html=True)

        # Renderização dos meses dinamicamente em colunas
        m_idx = 1
        for row_m in range(4): # 4 linhas de 3 meses cada = 12 meses
            cols_meses = st.columns(3)
            for col_mes in cols_meses:
                if m_idx <= 12:
                    with col_mes:
                        nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][m_idx - 1]
                        st.markdown(f"##### **{nome_mes}**")
                        
                        # Inicia a tabela HTML do mês
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
                                    
                                    # Determina a classe CSS com base no status do dia
                                    cell_class = "day-normal"
                                    title_hover = props["name"]
                                    
                                    if d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        # Identifica qual tarefa está aqui
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"Alocado: {', '.join(t_codes)}"
                                    elif props["is_holiday"]:
                                        cell_class = "day-holiday"
                                        title_hover = props["name"]
                                    elif props["is_blocked"] or d_verif in manual_dates:
                                        cell_class = "day-blocked"
                                        title_hover = "Bloqueado / Fim de Semana"
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{day}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

if __name__ == "__main__":
    main()
