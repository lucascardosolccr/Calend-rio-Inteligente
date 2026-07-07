import datetime
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Scheduler Engine PRO v2",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS para cartões de métricas modernos e elementos de interface
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
    }
    .subtitle {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #FFFFFF;
        border-left: 5px solid #2563EB;
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
    }
    .manual-box {
        background-color: #EFF6FF;
        border: 1px solid #BFDBFE;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
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
# 3. MOTOR DE FERIADOS BRASIL/DF NATIVO (ALGORITMO DE GAUSS)
# =============================================================================
class BrazilHolidaysPure:
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
        
        return {
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

    def get(self, d: datetime.date, default: str = "") -> str:
        return self.holidays_dict.get(d, default)

# =============================================================================
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL
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
            
            for idx in range(min(120, self.cal_mgr.total_days)):
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
                    "justification": "Alocação regulamentar ideal estruturada sob regras estritas."
                })
            return "SUCCESS", results, alternatives
            
        return "INFEASIBLE", {}, []

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO (STREAMLIT UX DESIGN)
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Engine de Agendamento Otimizado</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Planejamento Estratégico Multitarefas Livre de Conflitos e Feriados</div>', unsafe_allow_html=True)
    
    # MANUAL DIDÁTICO
    with st.expander("📖 MANUAL DO USUÁRIO: Como dominar o sistema em 3 passos", expanded=False):
        st.markdown("""
        <div class="manual-box">
            <h4>💡 Conceito Base: O que este sistema faz?</h4>
            <p>Esta aplicação utiliza algoritmos de <b>Pesquisa Operacional</b> para calcular automaticamente as datas ideais para seus compromissos, garantindo que nenhum caia em fins de semana ou feriados regulamentares, respeitando ordens de precedência e prazos limite definidos por você.</p>
        </div>
        """, unsafe_allow_html=True)
        
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.markdown("##### **Passo 1: Definir Calendário**")
            st.write("Na barra lateral esquerda, configure o ano vigente e quais regras de bloqueio genéricas deseja aplicar (ex: pular fins de semana ou feriados civis).")
        with m_col2:
            st.markdown("##### **Passo 2: Inserir Escopo**")
            st.write("Na aba **'Escopo & Regras'**, cadastre seus compromissos com códigos exclusivos (ex: T1, T2) e amarre regras de prazo ou dependências de fluxo.")
        with m_col3:
            st.markdown("##### **Passo 3: Gerar e Exportar**")
            st.write("Abra o **'Painel Analítico'** para visualizar as datas resolvidas matematicamente, avaliar os cartões de conformidade e baixar a planilha formatada.")

    st.divider()

    # Barra Lateral
    st.sidebar.header("⚙️ Controle de Calendário")
    ano_corrente = st.sidebar.number_input("Ano do Exercício", min_value=2024, max_value=2030, value=2026)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Nacionais/DF", value=True),
        "block_facultative": st.sidebar.checkbox("Bloquear Pontos Facultativos", value=False)
    }

    cal_mgr = CalendarManager(year=ano_corrente)

    st.sidebar.subheader("🚫 Bloqueios Customizados")
    manual_dates = st.sidebar.date_input("Adicionar exceções manuais", value=[])
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    # Inicialização do estado de sessão
    if "tasks" not in st.session_state:
        st.session_state.tasks = [
            Task(id="T1", name="Reunião de Planejamento Inicial"),
            Task(id="T2", name="Análise de Dados e Dashboard CILAES")
        ]
    if "restrictions" not in st.session_state:
        st.session_state.restrictions = [
            Restriction(type="deadline", params={"task_id": "T1", "after": datetime.date(ano_corrente, 1, 15)}),
            Restriction(type="dependency", params={"task_a": "T1", "task_b": "T2", "min_gap": 3})
        ]

    tab_compromissos, tab_visualizacao = st.tabs(["📋 1. Configurar Escopo & Regras", "📊 2. Painel Analítico & Exportação"])

    with tab_compromissos:
        col_tasks, col_rest = st.columns([1, 1], gap="large")
        
        with col_tasks:
            st.subheader("📌 Cadastro de Atividades e Compromissos")
            
            # CORRIGIDO: de st.get_container() para st.container()
            with st.container():
                new_id = st.text_input("Código de Identificação (Único)", value=f"T{len(st.session_state.tasks)+1}")
                new_name = st.text_input("Nome Descritivo do Compromisso", placeholder="Ex: Homologação do Sistema")
                if st.button("✨ Adicionar Atividade à Matriz", use_container_width=True):
                    if new_name and not any(t.id == new_id for t in st.session_state.tasks):
                        st.session_state.tasks.append(Task(id=new_id, name=new_name))
                        st.toast(f"Compromisso {new_id} acoplado com sucesso!")
                        st.rerun()
            
            st.markdown("---")
            df_tasks = pd.DataFrame([{"ID": t.id, "Compromisso Cadastrado": t.name} for t in st.session_state.tasks])
            st.dataframe(df_tasks, use_container_width=True, hide_index=True)

        with col_rest:
            st.subheader("⛓️ Restrições de Fluxo Operacional")
            
            rest_type = st.selectbox("Selecione o Modelo de Regra", ["Prazo Limite (Deadline)", "Dependência Sequencial"])
            
            if rest_type == "Prazo Limite (Deadline)":
                t_id = st.selectbox("Escolha o Alvo", [t.id for t in st.session_state.tasks])
                choice = st.radio("Critério Cronológico", ["Deve ocorrer obrigatoriamente APÓS", "Deve ocorrer antes"])
                d_val = st.date_input("Data de Referência Regulamentar", datetime.date(ano_corrente, 1, 20))
                if st.button("Vincular Prazo Fixo", use_container_width=True):
                    param_key = "after" if "APÓS" in choice else "before"
                    st.session_state.restrictions.append(Restriction(type="deadline", params={"task_id": t_id, param_key: d_val}))
                    st.toast("Restrição de prazo injetada.")
                    st.rerun()
                    
            elif rest_type == "Dependência Sequencial":
                t_a = st.selectbox("Atividade Antecessora (A)", [t.id for t in st.session_state.tasks], key="dep_a")
                t_b = st.selectbox("Atividade Sucessora (B)", [t.id for t in st.session_state.tasks], key="dep_b")
                min_g = st.number_input("Intervalo de Segurança Mínimo (Dias)", min_value=0, value=2)
                if st.button("Vincular Cadeia Sequencial", use_container_width=True):
                    if t_a != t_b:
                        st.session_state.restrictions.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                        st.toast("Amarração sequencial estabelecida.")
                        st.rerun()
                    else:
                        st.error("Uma atividade não pode depender dela mesma.")

            st.markdown("---")
            st.markdown("**Regras Ativas na Engine:**")
            for idx, r in enumerate(st.session_state.restrictions):
                st.caption(f"• **Regra {idx+1}:** {r.type.upper()} ➔ {r.params}")

    with tab_visualizacao:
        st.subheader("🚀 Resolução e Otimização em Tempo Real")
        
        engine = PurePythonScheduleEngine(cal_mgr, cal_config)
        engine.add_tasks(st.session_state.tasks)
        engine.apply_global_blocks(manual_dates)
        engine.apply_restrictions(st.session_state.restrictions)
        
        status, sol_dates, alt_cards = engine.solve()

        if status == "SUCCESS":
            st.success("🎯 Solução matemática perfeita encontrada! Todas as restrições foram atendidas.")
            
            col_m1, col_m2 = st.columns(2)
            for i, (t_id, date_val) in enumerate(sol_dates.items()):
                target_col = col_m1 if i % 2 == 0 else col_m2
                t_obj = next(t for t in st.session_state.tasks if t.id == t_id)
                with target_col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <span style="color:#2563EB; font-weight:bold; font-size:12px;">CÓDIGO: {t_id}</span>
                        <h4 style="margin:5px 0;">📌 {t_obj.name}</h4>
                        <h2 style="color:#1E3A8A; margin:10px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                        <p style="color:#4B5563; font-size:12px; margin:0;">
                            <b>Índice de Segurança:</b> {alt_cards[i]['score']}/100<br>
                            <b>Status:</b> {alt_cards[i]['justification']}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("### 📊 Tabela Geral Consolidadora")
            cronograma_data = [
                {
                    "Código ID": t_id,
                    "Descrição do Compromisso": next(t.name for t in st.session_state.tasks if t.id == t_id),
                    "Data Determinada": d_val.strftime('%d/%m/%Y'),
                    "Dia da Semana": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][d_val.weekday()],
                    "Ano Fiscal": d_val.year
                } for t_id, d_val in sol_dates.items()
            ]
            df_final = pd.DataFrame(cronograma_data)
            st.dataframe(df_final, use_container_width=True, hide_index=True)
            
            csv_buffer = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Cronograma Otimizado (.CSV)",
                data=csv_buffer,
                file_name=f"cronograma_otimizado_{ano_corrente}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.error("❌ Conflito Estrutural de Regras. A Engine determinou que é logicamente impossível alocar os compromissos dadas as restrições de prazos inseridas. Revise as regras na aba 1.")

if __name__ == "__main__":
    main()
