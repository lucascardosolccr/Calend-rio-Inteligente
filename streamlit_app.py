import datetime
import calendar
import copy
import json
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS (UX/UI ENTERPRISE)
# =============================================================================
st.set_page_config(page_title="Calendário Inteligente PRO v14.0", page_icon="📅", layout="wide", initial_sidebar_state="expanded")

if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A", "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE", "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2", "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Escopo & Lógica", "📊 2. Cronograma & Gantt", "📅 3. Visão do Ano", "📘 4. Curso & Algoritmos", "🎨 5. Personalização"],
        "cal_first_weekday": 6 
    }

THEME_PALETTES = {
    "Azul Corporativo": {"primary": "#1E3A8A", "alloc": "#DBEAFE", "alloc_border": "#2563EB"},
    "Verde Operacional": {"primary": "#14532D", "alloc": "#DCFCE7", "alloc_border": "#16A34A"},
    "Roxo Estratégico": {"primary": "#4C1D95", "alloc": "#F3E8FF", "alloc_border": "#7E22CE"},
    "Preto Clássico": {"primary": "#111827", "alloc": "#F3F4F6", "alloc_border": "#374151"}
}

st.markdown(f"""
    <style>
    .main-title {{ font-size: 2.2rem; font-weight: 800; color: {st.session_state.theme_config['color_primary']}; margin-bottom: 0.2rem; letter-spacing: -0.5px; }}
    .subtitle {{ font-size: 1.05rem; color: {st.session_state.theme_config['color_secondary']}; margin-bottom: 1.8rem; font-weight: 400; }}
    .metric-card {{ background-color: #FFFFFF; border-left: 6px solid {st.session_state.theme_config['color_allocated_border']}; padding: 18px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); margin-bottom: 15px; transition: transform 0.2s, box-shadow 0.2s; }}
    .metric-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 15px rgba(0,0,0,0.08); }}
    .onboarding-box {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }}
    .alert-box {{ background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 6px; margin-top:10px; }}
    .info-box {{ background-color: #F0F9FF; border-left: 5px solid #3B82F6; padding: 15px; border-radius: 6px; margin-bottom: 15px; }}
    .calendar-grid {{ display: block; margin-bottom: 20px; font-family: -apple-system, sans-serif; }}
    .calendar-row {{ display: table; width: 100%; table-layout: fixed; }}
    .calendar-cell {{ display: table-cell; text-align: center; padding: 8px 2px; font-size: 11px; border: 1px solid #F1F5F9; font-weight: 600; min-height: 45px; vertical-align: middle; border-radius: 2px; }}
    .day-normal {{ background-color: #FFFFFF; color: #334155; }}
    .day-allocated {{ background-color: {st.session_state.theme_config['color_allocated']}; color: {st.session_state.theme_config['color_primary']}; border: 2px solid {st.session_state.theme_config['color_allocated_border']} !important; font-weight: 800; border-radius: 6px; box-shadow: inset 0 0 5px rgba(0,0,0,0.05); }}
    .day-holiday {{ background-color: {st.session_state.theme_config['color_holiday']}; color: #991B1B; }}
    .day-blocked {{ background-color: {st.session_state.theme_config['color_blocked']}; color: #94A3B8; text-decoration: line-through; }}
    .day-marker {{ font-size: 14px; display: block; margin-top: 3px; }}
    .day-header {{ background-color: #F8FAFC; color: #475569; font-weight: bold; text-transform: uppercase; font-size: 10px; border: none; }}
    .flow-diagram {{ background: #1e293b; padding: 15px; border-radius: 8px; font-family: monospace; font-size: 14px; color: #10B981; margin: 10px 0; white-space: pre; overflow-x: auto; line-height: 1.5; }}
    .translation-box {{ background-color: #F8FAFC; padding: 10px 15px; border-left: 4px solid #3B82F6; margin-bottom: 8px; border-radius: 4px; font-size: 13.5px; color: #334155; }}
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. ESTRUTURAS DO MOTOR (NOVA LISTA DE ALGORITMOS)
# =============================================================================
LISTA_ALGORITMOS = [
    "Livre (Onde houver vaga)", 
    "Data Fixada (Ancorada)", 
    "1º Dia Útil após Data Base", 
    "Dias Úteis APÓS Tarefa Base", 
    "Dias Úteis ANTES da Tarefa Base",
    "Dias Corridos APÓS Tarefa Base",
    "Dias Corridos ANTES da Tarefa Base",
    "Primeiro dia útil após Tarefa Base",
    "Último dia útil antes da Tarefa Base",
    "Primeira Segunda-feira após Tarefa Base",
    "Primeira Sexta-feira após Tarefa Base",
    "Último dia útil do mês da Tarefa Base",
    "1º dia útil do mês seguinte à Tarefa Base",
    "Mesmo dia da semana (na próxima semana)",
    "Data Limite MÁXIMA (Antes de)"
]

class Task:
    def __init__(self, id: str, name: str): self.id = id; self.name = name

class Restriction:
    def __init__(self, type: str, params: Dict[str, Any]): self.type = type; self.params = params

# =============================================================================
# 3. MOTOR DE FERIADOS E CALENDÁRIO
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
            datetime.date(self.year, 1, 1): {"nome": "Ano Novo", "desc": "Feriado Nacional."},
            datetime.date(self.year, 4, 21): {"nome": "Tiradentes", "desc": "Feriado Nacional."},
            datetime.date(self.year, 5, 1): {"nome": "Dia do Trabalho", "desc": "Feriado Nacional."},
            datetime.date(self.year, 9, 7): {"nome": "Independência do Brasil", "desc": "Feriado Nacional."},
            datetime.date(self.year, 10, 12): {"nome": "Nossa Sra. Aparecida", "desc": "Feriado Nacional."},
            datetime.date(self.year, 11, 2): {"nome": "Finados", "desc": "Feriado Nacional."},
            datetime.date(self.year, 11, 15): {"nome": "Proclamação da República", "desc": "Feriado Nacional."},
            datetime.date(self.year, 12, 25): {"nome": "Natal", "desc": "Feriado Nacional."},
            carnaval: {"nome": "Carnaval", "desc": "Ponto Facultativo/Feriado."},
            sexta_santa: {"nome": "Sexta-feira Santa", "desc": "Feriado Religioso."},
            corpus: {"nome": "Corpus Christi", "desc": "Ponto Facultativo."}
        }
        for d, data_obj in self.custom_holidays.items():
            if isinstance(data_obj, str): base_holidays[d] = {"nome": data_obj, "desc": "Feriado Injetado."}
            else: base_holidays[d] = data_obj
        return base_holidays
    
    def get_info(self, d: datetime.date) -> Dict[str, str]: return self.holidays_dict.get(d, None)

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
            "date": current_date, "is_weekend": is_weekend, "is_holiday": is_holiday,
            "is_blocked": is_blocked, "name": holiday_info["nome"] if is_holiday else "Dia Livre",
            "desc": holiday_info["desc"] if is_holiday else "Apto para tarefas.", "weekday": current_date.weekday()
        }

    # MATEMÁTICA AVANÇADA DE CALENDÁRIO (V14.0)
    def get_next_working_day(self, start_date: datetime.date, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> datetime.date:
        idx = self.date_to_idx(start_date)
        while idx < self.total_days:
            idx += 1
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions: return props["date"]
        return self.end_date

    def get_previous_working_day(self, start_date: datetime.date, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> datetime.date:
        idx = self.date_to_idx(start_date)
        while idx > 0:
            idx -= 1
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions: return props["date"]
        return self.start_date

    def contar_dias_uteis_entre(self, start_idx: int, end_idx: int, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> int:
        if start_idx >= end_idx: return 0
        dias_uteis = 0
        for idx in range(start_idx + 1, end_idx + 1):
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions: dias_uteis += 1
        return dias_uteis

    def contar_dias_uteis_para_tras(self, start_idx: int, end_idx: int, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> int:
        if start_idx <= end_idx: return 0
        dias_uteis = 0
        for idx in range(start_idx - 1, end_idx - 1, -1):
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions: dias_uteis += 1
        return dias_uteis

    def get_next_specific_weekday(self, start_date: datetime.date, target_weekday: int) -> datetime.date:
        days_ahead = target_weekday - start_date.weekday()
        if days_ahead <= 0: days_ahead += 7
        return start_date + datetime.timedelta(days=days_ahead)

    def get_last_working_day_of_month(self, date_ref: datetime.date, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> datetime.date:
        last_day = calendar.monthrange(date_ref.year, date_ref.month)[1]
        test_date = datetime.date(date_ref.year, date_ref.month, last_day)
        if not self.get_day_properties(self.date_to_idx(test_date), config)["is_blocked"] and test_date not in manual_exclusions:
            return test_date
        return self.get_previous_working_day(test_date, config, manual_exclusions)

    def get_first_working_day_of_next_month(self, date_ref: datetime.date, config: Dict[str, bool], manual_exclusions: List[datetime.date]) -> datetime.date:
        if date_ref.month == 12: next_month_date = datetime.date(date_ref.year + 1, 1, 1)
        else: next_month_date = datetime.date(date_ref.year, date_ref.month + 1, 1)
        
        props = self.get_day_properties(self.date_to_idx(next_month_date), config)
        if not props["is_blocked"] and next_month_date not in manual_exclusions: return next_month_date
        return self.get_next_working_day(next_month_date, config, manual_exclusions)

# =============================================================================
# 4. PREVENÇÃO DE ERROS - VALIDAÇÃO E DIAGNÓSTICO PRÉ-CÁLCULO (V14.0)
# =============================================================================
def sanity_check_dependencies(engine_restrictions: List[Restriction], tasks: List[Task]) -> Tuple[bool, str]:
    """Valida referências circulares e órfãos usando DFS em Teoria dos Grafos antes de fundir o computador."""
    graph = {t.id: [] for t in tasks}
    valid_ids = set(graph.keys())
    
    for r in engine_restrictions:
        if hasattr(r, 'params') and "task_base" in r.params and "task_target" in r.params:
            base = r.params["task_base"]
            target = r.params["task_target"]
            if base not in valid_ids: return False, f"⚠️ Erro de Preenchimento: A Tarefa {target} depende da Tarefa '{base}', mas '{base}' não existe ou foi excluída da tabela!"
            if target not in valid_ids: return False, f"⚠️ Erro Fantasma: Referência ao alvo '{target}' que não existe."
            graph[base].append(target) # Aresta Base -> Target

    visited = set(); rec_stack = set()
    def detect_cycle(node, path):
        visited.add(node); rec_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if detect_cycle(neighbor, path + [neighbor]): return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False

    for node in graph:
        if node not in visited:
            if detect_cycle(node, [node]):
                return False, f"🛑 LOOP INFINITO DETECTADO: Você criou uma dependência circular. Uma tarefa não pode depender de si mesma em um ciclo fechado. Revise as amarrações da tabela."
    
    return True, "All clear"

# =============================================================================
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA (UPGRADE DE ALGORITMOS)
# =============================================================================
class PurePythonScheduleEngine:
    def __init__(self, cal_mgr: CalendarManager, cal_config: Dict[str, bool]):
        self.cal_mgr = cal_mgr; self.cal_config = cal_config; self.tasks = []; self.restrictions = []; self.manual_exclusions = []

    def add_tasks(self, tasks: List[Task]): self.tasks = tasks
    def apply_global_blocks(self, manual_exclusions: List[datetime.date]): self.manual_exclusions = manual_exclusions
    def apply_restrictions(self, restrictions: List[Restriction]): self.restrictions = restrictions

    def _validar_parcial(self, alocacao: Dict[str, int]) -> bool:
        for t_id, idx in alocacao.items():
            props = self.cal_mgr.get_day_properties(idx, self.cal_config)
            if props["is_blocked"] or props["date"] in self.manual_exclusions: return False

        for r in self.restrictions:
            # Regras Estáticas de Posição
            if r.type == "fixed_date":
                if r.params["task_id"] in alocacao and alocacao[r.params["task_id"]] != self.cal_mgr.date_to_idx(r.params["date"]): return False
            elif r.type == "deadline":
                if r.params["task_id"] in alocacao:
                    idx_atual = alocacao[r.params["task_id"]]
                    if r.params.get("before") and idx_atual >= self.cal_mgr.date_to_idx(r.params["before"]): return False
                    
            # Regras Dinâmicas de Custo e Relacionamento (V14.0 Master Engine)
            elif r.type in ["working_day_offset", "working_day_offset_backwards", "calendar_day_offset", "calendar_day_offset_backwards", 
                            "next_working_day", "prev_working_day", "next_monday", "next_friday", "last_working_month", "first_working_next_month", "same_weekday_next_week"]:
                if r.params["task_base"] in alocacao and r.params["task_target"] in alocacao:
                    idx_base = alocacao[r.params["task_base"]]
                    idx_target = alocacao[r.params["task_target"]]
                    date_base = self.cal_mgr.idx_to_date(idx_base)
                    date_target = self.cal_mgr.idx_to_date(idx_target)
                    
                    if r.type == "working_day_offset":
                        if self.cal_mgr.contar_dias_uteis_entre(idx_base, idx_target, self.cal_config, self.manual_exclusions) != r.params["offset"]: return False
                    elif r.type == "working_day_offset_backwards":
                        if self.cal_mgr.contar_dias_uteis_para_tras(idx_base, idx_target, self.cal_config, self.manual_exclusions) != r.params["offset"]: return False
                    elif r.type == "calendar_day_offset":
                        if idx_target != idx_base + r.params["offset"]: return False
                    elif r.type == "calendar_day_offset_backwards":
                        if idx_target != idx_base - r.params["offset"]: return False
                    elif r.type == "next_working_day":
                        if date_target != self.cal_mgr.get_next_working_day(date_base, self.cal_config, self.manual_exclusions): return False
                    elif r.type == "prev_working_day":
                        if date_target != self.cal_mgr.get_previous_working_day(date_base, self.cal_config, self.manual_exclusions): return False
                    elif r.type == "next_monday":
                        if date_target != self.cal_mgr.get_next_specific_weekday(date_base, 0): return False
                    elif r.type == "next_friday":
                        if date_target != self.cal_mgr.get_next_specific_weekday(date_base, 4): return False
                    elif r.type == "same_weekday_next_week":
                        if date_target != date_base + datetime.timedelta(days=7): return False
                    elif r.type == "last_working_month":
                        if date_target != self.cal_mgr.get_last_working_day_of_month(date_base, self.cal_config, self.manual_exclusions): return False
                    elif r.type == "first_working_next_month":
                        if date_target != self.cal_mgr.get_first_working_day_of_next_month(date_base, self.cal_config, self.manual_exclusions): return False

        return True

    def _avaliar_custo(self, alocacao: Dict[str, int]) -> int:
        return sum(50 for idx in alocacao.values() if self.cal_mgr.get_day_properties(idx, self.cal_config)["is_weekend"] or self.cal_mgr.get_day_properties(idx, self.cal_config)["is_holiday"])

    def solve(self, mock_only=False) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]], str]:
        if mock_only: return "MOCK", {}, [], "Simulação"
        
        solucao_otima = {}; melhor_custo = float('inf')
        task_ids = [t.id for t in self.tasks]
        if not task_ids: return "SUCCESS", {}, [], ""
        horizonte_busca = min(250, self.cal_mgr.total_days)

        def backtrack(task_index: int, alocacao_atual: Dict[str, int]):
            nonlocal solucao_otima, melhor_custo
            if not self._validar_parcial(alocacao_atual): return
            if task_index == len(task_ids):
                custo_atual = self._avaliar_custo(alocacao_atual)
                if custo_atual < melhor_custo:
                    melhor_custo = custo_atual; solucao_otima = alocacao_atual.copy()
                return
            t_id = task_ids[task_index]
            for idx in range(horizonte_busca):
                alocacao_atual[t_id] = idx
                if self._avaliar_custo(alocacao_atual) < melhor_custo: backtrack(task_index + 1, alocacao_atual)
                del alocacao_atual[t_id]

        backtrack(0, {})
        if solucao_otima:
            results = {t_id: self.cal_mgr.idx_to_date(idx) for t_id, idx in solucao_otima.items()}
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Validação Matemática 100%. Regras sistêmicas atendidas."} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
        return "INFEASIBLE", {}, [], "O volume de bloqueios (Férias/Feriados) ou a cadeia de regras é maior que os dias úteis possíveis no ano."

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO E WIZARD (V14.0 MASTER CLASS)
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v14.0")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Módulo Enterprise: Algoritmos Lógicos Avançados e Renderização Analítica")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # ESTADO SEGURO
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "marcadores_calendario" not in st.session_state: st.session_state.marcadores_calendario = {}
    if "export_config" not in st.session_state: st.session_state.export_config = {"file_name": "Planejamento_Oficial", "date_format": "%d/%m/%Y", "separator": ","}
    if "modo_didatico" not in st.session_state: st.session_state.modo_didatico = True

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Briefing com a Equipe", "Categoria": "Gestão", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Produção do Relatório Final", "Categoria": "Operacional", "Tipo de Regra": "Dias Úteis APÓS Tarefa Base", "Tarefa Base": "T1 - Briefing com a Equipe", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(copy.deepcopy(st.session_state.df_planilha))
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    # Função requerida: Injeção do Exemplo do Manual na Tabela Real
    def injetar_exemplo_curso():
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Reunião de Kick-off", "Categoria": "Fase 1", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Coleta de Dados", "Categoria": "Fase 1", "Tipo de Regra": "Primeiro dia útil após Tarefa Base", "Tarefa Base": "T1 - Reunião de Kick-off", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T3", "Nome da Tarefa": "Auditoria", "Categoria": "Fase 2", "Tipo de Regra": "Dias Úteis APÓS Tarefa Base", "Tarefa Base": "T2 - Coleta de Dados", "Valor / Dias": 10, "Data Fixa": None},
            {"Código ID": "T4", "Nome da Tarefa": "Pagamento a Fornecedor", "Categoria": "Fase 3", "Tipo de Regra": "Primeira Sexta-feira após Tarefa Base", "Tarefa Base": "T3 - Auditoria", "Valor / Dias": 0, "Data Fixa": None}
        ])
        st.toast("✅ Exemplo de Complexidade Alta Injetado! O motor já recalculou as datas na Aba 2.")

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL 
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ 1. Pilares do Projeto")
    st.session_state.modo_didatico = st.sidebar.toggle("🎓 Assistente Ligado (Modo Aula)", value=st.session_state.modo_didatico, help="Mantém o texto descritivo humano e botões de ajuda ativados.")
    
    base_opcao = st.sidebar.selectbox("📍 Iniciar o Cronograma a partir de:", ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], help="Seta a 'Data Base'. Todas as outras contas partirão deste dia.")
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Escolha o Dia Zero:", value=hoje)

    st.sidebar.markdown(f"**Data Base Computada:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    st.sidebar.header("🛡️ 2. Muros de Proteção")
    ano_corrente = st.sidebar.number_input("Ano de Referência das Contas", min_value=2024, max_value=2030, value=data_base_global.year)
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Desviar de Finais de Semana", value=True),
        "block_holidays": st.sidebar.checkbox("Desviar de Feriados Oficiais", value=True)
    }

    with st.sidebar.expander("🏛️ Injetar Recessos Extras"):
        f_name = st.text_input("Qual o Evento?", placeholder="Ex: Dia do Padroeiro")
        f_date = st.date_input("Qual o Dia?", datetime.date(ano_corrente, 11, 30))
        if st.button("➕ Ensinar ao Motor"):
            if f_name:
                st.session_state.custom_holidays[f_date] = {"nome": f_name, "desc": "Inserido pelo Operador."}
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Folgas Programadas (Dias Avulsos)", value=[])
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO 
    # -------------------------------------------------------------------------
    t1, t2, t3, t4, t5 = st.tabs(st.session_state.theme_config["tab_names"])

    with t1:
        st.subheader("📝 Matriz Lógica de Tarefas e Otimização")
        if st.session_state.modo_didatico:
            st.info("Abaixo você comanda o Cérebro do Sistema. Para cada tarefa, escolha uma **Regra** e referencie uma **Tarefa Base**. Toda alteração aciona um processamento autônomo.")
        
        c1, c2, c3 = st.columns([1, 1, 2])
        if c1.button("↩️ Reverter Planilha (Undo)", disabled=len(st.session_state.historico_planilha)==0):
            st.session_state.df_planilha = st.session_state.historico_planilha.pop(); st.rerun()
        if c2.button("🔢 Corrigir IDs (T1, T2...)", help="Reordena os prefixos lógicos para não gerar confusão de banco de dados."):
            df_temp = st.session_state.df_planilha.copy()
            df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
            salvar_historico(df_temp); st.session_state.df_planilha = df_temp; st.rerun()
        
        # ASSISTENTE WIZARD REQUISITADO NA REGRA 6
        with c3.popover("🤖 Assistente: Criar Tarefa Respondendo Perguntas"):
            st.write("Deixe que eu crio a linha na tabela para você.")
            w_name = st.text_input("Qual o nome da Tarefa?")
            w_base = st.selectbox("Ela ocorre DEPOIS de alguma já existente?", ["Não, independente"] + [f"{r['Código ID']} - {r['Nome da Tarefa']}" for _, r in st.session_state.df_planilha.iterrows() if pd.notna(r["Código ID"])])
            w_rule = st.selectbox("Qual o comportamento temporal?", ["Preciso que pule dias úteis", "Preciso que pule dias corridos", "Tem que ser na Primeira Segunda-feira", "Sempre no Último dia do Mês"])
            w_val = 0
            if "pule" in w_rule: w_val = st.number_input("Quantos dias pular?", min_value=1, value=5)
            
            if st.button("➕ Injetar na Tabela", use_container_width=True):
                if w_name:
                    n_id = f"T{len(st.session_state.df_planilha)+1}"
                    if "Não" in w_base: n_rule = "1º Dia Útil após Data Base"; n_base = ""
                    else: 
                        n_base = w_base
                        if "úteis" in w_rule: n_rule = "Dias Úteis APÓS Tarefa Base"
                        elif "corridos" in w_rule: n_rule = "Dias Corridos APÓS Tarefa Base"
                        elif "Segunda" in w_rule: n_rule = "Primeira Segunda-feira após Tarefa Base"
                        else: n_rule = "Último dia útil do mês da Tarefa Base"
                    
                    nova_linha = pd.DataFrame([{"Código ID": n_id, "Nome da Tarefa": w_name, "Categoria": "Adicionada via Assistente", "Tipo de Regra": n_rule, "Tarefa Base": n_base, "Valor / Dias": w_val, "Data Fixa": None}])
                    st.session_state.df_planilha = pd.concat([st.session_state.df_planilha, nova_linha], ignore_index=True)
                    st.toast("Sucesso! O Computador preencheu a linha na tabela para você.")
                    st.rerun()

        # SANITIZAÇÃO DE DADOS MESTRE
        df_safe = st.session_state.df_planilha.copy()
        if "Data Fixa" in df_safe.columns: df_safe["Data Fixa"] = pd.to_datetime(df_safe["Data Fixa"], errors='coerce')

        opcoes_dependentes_completas = [""] + [f"{r['Código ID']} - {r['Nome da Tarefa']}" for _, r in df_safe.iterrows() if pd.notna(r["Código ID"]) and str(r["Código ID"]).strip() != ""]

        df_edited = st.data_editor(
            df_safe,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código ID", required=True),
                "Nome da Tarefa": st.column_config.TextColumn("Descrição da Entrega/Ação", required=True, width="large"),
                "Categoria": st.column_config.TextColumn("Fase/Grupo"),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Algoritmo Lógico (O Motor de Regras)",
                    options=LISTA_ALGORITMOS,
                    required=True,
                    width="large",
                    help="Escolha o comportamento. A coluna 'Valor/Dias' ou 'Tarefa Base' só será lida se a regra exigir."
                ),
                "Tarefa Base": st.column_config.SelectboxColumn(
                    "Atrelada a qual Tarefa? (Origem)", 
                    options=opcoes_dependentes_completas,
                    width="medium"
                ),
                "Valor / Dias": st.column_config.NumberColumn("Quantos Dias? (Offset)", min_value=0),
                "Data Fixa": st.column_config.DateColumn("Preencher se escolheu 'Data Fixada'", format="DD/MM/YYYY")
            }
        )
        salvar_historico(df_edited); st.session_state.df_planilha = df_edited

        # TRADUTOR SIMULTÂNEO DIDÁTICO
        if st.session_state.modo_didatico:
            st.markdown("##### 🧠 O que o Computador Entendeu (Tradução Simultânea):")
            for _, r in df_edited.iterrows():
                cid = str(r.get('Código ID', '')).strip()
                crule = str(r.get('Tipo de Regra', ''))
                cbase = str(r.get('Tarefa Base', ''))
                cval = r.get('Valor / Dias', 0)
                if not cid: continue
                if crule == "Livre (Onde houver vaga)": trans = f"A Tarefa **{cid}** será jogada em qualquer dia livre do ano."
                elif crule == "1º Dia Útil após Data Base": trans = f"A Tarefa **{cid}** está presa ao começo do projeto (Sempre a Data Base)."
                elif "APÓS Tarefa Base" in crule: trans = f"O sistema vai achar o fim de **{cbase}**, pular **{cval}** dia(s), e alocar a **{cid}**."
                elif "ANTES da Tarefa Base" in crule: trans = f"O sistema fará viagem no tempo para trás: Achará **{cbase}**, recuará **{cval}** dias, e marcará a **{cid}** lá no passado."
                elif "Data Limite MÁXIMA" in crule: trans = f"A Tarefa **{cid}** sofrerá pressão máxima para acabar na Data Base somada a {cval} dias."
                else: trans = f"A Tarefa **{cid}** respeitará a regra de calendário específica '{crule}' após a execução da tarefa {cbase}."
                st.markdown(f'<div class="translation-box">⚙️ Linha {cid}: {trans}</div>', unsafe_allow_html=True)

        st.markdown("---")
        with st.expander("📁 Módulo Didático de Importação de Excel (Carregar Dados Prontos)"):
            if st.session_state.modo_didatico: 
                st.write("**Para que serve?** Carrega uma lista de tarefas inteira de uma vez que você montou no seu MS Excel ou Google Sheets.")
                st.write("**Aviso Importante:** A tabela precisa das seguintes colunas obrigatórias com os nomes EXATAMENTE descritos abaixo, caso contrário, a importação quebra:")
                cols_dict = {"Código ID": "Obrigatório (Texto)", "Nome da Tarefa": "Obrigatório (Texto)", "Tipo de Regra": "Obrigatório (Deve conter um dos nomes de regras exatos)", "Tarefa Base": "Opcional (Texto com o ID ou ID - Nome)", "Valor / Dias": "Opcional (Apenas Número)"}
                st.table(pd.DataFrame(list(cols_dict.items()), columns=["Nome Esperado no Cabeçalho", "Regra de Preenchimento"]))
            uploaded_file = st.file_uploader("Arraste o CSV ou Excel", type=["csv", "xlsx"])
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.session_state.df_planilha = df_up
                    st.success("Tabela Lida com Sucesso!")
                except Exception as e:
                    st.error("Erro na Ingestão. Verifique a tabela de ajuda acima para conferir as colunas exigidas.")

    # =============================================================================
    # MOTOR DE COMPILAÇÃO E VALIDAÇÃO DE PRÉ-CÁLCULO E GRAFOS (V14.0)
    # =============================================================================
    engine_tasks = []
    engine_restrictions = []
    
    # 1. Parsing
    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Nome da Tarefa", "Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]): continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        v_tipo = row.get("Tipo de Regra", "Livre")
        v_base_completa = str(row.get("Tarefa Base", "")).strip()
        v_base = v_base_completa.split(" - ")[0].strip() if " - " in v_base_completa else v_base_completa
        v_val = int(row.get("Valor / Dias", 0)) if pd.notna(row.get("Valor / Dias")) else 0
        v_fixa = row.get("Data Fixa")
        
        if v_tipo == "Data Fixada (Ancorada)" and pd.notna(v_fixa) and v_fixa is not pd.NaT:
            try:
                dt_obj = v_fixa.date() if hasattr(v_fixa, 'date') else v_fixa
                engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": dt_obj}))
            except: pass
        elif v_tipo == "1º Dia Útil após Data Base":
            primeiro_util = cal_mgr.get_next_working_day(data_base_global - datetime.timedelta(days=1), cal_config, manual_dates)
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": primeiro_util}))
        
        elif v_tipo == "Dias Úteis APÓS Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Dias Úteis ANTES da Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset_backwards", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Dias Corridos APÓS Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="calendar_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Dias Corridos ANTES da Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="calendar_day_offset_backwards", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
            
        elif v_tipo == "Primeiro dia útil após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="next_working_day", params={"task_base": v_base, "task_target": t_id}))
        elif v_tipo == "Último dia útil antes da Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="prev_working_day", params={"task_base": v_base, "task_target": t_id}))
            
        elif v_tipo == "Primeira Segunda-feira após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="next_monday", params={"task_base": v_base, "task_target": t_id}))
        elif v_tipo == "Primeira Sexta-feira após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="next_friday", params={"task_base": v_base, "task_target": t_id}))
        elif v_tipo == "Mesmo dia da semana (na próxima semana)" and v_base:
            engine_restrictions.append(Restriction(type="same_weekday_next_week", params={"task_base": v_base, "task_target": t_id}))
            
        elif v_tipo == "Último dia útil do mês da Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="last_working_month", params={"task_base": v_base, "task_target": t_id}))
        elif v_tipo == "1º dia útil do mês seguinte à Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="first_working_next_month", params={"task_base": v_base, "task_target": t_id}))
            
        elif v_tipo == "Data Limite MÁXIMA (Antes de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": data_base_global + datetime.timedelta(days=v_val)}))

    # 2. SANITY CHECK MATEMÁTICO ANTES DE RODAR
    check_ok, chk_msg = sanity_check_dependencies(engine_restrictions, engine_tasks)
    
    if not check_ok:
        status = "INFEASIBLE"
        diagnostico = chk_msg
        sol_dates, alt_cards = {}, []
    else:
        # RUN ENGINE (Apenas se o Sanity Check deu Aval Positivo)
        engine = PurePythonScheduleEngine(cal_mgr, cal_config)
        engine.add_tasks(engine_tasks)
        engine.apply_global_blocks(manual_dates)
        engine.apply_restrictions(engine_restrictions)
        status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        st.subheader("📊 Gráficos Operacionais e Relatório Lógico")
        if status == "SUCCESS":
            if st.session_state.modo_didatico:
                st.success("✅ **Análise Finalizada com Êxito.** O Cérebro da aplicação compilou suas linhas de texto e gerou um plano de vida executável blindado contra férias e feriados.")
                
            # NOVO MAPA VISUAL DE DEPENDÊNCIAS EM ÁRVORE TEXTUAL (Fluxo Gráfico Nativo)
            with st.expander("🌳 O Mapa Gráfico de Dependências e Conexões"):
                st.write("Abaixo o computador desenhou a teia de quem puxa quem. Veja como a arquitetura do seu projeto funciona na prática.")
                # Construção Segura do Diagrama Textual
                grafo = {t.id: [] for t in engine_tasks}
                ids = [t.id for t in engine_tasks]
                for r in engine_restrictions:
                    if hasattr(r, 'params') and "task_base" in r.params and "task_target" in r.params:
                        b = r.params["task_base"]; tg = r.params["task_target"]
                        if b in grafo: grafo[b].append(tg)
                
                # Acha raízes (Nós que ninguém aponta para eles)
                alvos = set()
                for v in grafo.values(): alvos.update(v)
                raizes = [n for n in ids if n not in alvos]
                
                tree_output = "[DATA BASE OFICIAL DO PROJETO]\n"
                def print_tree(node, depth):
                    res = "   " * depth + f" ➔ {node} (Alocado em: {sol_dates[node].strftime('%d/%m')})\n"
                    for child in grafo[node]: res += print_tree(child, depth + 1)
                    return res
                for rt in raizes: tree_output += print_tree(rt, 1)
                
                st.markdown(f'<div class="flow-diagram">{tree_output}</div>', unsafe_allow_html=True)
            
            # GANTT INTERATIVO (Altair)
            st.markdown("### 📈 Visualização do Cronograma ao Longo do Ano (Gantt)")
            gantt_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    gantt_data.append({"Código": t_id, "Tarefa": t_item.name, "Início": d_val.strftime("%Y-%m-%d"), "Fim": (d_val + datetime.timedelta(days=1)).strftime("%Y-%m-%d")})
            
            if gantt_data:
                df_gantt = pd.DataFrame(gantt_data)
                df_gantt['Início'] = pd.to_datetime(df_gantt['Início'])
                df_gantt['Fim'] = pd.to_datetime(df_gantt['Fim'])
                chart = alt.Chart(df_gantt).mark_bar(cornerRadius=3).encode(
                    x=alt.X('Início', title='Linha do Tempo Anual'), x2='Fim',
                    y=alt.Y('Tarefa', sort=alt.EncodingSortField(field="Início", order="ascending")),
                    color=alt.Color('Código', legend=None), tooltip=['Código', 'Tarefa', 'Início']
                ).properties(height=350).interactive()
                st.altair_chart(chart, use_container_width=True)

            st.markdown("### 📥 Documento Consolidado (Tabela Final)")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código ID": t_id, "Tarefa": t_item.name, "Data Final Homologada": f_date}
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0] if not df_edited[df_edited["Código ID"] == t_id].empty else None
                    if row_t is not None:
                        if "Categoria" in row_t: row_data["Categoria"] = row_t["Categoria"]
                        if "Prioridade" in row_t: row_data["Prioridade"] = row_t["Prioridade"]
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                
                txt_report = f"========================================\nRELATÓRIO DO MOTOR DE OTIMIZAÇÃO ({ano_corrente})\n"
                txt_report += f"Raiz de Partida: {data_base_global.strftime('%d/%m/%Y')}\n========================================\n📋 DATAS DEFINITIVAS:\n"
                for r in cronograma_data: txt_report += f"   ➤ Dia {r['Data Final Homologada']} | {r['Código ID']}: {r['Tarefa']}\n"
                
                c1, c2 = st.columns(2)
                c1.download_button(f"📥 Baixar Arquivo Computacional (.CSV)", data=csv_buffer, file_name=f"{st.session_state.export_config['file_name']}.csv", mime="text/csv", use_container_width=True)
                c2.download_button("📝 Baixar Relatório Humano (.TXT)", data=txt_report, file_name="Relatorio_De_Projeto.txt", mime="text/plain", use_container_width=True)

        else:
            st.error("⚠️ **Sistema em Colapso Lógico (Falha de Operação).**")
            st.markdown(f'<div class="alert-box"><b>Diagnóstico Inteligente do Inspetor:</b><br>{diagnostico}</div>', unsafe_allow_html=True)
            if st.session_state.modo_didatico:
                st.info("💡 **DICA DE OURO PARA RESOLVER AGORA:** Volte na Aba 1, encontre o 'Código ID' que o Inspetor Vermelho denunciou acima. Verifique se ele não está apontando para uma Tarefa que não existe, se os dias pulados não acabam virando o ano de dezembro, ou se não há um Ciclo Infinito (A->B, B->A).")

    with t3:
        st.subheader("📅 O Grande Quadro de Planejamento Térmico (Heatmap)")
        
        with st.expander("📌 Adicionar Etiquetas Visuais no Mapa"):
            m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
            m_date = m_col1.date_input("Dia Alvo:", data_base_global)
            m_text = m_col2.text_input("Recado Curto:", placeholder="Ex: Viagem Pessoal")
            m_icon = m_col3.selectbox("Símbolo", ["📌 Alfinete", "⭐ Foco", "✈️ Viagem", "🏖️ Férias", "💰 Pagamento", "🎂 Níver", "🎯 Meta Ouro"])
            if st.button("✏️ Colar Adesivo na Data"):
                if m_text: st.session_state.marcadores_calendario[m_date] = f"{m_icon.split()[0]} {m_text}"; st.rerun()
            if st.session_state.marcadores_calendario:
                for md, txt in st.session_state.marcadores_calendario.items(): st.caption(f"- {md.strftime('%d/%m')}: {txt}")
                if st.button("🗑️ Arrancar Todos Adesivos"): st.session_state.marcadores_calendario = {}; st.rerun()

        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div title="Vazio. Pronto para produzir."><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia Livre</div>
            <div title="A Planilha exigiu uso deste dia!"><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> <b>Entrega Programada</b></div>
            <div title="Carnaval e feriados. Pulo ativado!"><span style="background-color: {st.session_state.theme_config['color_holiday']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado Proibido</div>
            <div title="Os dias que bloqueamos no sistema."><span style="background-color: {st.session_state.theme_config['color_blocked']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Bloqueado/Fechado</div>
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
                                        title_hover = "📍 PONTO ZERO"
                                        cell_class = "day-allocated"
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"🎯 Compromissos Alocados Aqui: {', '.join(t_codes)}"
                                    elif props["is_holiday"]: 
                                        cell_class = "day-holiday"
                                        title_hover = f"🚫 {props['name']} - {props['desc']}"
                                    elif props["is_blocked"] or d_verif in manual_dates: 
                                        cell_class = "day-blocked"
                                        title_hover = "Bloqueado Forçadamente."
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{display_content}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    with t4:
        st.header("📘 O Curso Interativo e Exaustivo (O Manual Vivo)")
        
        st.markdown("<div class='info-box'><b>Você aprende na Prática!</b> Clicando no botão abaixo, as regras teóricas discutidas na documentação a seguir serão coladas na sua Tabela da Aba 1 de forma automática. Assim você pode ver a ciência operando diante dos seus olhos.</div>", unsafe_allow_html=True)
        if st.button("🚀 Carregar o 'Estudo de Caso 1' na Tabela de Operações (Aba 1)"): injetar_exemplo_curso()
            
        MANUAL_SECTIONS = {
            "💡 O Básico: Como a 'Data Base' Salva Vidas?": "A Data Base é o centro gravitacional. \n\n**O que ela resolve?** Imagine 50 tarefas no Excel que começam dia 01/Jan. O Projeto inteiro foi adiado para 01/Fev. Com a Data Base, você muda 1 campo na Barra Lateral, e o computador empurra e readapta 100% das regras da tabela para o novo mês, recalculando em que dia cada Carnaval ou fim de semana do novo mês cairá.",
            "⚙️ O Coração: Tradução dos Novos Algoritmos (Regras)": "**O Passo a Passo de Mestre da Tabela da Aba 1:**\n- **1º Dia Útil após Data Base:** Sempre cole a Tarefa 1 aqui.\n- **Primeira Segunda-feira após Tarefa Base:** O que faz? Se o seu cheque bate num sábado ou quinta, mas a política da empresa diz que toda auditoria só corre às Segundas, você amarra o ID e a máquina fará a Tarefa pular todos os dias até cair na próxima segunda-feira útil!\n- **Último dia útil do mês da Tarefa Base:** Fantástico para gerar folhas de pagamento da Tarefa Original antes do mês virar.",
            "❌ Regras de Segurança (Por que o Sistema grita Erro Lógico?)": "**O que é um Paradoxo (Ou Erro Logístico)?**\nImagine a Regra: A Tarefa 2 deve ocorrer na *Primeira Segunda-Feira* após a Tarefa 1. O motor obedece e joga a T2 lá. Só que você também configurou na barra lateral uma 'Folga de Férias' que bloqueia exatamente aquela Segunda-feira.\n\n**A Regra que evita o Desastre:** O sistema não mente. Se aquela segunda-feira está com os portões fechados na Barra Lateral, ele dispara a sirene e acusa: 'Conflito Lógico'. A sua Regra de 'Primeira Segunda-Feira' bateu numa 'Indisponibilidade Manual'. **Como Resolver:** Você é o humano no controle, apenas mude as Férias, ou diga para a T2 cair na próxima Sexta-feira.",
            "🗂️ A Subida Massiva (Upload do Excel) Explicado": "**Vantagens Absolutas:** Não quer clicar mil vezes? O seu Excel precisa de apenas 3 colunas obrigatórias com as palavras exatas:\n1. `Código ID` (Ex: T1, T2)\n2. `Nome da Tarefa` (Ex: Ligar Ar-Condicionado)\n3. `Tipo de Regra` (Ex: Livre, ou '1º Dia Útil após Data Base'). \nArraste o arquivo na Aba 1, e nós desenharemos o calendário gráfico em 2 segundos."
        }
        
        pesquisa = st.text_input("🔍 Pesquise e Isole um Capítulo de Aula Abaixo:", help="Motor Indexado de Busca.")
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo): st.markdown(conteudo)

    with t5:
        st.header("🎨 5. Centro de Controle (Front-End e Exports)")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Estética Global de Telas")
            st.session_state.theme_config["app_title"] = st.text_input("Nome da Plataforma (H1)", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v14.0"))
            tema_escolhido = st.selectbox("Paleta Segura do Streamlit Cloud", list(THEME_PALETTES.keys()))
            if st.button("🎨 Aplicar Resina de Cor"):
                st.session_state.theme_config["color_primary"] = THEME_PALETTES[tema_escolhido]["primary"]
                st.session_state.theme_config["color_allocated"] = THEME_PALETTES[tema_escolhido]["alloc"]
                st.session_state.theme_config["color_allocated_border"] = THEME_PALETTES[tema_escolhido]["alloc_border"]
                st.toast("Sucesso! O Front-End foi alterado.")
                st.rerun()
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Desenho da Grade HTML inicia por:", options=[("Domingo (EUA/Web)", 6), ("Segunda-Feira", 0)], format_func=lambda x: x[0]) [1]
            
        with c_p2:
            st.subheader("Customização dos CSV/TXT Finais")
            st.session_state.export_config["file_name"] = st.text_input("Nome de Fábrica do Relatório", value=st.session_state.export_config["file_name"])
            st.session_state.export_config["date_format"] = st.selectbox("Mascara de Data para Relatórios", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"])
            st.session_state.export_config["separator"] = st.selectbox("Separador para o Motor do Excel ler certo:", options=[";", ",", "\t"])

        st.divider()
        st.subheader("💾 O Salva-Vidas Master (Persistência Sem BD)")
        st.write("Exporte a fotografia matemática da tela para o seu pendrive e carregue amanhã sem perder nem uma vírgula ou um carimbo amarelo.")
        export_dict = {
            "theme": st.session_state.theme_config, "export": st.session_state.export_config,
            "markers": {d.strftime("%Y-%m-%d"): txt for d, txt in st.session_state.marcadores_calendario.items()},
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button("📦 Baixar Cópia Fiel do Sistema (Arquivo .JSON)", data=json_str, file_name="Minha_Maquina_Virtual_Salva.json", mime="application/json", use_container_width=True)

if __name__ == "__main__":
    main()
