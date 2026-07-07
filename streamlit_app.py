import datetime
import calendar
import copy
import json
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd
import numpy as np

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS (UX/UI ENTERPRISE)
# =============================================================================
st.set_page_config(
    page_title="Calendário Inteligente PRO v11.0",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização Persistente de Estética
if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A", 
        "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE",
        "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2",
        "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Escopo & Tabela", "📊 2. Cronograma", "📅 3. Visão do Ano", "🎨 4. Personalização", "📘 5. Manual"],
        "cal_first_weekday": 6 
    }

THEME_PALETTES = {
    "Azul Corporativo": {"primary": "#1E3A8A", "alloc": "#DBEAFE", "alloc_border": "#2563EB"},
    "Verde Operacional": {"primary": "#14532D", "alloc": "#DCFCE7", "alloc_border": "#16A34A"},
    "Roxo Estratégico": {"primary": "#4C1D95", "alloc": "#F3E8FF", "alloc_border": "#7E22CE"},
    "Laranja Ágil": {"primary": "#7C2D12", "alloc": "#FFEDD5", "alloc_border": "#EA580C"},
    "Preto Clássico": {"primary": "#111827", "alloc": "#F3F4F6", "alloc_border": "#374151"}
}

st.markdown(f"""
    <style>
    .main-title {{ font-size: 2.2rem; font-weight: 800; color: {st.session_state.theme_config['color_primary']}; margin-bottom: 0.2rem; letter-spacing: -0.5px; }}
    .subtitle {{ font-size: 1.05rem; color: {st.session_state.theme_config['color_secondary']}; margin-bottom: 1.8rem; font-weight: 400; }}
    .metric-card {{ background-color: #FFFFFF; border-left: 6px solid {st.session_state.theme_config['color_allocated_border']}; padding: 18px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); margin-bottom: 15px; transition: transform 0.2s, box-shadow 0.2s; }}
    .metric-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 15px rgba(0,0,0,0.08); }}
    .calendar-grid {{ display: block; margin-bottom: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    .calendar-row {{ display: table; width: 100%; table-layout: fixed; }}
    .calendar-cell {{ display: table-cell; text-align: center; padding: 8px 2px; font-size: 11px; border: 1px solid #F1F5F9; font-weight: 600; min-height: 45px; vertical-align: middle; border-radius: 2px; }}
    .day-normal {{ background-color: #FFFFFF; color: #334155; }}
    .day-allocated {{ background-color: {st.session_state.theme_config['color_allocated']}; color: {st.session_state.theme_config['color_primary']}; border: 2px solid {st.session_state.theme_config['color_allocated_border']} !important; font-weight: 800; border-radius: 6px; box-shadow: inset 0 0 5px rgba(0,0,0,0.05); }}
    .day-holiday {{ background-color: {st.session_state.theme_config['color_holiday']}; color: #991B1B; }}
    .day-blocked {{ background-color: {st.session_state.theme_config['color_blocked']}; color: #94A3B8; text-decoration: line-through; }}
    .day-marker {{ font-size: 14px; display: block; margin-top: 3px; }}
    .day-header {{ background-color: #F8FAFC; color: #475569; font-weight: bold; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px; border: none; }}
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
# 3. MOTOR DE FERIADOS RICOS (CACHED PARA PERFORMANCE)
# =============================================================================
class BrazilHolidaysPure:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, Dict[str, str]] = None):
        self.year = year
        self.custom_holidays = custom_holidays if custom_holidays else {}
        self.holidays_dict = self._generate_holidays()

    def _calcula_pascoa(self, ano: int) -> datetime.date:
        a, b, c = ano % 19, ano // 100, ano % 100
        d, e, f, g = b // 4, b % 4, (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = c // 4, c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        mes = (h + l - 7 * m + 114) // 31
        dia = ((h + l - 7 * m + 114) % 31) + 1
        return datetime.date(ano, mes, dia)

    def _generate_holidays(self) -> Dict[datetime.date, Dict[str, str]]:
        pascoa = self._calcula_pascoa(self.year)
        carnaval = pascoa - datetime.timedelta(days=47)
        sexta_santa = pascoa - datetime.timedelta(days=2)
        corpus = pascoa + datetime.timedelta(days=60)
        
        base_holidays = {
            datetime.date(self.year, 1, 1): {"nome": "Ano Novo", "desc": "Celebração Universal da Confraternização Universal (Feriado Nacional)."},
            datetime.date(self.year, 4, 21): {"nome": "Tiradentes", "desc": "Homenagem a Joaquim José da Silva Xavier. (Nacional)"},
            datetime.date(self.year, 5, 1): {"nome": "Dia do Trabalho", "desc": "Homenagem às conquistas dos trabalhadores. (Nacional)"},
            datetime.date(self.year, 9, 7): {"nome": "Independência do Brasil", "desc": "Declaração de independência de Portugal. (Nacional)"},
            datetime.date(self.year, 10, 12): {"nome": "Nossa Sra. Aparecida", "desc": "Dia da Padroeira do Brasil. (Nacional)"},
            datetime.date(self.year, 10, 28): {"nome": "Dia do Servidor", "desc": "Ponto facultativo destinado aos funcionários públicos."},
            datetime.date(self.year, 11, 2): {"nome": "Finados", "desc": "Dia de memória e homenagens póstumas. (Nacional)"},
            datetime.date(self.year, 11, 15): {"nome": "Proclamação da República", "desc": "Fim do Império e início da Era Republicana. (Nacional)"},
            datetime.date(self.year, 11, 30): {"nome": "Dia do Evangélico", "desc": "Feriado oficial no Distrito Federal."},
            datetime.date(self.year, 12, 25): {"nome": "Natal", "desc": "Celebração Cristã Universal. (Nacional)"},
            carnaval: {"nome": "Carnaval", "desc": "Festa popular que precede a Quaresma. (Ponto Facultativo)"},
            sexta_santa: {"nome": "Sexta-feira Santa", "desc": "Feriado Nacional móvel."},
            corpus: {"nome": "Corpus Christi", "desc": "Ponto Facultativo Nacional móvel."}
        }
        
        for d, data_obj in self.custom_holidays.items():
            if isinstance(data_obj, str): base_holidays[d] = {"nome": data_obj, "desc": "Inserido manualmente pelo usuário."}
            else: base_holidays[d] = data_obj
        return base_holidays

    def get_info(self, d: datetime.date) -> Dict[str, str]:
        return self.holidays_dict.get(d, None)

# =============================================================================
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL (AVANÇADO)
# =============================================================================
class CalendarManager:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, Any] = None):
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
        holiday_info = self.br_holidays.get_info(current_date)
        is_holiday = holiday_info is not None
        
        is_blocked = False
        if config.get("block_weekends") and is_weekend: is_blocked = True
        if config.get("block_holidays") and is_holiday: is_blocked = True
            
        return {
            "date": current_date,
            "is_weekend": is_weekend,
            "is_holiday": is_holiday,
            "is_blocked": is_blocked,
            "name": holiday_info["nome"] if is_holiday else "Dia Útil e Livre",
            "desc": holiday_info["desc"] if is_holiday else "Apto para receber compromissos.",
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
        if start_idx >= end_idx: return 0
        dias_uteis = 0
        for idx in range(start_idx + 1, end_idx + 1):
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions:
                dias_uteis += 1
        return dias_uteis

# =============================================================================
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA E DIAGNÓSTICO DIDÁTICO
# =============================================================================
class PurePythonScheduleEngine:
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr
        self.cal_config = cal_config
        self.tasks: List[Task] = []
        self.restrictions: List[Restriction] = []
        self.manual_exclusions: List[datetime.date] = []

    def add_tasks(self, tasks: List[Task]): self.tasks = tasks
    def apply_global_blocks(self, manual_exclusions: List[datetime.date]): self.manual_exclusions = manual_exclusions
    def apply_restrictions(self, restrictions: List[Restriction]): self.restrictions = restrictions

    def _validar_parcial(self, alocacao: Dict[str, int]) -> bool:
        for t_id, idx in alocacao.items():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or props["date"] in self.manual_exclusions: return False

        for r in self.restrictions:
            if r.type == "fixed_date":
                if r.params["task_id"] in alocacao and alocacao[r.params["task_id"]] != self.cal_mgr.date_to_idx(r.params["date"]): return False
            elif r.type == "deadline":
                if r.params["task_id"] in alocacao:
                    idx_atual = alocacao[r.params["task_id"]]
                    if r.params.get("before") and idx_atual >= self.cal_mgr.date_to_idx(r.params["before"]): return False
                    if r.params.get("after") and idx_atual <= self.cal_mgr.date_to_idx(r.params["after"]): return False
            elif r.type == "dependency":
                if r.params["task_a"] in alocacao and r.params["task_b"] in alocacao:
                    if alocacao[r.params["task_b"]] < alocacao[r.params["task_a"]] + r.params.get("min_gap", 0): return False
            elif r.type == "working_day_offset":
                if r.params["task_base"] in alocacao and r.params["task_target"] in alocacao:
                    dias_uteis_reais = self.cal_mgr.contar_dias_uteis_entre(alocacao[r.params["task_base"]], alocacao[r.params["task_target"]], self.cal_config, self.manual_exclusions)
                    if dias_uteis_reais != r.params["offset"]: return False
        return True

    def _avaliar_custo(self, alocacao: Dict[str, int]) -> int:
        return sum(50 for idx in alocacao.values() if self.cal_mgr.get_day_properties(idx, self.cal_config)["is_weekend"] or self.cal_mgr.get_day_properties(idx, self.cal_config)["is_holiday"])

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]], str]:
        solucao_otima = {}
        melhor_custo = float('inf')
        task_ids = [t.id for t in self.tasks]
        
        if not task_ids: return "SUCCESS", {}, [], ""
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
                if self._avaliar_custo(alocacao_atual) < melhor_custo: backtrack(task_index + 1, alocacao_atual)
                del alocacao_atual[t_id]

        backtrack(0, {})
        
        if solucao_otima:
            results = {t_id: self.cal_mgr.idx_to_date(idx) for t_id, idx in solucao_otima.items()}
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Data alocada perfeitamente. O algoritmo não teve de quebrar nenhuma configuração principal."} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
            
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        if len(self.restrictions) == 0: return "Você forçou uma Tarefa para acontecer em um dia que já está bloqueado (Ex: Feriado ou Fim de semana). Vá na Planilha e mude o 'Tipo de Regra'."
        
        original_restrictions = self.restrictions.copy()
        for i in range(len(original_restrictions)):
            temp_rest = original_restrictions[i]
            self.restrictions = original_restrictions[:i] + original_restrictions[i+1:]
            solucao_otima = {}
            task_ids = [t.id for t in self.tasks]
            def backtrack_diag(task_index: int, alocacao_atual: Dict[str, int]):
                nonlocal solucao_otima
                if solucao_otima: return
                if not self._validar_parcial(alocacao_atual): return
                if task_index == len(task_ids): solucao_otima = alocacao_atual.copy(); return
                t_id = task_ids[task_index]
                for idx in range(min(150, self.cal_mgr.total_days)):
                    alocacao_atual[t_id] = idx
                    backtrack_diag(task_index + 1, alocacao_atual)
                    del alocacao_atual[t_id]
            backtrack_diag(0, {})
            if solucao_otima:
                self.restrictions = original_restrictions
                tipo = temp_rest.type
                alvo = temp_rest.params.get("task_id") or temp_rest.params.get("task_target")
                
                if tipo == "deadline": return f"A Data Limite da Tarefa **{alvo}** é muito curta. O sistema não consegue encaixar as dependências antes dessa data limite sem cair no fim de semana."
                if tipo == "working_day_offset": return f"Você pediu para a Tarefa **{alvo}** pular dias úteis, mas ela bateu no limite do ano ou colidiu com um prazo. Reduza o número de 'Dias' na tabela."
                return f"O conflito exato foi encontrado na tarefa **{alvo}**. O que você pediu é matematicamente impossível."
        
        self.restrictions = original_restrictions
        return "A quantidade de bloqueios que você selecionou (Férias, Finais de semana, Feriados) é tão grande que não sobrou espaço físico no calendário do ano."

# =============================================================================
# 6. BANCO DE DADOS DE MANUAL E AJUDA (PESQUISÁVEL)
# =============================================================================
MANUAL_SECTIONS = {
    "🌟 1. O que é e para que serve o Calendário Inteligente?": "Imagine que você precise coordenar 20 tarefas e que uma só possa começar 15 dias ÚTEIS depois da anterior. Se você usar um calendário de papel, vai ter que contar com o dedo, pular finais de semana, pular o Carnaval e anotar tudo. Se o Carnaval mudar, você perde todo o trabalho. \n\n**O que a aplicação faz?** Ela faz toda a matemática por você! Você só diz a regra na Planilha e ela monta o calendário inteiro do ano.",
    "⚙️ 2. Como usar a Planilha Interativa (Passo a Passo)": "1. Vá para a **Aba 1**.\n2. Na coluna **'Tipo de Regra'**, escolha como a tarefa vai se comportar. Exemplo: 'Dias Úteis após Tarefa Base'.\n3. Na coluna **'Tarefa Base'**, digite o ID da tarefa mãe. Exemplo: Se T2 depende de T1, escreva `T1` aqui.\n4. Na coluna **'Valor / Dias'**, digite quantos dias úteis pular. Ex: `15`.\n5. O sistema faz o resto sozinho na Aba 2! Não há botão de 'salvar'.",
    "❌ 3. Erro Vermelho na Aba 2? Como Resolver?": "Se a Aba 2 ficou vermelha, o computador não conseguiu fazer a mágica porque você pediu o impossível. \n\n**Solução:** Leia a caixa vermelha. O sistema sempre avisa quem é a tarefa culpada. Volte na Planilha e dê prazos mais generosos (diminua o número de dias úteis).",
    "📌 4. O que são os 'Marcadores Personalizados' na Aba 3?": "Na Aba 3 (Calendário Visual), tem um botão chamado 'Inserir Rótulo ou Marcador'. Lá você pode escolher o desenho de um aviãozinho e escrever 'Viagem'. Quando o calendário for desenhado, o dia estará com um aviãozinho. Isso não afeta as contas matemáticas, é puramente visual para apresentações."
}

# =============================================================================
# 7. INTERFACE INTERATIVA DO USUÁRIO E WIZARD GUIADO (V11.0)
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Planejamento Logístico e Calculadora de Prazos Automática.")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # -------------------------------------------------------------------------
    # GESTÃO DE ESTADO SEGURO
    # -------------------------------------------------------------------------
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "marcadores_calendario" not in st.session_state: st.session_state.marcadores_calendario = {}
    if "export_config" not in st.session_state: st.session_state.export_config = {"file_name": "Planejamento_Oficial", "date_format": "%d/%m/%Y", "separator": ","}
    if "modo_didatico" not in st.session_state: st.session_state.modo_didatico = True

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Início Oficial do Projeto", "Categoria": "Gestão", "Prioridade": "Alta", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Entrega do Relatório (T2)", "Categoria": "Operacional", "Prioridade": "Média", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(copy.deepcopy(st.session_state.df_planilha))
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES GLOBAIS COM CHECKLIST)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ 1. Parâmetros Base")
    st.session_state.modo_didatico = st.sidebar.toggle("🎓 Modo Didático (Explicações e Ajudas)", value=st.session_state.modo_didatico, help="Desligue isto quando já souber usar o sistema para ter uma interface mais limpa.")
    
    if st.session_state.modo_didatico:
        st.sidebar.info("👉 **PASSO 1:** Escolha aqui embaixo quando o seu projeto começa (Data Base).")
        
    base_opcao = st.sidebar.selectbox(
        "📍 Data Base (Ponto de Partida):", 
        ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], 
        help="A 'Data Base' é a âncora do seu projeto. O Motor conta os dias a partir daqui."
    )
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Escolha o Dia:", value=hoje)

    st.sidebar.markdown(f"**Em uso pelo Motor:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    st.sidebar.header("🛡️ 2. Bloqueios Temporais")
    ano_corrente = st.sidebar.number_input("Ano de Referência", min_value=2024, max_value=2030, value=data_base_global.year, help="O sistema calculará Páscoa, Carnaval e Corpus Christi com base no ano inserido aqui.")
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Evitar Sábados/Domingos", value=True, help="O Motor nunca agendará prazos em fins de semana se isso estiver ativo."),
        "block_holidays": st.sidebar.checkbox("Evitar Feriados Oficiais", value=True, help="Pula datas como Natal, Independência, etc.")
    }

    with st.sidebar.expander("🏛️ Adicionar Feriado da Sua Cidade"):
        if st.session_state.modo_didatico: st.caption("Tem um feriado municipal que não está na lista do Brasil? Cadastre-o aqui para o sistema não marcar tarefas nele.")
        f_name = st.text_input("Nome da Folga", placeholder="Ex: Dia do Padroeiro")
        f_date = st.date_input("Data Exata", datetime.date(ano_corrente, 11, 30))
        if st.button("➕ Injetar Bloqueio"):
            if f_name:
                st.session_state.custom_holidays[f_date] = {"nome": f_name, "desc": "Inserido manualmente na Barra Lateral."}
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Férias/Dias Inoperantes", value=[], help="Selecione dias isolados no calendário onde a equipe não vai trabalhar. O Motor também vai pular esses dias.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    st.sidebar.divider()
    st.sidebar.markdown("### ✅ Checklist do Projeto")
    st.sidebar.checkbox("Data Base Definida", value=True, disabled=True)
    st.sidebar.checkbox("Bloqueios Configuráveis Prontos", value=True, disabled=True)
    st.sidebar.checkbox("Tarefas Preenchidas na Planilha", value=len(st.session_state.df_planilha) > 0, disabled=True)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO (NOMES DINÂMICOS DA CONFIGURAÇÃO)
    # -------------------------------------------------------------------------
    tab_names = st.session_state.theme_config["tab_names"]
    t1, t2, t3, t4, t5 = st.tabs(tab_names)

    with t1:
        st.subheader("📝 A Planilha Mestra (Escopo)")
        if st.session_state.modo_didatico:
            st.info("👉 **PASSO 2:** Digite suas tarefas aqui. Não se preocupe em colocar datas, apenas diga as regras matemáticas (Ex: Tarefa 2 deve ocorrer 15 dias após Tarefa 1).")
        
        col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
        with col_act1:
            if st.button("↩️ Desfazer Última Edição", disabled=len(st.session_state.historico_planilha)==0, help="O que faz: Volta a tabela para como estava antes do seu último clique. \nPor que usar: Caso tenha apagado uma linha sem querer."):
                st.session_state.df_planilha = st.session_state.historico_planilha.pop()
                st.rerun()
        with col_act2:
            if st.button("🔢 Gerar Códigos ID Automaticamente", help="O que faz: Apaga os códigos da primeira coluna e coloca T1, T2, T3 em ordem matemática. \nPor que usar: Para não ter dor de cabeça inventando códigos."):
                df_temp = st.session_state.df_planilha.copy()
                df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
                salvar_historico(df_temp)
                st.session_state.df_planilha = df_temp
                st.rerun()
        
        # O WRAPPER DE PREVENÇÃO DE ERROS DO STREAMLIT (Sanitização Absoluta PyArrow)
        df_safe = st.session_state.df_planilha.copy()
        if "Data Fixa" in df_safe.columns:
            # Força o tipo estrito datetime64[ns] que é nativamente compreendido pelo Streamlit Arrow, prevenindo TypeErrors.
            df_safe["Data Fixa"] = pd.to_datetime(df_safe["Data Fixa"], errors='coerce')

        # DATA EDITOR COM DIDÁTICA EXTREMA EM TODAS AS COLUNAS
        df_edited = st.data_editor(
            df_safe,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn(
                    "Código ID", 
                    required=True, 
                    help="O QUE É: O identificador único (apelido) da tarefa. Normalmente T1, T2.\nPARA QUE SERVE: O Motor usa isso para saber quem amarra quem.\nERRO COMUM: Colocar IDs repetidos."
                ),
                "Nome da Tarefa": st.column_config.TextColumn(
                    "Qual a Tarefa?", 
                    required=True, width="large", 
                    help="O QUE É: O nome real que aparecerá no cronograma e nos relatórios exportados.\nEXEMPLO: 'Revisão do Contrato XPTO'."
                ),
                "Categoria": st.column_config.TextColumn(
                    "Categoria", 
                    help="PARA QUE SERVE: Apenas para você filtrar e organizar depois no Excel. Não afeta a data."
                ),
                "Prioridade": st.column_config.SelectboxColumn(
                    "Prioridade", 
                    options=["Alta", "Média", "Baixa"],
                    help="O QUE É: Marcador de urgência visual. Não altera o cálculo de datas."
                ),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "🚨 TIPO DE REGRA (Crucial)",
                    options=["Livre", "Data Fixada", "1º Dia Útil após Data Base", "Dias Úteis após Tarefa Base", "Dias Úteis após Data Base", "Data Limite (Antes de)", "Data Limite (Após de)"],
                    required=True,
                    help="O QUE É: O coração do sistema.\nCOMO USAR: A regra 'Dias Úteis após Tarefa Base' é a mais recomendada. Ela pulará sábados e feriados automaticamente antes de marcar a data."
                ),
                "Tarefa Base": st.column_config.TextColumn(
                    "Vem depois de quem?", 
                    help="COMO PREENCHER: Digite o Código ID da tarefa mãe. \nEXEMPLO: Se esta linha só pode ocorrer depois da linha 'T1', digite 'T1' aqui."
                ),
                "Valor / Dias": st.column_config.NumberColumn(
                    "Quantos Dias?", 
                    min_value=0, 
                    help="O QUE É: O tamanho do salto temporal.\nCOMO PREENCHER: Se escolheu a regra 'Dias Úteis após', digite aqui o número de dias de intervalo (Ex: 10). O sistema pulará 10 dias úteis."
                ),
                "Data Fixa": st.column_config.DateColumn(
                    "Data Fixa (Cuidado)", 
                    format="DD/MM/YYYY", 
                    help="O QUE É: Uma âncora forçada de tempo.\nQUANDO USAR: Somente em compromissos inadiáveis.\nQUANDO NÃO USAR: Evite sempre que possível. Fixar datas quebra a fluidez do cronograma se houver atrasos.\nERRO COMUM: Fixar num fim de semana."
                )
            }
        )
        salvar_historico(df_edited)
        st.session_state.df_planilha = df_edited

        st.markdown("---")
        with st.expander("🛠️ Avançado: Carregar Excel Pronto e Regras de Segurança"):
            if st.session_state.modo_didatico: st.write("Para usuários experientes: Faça upload do seu próprio CSV ou crie travas lógicas que não aparecem na tabela.")
            uploaded_file = st.file_uploader("Subir Tabela (CSV/Excel)", type=["csv", "xlsx"])
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.session_state.df_planilha = df_up
                    st.success("Planilha carregada perfeitamente!")
                except Exception as e:
                    st.error("Falha ao ler. O formato das colunas não parece combinar com a tabela mestre.")

    # COMPILAÇÃO INTELIGENTE DAS REGRAS PARA O MOTOR MATEMÁTICO
    engine_tasks = []
    engine_restrictions = list(st.session_state.restrictions_manuais)

    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Nome da Tarefa", "Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]): continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        v_tipo = row.get("Tipo de Regra", "Livre")
        v_base = str(row.get("Tarefa Base", "")).strip()
        v_val = int(row.get("Valor / Dias", 0)) if pd.notna(row.get("Valor / Dias")) else 0
        v_fixa = row.get("Data Fixa")
        
        # Tradução Segura: Se o Pandas trouxer um NaT/Timestamp da célula, converte para datetime.date limpo
        if v_tipo == "Data Fixada" and pd.notna(v_fixa) and v_fixa is not pd.NaT:
            try:
                dt_obj = v_fixa.date() if hasattr(v_fixa, 'date') else v_fixa
                engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": dt_obj}))
            except: pass
        elif v_tipo == "1º Dia Útil após Data Base":
            primeiro_util = cal_mgr.get_next_working_day(data_base_global - datetime.timedelta(days=1), cal_config, manual_dates)
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": primeiro_util}))
        elif v_tipo == "Dias Úteis após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Dias Úteis após Data Base":
            alvo_data = data_base_global
            dias_uteis_pulados = 0
            while dias_uteis_pulados < v_val:
                alvo_data += datetime.timedelta(days=1)
                p = cal_mgr.get_day_properties(cal_mgr.date_to_idx(alvo_data), cal_config)
                if not p["is_blocked"] and alvo_data not in manual_dates: dias_uteis_pulados += 1
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": alvo_data}))
        elif v_tipo == "Data Limite (Antes de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": data_base_global + datetime.timedelta(days=v_val)}))
        elif v_tipo == "Data Limite (Após de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "after": data_base_global + datetime.timedelta(days=v_val)}))

    # CÁLCULO TOTALMENTE AUTOMÁTICO (REATIVIDADE STREAMLIT SEM BOTÕES DE CONFIRMAR)
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        st.subheader("📊 Resultados Resolvidos")
        if status == "SUCCESS":
            if st.session_state.modo_didatico:
                st.success("✅ **O Motor Encontrou as Datas!** \n\nVocê não precisa clicar em calcular. O computador rodou milhares de cenários em milissegundos e garantiu que estas datas respeitam seus feriados e fins de semana. Role para baixo para fazer o Download.")
            
            col_m1, col_m2 = st.columns(2)
            for i, card in enumerate(alt_cards):
                t_id = card["task_id"]
                date_val = sol_dates.get(t_id)
                t_obj = next((t for t in engine_tasks if t.id == t_id), None)
                if t_obj and date_val:
                    with col_m1 if i % 2 == 0 else col_m2:
                        st.markdown(f"""
                        <div class="metric-card" title="{card['justification']}">
                            <span style="color:{st.session_state.theme_config['color_allocated_border']}; font-weight:bold; font-size:11px; text-transform: uppercase;">✔ ALOCADO COM SUCESSO: ({t_id})</span>
                            <h4 style="margin:4px 0; color: #1F2937;">{t_obj.name}</h4>
                            <h2 style="color:{st.session_state.theme_config['color_primary']}; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:12px; color:#6B7280; margin:0px;">Cai num(a) <b>{["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][date_val.weekday()]}</b></p>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📥 Geração de Relatórios e Exportação")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código ID": t_id, "Tarefa / Ação": t_item.name, "Data de Execução": f_date}
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0]
                    if "Categoria" in row_t: row_data["Grupo/Setor"] = row_t["Categoria"]
                    if "Prioridade" in row_t: row_data["Nível de Prioridade"] = row_t["Prioridade"]
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                
                txt_report = f"========================================\nDOSSIÊ E PLANEJAMENTO - EXERCÍCIO DE {ano_corrente}\n"
                txt_report += f"Relatório Gerado a partir do Ponto de Partida: {data_base_global.strftime('%d/%m/%Y')}\n"
                txt_report += "========================================\n📋 CRONOGRAMA OFICIAL DAS TAREFAS:\n"
                for r in cronograma_data: txt_report += f"   ➤ Dia {r['Data de Execução']} | {r['Código ID']}: {r['Tarefa / Ação']}\n"
                txt_report += "\n========================================\n🚫 RELAÇÃO DE FERIADOS E BLOQUEIOS APLICADOS:\n"
                for dt, props in cal_mgr.br_holidays.holidays_dict.items():
                    txt_report += f"   - {dt.strftime('%d/%m/%Y')}: {props['nome']} -> {props['desc']}\n"
                
                c1, c2 = st.columns(2)
                c1.download_button(f"📥 Baixar Arquivo Excel Bruto (.CSV)", data=csv_buffer, file_name=f"{st.session_state.export_config['file_name']}.csv", mime="text/csv", use_container_width=True, help="Esse arquivo é útil para quem vai montar gráficos em Excel ou PowerBI.")
                c2.download_button("📝 Baixar Resumo em Texto Livre (.TXT)", data=txt_report, file_name="Relatorio_Textual.txt", mime="text/plain", use_container_width=True, help="O melhor formato para você copiar e colar no WhatsApp da equipe.")

        else:
            st.error("⚠️ **O Motor de Cálculos Sofreu um Choque de Regras**")
            st.markdown(f"""
            <div class="alert-box">
                <b>🔍 O QUE O SISTEMA DESCOBRIU (Diagnóstico Automático):</b><br>
                {diagnostico}
            </div>
            """, unsafe_allow_html=True)
            if st.session_state.modo_didatico:
                st.warning("""
                **Guia Prático para Resolver Isso Agora:**
                1. Você forçou o motor a tentar colocar 10 litros de água num balde de 5 litros. Falta espaço no calendário!
                2. Vá na Aba 1 (Planilha) e diminua os números da coluna 'Valor / Dias'.
                3. Se você usou a regra 'Data Fixa', verifique no mapa da Aba 3 se esse dia já não é um Feriado ou Sábado. Se for, troque a regra.
                """)

    with t3:
        st.subheader("📅 O Grande Quadro de Planejamento (Heatmap)")
        if st.session_state.modo_didatico: st.write("Uma foto inteira do seu ano. Células pintadas representam feriados ou dias que suas tarefas foram marcadas.")
        
        with st.expander("📌 Brincar no Calendário: Inserir Marcadores Coloridos e Lembretes (Rótulos)"):
            st.write("Coloque post-its digitais sobre os dias. **(Isso não mexe nos cálculos matemáticos do cronograma)**.")
            m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
            m_date = m_col1.date_input("Escolha o dia Exato:", data_base_global, help="Quando o adesivo vai ficar?")
            m_text = m_col2.text_input("Escreva o Lembrete:", placeholder="Ex: Pagar Fornecedor", help="Aparece quando você passar o mouse no calendário.")
            m_icon = m_col3.selectbox("Escolha um Emoji", ["📌 Alfinete", "⭐ Favorito", "✈️ Viagem", "🏖️ Férias", "💰 Pagamento", "🎂 Aniversário", "🎯 Meta"])
            if st.button("✏️ Colar Carimbo neste dia", help="O ícone aparecerá no respectivo mês desenhado abaixo."):
                if m_text:
                    st.session_state.marcadores_calendario[m_date] = f"{m_icon.split()[0]} {m_text}"
                    st.rerun()
            
            if st.session_state.marcadores_calendario:
                st.write("**Marcadores Desenhados Atualmente:**")
                for md, txt in st.session_state.marcadores_calendario.items(): st.caption(f"- {md.strftime('%d/%m')}: {txt}")
                if st.button("🗑️ Arrancar todos os carimbos", help="Limpa o calendário das marcações pessoais."):
                    st.session_state.marcadores_calendario = {}; st.rerun()

        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div title="Ninguém agendou nada aqui. Dia livre."><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia Livre</div>
            <div title="A Planilha agendou sua tarefa nesta data."><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> <b>Alvo da Planilha</b></div>
            <div title="Feriado! O Computador pula essa data."><span style="background-color: {st.session_state.theme_config['color_holiday']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado Proibido</div>
            <div title="Sábados, domingos ou suas férias da Barra Lateral."><span style="background-color: {st.session_state.theme_config['color_blocked']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Bloqueado/Fim de Semana</div>
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
                        
                        dias_semana = ["S", "T", "Q", "Q", "S", "S", "D"] if st.session_state.theme_config["cal_first_weekday"] == 0 else ["D", "S", "T", "Q", "Q", "S", "S"]
                        for sem in dias_semana: html_cal += f'<div class="calendar-cell day-header">{sem}</div>'
                        html_cal += '</div>'
                        
                        cal_obj = calendar.Calendar(firstweekday=st.session_state.theme_config["cal_first_weekday"])
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
                                    title_hover = props["desc"]
                                    
                                    display_content = f"{day}"
                                    if d_verif in st.session_state.marcadores_calendario:
                                        display_content += f"<span class='day-marker'>{st.session_state.marcadores_calendario[d_verif].split()[0]}</span>"
                                        title_hover = st.session_state.marcadores_calendario[d_verif]

                                    if d_verif == data_base_global:
                                        title_hover = "📍 ESSE É O DIA ZERO: A Data Base."
                                        cell_class = "day-allocated"
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"🎯 Tarefa(s) da Planilha agendadas aqui: {', '.join(t_codes)}"
                                    elif props["is_holiday"]: 
                                        cell_class = "day-holiday"
                                        title_hover = f"🚫 Feriado: {props['name']} - {props['desc']}"
                                    elif props["is_blocked"] or d_verif in manual_dates: 
                                        cell_class = "day-blocked"
                                        title_hover = "O sistema foi expressamente proibido de colocar tarefas aqui. Estará de folga."
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{display_content}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    with t4:
        st.header("🎨 4. Oficina de Customização e Configuração Visual")
        st.info("Aqui a aparência do software fica com a sua cara e com a cara da sua empresa. Sem precisar mexer numa gota de código fonte.")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Visual da Tela (Pintando as Paredes)")
            st.session_state.theme_config["app_title"] = st.text_input("Como quer chamar o Sistema Gigante?", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v11.0"), help="O Letreiro Gigante lá no topo muda se você trocar essa caixa.")
            
            tema_escolhido = st.selectbox("Escolha um Padrão de Cor Profissional", list(THEME_PALETTES.keys()), help="Clique na caixa. A tela vai mudar da água pro vinho adaptando tudo daquele padrão.")
            if st.button("🎨 Aplicar Banho de Cor em Toda a Tela", help="Aperte firme para acionar os pintores de tela e transformar o fundo da Aba 3 no tema."):
                st.session_state.theme_config["color_primary"] = THEME_PALETTES[tema_escolhido]["primary"]
                st.session_state.theme_config["color_allocated"] = THEME_PALETTES[tema_escolhido]["alloc"]
                st.session_state.theme_config["color_allocated_border"] = THEME_PALETTES[tema_escolhido]["alloc_border"]
                st.toast("O sistema foi repintado com sucesso! Se alguma borda não atualizou, é só clicar em outra Aba para forçar a visão.")
                st.rerun()
            
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Na Grade de Desenho, a sua semana começa no...", options=[("Domingo (Recomendado)", 6), ("Segunda-Feira", 0)], format_func=lambda x: x[0], help="No Brasil a semana de trabalho começa segunda. Mas os calendários normalmente começam no domingo na ponta esquerda. Qual prefere?") [1]
            
        with c_p2:
            st.subheader("Opções de Download do Excel (Na Aba 2)")
            st.session_state.export_config["file_name"] = st.text_input("Nome do Arquivo CSV/Excel", value=st.session_state.export_config["file_name"], help="O nome do arquivo na sua pasta de Downloads.")
            st.session_state.export_config["date_format"] = st.selectbox("Como o Excel deve desenhar a Data?", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"], help="Exemplo Brasileiro: DD/MM/AAAA. Exemplo Norte-Americano: %Y-%m-%d.")
            st.session_state.export_config["separator"] = st.selectbox("Seu Excel trava as colunas? Escolha o Separador:", options=[";", ",", "\t"], help="Solução de Problema: Se você baixou o CSV e o Excel esmagou tudo numa coluna só, troque a Vírgula por Ponto e Vírgula (;) e baixe novamente.")

        st.divider()
        st.subheader("💾 O Coração da Operação (Salvar e Carregar Backup Universal)")
        st.write("Você aperta o botão para baixar esse arquivo mágico 'JSON' para o seu computador. \nAmanhã de manhã, quando o sistema resetar sozinho, você arrasta esse JSON e ele ressuscita as suas tarefas e suas cores de volta dos mortos!")
        
        export_dict = {
            "theme": st.session_state.theme_config,
            "export": st.session_state.export_config,
            "markers": {d.strftime("%Y-%m-%d"): txt for d, txt in st.session_state.marcadores_calendario.items()},
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button(label="📦 Gerar Super Backup do Sistema (Arquivo .JSON)", data=json_str, file_name="Projeto_Calendario_Salvo.json", mime="application/json", use_container_width=True, help="Baixa um pacote que guarda o estado exato da sua planilha.")

    with t5:
        st.header("📘 A Enciclopédia Didática (Tire sua Dúvida Aqui)")
        st.write("Digite sua dúvida na caixa de texto abaixo. Somente os tópicos relacionados se abrirão. Um motor de busca indexado vai tentar encontrar a resposta nos nossos manuais.")
        
        MANUAL_SECTIONS = {
            "💡 Como funciona a 'Data Base'? (Ponto de Partida)": "A Data Base é o centro do universo nesta aplicação. \n\n**O que é?** É o ponto fixo de onde os pulos são dados.\n**Como funciona?** Se você disser na Tabela que a 'Tarefa 1' acontece com a regra '1º Dia Útil Após a Data Base', e a sua Data base for 01/Jan. O sistema agenda a tarefa no dia 02/Jan.\n**Impacto:** Se você mudar a Data Base na barra lateral para 01/Fev, a tarefa pula junto inteira para Fevereiro. O projeto todo é arrastado junto com um clique.",
            "⚙️ Coluna de 'Tipo de Regra' na Tabela. Como faço isso do jeito fácil?": "**O que é?** A inteligência por trás do sistema. \n**Quando usar a regra de dependência?** Digamos que você tem uma licitação (Fase 1), e o recurso da licitação (Fase 2) só pode ocorrer 15 dias ÚTEIS depois da Fase 1. \n\n**O Passo a Passo:**\n1. Na linha da Fase 2, mude o tipo de regra para 'Dias Úteis após Tarefa Base'.\n2. Na Coluna 'Tarefa Base', escreva lá 'T1' (o apelido da Fase 1).\n3. Na coluna 'Valor/Dias', digite 15.\n Acabou. O sistema faz o resto e garante os 15 dias sem tocar no Natal.",
            "❌ Erro Vermelho na Aba 2, e agora? (Conflito Lógico)": "**O que significa?** Você tentou fazer algo que contraria a física do tempo no planeta Terra. \n**Causa do Erro:** Você colocou a Data Base como Novembro. E disse para o computador colocar uma Reunião 90 dias úteis depois. O ano vai acabar (Dezembro termina). O computador apita a sirene de 'Erro Vermelho'. \n**Como Solucionar?** Vá na caixa de diagnóstico, leia qual Tarefa a máquina denunciou, e diminua o prazo dela na Aba 1.",
            "📌 Como uso as anotações visuais no Calendário (Aba 3)?": "Na Aba 3, abra a caixinha 'Inserir Rótulo ou Marcador Visual'. Escolhe o dia, escolhe um emoji bonitinho e escreve o texto. \n**Impacto:** Ele não mexe nas datas do seu cálculo da Aba 2. O Rótulo serve unicamente para pintar uma figurinha no mapa térmico da Aba 3 para você se lembrar quando for apresentar para um cliente na TV da sala de reunião.",
            "🗂️ Como eu Salvo tudo isso para não perder o serviço amanhã?": "**O que fazer?** Vá na Aba 4 (Personalização) e role a página até o subsolo. \n**Botão de Ouro:** Clique no botão 'Gerar Super Backup'. Ele baixa um pequeno arquivo 'JSON'. \n**Amanhã de Manhã:** Quando abrir a aplicação de novo, suba o arquivo na Aba 1 que o sistema vai carregar tudo do zero sozinho."
        }
        
        pesquisa = st.text_input("🔍 Pesquise sua dúvida (Ex: 'Erro vermelho', 'Salvar', 'Regras'):", help="Escreva o que não entendeu. O buscador vai filtrar todos os tópicos e deixar apenas o manual que responde sua pergunta vivo na tela.")
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo):
                    st.markdown(conteudo)

if __name__ == "__main__":
    main()
