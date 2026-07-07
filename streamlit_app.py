import sys
import subprocess
import datetime
from typing import List, Dict, Any, Tuple

# =============================================================================
# MECANISMO DE DEFESA CONTRA MODULE-NOT-FOUND (GARANTIA DE EXECUÇÃO NO CLOUD)
# =============================================================================
def assegurar_dependencias():
    pacotes_criticos = {
        "plotly": "plotly",
        "holidays": "holidays",
        "ortools": "ortools"
    }
    for modulo, pacote in pacotes_criticos.items():
        try:
            __import__(modulo)
        except ImportError:
            # Instala silenciosamente em tempo de execução se o Cloud falhar
            subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])

# Executa a verificação antes de qualquer importação pesada
assegurar_dependencias()

import streamlit as st
import pandas as pd
import plotly.express as px
import holidays
from ortools.sat.python import cp_model

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES DE UI
# =============================================================================
st.set_page_config(
    page_title="Scheduler Engine PRO",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-left: 5px solid #007bff;
        padding: 15px;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }
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
# 3. GERENCIADOR DE CALENDÁRIO
# =============================================================================
class CalendarManager:
    def __init__(self, year: int, state: str = "DF"):
        self.year = year
        self.state = state
        self.br_holidays = holidays.Brazil(years=self.year, subdivisions=self.state)
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
        is_holiday = current_date in self.br_holidays
        is_facultative = "facultativo" in self.br_holidays.get(current_date, "").lower()
        
        is_blocked = False
        if config.get("block_weekends") and is_weekend:
            is_blocked = True
        if config.get("block_holidays") and is_holiday and not is_facultative:
            is_blocked = True
        if config.get("block_facultative") and is_facultative:
            is_blocked = True
            
        return {
            "date": current_date,
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "is_blocked": is_blocked,
            "name": self.br_holidays.get(current_date, "Dia Comum"),
            "weekday": current_date.weekday()
        }

# =============================================================================
# 4. MOTOR DE OTIMIZAÇÃO (OR-TOOLS)
# =============================================================================
class ScheduleEngine:
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr
        self.cal_config = cal_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 5.0
        
        self.task_vars: Dict[str, cp_model.IntVar] = {}
        self.tasks: Dict[str, Task] = {}

    def add_tasks(self, tasks: List[Task]):
        for t in tasks:
            self.tasks[t.id] = t
            self.task_vars[t.id] = self.model.NewIntVar(0, self.cal_mgr.total_days - 1, f"task_{t.id}")

    def apply_global_blocks(self, manual_exclusions: List[datetime.date]):
        excluded_indices = set([self.cal_mgr.date_to_idx(d) for d in manual_exclusions])
        for idx in range(self.cal_mgr.total_days):
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or idx in excluded_indices:
                for var in self.task_vars.values():
                    self.model.Add(var != idx)

    def apply_restrictions(self, restrictions: List[Restriction]):
        for r in restrictions:
            if r.type == "deadline":
                t_id = r.params["task_id"]
                if t_id not in self.task_vars: continue
                if r.params.get("before"):
                    idx = self.cal_mgr.date_to_idx(r.params["before"])
                    self.model.Add(self.task_vars[t_id] < idx)
                if r.params.get("after"):
                    idx = self.cal_mgr.date_to_idx(r.params["after"])
                    self.model.Add(self.task_vars[t_id] > idx)
                    
            elif r.type == "dependency":
                t_a = r.params["task_a"]
                t_b = r.params["task_b"]
                if t_a not in self.task_vars or t_b not in self.task_vars: continue
                min_gap = r.params.get("min_gap", 0)
                self.model.Add(self.task_vars[t_b] >= self.task_vars[t_a] + min_gap)

    def build_objectives(self):
        penalties = []
        for t_id, var in self.task_vars.items():
            for idx in range(self.cal_mgr.total_days):
                props = self.cal_mgr.get_day_properties(idx, self.cal_config)
                if props["is_weekend"] or props["is_holiday"]:
                    bool_var = self.model.NewBoolVar(f"pen_{t_id}_{idx}")
                    self.model.Add(var == idx).OnlyEnforceIf(bool_var)
                    self.model.Add(var != idx).OnlyEnforceIf(bool_var.Not())
                    penalties.append(bool_var * 50)
        if penalties:
            self.model.Minimize(sum(penalties))

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]]]:
        status = self.solver.Solve(self.model)
        results = {}
        alternatives = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for t_id, var in self.task_vars.items():
                idx_sol = self.solver.Value(var)
                chosen_date = self.cal_mgr.idx_to_date(idx_sol)
                results[t_id] = chosen_date
                alternatives.append({
                    "task_id": t_id,
                    "score": 100 - int(self.solver.ObjectiveValue() if self.solver.HasObjective() else 0),
                    "justification": "Respeita as restrições rígidas e evita janelas críticas bloqueadas."
                })
            return "SUCCESS", results, alternatives
        return "INFEASIBLE", {}, []

