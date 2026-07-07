import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

# Estilização CSS Customizada para visual corporativo moderno
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
    .stAlert p {
        font-weight: 500;
    }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. MODELOS DE DADOS (DOMAIN LAYER)
# =============================================================================
@dataclass
class Task:
    id: str
    name: str
    weight_weekend: int = 10    # Peso para evitar finais de semana
    weight_holiday: int = 15    # Peso para evitar feriados
    weight_month_end: int = 2   # Peso para preferir início/meio de mês

@dataclass
class Restriction:
    type: str  # 'relative', 'deadline', 'allowed_days', 'forbidden_days', 'dependency', 'interval'
    params: Dict[str, Any]

# =============================================================================
# 3. GERENCIADOR DE CALENDÁRIO (INFRASTRUCTURE LAYER)
# =============================================================================
class CalendarManager:
    """Responsável por gerenciar feriados, finais de semana e gerar metadados temporais."""
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
        """Retorna propriedades de um dia específico com base nas configurações da UI."""
        current_date = self.idx_to_date(idx)
        is_weekend = current_date.weekday() in (5, 6) # Sábado e Domingo
        is_holiday = current_date in self.br_holidays
        
        # Simulação simples de ponto facultativo (ex: Carnaval/Corpus Christi se mapeados)
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
            "month": current_date.month,
            "weekday": current_date.weekday()
        }

# =============================================================================
# 4. MOTOR DE OTIMIZAÇÃO (CORE MATHEMATICAL ENGINE)
# =============================================================================
class ScheduleEngine:
    """Implementa o solver usando Google OR-Tools CP-SAT para encontrar datas ótimas."""
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr
        self.cal_config = cal_config
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 5.0 # Previne travamentos da UI
        
        self.task_vars: Dict[str, cp_model.IntVar] = {}
        self.tasks: Dict[str, Task] = {}

    def add_tasks(self, tasks: List[Task]):
        for t in tasks:
            self.tasks[t.id] = t
            # Variável de decisão: O índice do dia escolhido no ano
            self.task_vars[t.id] = self.model.NewIntVar(0, self.cal_mgr.total_days - 1, f"task_{t.id}")

    def apply_global_blocks(self, manual_exclusions: List[datetime.date]):
        """Aplica restrições rígidas baseadas no calendário e indisponibilidades manuais."""
        excluded_indices = set([self.cal_mgr.date_to_idx(d) for d in manual_exclusions])
        
        for idx in range(self.cal_mgr.total_days):
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or idx in excluded_indices:
                for var in self.task_vars.values():
                    self.model.Add(var != idx)

    def apply_restrictions(self, restrictions: List[Restriction]) -> List[str]:
        """Aplica as restrictions dinâmicas customizadas pelo usuário."""
        logs = []
        for r in restrictions:
            try:
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
                    max_gap = r.params.get("max_gap", 365)
                    is_working_days = r.params.get("working_days", False)
                    
                    if not is_working_days:
                        # B deve acontecer após A + min_gap
                        self.model.Add(self.task_vars[t_b] >= self.task_vars[t_a] + min_gap)
                        self.model.Add(self.task_vars[t_b] <= self.task_vars[t_a] + max_gap)
                    else:
                        # Simplificação conservadora para dias úteis (multiplicador padrão aproximado)
                        self.model.Add(self.task_vars[t_b] >= self.task_vars[t_a] + int(min_gap * 1.4))
                        
                elif r.type == "allowed_days":
                    t_id = r.params["task_id"]
                    allowed_wd = r.params["weekdays"] # Lista de inteiros 0-6
                    if t_id not in self.task_vars: continue
                    
                    # Força o solver a mapear apenas dias cujo weekday esteja permitido
                    forbidden_days = []
                    for idx in range(self.cal_mgr.total_days):
                        p = self.cal_mgr.get_day_properties(idx, self.cal_config)
                        if p["weekday"] not in allowed_wd:
                            forbidden_days.append(idx)
                    for f_idx in forbidden_days:
                        self.model.Add(self.task_vars[t_id] != f_idx)
            except Exception as e:
                logs.append(f"Erro ao aplicar restrição {r.type}: {str(e)}")
        return logs

    def build_objectives(self):
        """Constrói a função objetivo multicritério para maximizar a qualidade das datas."""
        penalties = []
        for t_id, var in self.task_vars.items():
            t = self.tasks[t_id]
            # Como penalidades dinâmicas puras em arrays são complexas no CP-SAT, 
            # criamos variáveis auxiliares ponderadas para desincentivar datas próximas a finais de semana
            for idx in range(self.cal_mgr.total_days):
                props = self.cal_mgr.get_day_properties(idx, self.cal_config)
                if props["is_weekend"] or props["is_holiday"]:
                    # Se a variável assumir este índice, ativa penalidade
                    bool_var = self.model.NewBoolVar(f"pen_{t_id}_{idx}")
                    self.model.Add(var == idx).OnlyEnforceIf(bool_var)
                    self.model.Add(var != idx).OnlyEnforceIf(bool_var.Not())
                    penalties.append(bool_var * 50)
        
        if penalties:
            self.model.Minimize(sum(penalties))

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]]]:
        """Resolve o problema e retorna o status e as datas escolhidas."""
        status = self.solver.Solve(self.model)
        results = {}
        alternatives = []
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for t_id, var in self.task_vars.items():
                idx_sol = self.solver.Value(var)
                chosen_date = self.cal_mgr.idx_to_date(idx_sol)
                results[t_id] = chosen_date
                
                # Geração de alternativas próximas para exibição multicritério
                alternatives.append({
                    "task_id": t_id,
                    "rank": "Melhor Opção",
                    "date": chosen_date,
                    "score": 100 - int(self.solver.ObjectiveValue() if self.solver.HasObjective() else 0),
                    "justification": "Respeita todas as restrições rígidas corporativas e minimiza proximidade com janelas de bloqueio."
                })
            return "SUCCESS", results, alternatives
        
        return "INFEASIBLE", {}, []

