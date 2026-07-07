import datetime
import calendar
import copy
import json
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt # BILIOTECA NATIVA E SEGURA DO STREAMLIT (Substitui o Plotly)

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS (UX/UI ENTERPRISE)
# =============================================================================
st.set_page_config(page_title="Calendário Inteligente PRO v13.0", page_icon="📅", layout="wide", initial_sidebar_state="expanded")

if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A", "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE", "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2", "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Escopo & Tabela", "📊 2. Cronograma & Gantt", "📅 3. Visão do Ano", "📘 4. Curso & Ajuda", "🎨 5. Personalização"],
        "cal_first_weekday": 6 
    }

THEME_PALETTES = {
    "Azul Corporativo": {"primary": "#1E3A8A", "alloc": "#DBEAFE", "alloc_border": "#2563EB"},
    "Verde Operacional": {"primary": "#14532D", "alloc": "#DCFCE7", "alloc_border": "#16A34A"},
    "Roxo Estratégico": {"primary": "#4C1D95", "alloc": "#F3E8FF", "alloc_border": "#7E22CE"}
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
    .flow-diagram {{ background: #f4f4f5; padding: 10px; border-radius: 8px; font-family: monospace; font-size: 13px; color: #1e293b; margin: 10px 0; }}
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
# 3. MOTOR DE FERIADOS RICOS
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
            datetime.date(self.year, 1, 1): {"nome": "Ano Novo", "desc": "Celebração Universal da Confraternização Universal."},
            datetime.date(self.year, 4, 21): {"nome": "Tiradentes", "desc": "Homenagem a Joaquim José da Silva Xavier. (Nacional)"},
            datetime.date(self.year, 5, 1): {"nome": "Dia do Trabalho", "desc": "Homenagem às conquistas dos trabalhadores."},
            datetime.date(self.year, 9, 7): {"nome": "Independência do Brasil", "desc": "Declaração de independência de Portugal em 1822."},
            datetime.date(self.year, 10, 12): {"nome": "Nossa Sra. Aparecida", "desc": "Dia da Padroeira do Brasil."},
            datetime.date(self.year, 10, 28): {"nome": "Dia do Servidor", "desc": "Ponto facultativo aos funcionários públicos."},
            datetime.date(self.year, 11, 2): {"nome": "Finados", "desc": "Dia de memória e homenagens póstumas."},
            datetime.date(self.year, 11, 15): {"nome": "Proclamação da República", "desc": "Fim do Império e início da Era Republicana."},
            datetime.date(self.year, 11, 30): {"nome": "Dia do Evangélico", "desc": "Feriado oficial no Distrito Federal."},
            datetime.date(self.year, 12, 25): {"nome": "Natal", "desc": "Celebração Cristã Universal. (Nacional)"},
            carnaval: {"nome": "Carnaval", "desc": "Ponto Facultativo/Feriado Local."},
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
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL
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
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA
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
            if r.type == "fixed_date" and r.params["task_id"] in alocacao and alocacao[r.params["task_id"]] != self.cal_mgr.date_to_idx(r.params["date"]): return False
            elif r.type == "deadline" and r.params["task_id"] in alocacao:
                idx_atual = alocacao[r.params["task_id"]]
                if r.params.get("before") and idx_atual >= self.cal_mgr.date_to_idx(r.params["before"]): return False
                if r.params.get("after") and idx_atual <= self.cal_mgr.date_to_idx(r.params["after"]): return False
            elif r.type == "dependency" and r.params["task_a"] in alocacao and r.params["task_b"] in alocacao:
                if alocacao[r.params["task_b"]] < alocacao[r.params["task_a"]] + r.params.get("min_gap", 0): return False
            elif r.type == "working_day_offset" and r.params["task_base"] in alocacao and r.params["task_target"] in alocacao:
                if self.cal_mgr.contar_dias_uteis_entre(alocacao[r.params["task_base"]], alocacao[r.params["task_target"]], self.cal_config, self.manual_exclusions) != r.params["offset"]: return False
        return True

    def _avaliar_custo(self, alocacao: Dict[str, int]) -> int:
        return sum(50 for idx in alocacao.values() if self.cal_mgr.get_day_properties(idx, self.cal_config)["is_weekend"] or self.cal_mgr.get_day_properties(idx, self.cal_config)["is_holiday"])

    def solve(self) -> Tuple[str, Dict[str, datetime.date], List[Dict[str, Any]], str]:
        solucao_otima = {}; melhor_custo = float('inf')
        task_ids = [t.id for t in self.tasks]
        if not task_ids: return "SUCCESS", {}, [], ""
        horizonte_busca = min(220, self.cal_mgr.total_days)

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
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Data alocada perfeitamente. O algoritmo atendeu todas as amarrações do projeto."} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        if len(self.restrictions) == 0: return "Você forçou uma Tarefa de Data Fixa que cai em um dia de feriado ou bloqueado."
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
                tipo = temp_rest.type; alvo = temp_rest.params.get("task_id") or temp_rest.params.get("task_target")
                if tipo == "deadline": return f"A regra de **Data Limite** para a Tarefa **{alvo}** estourou o tempo. Não há dias úteis suficientes para concluí-la antes do prazo."
                if tipo == "working_day_offset": return f"Os saltos de **Dias Úteis** a partir da Tarefa **{alvo}** ultrapassaram o tamanho da Data Limite. **Como resolver:** Diminua o prazo de Dias Úteis da Tarefa {alvo}."
                return f"Conflito logístico na tarefa **{alvo}**."
        self.restrictions = original_restrictions
        return "Conflito severo: Muitos bloqueios inseridos e faltou espaço no calendário."


# =============================================================================
# 7. INTERFACE INTERATIVA DO USUÁRIO E WIZARD (V13.0 MASTER CLASS)
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Enterprise Edition: Planejamento Logístico Totalmente Orientado a Eventos")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # GESTÃO DE ESTADO SEGURO E WIZARD INICIAL
    if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "marcadores_calendario" not in st.session_state: st.session_state.marcadores_calendario = {}
    if "export_config" not in st.session_state: st.session_state.export_config = {"file_name": "Planejamento_Oficial", "date_format": "%d/%m/%Y", "separator": ","}
    if "modo_didatico" not in st.session_state: st.session_state.modo_didatico = True

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Briefing com a Equipe", "Categoria": "Gestão", "Prioridade": "Alta", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Produção do Relatório Final", "Categoria": "Operacional", "Prioridade": "Média", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1 - Briefing com a Equipe", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(copy.deepcopy(st.session_state.df_planilha))
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    def force_inject_example():
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Reunião de Kick-off", "Categoria": "Etapa 1", "Prioridade": "Alta", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Análise de Riscos e Permissões", "Categoria": "Etapa 1", "Prioridade": "Média", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1 - Reunião de Kick-off", "Valor / Dias": 3, "Data Fixa": None},
            {"Código ID": "T3", "Nome da Tarefa": "Execução da Homologação", "Categoria": "Etapa 2", "Prioridade": "Alta", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T2 - Análise de Riscos e Permissões", "Valor / Dias": 10, "Data Fixa": None}
        ])
        st.toast("✅ Exemplo Didático Injetado! Vá para a Aba 2 e veja a Mágica.")

    # BARRA LATERAL (CONFIGURAÇÕES GLOBAIS COM CHECKLIST)
    st.sidebar.header("⚙️ 1. Parâmetros do Motor")
    st.session_state.modo_didatico = st.sidebar.toggle("🎓 Modo 'Me Explique Tudo'", value=st.session_state.modo_didatico, help="Deixe ativado para ler as caixas azuis de dicas de tela.")
    
    base_opcao = st.sidebar.selectbox("📍 Data Base (Início do Projeto):", ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], help="A 'Data Base' é a âncora do seu projeto. O Motor usará isso como Dia 1.")
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Escolha o Dia:", value=hoje)

    st.sidebar.markdown(f"**Calculando a partir de:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    st.sidebar.header("🛡️ 2. Bloqueios Temporais")
    ano_corrente = st.sidebar.number_input("Ano de Referência", min_value=2024, max_value=2030, value=data_base_global.year, help="O sistema calculará Páscoa, Carnaval e feriados do ano preenchido aqui.")
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Ocultar Finais de Semana", value=True, help="O Motor nunca agendará prazos em fins de semana se isso estiver ativo."),
        "block_holidays": st.sidebar.checkbox("Pular Feriados Oficiais", value=True, help="Evita datas como Natal e Independência.")
    }

    with st.sidebar.expander("🏛️ Injetar Feriados Especiais"):
        if st.session_state.modo_didatico: st.caption("Para evitar marcar prazos em dias como Padroeiras Locais.")
        f_name = st.text_input("Nome", placeholder="Ex: Dia do Padroeiro")
        f_date = st.date_input("Data Exata", datetime.date(ano_corrente, 11, 30))
        if st.button("➕ Gravar Feriado", help="Após gravar, o cálculo das tabelas refaz a matemática automaticamente pulando este dia."):
            if f_name:
                st.session_state.custom_holidays[f_date] = {"nome": f_name, "desc": "Inserido manualmente na Barra Lateral."}
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Férias/Dias Inoperantes (Time)", value=[], help="A Equipe vai viajar e parar de trabalhar nestes dias? Selecione-os e o motor pulará todos eles.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    st.sidebar.divider()
    st.sidebar.markdown("### ✅ Checklist Operacional")
    st.sidebar.checkbox("Data de Partida Cadastrada", value=True, disabled=True)
    st.sidebar.checkbox("Feriados Analisados", value=True, disabled=True)
    st.sidebar.checkbox("Tabela de Cronograma Possui Linhas", value=len(st.session_state.df_planilha) > 0, disabled=True)

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # ABAS DA APLICAÇÃO
    t1, t2, t3, t4, t5 = st.tabs(st.session_state.theme_config["tab_names"])

    with t1:
        st.subheader("📝 Planilha e Engine de Cronograma")
        if st.session_state.modo_didatico:
            st.info("👉 **A Tabela Abaixo é Viva.** Cada alteração que você digitar refaz toda a matemática de fluxo do seu projeto na Aba 2 instantaneamente. Dica: Para deletar, clique na célula cinza na margem esquerda da tabela e aperte DELETE.")
        
        with st.popover("💡 O que cada 'Tipo de Regra' faz na tabela? (Ajuda Visual Detalhada)"):
            st.markdown("""
            A coluna **Tipo de Regra** garante precisão.
            * **Livre:** Deixe o computador achar qualquer dia no ano e alocar.
            * **Data Fixada:** Cuidado com essa. Você impõe a data exata usando a coluna de *Data Fixa*. Se cair num domingo, apita erro!
            * **1º Dia Útil após Data Base:** A forma mais garantida de começar a primeira linha do projeto. Puxa a data configurada na Barra Lateral e não foge disso.
            * **Dias Úteis após Tarefa Base:** A Regra Suprema (Cadeia Ouro). Você diz que a tarefa B deve aguardar a aprovação da Tarefa A por 5 dias. Assim que a Tarefa A terminar, o cronômetro começa a rodar descontando sábados, domingos e os feriados.
            * **Data Limite (Antes de/Após de):** Força o Motor a jogar a Tarefa em um espaço menor que X dias a partir de hoje. É uma trava de segurança severa.
            """)
        
        c1, c2, c3 = st.columns([1, 1, 2])
        if c1.button("↩️ Desfazer Ação (Histórico)", disabled=len(st.session_state.historico_planilha)==0, help="Desfaz um corte ou alteração que você acabou de cometer."):
            st.session_state.df_planilha = st.session_state.historico_planilha.pop(); st.rerun()
        if c2.button("🔢 Formatar IDs em Ordem", help="Reescreve a Coluna de Códigos com nomes sequenciais (T1, T2...)."):
            df_temp = st.session_state.df_planilha.copy()
            df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
            salvar_historico(df_temp); st.session_state.df_planilha = df_temp; st.rerun()
        
        # SANITIZAÇÃO DE DADOS MESTRE (O SEGREDO DA RESOLUÇÃO DO ERRO DO STREAMLIT 13.0)
        df_safe = st.session_state.df_planilha.copy()
        if "Data Fixa" in df_safe.columns: 
            # A conversão para datetime64[ns] previne o erro nativo do PyArrow com NaT
            df_safe["Data Fixa"] = pd.to_datetime(df_safe["Data Fixa"], errors='coerce')

        # LISTA INTELIGENTE DE TAREFAS BASE FORMATADAS
        opcoes_dependentes_completas = [""] + [f"{r['Código ID']} - {r['Nome da Tarefa']}" for _, r in df_safe.iterrows() if pd.notna(r["Código ID"]) and str(r["Código ID"]).strip() != ""]

        df_edited = st.data_editor(
            df_safe,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("ID", required=True, help="O identificador matemático da tarefa."),
                "Nome da Tarefa": st.column_config.TextColumn("Descrição da Entrega/Ação", required=True, width="large", help="Exemplo: Fazer relatório trimestral."),
                "Categoria": st.column_config.TextColumn("Fase/Categoria"),
                "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=["Alta", "Média", "Baixa"]),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Qual Algoritmo Lógico usar?",
                    options=["Livre", "Data Fixada", "1º Dia Útil após Data Base", "Dias Úteis após Tarefa Base", "Dias Úteis após Data Base", "Data Limite (Antes de)", "Data Limite (Após de)"],
                    required=True,
                    help="Leia as ajudas detalhadas no botão 'O que cada regra faz' acima da tabela."
                ),
                "Tarefa Base": st.column_config.SelectboxColumn(
                    "Ela depende de qual Tarefa?", 
                    options=opcoes_dependentes_completas,
                    help="EVOLUÇÃO: Ao invés de você digitar 'T1' correndo risco de errar, clique aqui e selecione 'T1 - Briefing'."
                ),
                "Valor / Dias": st.column_config.NumberColumn("Quantos Dias?", min_value=0, help="O número de pulos temporais do Algoritmo. (Ex: 10 dias úteis)."),
                "Data Fixa": st.column_config.DateColumn("Preencher se escolheu 'Data Fixada'", format="DD/MM/YYYY", help="Força uma data a contra-gosto.")
            }
        )
        salvar_historico(df_edited); st.session_state.df_planilha = df_edited

        st.markdown("---")
        with st.expander("📁 Subir seu Próprio Arquivo Excel Completo (Carregar Dados Prontos)"):
            if st.session_state.modo_didatico: 
                st.write("**O que essa função faz?** Apaga a matriz da tela e substitui com os dados limpos vindos do seu pendrive ou Excel.")
                st.write("**O que é obrigatório no Excel:** Você deve manter o cabeçalho idêntico à nossa tabela (Ex: Uma coluna precisa se chamar exatamente `Código ID`, outra `Nome da Tarefa` e a `Tipo de Regra`).")
            uploaded_file = st.file_uploader("Arraste e solte o CSV ou Excel", type=["csv", "xlsx"])
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.session_state.df_planilha = df_up
                    st.success("Tabela Importada e Compilada!")
                except Exception as e:
                    st.error("A tabela não subiu corretamente. Você alterou os cabeçalhos do modelo padrão?")

    # =============================================================================
    # MOTOR LÓGICO E INTERPRETAÇÃO DOS DADOS HÍBRIDOS DA PLANILHA PARA A CPU
    # =============================================================================
    engine_tasks = []
    engine_restrictions = list(st.session_state.restrictions_manuais)
    fluxo_didatico = [] # Gravação visual de como a matemática pensa

    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Nome da Tarefa", "Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]): continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        v_tipo = row.get("Tipo de Regra", "Livre")
        v_base_completa = str(row.get("Tarefa Base", "")).strip()
        # Corta inteligentemente o 'T1 - Briefing' e deixa apenas 'T1' pro cérebro do cálculo
        v_base = v_base_completa.split(" - ")[0].strip() if " - " in v_base_completa else v_base_completa
        
        v_val = int(row.get("Valor / Dias", 0)) if pd.notna(row.get("Valor / Dias")) else 0
        v_fixa = row.get("Data Fixa")
        
        # Mapeamento do Cérebro da Tabela (Human -> Machine)
        if v_tipo == "Data Fixada" and pd.notna(v_fixa) and v_fixa is not pd.NaT:
            try:
                dt_obj = v_fixa.date() if hasattr(v_fixa, 'date') else v_fixa
                engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": dt_obj}))
                fluxo_didatico.append(f"🔒 A Tarefa {t_id} foi cravada à força para a data {dt_obj.strftime('%d/%m/%Y')}.")
            except: pass
        elif v_tipo == "1º Dia Útil após Data Base":
            primeiro_util = cal_mgr.get_next_working_day(data_base_global - datetime.timedelta(days=1), cal_config, manual_dates)
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": primeiro_util}))
            fluxo_didatico.append(f"🎯 O Computador encontrou que o Dia Útil Zero livre do ano é {primeiro_util.strftime('%d/%m/%Y')} e colou a Tarefa {t_id} lá.")
        elif v_tipo == "Dias Úteis após Tarefa Base" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
            fluxo_didatico.append(f"🔗 TAREFAS AMARRADAS: A Tarefa {t_id} só ocorrerá exatos {v_val} dias ÚTEIS pulados a partir do dia em que {v_base} for encerrada.")
        elif v_tipo == "Dias Úteis após Data Base":
            alvo_data = data_base_global
            dias_uteis_pulados = 0
            while dias_uteis_pulados < v_val:
                alvo_data += datetime.timedelta(days=1)
                p = cal_mgr.get_day_properties(cal_mgr.date_to_idx(alvo_data), cal_config)
                if not p["is_blocked"] and alvo_data not in manual_dates: dias_uteis_pulados += 1
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": alvo_data}))
            fluxo_didatico.append(f"A Tarefa {t_id} foi disparada {v_val} dias de trabalho longos a partir da Data Base.")
        elif v_tipo == "Data Limite (Antes de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": data_base_global + datetime.timedelta(days=v_val)}))
        elif v_tipo == "Data Limite (Após de)":
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "after": data_base_global + datetime.timedelta(days=v_val)}))

    # RUN DO MOTOR EM ALTA VELOCIDADE (STREAMLIT BACKTRACKING)
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        st.subheader("📊 Relatórios e Cronograma de Projetos (Gantt)")
        if status == "SUCCESS":
            if st.session_state.modo_didatico:
                st.success("✅ **Fórmula Matemática Aprovada.** Seu Fluxo Operacional obedeceu às leis de feriados e tem espaço físico no ano corrente.")
                
            with st.expander("🧐 Como o computador pensou? (Log de Rastreabilidade Lógica)"):
                st.markdown("<p style='font-size:12px; color:#4B5563;'>Veja exatamente como cada regra escrita no Excel foi convertida e avaliada pelos satélites operacionais.</p>", unsafe_allow_html=True)
                for f_log in fluxo_didatico:
                    st.markdown(f'<div class="flow-diagram">➔ {f_log}</div>', unsafe_allow_html=True)
            
            # GANTT INTERATIVO DA TIMELINE (Substituído Plotly por Altair para Zero-Dependência Externa e Robustez Total - V13.0)
            st.markdown("### 📈 Visualização Timeline Interativa (Gantt)")
            gantt_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    # Preparando dados para o Altair (Início e Fim fictícios de 1 dia para gerar a barra)
                    gantt_data.append({
                        "Código": t_id, 
                        "Tarefa": t_item.name, 
                        "Início": d_val.strftime("%Y-%m-%d"), 
                        "Fim": (d_val + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                    })
            
            if gantt_data:
                df_gantt = pd.DataFrame(gantt_data)
                df_gantt['Início'] = pd.to_datetime(df_gantt['Início'])
                df_gantt['Fim'] = pd.to_datetime(df_gantt['Fim'])
                
                # Gráfico de Gantt Nativo e Seguro (Altair)
                chart = alt.Chart(df_gantt).mark_bar().encode(
                    x=alt.X('Início', title='Linha do Tempo (Dias do Ano)'),
                    x2='Fim',
                    y=alt.Y('Tarefa', sort=alt.EncodingSortField(field="Início", order="ascending"), title='Ordem de Atividades'),
                    color=alt.Color('Código', legend=None),
                    tooltip=['Código', 'Tarefa', 'Início']
                ).properties(
                    height=300
                ).interactive()
                st.altair_chart(chart, use_container_width=True)

            st.markdown("### 📥 Tabela Consolidada para Exportação (Final)")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código ID": t_id, "Tarefa": t_item.name, "Data Homologada": f_date}
                    
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0]
                    if "Categoria" in row_t: row_data["Categoria"] = row_t["Categoria"]
                    if "Prioridade" in row_t: row_data["Prioridade"] = row_t["Prioridade"]
                    
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                
                txt_report = f"========================================\nDOSSIÊ DE PLANEJAMENTO ({ano_corrente})\n"
                txt_report += f"Relatório Gerado com Data Base: {data_base_global.strftime('%d/%m/%Y')}\n========================================\n📋 AÇÕES CALCULADAS:\n"
                for r in cronograma_data: txt_report += f"   ➤ Dia {r['Data Homologada']} | {r['Código ID']}: {r['Tarefa']}\n"
                
                c1, c2 = st.columns(2)
                c1.download_button(f"📥 Exportar Planilha Bruta (.CSV)", data=csv_buffer, file_name=f"{st.session_state.export_config['file_name']}.csv", mime="text/csv", use_container_width=True)
                c2.download_button("📝 Exportar Resumo Visual (Texto Simples .TXT)", data=txt_report, file_name="Relatorio_De_Projeto.txt", mime="text/plain", use_container_width=True)

        else:
            st.error("⚠️ **O Computador Declarou Paradoxo Lógico! Suas regras colidem.**")
            st.markdown(f'<div class="alert-box"><b>O que explodiu os limites da matemática?</b><br>{diagnostico}</div>', unsafe_allow_html=True)
            if st.session_state.modo_didatico:
                st.warning("**O que eu faço agora para consertar?** \nVá na Planilha. Alguma tarefa está com 'Dias Úteis' acima de 60? Diminua o número. As férias e finais de semana e as correntes matemáticas excederam as margens reais do ano que estamos vivendo.")

    with t3:
        st.subheader("📅 O Grande Quadro de Planejamento Térmico (Heatmap)")
        
        with st.expander("📌 Inserir Rótulos Didáticos e Visuais na Matriz"):
            st.write("Coloque adesivos virtuais na tela para ajudar a lembrar a equipe durante a apresentação da tela. (Esses adesivos não interferem no sistema de contas de datas).")
            m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
            m_date = m_col1.date_input("Escolha o dia Exato:", data_base_global, help="Quando o adesivo vai ficar?")
            m_text = m_col2.text_input("Escreva o Lembrete Curtinho:", placeholder="Ex: Viagem Pessoal")
            m_icon = m_col3.selectbox("Escolha um Emoji", ["📌 Alfinete", "⭐ Favorito", "✈️ Viagem", "🏖️ Férias", "💰 Pagamento", "🎂 Aniversário", "🎯 Meta Final"])
            if st.button("✏️ Colar Carimbo", help="Aperte e a página dará um refresh desenhando o ícone."):
                if m_text: st.session_state.marcadores_calendario[m_date] = f"{m_icon.split()[0]} {m_text}"; st.rerun()
            if st.session_state.marcadores_calendario:
                for md, txt in st.session_state.marcadores_calendario.items(): st.caption(f"- {md.strftime('%d/%m')}: {txt}")
                if st.button("🗑️ Arrancar Todos os Marcadores Manuais"): st.session_state.marcadores_calendario = {}; st.rerun()

        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div title="Dia para o sistema pular e trabalhar."><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia Livre</div>
            <div title="Neste dia bate uma entrega crucial!"><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> <b>Entrega Programada</b></div>
            <div title="Carnaval e feriados. Pula!"><span style="background-color: {st.session_state.theme_config['color_holiday']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado Proibido</div>
            <div title="Os finais de semana que bloqueamos no sistema."><span style="background-color: {st.session_state.theme_config['color_blocked']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Bloqueado/Fim de Semana</div>
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
                                        title_hover = "📍 ESSE É O DIA ZERO: A Data Base do Motor. Tudo nasce a partir dela se a tabela mandar."
                                        cell_class = "day-allocated"
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"🎯 Compromissos Alocados: {', '.join(t_codes)}"
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
        st.header("📘 O Grande Livro Didático de Planejamento (Curso Rápido)")
        
        # O BOTÃO MÁGICO DO CURSO INTERATIVO (CARREGAR EXEMPLO REAL)
        st.info("💡 **Aprenda na Prática:** Não quer ler? Clique no botão abaixo e a aplicação vai preencher um projeto exemplo na Aba 1 de preenchimento para você olhar as fórmulas.")
        if st.button("✨ Carregar Exemplo do Tutorial 1 diretamente na Aba 1"):
            force_inject_example()
            
        MANUAL_SECTIONS = {
            "💡 Como funciona a 'Data Base'? (Ponto de Partida)": "A Data Base é a âncora principal do sistema. \n\n**Como funciona?** O dia que você coloca na Barra Lateral, serve como base de contagem para o primeiro cálculo do motor.\n**Para quem:** Projetos grandes que atrasaram inteiros e você só precisa mudar a data de Início para todo o resto do ano ser empurrado para frente simultaneamente.",
            "⚙️ O Coração: A Coluna de 'Tipo de Regra' na Tabela": "O sistema não deixa você inventar datas. Você diz regras de dias úteis e o sistema faz a conta de calendário que uma calculadora não faz. \n\n**O Passo a Passo de Mestre:**\n1. Na sua linha final do projeto, coloque a Regra 'Dias Úteis após Tarefa Base'.\n2. Na Coluna 'Tarefa Base', clique e aponte para qual fase do projeto ela depende.\n3. Digite 15 (para 15 dias uteis). O sistema engole os finais de semana e resolve o resto.",
            "❌ Erro Vermelho de Paradoxo de Dados. O que é?": "**Causa do Erro:** Quando o Computador descobre que você ordenou ele espremer 10 dias úteis de trabalho dentro de um espaço na agenda que só tinham 2 dias sem feriado. Ele acusa na Caixa vermelha quem é o Tarefa que está quebrando as leis da física matemática. Para consertar, vá na Aba 1 e diminua o prazo que você preencheu nela.",
            "🗂️ Tem Upload de Excel? Quais os Formatos permitidos?": "SIM! É a melhor função para times corporativos! Se o seu chefe mandou um arquivo .CSV gigante com todas as tarefas. Você entra na Aba 1, e arrasta ele para a Caixa Pontilhada. O sistema lê e traduz os dados instantaneamente. Mas atenção: O arquivo DEVE possuir cabeçalhos idênticos aos da nossa tabela (Ex: 'Nome da Tarefa', 'Código ID')."
        }
        
        pesquisa = st.text_input("🔍 Pesquise e Filtre os Capítulos do Curso (Ex: 'Planilha', 'Erro'):", help="Escreva o que não entendeu. O buscador fecha o manual e deixa apenas o tópico correto aberto para leitura.")
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo): st.markdown(conteudo)

    with t5:
        st.header("🎨 5. Oficina de Customização e Cores do App")
        st.info("Aqui a aparência do software fica com a sua cara e com a cara da sua empresa. Sem precisar mexer numa gota de código fonte.")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Estética da Tela (Front-end)")
            st.session_state.theme_config["app_title"] = st.text_input("Nome do Sistema (Top Level)", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v13.0"), help="O Letreiro Gigante lá no topo muda se você trocar essa caixa.")
            
            tema_escolhido = st.selectbox("Escolha um Padrão de Cor Profissional", list(THEME_PALETTES.keys()), help="Paletas seguras homologadas e sem uso de JS assíncrono para garantir fluidez na web.")
            if st.button("🎨 Disparar Tema em Tudo"):
                st.session_state.theme_config["color_primary"] = THEME_PALETTES[tema_escolhido]["primary"]
                st.session_state.theme_config["color_allocated"] = THEME_PALETTES[tema_escolhido]["alloc"]
                st.session_state.theme_config["color_allocated_border"] = THEME_PALETTES[tema_escolhido]["alloc_border"]
                st.toast("Sucesso! Tema Acoplado e Persistente.")
                st.rerun()
            
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Na Grade de Desenho do Calendário, a sua semana começa no...", options=[("Domingo (Recomendado)", 6), ("Segunda-Feira", 0)], format_func=lambda x: x[0], help="Muda a ordenação estritamente visual da matriz HTML.") [1]
            
        with c_p2:
            st.subheader("Módulo de Exportação do Dossiê CSV")
            st.session_state.export_config["file_name"] = st.text_input("Prefixo de Relatórios do Computador", value=st.session_state.export_config["file_name"], help="Este nome estará no Download da aba 2.")
            st.session_state.export_config["date_format"] = st.selectbox("Formato de Datas nos Relatórios", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"], help="DD/MM/AAAA é o padrão para o Brasil.")
            st.session_state.export_config["separator"] = st.selectbox("Como o arquivo de Excel Separa as colunas?", options=[";", ",", "\t"], help="Trocar Virgula por Ponto-e-Vírgula é a melhor solução quando você baixar a planilha e ela vier toda quebrada.")

        st.divider()
        st.subheader("💾 O Salva-Vidas Oficial (Import e Backup das Configurações de Máquina)")
        st.write("Aperte o botão para baixar esse arquivo 'JSON'. Amanhã, quando subir para este ambiente de volta, ele carrega tudo que ficou esquecido em sessão na memória do navegador e restabelece suas cores exatas.")
        
        export_dict = {
            "theme": st.session_state.theme_config,
            "export": st.session_state.export_config,
            "markers": {d.strftime("%Y-%m-%d"): txt for d, txt in st.session_state.marcadores_calendario.items()},
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button(label="📦 Gerar Super Backup do Sistema Operacional (.JSON)", data=json_str, file_name="Projeto_Calendario_Salvo.json", mime="application/json", use_container_width=True, help="Esse arquivo empacota as matrizes e regras matemáticas no formato que o Streamlit as entende sem compressão com perdas.")

if __name__ == "__main__":
    main()