# =============================================================================
# 5. USER INTERFACE (STREAMLIT)
# =============================================================================
def main():
    st.title("📅 Engine de Agendamento Inteligente e Otimização")
    st.caption("Sistema de Alta Resiliência para Alocação de Datas")
    st.hr()

    st.sidebar.header("⚙️ Configurações do Calendário")
    ano_corrente = st.sidebar.number_input("Ano de Análise", min_value=2024, max_value=2030, value=2026)
    estado_br = st.sidebar.selectbox("Feriados Estaduais (UF)", ["DF", "SP", "RJ", "MG", "BA", "RS"])
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Finais de Semana", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Nacionais", value=True),
        "block_facultative": st.sidebar.checkbox("Bloquear Pontos Facultativos", value=False)
    }

    cal_mgr = CalendarManager(year=ano_corrente, state=estado_br)

    st.sidebar.subheader("🚫 Indisponibilidades Manuais")
    manual_dates = st.sidebar.date_input("Selecione datas para bloquear", value=[])
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    tab_compromissos, tab_visualizacao = st.tabs(["📋 Compromissos & Restrições", "📊 Painel de Soluções"])

    with tab_compromissos:
        col_tasks, col_rest = st.columns([1, 1])
        with col_tasks:
            st.subheader("1. Escopo de Compromissos")
            if "tasks" not in st.session_state:
                st.session_state.tasks = [
                    Task(id="T1", name="Reunião de Alinhamento Estratégico"),
                    Task(id="T2", name="Entrega do Relatório de Auditoria CILAES")
                ]
                
            with st.expander("➕ Adicionar Novo Compromisso"):
                new_id = st.text_input("Código Único", value=f"T{len(st.session_state.tasks)+1}")
                new_name = st.text_input("Nome do Compromisso")
                if st.button("Inserir na Agenda"):
                    if not any(t.id == new_id for t in st.session_state.tasks) and new_name:
                        st.session_state.tasks.append(Task(id=new_id, name=new_name))
                        st.rerun()

            df_tasks = pd.DataFrame([{"ID": t.id, "Compromisso": t.name} for t in st.session_state.tasks])
            st.dataframe(df_tasks, use_container_width=True)

        with col_rest:
            st.subheader("2. Regras e Restrições")
            if "restrictions" not in st.session_state:
                st.session_state.restrictions = [
                    Restriction(type="deadline", params={"task_id": "T1", "after": datetime.date(ano_corrente, 3, 1)}),
                    Restriction(type="dependency", params={"task_a": "T1", "task_b": "T2", "min_gap": 5})
                ]

            with st.expander("➕ Adicionar Regra Dinâmica"):
                rest_type = st.selectbox("Tipo de Restrição", ["Prazo Limite (Deadline)", "Dependência entre Atividades"])
                if rest_type == "Prazo Limite (Deadline)":
                    t_id = st.selectbox("Compromisso Alvo", [t.id for t in st.session_state.tasks])
                    choice = st.radio("Critério", ["Deve ocorrer após", "Deve ocorrer antes"])
                    d_val = st.date_input("Data de Referência", datetime.date(ano_corrente, 3, 15))
                    if st.button("Adicionar Restrição"):
                        param_key = "after" if choice == "Deve ocorrer após" else "before"
                        st.session_state.restrictions.append(Restriction(type="deadline", params={"task_id": t_id, param_key: d_val}))
                        st.rerun()
                elif rest_type == "Dependência entre Atividades":
                    t_a = st.selectbox("Antecessor (A)", [t.id for t in st.session_state.tasks])
                    t_b = st.selectbox("Sucessor (B)", [t.id for t in st.session_state.tasks])
                    min_g = st.number_input("Intervalo Mínimo (Dias)", min_value=0, value=5)
                    if st.button("Adicionar Dependência"):
                        if t_a != t_b:
                            st.session_state.restrictions.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                            st.rerun()

            for idx, r in enumerate(st.session_state.restrictions):
                st.text(f"Regra {idx+1}: {r.type.upper()} -> {r.params}")

    with tab_visualizacao:
        engine = ScheduleEngine(cal_mgr, cal_config)
        engine.add_tasks(st.session_state.tasks)
        engine.apply_global_blocks(manual_dates)
        engine.apply_restrictions(st.session_state.restrictions)
        engine.build_objectives()
        status, sol_dates, alt_cards = engine.solve()

        if status == "SUCCESS":
            st.success("🎉 Solução otimizada encontrada com sucesso!")
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                t_obj = next(t for t in st.session_state.tasks if t.id == t_id)
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>📌 {t_obj.name} ({t_id})</h4>
                        <h2>{date_val.strftime('%d/%m/%Y')}</h2>
                        <p style="color:#6c757d; font-size:13px;"><b>Score:</b> {alt_cards[i]['score']}/100<br>
                        <b>Justificativa:</b> {alt_cards[i]['justification']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            gantt_data = [{"Compromisso": next(t.name for t in st.session_state.tasks if t.id == t_id), "Início": d_val, "Fim": d_val + datetime.timedelta(days=1), "Código": t_id} for t_id, d_val in sol_dates.items()]
            df_gantt = pd.DataFrame(gantt_data)
            fig_timeline = px.timeline(df_gantt, x_start="Início", x_end="Fim", y="Compromisso", color="Código", title="Cronograma Otimizado (Linha do Tempo)")
            fig_timeline.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_timeline, use_container_width=True)
        else:
            st.error("❌ Conflito de Restrições. Modifique os prazos ou dependências para recalcular.")

if __name__ == "__main__":
    main()