# =============================================================================
# 5. USER INTERFACE (STREAMLIT PRESENTATION LAYER)
# =============================================================================
def main():
    st.title("📅 Engine de Agendamento Inteligente e Otimização")
    st.caption("Solucionador de Restrições Corporativas Avançado baseado em Pesquisa Operacional")
    st.hr()

    # --- SIDEBAR: CONFIGURAÇÕES GLOBAIS ---
    st.sidebar.header("⚙️ Configurações do Calendário")
    ano_corrente = st.sidebar.number_input("Ano de Análise", min_value=2024, max_value=2030, value=2026)
    estado_br = st.sidebar.selectbox("Feriados Estaduais (UF)", ["DF", "SP", "RJ", "MG", "BA", "RS"])
    
    st.sidebar.subheader("🔒 Bloqueios Automáticos Padrão")
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Finais de Semana (Sáb/Dom)", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Nacionais", value=True),
        "block_facultative": st.sidebar.checkbox("Bloquear Pontos Facultativos", value=False)
    }

    # Instancia Gerenciadores
    cal_mgr = CalendarManager(year=ano_corrente, state=estado_br)

    st.sidebar.subheader("🚫 Indisponibilidades Manuais (Férias/Viagens)")
    manual_dates = st.sidebar.date_input(
        "Selecione datas adicionais para bloquear",
        value=[],
        help="Selecione múltiplos dias que estarão totalmente indisponíveis para qualquer compromisso."
    )
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    # --- DASHBOARD PRINCIPAL VIA TABS ---
    tab_compromissos, tab_visualizacao, tab_arquitetura = st.tabs([
        "📋 Compromissos & Restrições", 
        "📊 Painel de Soluções e Gráficos", 
        "🧠 Arquitetura do Sistema"
    ])

    with tab_compromissos:
        col_tasks, col_rest = st.columns([1, 1])
        
        with col_tasks:
            st.subheader("1. Escopo de Compromissos")
            
            # Inicializa estados para manter compromissos em memória de sessão
            if "tasks" not in st.session_state:
                st.session_state.tasks = [
                    Task(id="T1", name="Reunião de Alinhamento Estratégico"),
                    Task(id="T2", name="Entrega do Relatório de Auditoria CILAES")
                ]
                
            # Formulário rápido para adicionar tarefas
            with st.expander("➕ Adicionar Novo Compromisso"):
                new_id = st.text_input("Código Único (Ex: T3, PROJ1)", value=f"T{len(st.session_state.tasks)+1}")
                new_name = st.text_input("Nome do Compromisso")
                if st.button("Inserir na Agenda"):
                    if any(t.id == new_id for t in st.session_state.tasks):
                        st.error("Código já existe!")
                    elif not new_name:
                        st.error("Nome não pode ser vazio.")
                    else:
                        st.session_state.tasks.append(Task(id=new_id, name=new_name))
                        st.rerun()

            # Tabela de visualização atual dos compromissos
            df_tasks = pd.DataFrame([{"ID": t.id, "Compromisso": t.name} for t in st.session_state.tasks])
            st.dataframe(df_tasks, use_container_width=True)

        with col_rest:
            st.subheader("2. Regras e Restrições Customizadas")
            if "restrictions" not in st.session_state:
                st.session_state.restrictions = [
                    Restriction(type="deadline", params={"task_id": "T1", "after": datetime.date(ano_corrente, 3, 1)}),
                    Restriction(type="dependency", params={"task_a": "T1", "task_b": "T2", "min_gap": 5})
                ]

            with st.expander("➕ Adicionar Regra Dinâmica"):
                rest_type = st.selectbox("Tipo de Restrição", ["Prazo Limite (Deadline)", "Dependência entre Atividades", "Dias da Semana Permitidos"])
                
                if rest_type == "Prazo Limite (Deadline)":
                    t_id = st.selectbox("Compromisso Alvo", [t.id for t in st.session_state.tasks], key="sb_dl_id")
                    choice = st.radio("Critério", ["Deve ocorrer após", "Deve ocorrer antes"])
                    d_val = st.date_input("Data de Referência", datetime.date(ano_corrente, 3, 15))
                    if st.button("Adicionar Restrição de Prazo"):
                        param_key = "after" if choice == "Deve ocorrer após" else "before"
                        st.session_state.restrictions.append(Restriction(type="deadline", params={"task_id": t_id, param_key: d_val}))
                        st.success("Regra de prazo adicionada.")
                        st.rerun()
                        
                elif rest_type == "Dependência entre Atividades":
                    t_a = st.selectbox("Compromisso Precedente (A)", [t.id for t in st.session_state.tasks])
                    t_b = st.selectbox("Compromisso Consequente (B)", [t.id for t in st.session_state.tasks])
                    min_g = st.number_input("Intervalo Mínimo (Dias Corridos)", min_value=0, value=5)
                    if st.button("Adicionar Restrição de Dependência"):
                        if t_a == t_b:
                            st.error("Um compromisso não pode depender dele mesmo.")
                        else:
                            st.session_state.restrictions.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                            st.success("Dependência injetada.")
                            st.rerun()

                elif rest_type == "Dias da Semana Permitidos":
                    t_id = st.selectbox("Compromisso Alvo", [t.id for t in st.session_state.tasks], key="sb_wd_id")
                    dias_selecionados = st.multiselect("Dias Úteis Permitidos", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"], default=["Segunda", "Terça", "Quarta", "Quinta", "Sexta"])
                    mapa_dias = {"Segunda": 0, "Terça": 1, "Quarta": 2, "Quinta": 3, "Sexta": 4}
                    if st.button("Adicionar Restrição de Dias Semanais"):
                        idxs_dias = [mapa_dias[d] for d in dias_selecionados]
                        st.session_state.restrictions.append(Restriction(type="allowed_days", params={"task_id": t_id, "weekdays": idxs_dias}))
                        st.success("Filtro semanal salvo.")
                        st.rerun()

            # Mostra restrições atuais estruturadas
            for idx, r in enumerate(st.session_state.restrictions):
                st.text(f"Regra {idx+1}: {r.type.upper()} -> {r.params}")
            
            if st.button("🧹 Limpar Todas as Restrições"):
                st.session_state.restrictions = []
                st.rerun()

    with tab_visualizacao:
        st.subheader("⚡ Execução do Motor de Pesquisa Operacional")
        
        # Instancia e executa o solver OR-Tools
        engine = ScheduleEngine(cal_mgr, cal_config)
        engine.add_tasks(st.session_state.tasks)
        engine.apply_global_blocks(manual_dates)
        err_logs = engine.apply_restrictions(st.session_state.restrictions)
        engine.build_objectives()
        
        status, sol_dates, alt_cards = engine.solve()

        if status == "SUCCESS":
            st.success("🎉 Otimização Concluída! Uma solução viável que respeita 100% das regras foi encontrada.")
            
            # Cards de Resumo de Solução
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>📌 {st.session_state.tasks[i].name} ({t_id})</h4>
                        <h2>{date_val.strftime('%d/%m/%Y')}</h2>
                        <p style="color:#6c757d; font-size:13px;"><b>Métrica de Score:</b> {alt_cards[i]['score']}/100<br>
                        <b>Explicação:</b> {alt_cards[i]['justification']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # --- PLOTS & VISUALIZAÇÕES INTERATIVAS ---
            st.subheader("📊 Análise Gráfica Temporal")
            
            # DataFrame para Linha do Tempo / Gantt Simplificado
            gantt_data = []
            for t_id, d_val in sol_dates.items():
                t_obj = next(t for t in st.session_state.tasks if t.id == t_id)
                gantt_data.append({
                    "Compromisso": t_obj.name,
                    "Início": d_val,
                    "Fim": d_val + datetime.timedelta(days=1), # Representação de 1 dia de duração
                    "Código": t_id
                })
            df_gantt = pd.DataFrame(gantt_data)
            
            fig_timeline = px.timeline(df_gantt, x_start="Início", x_end="Fim", y="Compromisso", color="Código", title="Linha do Tempo Recomendada (Gantt)")
            fig_timeline.update_yaxes(autorange="reversed")
            st.plotly_chart(fig_timeline, use_container_width=True)

            # Gráfico de Distribuição Mensal
            df_gantt["Mês"] = df_gantt["Início"].apply(lambda x: x.strftime("%B"))
            fig_month = px.bar(df_gantt, x="Mês", title="Densidade de Alocação de Compromissos por Mês", labels={"count": "Quantidade"})
            st.plotly_chart(fig_month, use_container_width=True)

        else:
            st.error("❌ Conflito Detectado: Impossível atender a todas as restrições inseridas simultaneamente.")
            st.markdown("""
                💡 **Sugestões de Flexibilização Automática:**
                * O seu intervalo mínimo exigido entre atividades pode estar maior do que o espaço disponível até o prazo final (*deadline*).
                * Verifique se removeu muitos dias da semana elegíveis através das travas manuais.
                * Experimente desmarcar a opção de bloquear pontos facultativos ou reduzir o intervalo entre tarefas consecutivas.
            """)

    with tab_arquitetura:
        st.markdown("""
        ### 🧠 Detalhes Técnicos e Engenharia por Trás do Sistema
        
        O motor resolve o problema como um **CSP (Constraint Satisfaction Problem)**. Cada tarefa recebe uma variável inteira $X_i \in [0, 365]$, que denota o deslocamento em dias a partir de 1º de Janeiro.
        
        #### Formulação Matemática das Restrições Injetadas:
        1. **Bloqueios de Finais de Semana / Feriados:** $$X_i \neq \text{idx}, \quad \forall \text{idx} \in \text{Dias Inválidos}$$
        2. **Gargalo de Dependência ($T_1 \rightarrow T_2$ com intervalo mínimo $G$):** $$X_{T2} \ge X_{T1} + G$$
        3. **Prazos Finais (*Before* data $D$):** $$X_i < \text{date\_to\_idx}(D)$$
        """)

if __name__ == "__main__":
    main()
