import datetime
import calendar
import copy
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Calendário Inteligente PRO v6.0",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main-title { font-size: 2.3rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.2rem; }
    .subtitle { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .metric-card { background-color: #FFFFFF; border-left: 5px solid #2563EB; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .onboarding-box { background-color: #F0FDF4; border: 2px solid #22C55E; padding: 20px; border-radius: 10px; margin-bottom: 25px; }
    .alert-box { background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 4px; margin-top:10px; }
    .calendar-grid { display: block; margin-bottom: 20px; }
    .calendar-row { display: table; width: 100%; table-layout: fixed; }
    .calendar-cell { display: table-cell; text-align: center; padding: 6px 2px; font-size: 11px; border: 1px solid #E5E7EB; font-weight: 600; }
    .day-normal { background-color: #F9FAFB; color: #1F2937; }
    .day-allocated { background-color: #DBEAFE; color: #1E40AF; border: 2px solid #2563EB !important; }
    .day-holiday { background-color: #FEE2E2; color: #991B1B; }
    .day-blocked { background-color: #E5E7EB; color: #6B7280; }
    .day-header { background-color: #F3F4F6; color: #374151; font-weight: bold; }
    .history-log { font-size: 12px; color: #6B7280; font-family: monospace; }
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
# 3. MOTOR DE FERIADOS (CACHED PARA PERFORMANCE)
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
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL (AVANÇADO)
# =============================================================================
class CalendarManager:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, str] = None):
        self.year = year
        self.br_holidays = BrazilHolidaysPure(year=self.year, custom_holidays=custom_holidays)
        self.start_date = datetime.date(year, 1, 1)
        self.end_date = datetime.date(year, 12, 31)
        self.total_days = (self.end_date - self.start_date).days + 1
        
    def date_to_idx(self, d: datetime.date) -> int:
        if d < self.start_date: return 0
        if d > self.end_date: return self.total_days - 1
        return (d - self.start_date).days
        
    def idx_to_date(self, idx: int) -> datetime.date:
        return self.start_date + datetime.timedelta(days=max(0, idx))
        
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

    def get_next_working_day(self, start_date: datetime.date, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> datetime.date:
        idx = self.date_to_idx(start_date)
        while idx < self.total_days:
            idx += 1
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions:
                return props["date"]
        return self.end_date

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
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA COM DIAGNÓSTICO INTELIGENTE
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
            if r.type == "fixed_date":
                t_id = r.params["task_id"]
                if t_id in alocacao:
                    if alocacao[t_id] != self.cal_mgr.date_to_idx(r.params["date"]):
                        return False

            elif r.type == "deadline":
                t_id = r.params["task_id"]
                if t_id in alocacao:
                    idx_atual = alocacao[t_id]
                    if r.params.get("before"):
                        if idx_atual >= self.cal_mgr.date_to_idx(r.params["before"]): return False
                    if r.params.get("after"):
                        if idx_atual <= self.cal_mgr.date_to_idx(r.params["after"]): return False
                        
            elif r.type == "dependency":
                t_a = r.params["task_a"]
                t_b = r.params["task_b"]
                if t_a in alocacao and t_b in alocacao:
                    if alocacao[t_b] < alocacao[t_a] + r.params.get("min_gap", 0):
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
        return sum(50 for idx in alocacao.values() if self.cal_mgr.get_day_properties(idx, self.cal_config)["is_weekend"] or self.cal_mgr.get_day_properties(idx, self.cal_config)["is_holiday"])

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]], str]:
        solucao_otima = {}
        melhor_custo = float('inf')
        task_ids = [t.id for t in self.tasks]
        
        if not task_ids:
            return "SUCCESS", {}, [], ""

        horizonte_busca = min(200, self.cal_mgr.total_days)

        def backtrack(task_index: int, alocacao_atual: Dict[str, int]):
            nonlocal solucao_otima, melhor_custo
            
            if not self._validar_parcial(alocacao_atual): return
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
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Data alocada respeitando todos os intervalos e dias úteis exigidos. (Score de Segurança: {max(0, 100 - melhor_custo)}%)"} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
            
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        """Tenta achar exatamente qual restrição quebrou a lógica."""
        if len(self.restrictions) == 0:
            return "Há tarefas com Datas Fixas que caem em dias bloqueados (Feriado/Fim de semana)."
        
        original_restrictions = self.restrictions.copy()
        for i in range(len(original_restrictions)):
            temp_rest = original_restrictions[i]
            self.restrictions = original_restrictions[:i] + original_restrictions[i+1:]
            
            # Testa novamente sem esta restrição
            solucao_otima = {}
            task_ids = [t.id for t in self.tasks]
            def backtrack_diag(task_index: int, alocacao_atual: Dict[str, int]):
                nonlocal solucao_otima
                if solucao_otima: return
                if not self._validar_parcial(alocacao_atual): return
                if task_index == len(task_ids):
                    solucao_otima = alocacao_atual.copy()
                    return
                t_id = task_ids[task_index]
                for idx in range(min(150, self.cal_mgr.total_days)):
                    alocacao_atual[t_id] = idx
                    backtrack_diag(task_index + 1, alocacao_atual)
                    del alocacao_atual[t_id]
            backtrack_diag(0, {})
            
            if solucao_otima:
                # Se achou solução sem essa restrição, ela é a culpada.
                self.restrictions = original_restrictions
                tipo = temp_rest.type
                alvo = temp_rest.params.get("task_id") or temp_rest.params.get("task_target")
                if tipo == "deadline": return f"A regra de Data Limite (Deadline) aplicada à Tarefa {alvo} é muito apertada e conflita com os prazos e bloqueios vigentes."
                if tipo == "working_day_offset": return f"O Deslocamento de Dias Úteis exigido para chegar à Tarefa {alvo} colide com os limites de tempo."
                return f"Conflito logístico gerado na regra: {tipo} referente à tarefa {alvo}."
        
        self.restrictions = original_restrictions
        return "Conflito sistêmico. O volume de bloqueios manuais, feriados ou regras encadeadas é maior que os dias úteis disponíveis no período."

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO & ONBOARDING MASTER
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Calendário Inteligente PRO v6.0</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Planejamento Reativo, Diagnóstico Inteligente e Tabela Bidirecional Integrada</div>', unsafe_allow_html=True)
    
    hoje = datetime.date.today() # Utilizado para contexto atual (ex: Julho 2026)

    # -------------------------------------------------------------------------
    # UX: SISTEMA DE ONBOARDING (ASSISTENTE GUIADO)
    # -------------------------------------------------------------------------
    if "onboarding_concluido" not in st.session_state:
        st.session_state.onboarding_concluido = False

    if not st.session_state.onboarding_concluido:
        st.markdown("""
        <div class="onboarding-box">
            <h2 style="margin-top: 0; color: #166534;">👋 Olá! Bem-vindo ao Assistente Guiado.</h2>
            <p style="font-size: 16px; color: #15803D;">Este sistema vai acabar com a contagem manual de dias úteis e prazos. Ele faz a matemática por você!</p>
            <hr style="border-color: #86EFAC;">
            <h4>Como utilizar o sistema perfeitamente:</h4>
            <ol style="font-size: 15px; color: #166534;">
                <li><b>Escolha a Data Base (Menu Esquerdo):</b> Defina a partir de que dia o cronograma começa a contar (pode ser Hoje ou uma data customizada).</li>
                <li><b>Use a Planilha Inteligente (Aba 1):</b> Digite as suas tarefas ali dentro. A planilha é interativa! Se precisar, você pode dar Ctrl+C e Ctrl+V do Excel direto para ela.</li>
                <li><b>Crie Vínculos Matemáticos:</b> Na coluna "Tipo de Regra", avise se a tarefa precisa pular dias úteis a partir da Data Base, ou a partir de outra Tarefa.</li>
                <li><b>Visualize e Exporte (Aba 2):</b> O sistema calcula tudo em tempo real enquanto você digita. A Aba 2 já terá o cronograma pronto para download.</li>
            </ol>
            <p>Precisa de mais detalhes? Explore a <b>Aba 4 (Manual Completo)</b>. Lá temos FAQs e Glossários!</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 Entendi o funcionamento! Iniciar Aplicação", type="primary"):
            st.session_state.onboarding_concluido = True
            st.rerun()
        st.divider()

    # -------------------------------------------------------------------------
    # GESTÃO DE ESTADO E HISTÓRICO DE ALTERAÇÕES (UNDO)
    # -------------------------------------------------------------------------
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []

    if "df_planilha" not in st.session_state:
        # Default Context - Initialized naturally
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Início das Atividades (CILAES)", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base (Opcional)": "", "Valor / Dias": 0, "Data Fixa (Opcional)": None},
            {"Código ID": "T2", "Nome da Tarefa": "Entrega de Dashboard", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base (Opcional)": "T1", "Valor / Dias": 15, "Data Fixa (Opcional)": None},
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            # Mantém apenas as últimas 5 ações para não onerar a memória
            st.session_state.historico_planilha.append(st.session_state.df_planilha.copy())
            if len(st.session_state.historico_planilha) > 5:
                st.session_state.historico_planilha.pop(0)

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES & DATA BASE)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ Configurações e Parâmetros")
    
    # FUNCIONALIDADE 1: Data Base Totalmente Configurável
    st.sidebar.subheader("📍 Data Base do Projeto")
    st.sidebar.info("A Data Base é o 'Dia Zero' para os seus cálculos.")
    base_opcao = st.sidebar.selectbox("Ponto de Partida:", ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], help="Determina a data principal que as regras da tabela usarão de referência.")
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)":
        data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil":
        data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else:
        data_base_global = st.sidebar.date_input("Selecione a Data Base", value=hoje)

    st.sidebar.markdown(f"**Data Base Ativa:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    ano_corrente = st.sidebar.number_input("Ano do Exercício", min_value=2024, max_value=2030, value=data_base_global.year)
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True, help="Impede alocações em finais de semana."),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados", value=True, help="Impede alocações em dias de feriado Nacional e Estadual.")
    }

    with st.sidebar.expander("🏛️ Cadastrar Feriado Regional"):
        f_name = st.text_input("Nome", placeholder="Ex: Feriado Distrital")
        f_date = st.date_input("Data", datetime.date(ano_corrente, 11, 30))
        if st.button("Injetar Feriado"):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Indisponibilidades Manuais (Férias)", value=[], help="Dias de bloqueio forçado.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO
    # -------------------------------------------------------------------------
    tab_planilha, tab_visualizacao, tab_calendario_visual, tab_manual = st.tabs([
        "📋 1. Edição de Planilha", 
        "📊 2. Resultados & Análises", 
        "📅 3. Calendário Anual",
        "📘 4. Manual da Aplicação"
    ])

    with tab_planilha:
        st.subheader("📝 Planilha Inteligente Interativa")
        st.markdown("Aqui você digita e estrutura todo o projeto. A tabela abaixo é **reativa**: edite as células diretamente. O cálculo é feito instantaneamente em segundo plano.")
        
        # Histórico e Ações de Tabela
        col_hist1, col_hist2 = st.columns([1, 4])
        with col_hist1:
            if st.button("↩️ Desfazer Alteração", disabled=len(st.session_state.historico_planilha)==0, help="Restaura a planilha ao estado anterior."):
                st.session_state.df_planilha = st.session_state.historico_planilha.pop()
                st.rerun()
        
        # DATA EDITOR AVANÇADO (FUNCIONALIDADE 2: INTERAÇÃO TOTAL)
        df_edited = st.data_editor(
            st.session_state.df_planilha,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código ID (Ex: T1)", required=True),
                "Nome da Tarefa": st.column_config.TextColumn("Nome da Tarefa", width="large"),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Regras de Otimização",
                    options=[
                        "Livre", 
                        "Data Fixada",
                        "1º Dia Útil após Data Base", 
                        "Dias Úteis após Tarefa Base", 
                        "Dias Úteis após Data Base",
                        "Data Limite (Antes de)", 
                        "Data Limite (Após de)"
                    ],
                    required=True
                ),
                "Tarefa Base (Opcional)": st.column_config.TextColumn("Código Base"),
                "Valor / Dias": st.column_config.NumberColumn("Valor Numérico (Dias)", min_value=0),
                "Data Fixa (Opcional)": st.column_config.DateColumn("Fixo (Opcional)", format="DD/MM/YYYY")
            },
            help="Tabela bidirecional: Você pode colar dados do Excel, adicionar linhas no '+' inferior, ou clicar nos cabeçalhos para ordenar."
        )
        
        salvar_historico(df_edited)
        st.session_state.df_planilha = df_edited

        with st.expander("🛠️ Ferramentas Clássicas (Botões)"):
            st.caption("Se preferir, crie regras suplementares fora da tabela usando formulários.")
            rest_type = st.selectbox("Modelo de Regra:", ["Data Limite (Deadline)", "Dependência Sequencial Simples"])
            if rest_type == "Data Limite (Deadline)":
                t_id_f = st.selectbox("Qual Tarefa?", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])])
                d_val = st.date_input("Escolha a data", datetime.date(ano_corrente, 6, 1))
                if st.button("Vincular Prazo"):
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, "before": d_val}))
                    st.rerun()

            if st.session_state.restrictions_manuais:
                for idx, r in enumerate(st.session_state.restrictions_manuais):
                    st.caption(f"• Regra {idx+1}: {r.type.upper()} -> {r.params}")
                if st.button("Limpar Manuais"):
                    st.session_state.restrictions_manuais = []
                    st.rerun()

    # COMPILAÇÃO DAS REGRAS PARA O MOTOR (FUNCIONALIDADE 3: USO DA DATA BASE)
    engine_tasks = []
    engine_restrictions = list(st.session_state.restrictions_manuais)

    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Nome da Tarefa", "Tarefa Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]): continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        
        v_tipo = row.get("Tipo de Regra", "Livre")
        v_base = str(row.get("Tarefa Base (Opcional)", "")).strip()
        v_val = int(row.get("Valor / Dias", 0)) if pd.notna(row.get("Valor / Dias")) else 0
        v_fixa = row.get("Data Fixa (Opcional)")
        
        # Converte as regras da planilha para restrições operacionais
        if v_tipo == "Data Fixada" and pd.notna(v_fixa):
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": v_fixa}))
        elif v_tipo == "1º Dia Útil após Data Base":
            primeiro_util = cal_mgr.get_next_working_day(data_base_global - datetime.timedelta(days=1), cal_config, manual_dates)
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": primeiro_util}))
        elif v_tipo == "Dias Úteis após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Dias Úteis após Data Base":
            # Força o sistema a tratar a data base como uma âncora invisível
            alvo_data = data_base_global
            dias_uteis_pulados = 0
            while dias_uteis_pulados < v_val:
                alvo_data += datetime.timedelta(days=1)
                p = cal_mgr.get_day_properties(cal_mgr.date_to_idx(alvo_data), cal_config)
                if not p["is_blocked"] and alvo_data not in manual_dates:
                    dias_uteis_pulados += 1
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": alvo_data}))
        elif v_tipo == "Data Limite (Antes de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": data_base_global + datetime.timedelta(days=v_val)}))

    # EXECUÇÃO DO MOTOR TRADICIONAL (FUNCIONALIDADE 4: RECALCULAR AUTOMÁTICO)
    # A reatividade natural do Streamlit roda este bloco a cada dígito inserido na planilha
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with tab_visualizacao:
        if status == "SUCCESS":
            st.success("✅ **Cálculo Efetuado:** As datas abaixo respeitam fielmente os bloqueios e os dias úteis definidos.")
            
            # Recomendações Automáticas
            if len(engine_tasks) > 5:
                st.info("💡 **Sugestão Inteligente:** Como você possui mais de 5 tarefas encadeadas, recomendamos revisar a Aba 3 para verificar se os meses futuros estão excessivamente preenchidos.")
            
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
                            <span style="color:#2563EB; font-weight:bold; font-size:11px;">{t_id} | CONFIANÇA: {card['score']}%</span>
                            <h4 style="margin:2px 0;">{t_obj.name}</h4>
                            <h2 style="color:#1E3A8A; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:11.5px; color:#4B5563; margin:4px 0;"><b>Feedback do Motor:</b> {card['justification']}</p>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📊 Tabela Consolidada para Exportação")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    cronograma_data.append({
                        "Código": t_id,
                        "Nome da Tarefa": t_item.name,
                        "Data Oficial Alocada": d_val.strftime('%d/%m/%Y'),
                        "Dia da Semana": ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][d_val.weekday()]
                    })
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Baixar Cronograma de Datas (.CSV)", data=csv_buffer, file_name=f"Cronograma_{ano_corrente}.csv", mime="text/csv", use_container_width=True)
        else:
            # FUNCIONALIDADE 7: Validações Inteligentes (Didáticas)
            st.error("⚠️ **Ops! Encontramos um Conflito Logístico.** O sistema não conseguiu encontrar datas que satisfaçam todas as regras.")
            st.markdown(f"""
            <div class="alert-box">
                <b>🔬 Diagnóstico do Motor:</b><br>
                {diagnostico}
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            **O que você pode fazer para resolver (Alternativas):**
            * 🔄 **Revisar a Tabela:** Verifique se uma Tarefa que deve ocorrer DEPOIS de outra tem um prazo limite curto demais.
            * 📅 **Relaxar Bloqueios:** Se você marcou muitos dias de férias (Indisponibilidade Manual), pode faltar dia útil no mês.
            * ↩️ **Usar o Histórico:** Vá na Aba 1 e clique em *Desfazer Alteração* para voltar ao estado anterior sem erro.
            """)

    with tab_calendario_visual:
        st.subheader("📅 Seu Ano Inteiro Desenhado")
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia Livre</div>
            <div><span style="background-color: #DBEAFE; padding: 2px 10px; border: 1px solid #2563EB;"></span> <b>Agendado</b></div>
            <div><span style="background-color: #FEE2E2; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado</div>
            <div><span style="background-color: #E5E7EB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Bloqueado</div>
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
                        for sem in ["D", "S", "T", "Q", "Q", "S", "S"]: html_cal += f'<div class="calendar-cell day-header">{sem}</div>'
                        html_cal += '</div>'
                        
                        cal_obj = calendar.Calendar(firstweekday=6)
                        weeks = cal_obj.monthdayscalendar(ano_corrente, m_idx)
                        
                        for week in weeks:
                            html_cal += '<div class="calendar-row">'
                            for day in week:
                                if day == 0: html_cal += '<div class="calendar-cell day-blocked"></div>'
                                else:
                                    d_verif = datetime.date(ano_corrente, m_idx, day)
                                    idx_verif = cal_mgr.date_to_idx(d_verif)
                                    props = cal_mgr.get_day_properties(idx_verif, cal_config)
                                    cell_class = "day-normal"
                                    title_hover = props["name"]
                                    
                                    if d_verif == data_base_global:
                                        title_hover = "DATA BASE DE CÁLCULO"
                                        cell_class = "day-allocated" # Destaque visual
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        title_hover = f"Tarefa(s): {', '.join([t for t, dt in sol_dates.items() if dt == d_verif])}"
                                    elif props["is_holiday"]: cell_class = "day-holiday"
                                    elif props["is_blocked"] or d_verif in manual_dates: cell_class = "day-blocked"
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{day}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    # -------------------------------------------------------------------------
    # UX: ABA MANUAL (DOCUMENTAÇÃO ENTERPRISE EMBUTIDA - ATUALIZADA V6.0)
    # -------------------------------------------------------------------------
    with tab_manual:
        st.header("📘 Manual da Aplicação: A Enciclopédia do Sistema")
        st.info("Este manual é dinâmico e reflete todas as funções atualizadas da Versão 6.0.")

        with st.expander("🌟 1. Introdução e Objetivo"):
            st.markdown("""
            **O que é?** O Calendário Inteligente PRO é um sistema projetado para automatizar fluxos logísticos e administrativos, livrando você do esforço de contar prazos no calendário.
            
            **Principais Benefícios:**
            * Elimina o erro humano no salto de finais de semana e feriados.
            * Diagnóstico Ativo: Se você pedir algo matematicamente impossível, o sistema analisa as restrições e avisa exatamente qual regra está quebrando o calendário.
            * Histórico Seguro: Cometeu um erro na planilha? Use o botão 'Desfazer'.
            """)

        with st.expander("🖥️ 2. Conhecendo a Interface (O que faz cada botão)"):
            st.markdown("""
            * **Data Base do Projeto (Sidebar):** É o Ponto Zero. Você diz ao sistema onde a matemática começa. Se alterar para 'Próximo dia Útil', todas as tarefas vinculadas à Data Base vão mudar sozinhas!
            * **Planilha Inteligente (Aba 1):** Clicou, digitou. É como o Excel. Você pode inserir linhas novas no `+` lá embaixo. A coluna "Data Fixa" serve para forçar um dia (o motor construirá as dependências ao redor desta data).
            * **Botão 'Desfazer Alteração':** Restaura a tabela ao estado anterior caso tenha deletado uma linha sem querer.
            """)

        with st.expander("🛠️ 3. Tutorial Completo de Fluxo (Passo a Passo)"):
            st.markdown("""
            **Siga o Fluxo de Ouro:**
            1. **Configure o Sistema (Lateral Esquerda):** Defina a Data Base e o Ano.
            2. **Aba 1 - Estruture as Tarefas:** Comece preenchendo a Planilha. Crie o Código (T1), Nome e o *Tipo de Regra*.
            3. **Para ancorar na Data Base:** Escolha a regra `"1º Dia Útil após Data Base"`.
            4. **Para ancorar em outra Tarefa:** Na linha do `T2`, escolha a regra `"Dias Úteis após Tarefa Base"`. Em seguida, na coluna "Tarefa Base", digite `T1` e no "Valor", digite `5`. (Isto significa que T2 ocorrerá 5 dias úteis depois de T1).
            5. **O Motor Trabalha (Transparente):** Você não precisa apertar 'Calcular'. A cada letra que digita, o motor já gera o cronograma!
            6. **Vá para a Aba 2:** Veja os resultados, o diagnóstico e baixe o seu Excel!
            """)

        with st.expander("❓ 4. Perguntas Frequentes (FAQ) & Erros Comuns"):
            st.markdown("""
            * **Por que a Aba 2 ficou vermelha e não me deu o arquivo?** *Ocorreu um "Conflito Matemático". O sistema acusará na caixa Vermelha exatamente o motivo. Exemplo: A Tarefa T1 foi forçada para o dia 20/02, mas você também disse que ela tinha que ocorrer 15 dias úteis depois da Data Base (que era dia 15/02). É impossível. Você precisa corrigir a tabela!*
            
            * **Como ordeno a tabela?** *Basta clicar no cabeçalho das colunas (Ex: Clique no cabeçalho "Código ID" para ordenar de A-Z).*
            
            * **Como excluo uma linha?** *Passe o mouse do lado esquerdo da linha na planilha, clique no quadradinho que vai aparecer, e pressione a tecla 'Delete' no seu teclado.*
            """)

        with st.expander("📚 5. Glossário Atualizado (V6.0)"):
            st.markdown("""
            * **Data Base:** O Dia-Zero. Todas as tarefas relativas usam esta data para iniciar a contagem.
            * **Offset:** Deslocamento. Pular dias úteis (Ex: Offset de 10 significa pular 10 dias úteis para a frente).
            * **Diagnóstico Inteligente (Stress Test):** Quando o sistema quebra uma regra, ele roda o algoritmo sozinho excluindo regra por regra para descobrir quem é o "culpado" pelo erro e avisar o usuário no painel de alertas.
            """)

if __name__ == "__main__":
    main()
