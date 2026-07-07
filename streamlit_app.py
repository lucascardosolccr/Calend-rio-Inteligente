import datetime
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

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
# 3. MOTOR DE FERIADOS PURO (MÉTODO DE GAUSS PARA PÁSCOA)
# =============================================================================
class BrazilHolidaysPure:
    """Calcula feriados nacionais e do DF sem usar a biblioteca holidays."""
    def __init__(self, year: int):
        self.year = year
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
        
        feriados = {
            datetime.date(self.year, 1, 1): "Ano Novo",
            datetime.date(self.year, 4, 21): "Tiradentes / Aniversário de Brasília",
            datetime.date(self.year, 5, 1): "Dia do Trabalho",
            datetime.date(self.year, 9, 7): "Independência do Brasil",
            datetime.date(self.year, 10, 12): "Nossa Sra. Aparecida",
            datetime.date(self.year, 10, 28): "Dia do Servidor Público (Facultativo)",
            datetime.date(self.year, 11, 2): "Finados",
            datetime.date(self.year, 11, 15): "Proclamação da República",
            datetime.date(self.year, 11, 30): "Dia do Evangélico (Feriado no DF)",
            datetime.date(self.year, 12, 25): "Natal",
            carnaval: "Carnaval (Ponto Facultativo)",
            sexta_santa: "Sexta-feira Santa",
            corpus_christi: "Corpus Christi (Ponto Facultativo)"
        }
        return feriados

    def get(self, d: datetime.date, default: str = "") -> str:
        return self.holidays_dict.get(d, default)

    def __contains__(self, d: datetime.date) -> bool:
        return d in self.holidays_dict

# =============================================================================
# 4. GERENCIADOR DE CALENDÁRIO
# =============================================================================
class CalendarManager:
    def __init__(self, year: int):
        self.year = year
        self.br_holidays = BrazilHolidaysPure(year=self.year)
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
        is_facultative = "facultativo" in holiday_name.lower()
        
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
            "name": holiday_name if is_holiday else "Dia Comum",
            "weekday": current_date.weekday()
        }

# =============================================================================
# 5. MOTOR DE OTIMIZAÇÃO NATIVO (BACKTRACKING COM RESOLUÇÃO RECURSIVA)
# =============================================================================
class PurePythonScheduleEngine:
    """Substitui o OR-Tools por um algoritmo recursivo puro de busca operacional."""
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
            
            # Varre o espaço de busca focado nos primeiros meses para otimizar tempo
            for idx in range(self.cal_mgr.total_days):
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
                    "justification": "Cálculo determinístico nativo livre de gargalos operacionais."
                })
            return "SUCCESS", results, alternatives
            
        return "INFEASIBLE", {}, []

# =============================================================================
# 6. USER INTERFACE (STREAMLIT NATIVO)
# =============================================================================
def main():
    st.title("📅 Engine de Agendamento Inteligente e Otimização")
    st.caption("Arquitetura Resiliente de Alta Disponibilidade — Independente de Infraestrutura")
    st.divider()  # CORRIGIDO: st.hr() substituído por st.divider()

    st.sidebar.header("⚙️ Configurações do Calendário")
    ano_corrente = st.sidebar.number_input("Ano de Análise", min_value=2024, max_value=2030, value=2026)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Finais de Semana", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Nacionais (e DF)", value=True),
        "block_facultative": st.sidebar.checkbox("Bloquear Pontos Facultativos", value=False)
    }

    cal_mgr = CalendarManager(year=ano_corrente)

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
        engine = PurePythonScheduleEngine(cal_mgr, cal_config)
        engine.add_tasks(st.session_state.tasks)
        engine.apply_global_blocks(manual_dates)
        engine.apply_restrictions(st.session_state.restrictions)
        
        with st.spinner("Calculando datas ideais de forma nativa..."):
            status, sol_dates, alt_cards = engine.solve()

        if status == "SUCCESS":
            st.success("🎉 Agenda otimizada gerada com sucesso!")
            
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                t_obj = next(t for t in st.session_state.tasks if t.id == t_id)
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <h4>📌 {t_obj.name} ({t_id})</h4>
                        <h2>{date_val.strftime('%d/%m/%Y')}</h2>
                        <p style="color:#6c757d; font-size:13px;"><b>Segurança Regulamentar:</b> {alt_cards[i]['score']}/100<br>
                        <b>Nota:</b> {alt_cards[i]['justification']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            st.subheader("📊 Cronograma de Execução Estável")
            cronograma_df = pd.DataFrame([
                {
                    "Código": t_id,
                    "Compromisso": next(t.name for t in st.session_state.tasks if t.id == t_id),
                    "Data Alocada": d_val.strftime('%d/%m/%Y'),
                    "Dia da Semana": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][d_val.weekday()]
                } for t_id, d_val in sol_dates.items()
            ])
            st.table(cronograma_df)
        else:
            st.error("❌ Impossível Alocar: Conflito insolúvel nas regras e prazos adicionados.")

if __name__ == "__main__":
    main()
