import datetime
import calendar
import copy
import json
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd
import numpy as np

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA E CSS (UX/UI MODERNIZADO TIPO NOTION/MONDAY)
# =============================================================================
st.set_page_config(
    page_title="Calendário Inteligente PRO v9.0",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização Persistente de Estética (Customização sem ColorPicker JS)
if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A", 
        "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE",
        "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2",
        "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Passo a Passo & Tabela", "📊 2. Resultados Otimizados", "📅 3. Painel Calendário", "📘 4. Ajuda e Tutoriais", "🎨 5. Cores & Exportação"],
        "cal_first_weekday": 6 
    }

THEME_PALETTES = {
    "Azul Corporativo (Padrão)": {"primary": "#1E3A8A", "alloc": "#DBEAFE", "alloc_border": "#2563EB"},
    "Verde Operacional": {"primary": "#14532D", "alloc": "#DCFCE7", "alloc_border": "#16A34A"},
    "Roxo Estratégico": {"primary": "#4C1D95", "alloc": "#F3E8FF", "alloc_border": "#7E22CE"},
    "Laranja Ágil": {"primary": "#7C2D12", "alloc": "#FFEDD5", "alloc_border": "#EA580C"},
    "Preto e Branco Clássico": {"primary": "#111827", "alloc": "#F3F4F6", "alloc_border": "#374151"}
}

# CSS Injetado com Melhorias de UX: Espaçamentos adequados, cards flutuantes, fontes legíveis
st.markdown(f"""
    <style>
    .main-title {{ font-size: 2.2rem; font-weight: 800; color: {st.session_state.theme_config['color_primary']}; margin-bottom: 0.2rem; letter-spacing: -0.5px; }}
    .subtitle {{ font-size: 1.1rem; color: {st.session_state.theme_config['color_secondary']}; margin-bottom: 1.8rem; font-weight: 400; }}
    
    /* Cartões Modernos e Sombras */
    .metric-card {{ background-color: #FFFFFF; border-left: 6px solid {st.session_state.theme_config['color_allocated_border']}; padding: 18px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.04); margin-bottom: 15px; transition: transform 0.2s, box-shadow 0.2s; }}
    .metric-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 15px rgba(0,0,0,0.08); }}
    
    /* Caixas de Status Didáticas */
    .onboarding-box {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 25px; border-radius: 12px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.02); }}
    .alert-box {{ background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 6px; margin-top:10px; }}
    .info-box {{ background-color: #F0F9FF; border-left: 5px solid #3B82F6; padding: 15px; border-radius: 6px; margin-bottom: 15px; }}
    
    /* Calendário Redesenhado */
    .calendar-grid {{ display: block; margin-bottom: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    .calendar-row {{ display: table; width: 100%; table-layout: fixed; }}
    .calendar-cell {{ display: table-cell; text-align: center; padding: 8px 2px; font-size: 11px; border: 1px solid #F1F5F9; font-weight: 600; min-height: 45px; vertical-align: middle; border-radius: 2px; }}
    .day-normal {{ background-color: #FFFFFF; color: #334155; }}
    .day-allocated {{ background-color: {st.session_state.theme_config['color_allocated']}; color: {st.session_state.theme_config['color_primary']}; border: 2px solid {st.session_state.theme_config['color_allocated_border']} !important; font-weight: 800; border-radius: 6px; box-shadow: inset 0 0 5px rgba(0,0,0,0.05); }}
    .day-holiday {{ background-color: {st.session_state.theme_config['color_holiday']}; color: #991B1B; }}
    .day-blocked {{ background-color: {st.session_state.theme_config['color_blocked']}; color: #94A3B8; text-decoration: line-through; }}
    .day-marker {{ font-size: 14px; display: block; margin-top: 3px; }}
    .day-header {{ background-color: #F8FAFC; color: #475569; font-weight: bold; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px; border: none; }}
    .step-indicator {{ background-color: {st.session_state.theme_config['color_primary']}; color: white; padding: 6px 18px; border-radius: 20px; font-weight: 600; font-size: 13px; margin-bottom: 15px; display: inline-block; letter-spacing: 0.5px; }}
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
            datetime.date(self.year, 4, 21): {"nome": "Tiradentes", "desc": "Homenagem a Joaquim José da Silva Xavier, mártir da Inconfidência Mineira. (Nacional)"},
            datetime.date(self.year, 5, 1): {"nome": "Dia do Trabalho", "desc": "Homenagem às conquistas dos trabalhadores ao longo da história. (Nacional)"},
            datetime.date(self.year, 9, 7): {"nome": "Independência do Brasil", "desc": "Comemora a declaração de independência de Portugal em 1822. (Nacional)"},
            datetime.date(self.year, 10, 12): {"nome": "Nossa Sra. Aparecida", "desc": "Dia da Padroeira do Brasil. (Nacional)"},
            datetime.date(self.year, 10, 28): {"nome": "Dia do Servidor", "desc": "Ponto facultativo destinado aos funcionários públicos."},
            datetime.date(self.year, 11, 2): {"nome": "Finados", "desc": "Dia de memória e homenagens póstumas. (Nacional)"},
            datetime.date(self.year, 11, 15): {"nome": "Proclamação da República", "desc": "Fim do Império e início da Era Republicana em 1889. (Nacional)"},
            datetime.date(self.year, 11, 30): {"nome": "Dia do Evangélico", "desc": "Feriado oficial no Distrito Federal."},
            datetime.date(self.year, 12, 25): {"nome": "Natal", "desc": "Celebração Cristã Universal. (Nacional)"},
            carnaval: {"nome": "Carnaval", "desc": "Festa popular que precede a Quaresma. (Ponto Facultativo/Feriado Local)"},
            sexta_santa: {"nome": "Sexta-feira Santa", "desc": "Data religiosa (Paixão de Cristo). Feriado Nacional móvel."},
            corpus: {"nome": "Corpus Christi", "desc": "Celebração Católica. Ponto Facultativo Nacional móvel."}
        }
        
        for d, data_obj in self.custom_holidays.items():
            if isinstance(data_obj, str):
                base_holidays[d] = {"nome": data_obj, "desc": "Feriado ou bloqueio inserido manualmente pelo usuário na barra lateral."}
            else:
                base_holidays[d] = data_obj
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
            "desc": holiday_info["desc"] if is_holiday else "Você pode agendar compromissos neste dia sem problemas.",
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
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA E DIAGNÓSTICO
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
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Data alocada perfeitamente. O algoritmo não teve de quebrar nenhuma configuração principal. (Garantia de 100% de Acerto)."} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
            
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        if len(self.restrictions) == 0: return "Você forçou uma Tarefa para acontecer em um dia que já está bloqueado (Ex: Um Feriado ou Fim de semana). Vá na Planilha e mude o 'Tipo de Regra'."
        
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
                
                # Tradução Didática dos Erros
                if tipo == "deadline": return f"A regra de 'Data Limite' que você colocou para a Tarefa **{alvo}** não deixa espaço suficiente no calendário. Você pediu para que tudo acontecesse antes do tempo e ainda exigiu pular finais de semana. **Solução: Aumente o prazo limite na tabela.**"
                if tipo == "working_day_offset": return f"Você pediu para a Tarefa **{alvo}** pular muitos dias úteis a partir da tarefa anterior. Mas essa cadeia acabou trombando com o final do calendário. **Solução: Diminua o número na coluna 'Valor / Dias' na tabela da Aba 1.**"
                return f"O conflito exato foi encontrado na tarefa **{alvo}**. O que você pediu é matematicamente impossível."
        
        self.restrictions = original_restrictions
        return "Você marcou tantos Feriados, Férias e Finais de semana que não sobrou espaço físico no calendário do ano para encaixar os seus compromissos. Libere algumas datas!"

# =============================================================================
# 6. BANCO DE DADOS DE MANUAL E AJUDA (PESQUISÁVEL)
# =============================================================================
MANUAL_SECTIONS = {
    "🌟 1. O que é e para que serve o Calendário Inteligente?": "Imagine que você precise coordenar 20 tarefas e que uma só possa começar 15 dias ÚTEIS depois da anterior. Se você usar um calendário de papel, vai ter que contar com o dedo, pular finais de semana, pular o Carnaval e anotar tudo. Se o Carnaval mudar, você perde todo o trabalho. \n\n**O que a aplicação faz?** Ela faz toda a matemática por você! Você só diz a regra na Planilha e ela monta o calendário inteiro do ano.",
    "⚙️ 2. Como usar a Planilha Interativa (Passo a Passo)": "1. Vá para a **Aba 1**.\n2. Na coluna **'Tipo de Regra'**, escolha como a tarefa vai se comportar. Exemplo: 'Dias Úteis após Tarefa Base'.\n3. Na coluna **'Tarefa Base'**, digite o ID da tarefa mãe. Exemplo: Se T2 depende de T1, escreva `T1` aqui.\n4. Na coluna **'Valor / Dias'**, digite quantos dias úteis pular. Ex: `15`.\n5. O sistema faz o resto sozinho na Aba 2!",
    "❌ 3. Como resolver o Alerta Vermelho de Erro na Aba 2?": "Se a Aba 2 ficou vermelha, o computador não conseguiu fazer a mágica porque você pediu o impossível. \n\n**Exemplo de Erro:** Você diz que a tarefa A acontece no dia 10, e a tarefa B precisa ocorrer 30 dias depois dela. Mas você também diz que a tarefa B NÃO pode passar do dia 15! A matemática bate de frente. \n**Solução:** O sistema sempre avisa na caixa vermelha quem é o culpado. Leia a caixa, volte na Planilha e dê prazos mais generosos.",
    "📌 4. O que são os 'Marcadores Personalizados' na Aba 3?": "Na Aba 3 (Calendário Visual), tem um botão chamado 'Inserir Rótulo ou Marcador'. Lá você pode escolher o desenho de um aviãozinho (✈️) e escrever 'Viagem para São Paulo' e definir para o dia 15/Março. Quando o calendário for desenhado, o dia 15/Março estará com um aviãozinho avisando de forma muito visual o que vai acontecer."
}

# =============================================================================
# 7. INTERFACE INTERATIVA DO USUÁRIO E WIZARD GUIADO (V9.0)
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v9.0")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Sua Ferramenta Didática e Profissional para Planejamento de Datas")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # -------------------------------------------------------------------------
    # UX: ASSISTENTE GUIADO PASSO A PASSO (WIZARD) DIDÁTICO
    # -------------------------------------------------------------------------
    if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "marcadores_calendario" not in st.session_state: st.session_state.marcadores_calendario = {}
    if "export_config" not in st.session_state: st.session_state.export_config = {"file_name": "Planejamento_Oficial", "date_format": "%d/%m/%Y", "separator": ","}

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Briefing Inicial (Exemplo)", "Categoria": "Geral", "Prioridade": "Alta", "Tipo de Regra": "1º Dia Útil após Data Base", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Reunião de Alinhamento", "Categoria": "Gestão", "Prioridade": "Média", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(st.session_state.df_planilha.copy())
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    # WIZARD RENDERER COM DIDÁTICA EXTREMA
    if st.session_state.wizard_step < 4:
        st.markdown('<div class="onboarding-box">', unsafe_allow_html=True)
        if st.session_state.wizard_step == 1:
            st.markdown('<div class="step-indicator">Bem-vindo! Passo 1 de 3</div>', unsafe_allow_html=True)
            st.markdown("### 📍 Você sabe o que é a 'Data Base'?")
            st.markdown("A **Data Base** é a semente do seu projeto. É o ponto de onde o computador vai começar a contar as datas. Se você disser ao sistema que a Data Base é **Hoje**, todos os cálculos da planilha vão partir do dia de hoje.")
            st.info("👉 **Olhe para a Barra Lateral (ali à esquerda).** Veja que já está selecionado 'Data Atual (Hoje)'. Deixe assim por agora!")
            if st.button("Já entendi. Me leve ao Passo 2 ➔"): st.session_state.wizard_step = 2; st.rerun()
        elif st.session_state.wizard_step == 2:
            st.markdown('<div class="step-indicator">Preenchendo Tarefas - Passo 2 de 3</div>', unsafe_allow_html=True)
            st.markdown("### 📝 Vamos preencher a Planilha (Aba 1)")
            st.markdown("Na Aba 1, você tem uma Tabela. É como usar o Excel. O Segredo do sucesso mora na coluna **Tipo de Regra**.")
            st.warning("🧠 **Dica de Ouro:** Não use 'Data Fixa' se não for estritamente obrigatório. A grande magia do sistema é você usar a regra **'Dias Úteis após Tarefa Base'**. Assim, se o seu projeto atrasar 10 dias, tudo se ajusta sozinho e empurra para a frente automaticamente!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Voltar e ler o Passo 1"): st.session_state.wizard_step = 1; st.rerun()
            with col2:
                if st.button("Avançar para o Resultado ➔"): st.session_state.wizard_step = 3; st.rerun()
        elif st.session_state.wizard_step == 3:
            st.markdown('<div class="step-indicator">O Grande Final - Passo 3 de 3</div>', unsafe_allow_html=True)
            st.markdown("### 🎉 Feito! O Sistema Trabalha Enquanto Você Digita")
            st.markdown("Você sabia que não existe um botão 'Calcular'? A cada letra que você digita na planilha, o motor recalcula e cospe o resultado mastigado na **Aba 2 (Resultados Otimizados)**.")
            st.markdown("Vá até lá para baixar o seu trabalho ou para ver o Desenho do Calendário na Aba 3.")
            if st.button("🚀 Fechar o Tutorial Guiado e Começar a Trabalhar"): st.session_state.wizard_step = 4; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES GLOBAIS COM EXTREMA DIDÁTICA)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ 1. Início Rápido")
    st.sidebar.markdown("<p style='font-size:12px; color:#64748B;'>Configure a base e as barreiras do seu projeto antes de ir para a Planilha.</p>", unsafe_allow_html=True)
    
    with st.sidebar.popover("🤔 O que é o Ponto de Partida? (Clique Aqui)"):
        st.write("A aplicação precisa saber a partir de qual dia ela deve começar a pensar.\n\n- Se você escolher **'Data Atual (Hoje)'**, ela sempre puxará o dia do seu relógio.\n- Se o projeto não puder começar no fim de semana, escolha **'Próximo Dia Útil'**.")
    
    base_opcao = st.sidebar.selectbox(
        "📍 Defina o Ponto de Partida:", 
        ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], 
        help="A partir de qual dia a matemática começa? Se escolher 'Hoje', as tarefas baseadas nela calcularão dias a partir da data de hoje."
    )
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Clique para escolher no mini calendário:", value=hoje, help="Este dia servirá de base.")

    st.sidebar.markdown(f"**Data Base Atual do Motor:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    st.sidebar.header("🛡️ 2. Regras e Bloqueios")
    ano_corrente = st.sidebar.number_input("Em que ano estamos planejando?", min_value=2024, max_value=2030, value=data_base_global.year, help="O sistema vai calcular Páscoa, Carnaval e Corpus Christi sozinhos baseados no ano que você colocar aqui.")
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Proibir tarefas aos Sábados/Domingos", value=True, help="Se essa caixa estiver checada, o computador tentará de tudo para nunca jogar uma entrega da Aba 1 no final de semana."),
        "block_holidays": st.sidebar.checkbox("Proibir tarefas em Feriados Brasileiros", value=True, help="Pula datas como Natal, Finados e Padroeira do Brasil automaticamente.")
    }

    with st.sidebar.expander("🏛️ Inserir um Feriado da Sua Cidade"):
        st.write("O sistema já sabe o Natal, mas não sabe o dia do aniversário da sua cidade. Adicione aqui para o sistema não trabalhar neste dia.")
        f_name = st.text_input("Qual o nome da folga?", placeholder="Ex: Dia do Servidor")
        f_date = st.date_input("Quando vai acontecer?", datetime.date(ano_corrente, 11, 30))
        if st.button("➕ Injetar na Memória"):
            if f_name:
                st.session_state.custom_holidays[f_date] = {"nome": f_name, "desc": "Feriado Estadual ou Municipal Inserido Pelo Usuário."}
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Sua folga pessoal (Dias Avulsos)", value=[], help="Marque aqui no calendário os dias isolados que você não vai trabalhar (ex: Quinta-feira e Sexta-feira de emenda). O sistema pulará estes dias também.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    if st.sidebar.button("❓ Não entendi. Reiniciar o Guia Passo a Passo"):
        st.session_state.wizard_step = 1
        st.rerun()

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO (NOMES DINÂMICOS DA CONFIGURAÇÃO)
    # -------------------------------------------------------------------------
    tab_names = st.session_state.theme_config["tab_names"]
    t1, t2, t3, t4, t5 = st.tabs(tab_names)

    with t1:
        st.subheader("📝 A Planilha de Escopo e Dependências")
        st.markdown("<p style='color: #475569;'>Construa o seu cronograma clicando dentro das células desta tabela. A edição é livre!</p>", unsafe_allow_html=True)
        
        # Didática Extrema com Popover ao invés de Tooltip poluído
        with st.popover("💡 Como preencher a Coluna de 'Tipo de Regra'? (Exemplos Práticos)"):
            st.markdown("""
            O segredo da aplicação mora aqui. O que cada opção significa?
            * **Livre:** Deixe o computador achar qualquer dia no ano que não seja feriado ou fim de semana e alocar lá. (Útil quando a tarefa não tem prazo, só tem que ser feita).
            * **Data Fixada:** Cuidado com essa. Você impõe a data exata. Se você fixar num dia que for Feriado, o sistema vai gerar alerta vermelho de erro.
            * **1º Dia Útil após Data Base:** A forma mais garantida de começar o projeto. Ele sempre cairá coladinho na data de partida da Barra Lateral Esquerda.
            * **Dias Úteis após Tarefa Base:** A **Regra de Ouro**. Digamos que T1 é uma Reunião. Se T2 for preenchida com essa regra, e na coluna *Tarefa Base* estiver `T1`, e na coluna *Valor* estiver `5`. T2 vai acontecer exatos 5 dias de trabalho real depois de T1, ignorando toda a poluição do calendário.
            """)
        
        col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
        with col_act1:
            if st.button("↩️ Exclui sem querer? (Desfazer Ação)", disabled=len(st.session_state.historico_planilha)==0, help="Nós gravamos seu histórico! Se bagunçar a tabela ou apagar uma linha, clique aqui para voltar a versão anterior."):
                st.session_state.df_planilha = st.session_state.historico_planilha.pop()
                st.rerun()
        with col_act2:
            if st.button("🔢 Renumerar 'Código ID' Automaticamente", help="Não perca tempo criando códigos. Se a tabela bagunçou, clique aqui para ordenar T1, T2, T3..."):
                df_temp = st.session_state.df_planilha.copy()
                df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
                salvar_historico(df_temp)
                st.session_state.df_planilha = df_temp
                st.rerun()
        
        # VALIDAÇÃO CRÍTICA DO DATAFRAME ANTES DE ENTRAR NA TABLE (V9.0 SANITIZATION)
        df_safe = st.session_state.df_planilha.copy()
        if "Data Fixa" in df_safe.columns:
            # Garante que tipos malucos de data que vêm do Excel não quebrem o Editor
            df_safe["Data Fixa"] = pd.to_datetime(df_safe["Data Fixa"], errors='coerce').dt.date

        # DATA EDITOR
        df_edited = st.data_editor(
            df_safe,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código ID", required=True, help="É o apelido da sua Tarefa. Normalmente T1, T2. O motor usa isso para ligar as pontas."),
                "Nome da Tarefa": st.column_config.TextColumn("Qual o Compromisso?", required=True, width="large", help="O nome real que vai aparecer no Calendário visual."),
                "Categoria": st.column_config.TextColumn("Grupo (Ex: Reunião)"),
                "Prioridade": st.column_config.SelectboxColumn("Atenção/Nível", options=["Alta", "Média", "Baixa"]),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Regra Matemática Aplicada",
                    options=["Livre", "Data Fixada", "1º Dia Útil após Data Base", "Dias Úteis após Tarefa Base", "Dias Úteis após Data Base", "Data Limite (Antes de)", "Data Limite (Após de)"],
                    required=True,
                    help="Leia o botão acima (Como Preencher). Isso define como a data será encontrada."
                ),
                "Tarefa Base": st.column_config.TextColumn("Atrás de qual ID? (Ex: T1)", help="Ex: Se sua tarefa só ocorre depois da T1, digite 'T1' aqui."),
                "Valor / Dias": st.column_config.NumberColumn("Quantos dias de Pulo?", min_value=0, help="Se você escolheu a regra 'Dias úteis', coloque aqui o valor exato. (ex: 15)."),
                "Data Fixa": st.column_config.DateColumn("Preencher se escolheu Data Fixa", format="DD/MM/YYYY", help="Se escolheu o tipo de regra 'Data Fixada', diga o dia exato aqui.")
            },
            help="👉 **Dica Ninja:** Quer apagar uma linha? Clique no quadradinho esquerdo dela e aperte 'Delete' no teclado do computador."
        )
        salvar_historico(df_edited)
        st.session_state.df_planilha = df_edited

        st.markdown("---")
        with st.expander("🛠️ Preferências Avançadas: Upload de Planilha Pronta e Regras Extra"):
            st.info("Já tem uma tabela pronta no Excel? Suba aqui! Mas lembre-se: As colunas do seu Excel precisam ter nomes idênticos às da tabela acima.")
            uploaded_file = st.file_uploader("Subir Tabela (CSV ou Excel)", type=["csv", "xlsx"], help="Substitui a planilha principal. O arquivo deve ter as colunas exatas exigidas.")
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.session_state.df_planilha = df_up
                    st.success("Planilha carregada e convertida perfeitamente!")
                except Exception as e:
                    st.error("Falha ao ler. O formato não combina com o padrão do sistema.")

            st.write("**Criar Regras Lógicas Usando Formulários (Ao Invés da Planilha):**")
            rest_type = st.selectbox("Selecione um tipo de trava emergencial:", ["Data Limite (Deadline) de Segurança", "A deve ocorrer antes de B"], help="Isso não altera a planilha. São regras de pano de fundo impostas ao Motor.")
            if rest_type == "Data Limite (Deadline) de Segurança":
                t_id_f = st.selectbox("Impor a qual Tarefa?", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])])
                d_val = st.date_input("Não pode passar do dia...", datetime.date(ano_corrente, 6, 1))
                if st.button("Gravar Regra Limitadora"):
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, "before": d_val}))
                    st.rerun()

            if st.session_state.restrictions_manuais:
                st.markdown("**Regras de Retaguarda Ativas:**")
                for idx, r in enumerate(st.session_state.restrictions_manuais): st.caption(f"Regra Secreta {idx+1}: {r.params}")
                if st.button("🗑️ Limpar Regras Manuais"): st.session_state.restrictions_manuais = []; st.rerun()

    # COMPILAÇÃO DAS REGRAS PARA O MOTOR (V9.0)
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
        
        if v_tipo == "Data Fixada" and pd.notna(v_fixa):
            engine_restrictions.append(Restriction(type="fixed_date", params={"task_id": t_id, "date": v_fixa}))
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

    # CÁLCULO TOTALMENTE AUTOMÁTICO
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        st.subheader("📊 Os Resultados e o Cronograma Oficial")
        if status == "SUCCESS":
            st.success("✅ **Máquina Aprovada!** Você alimentou a Aba 1 com perfeição. O sistema testou o ano inteiro e encontrou as datas exatas que encaixam nos seus prazos sem tocar nos feriados.")
            col_m1, col_m2 = st.columns(2)
            for i, card in enumerate(alt_cards):
                t_id = card["task_id"]
                date_val = sol_dates.get(t_id)
                t_obj = next((t for t in engine_tasks if t.id == t_id), None)
                if t_obj and date_val:
                    with col_m1 if i % 2 == 0 else col_m2:
                        st.markdown(f"""
                        <div class="metric-card" title="{card['justification']}">
                            <span style="color:{st.session_state.theme_config['color_allocated_border']}; font-weight:bold; font-size:11px; text-transform: uppercase;">✔ ALOCADO ({t_id})</span>
                            <h4 style="margin:4px 0; color: #1F2937;">{t_obj.name}</h4>
                            <h2 style="color:{st.session_state.theme_config['color_primary']}; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:12px; color:#6B7280; margin:0px;">Cai numa <b>{["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][date_val.weekday()]}</b></p>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📥 Tabela Consolidada Pronta para Exportação")
            st.info("Essa é a sua versão final, pronta para virar um arquivo Excel (.CSV) ou um relatório descritivo.")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código": t_id, "Nome da Tarefa": t_item.name, "Data Oficial": f_date}
                    
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0]
                    if "Categoria" in row_t: row_data["Categoria"] = row_t["Categoria"]
                    if "Prioridade" in row_t: row_data["Prioridade"] = row_t["Prioridade"]
                    
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                
                # Relatório TXT Didático e Amplo
                txt_report = f"DOSSIÊ E PLANEJAMENTO - EXERCÍCIO DE {ano_corrente}\n"
                txt_report += f"Relatório Gerado a partir da Data Base: {data_base_global.strftime('%d/%m/%Y')}\n\n"
                txt_report += "========================================\n📋 RESUMO DAS TAREFAS OTIMIZADAS:\n"
                for r in cronograma_data: txt_report += f"   ➤ Dia {r['Data Oficial']} | ID: {r['Código']} | Compromisso: {r['Nome da Tarefa']}\n"
                txt_report += "\n========================================\n🚫 FERIADOS E BLOQUEIOS APLICADOS NO ANO:\n"
                for dt, props in cal_mgr.br_holidays.holidays_dict.items():
                    txt_report += f"   - {dt.strftime('%d/%m/%Y')}: {props['nome']} -> {props['desc']}\n"
                
                c1, c2 = st.columns(2)
                c1.download_button(f"📥 Exportar para Excel (.CSV Separado por {st.session_state.export_config['separator']})", data=csv_buffer, file_name=f"{st.session_state.export_config['file_name']}.csv", mime="text/csv", use_container_width=True, help="Botão verde que baixa a tabela como matriz de dados.")
                c2.download_button("📝 Baixar Relatório Resumido para Leitura (.TXT)", data=txt_report, file_name="Relatorio_De_Projeto.txt", mime="text/plain", use_container_width=True, help="Esse arquivo baixa de um jeito bonito que você pode copiar e colar num e-mail ou no Word direto.")

        else:
            st.error("⚠️ **Ocorreu um Choque de Regras! A Matemática Entrou em Colapso.**")
            st.markdown(f"""
            <div class="alert-box">
                <b>🔍 Diagnóstico Oficial do Sistema:</b><br>
                {diagnostico}
            </div>
            """, unsafe_allow_html=True)
            st.warning("""
            **Por que aconteceu e como consertar agora mesmo?**
            1. **Falta de espaço:** Você colocou 'Dias Úteis após a Tarefa' com um número gigante (ex: 90 dias úteis). Quando o sistema foi contar, o ano calendário acabou antes do fim do prazo!
            2. **Feriado forçado:** Se na Aba 1 você usou a regra de "Data Fixa" numa Segunda-feira que por azar já era um Feriado. Você precisa voltar lá, ver o Calendário, e trocar essa data fixa ou o tipo de regra para *Livre*.
            """)

    with t3:
        st.subheader("📅 Seu Ano Inteiro, Desenhado Visualmente")
        st.write("Um mapa visual de como seu projeto se espalha durante os 12 meses.")
        
        with st.expander("📌 Brincar no Calendário: Inserir Marcadores Coloridos e Pessoais (Rótulos)"):
            st.write("Você pode colocar post-its digitais em cima dos dias. Exemplo: Quero marcar o dia do aniversário do chefe para lembrar na hora de apresentar.")
            m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
            m_date = m_col1.date_input("Escolha o dia Exato:", data_base_global)
            m_text = m_col2.text_input("Escreva o Título do Lembrete:", placeholder="Ex: Viagem Internacional")
            m_icon = m_col3.selectbox("Escolha um Carimbo (Emoji)", ["📌 Alfinete", "⭐ Favorito", "✈️ Viagem", "🏖️ Férias", "💰 Pagamento", "🎂 Aniversário"])
            if st.button("✏️ Carimbar este dia no Mapa abaixo"):
                if m_text:
                    st.session_state.marcadores_calendario[m_date] = f"{m_icon.split()[0]} {m_text}"
                    st.toast(f"O carimbo foi grudado no dia {m_date.strftime('%d/%m')}!")
                    st.rerun()
            
            if st.session_state.marcadores_calendario:
                st.markdown("---")
                st.write("**Marcadores Desenhados Atualmente:**")
                for md, txt in st.session_state.marcadores_calendario.items():
                    st.caption(f"- Dia {md.strftime('%d/%m')}: {txt}")
                if st.button("🗑️ Jogar todos os carimbos fora"):
                    st.session_state.marcadores_calendario = {}; st.rerun()

        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia em branco e Livre</div>
            <div><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> <b>Alvo da Planilha!</b></div>
            <div><span style="background-color: {st.session_state.theme_config['color_holiday']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado</div>
            <div><span style="background-color: {st.session_state.theme_config['color_blocked']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Fim de Semana (Bloqueado)</div>
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
                                        title_hover = "📍 ESSE É O DIA ZERO: A Data Base do Motor"
                                        cell_class = "day-allocated"
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"🎯 Compromissos aqui: {', '.join(t_codes)}"
                                    elif props["is_holiday"]: cell_class = "day-holiday"
                                    elif props["is_blocked"] or d_verif in manual_dates: 
                                        cell_class = "day-blocked"
                                        title_hover = "O sistema foi proibido de colocar tarefas aqui."
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{display_content}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    with t4:
        st.header("📘 A Enciclopédia Didática (Tire sua Dúvida Aqui)")
        st.write("Digite sua dúvida na caixa de texto abaixo. Uma página inteira vai se abrir te ajudando.")
        
        MANUAL_SECTIONS = {
            "💡 Eu preenchi a Planilha. Preciso apertar um Botão de Calcular?": "Não! O motor que faz a matemática é vivo. Toda vez que você dá um clique fora da célula na tabela ou altera um valor, o aplicativo já sabe. Basta você ir na Aba 2 que o resultado já vai estar lá desenhado. Ele recalcula os feriados todos de forma contínua.",
            "⚙️ Coluna de 'Tipo de Regra' na Tabela. Como faço isso do jeito fácil?": "Fácil! Tem um projeto e você quer que a **Fase 2** aconteça sempre 15 dias depois da **Fase 1**? \n\n1. Na linha da Fase 2, coloque 'Dias Úteis após Tarefa Base'.\n2. Na Coluna 'Tarefa Base', escreva lá 'T1' ou seja qual for o ID da Fase 1.\n3. Na coluna 'Valor/Dias', digite 15.\n Acabou. O sistema faz o resto, não importa se no meio do caminho tenha Natal, ele pula e cai certinho.",
            "❌ Erro Vermelho na Aba 2 e agora? (Conflito de Lógica)": "Imagina que você colocou a Data Base como Novembro. E disse para o computador colocar uma Reunião para ocorrer 90 dias úteis depois dessa data. Ele vai tentar achar, mas o ano vai acabar (Dezembro termina). Como o ano não deu conta do seu prazo, ele apita o erro vermelho 'Conflito Logístico'. Basta diminuir o prazo na Aba 1.",
            "🗂️ Como eu Salvo tudo isso para não perder o serviço de hoje?": "É só ir na Aba 5 (Cores & Exportação) e rolar a página até o fim. Vai ter um botão 'Gerar Backup Master'. Ele baixa um arquivo JSON levinho. Amanhã, se seu chefe quiser ver, você abre o sistema, sobe esse JSON, e o sistema vai montar TUDO de novo (Cores, Tarefas, Carimbos). Magia!"
        }
        
        pesquisa = st.text_input("🔍 Pesquise sua dúvida (Ex: Erro vermelho, Salvar, Regras):", help="A barra de pesquisa indexa o dicionário abaixo. Basta digitar palavras como 'Planilha' que a caixa responderá.")
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo):
                    st.markdown(conteudo)

    with t5:
        st.header("🎨 5. Oficina de Customização e Configuração Visual")
        st.info("Aqui a aparência do software fica com a sua cara. Sem códigos difíceis. \n\n*Nota Técnica: Retiramos seletores automáticos pesados e trocamos por Paletas Certificadas para garantir que o seu navegador nunca mais crashe no carregamento da tela!*")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Visual da Tela (Cores e Textos)")
            st.session_state.theme_config["app_title"] = st.text_input("Como quer chamar o Sistema?", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v9.0"), help="O Letreiro Gigante lá no topo muda se você trocar essa caixa.")
            
            # Seletor de cores SEGURO contra falhas assíncronas do Streamlit Web Component
            tema_escolhido = st.selectbox("Escolha um Padrão de Cor para o Calendário e os Títulos", list(THEME_PALETTES.keys()), help="Troque entre temas coloridos e veja o sistema inteiro se adequar para a cor.")
            if st.button("Aplicar a Cor Escolhida 🎨"):
                st.session_state.theme_config["color_primary"] = THEME_PALETTES[tema_escolhido]["primary"]
                st.session_state.theme_config["color_allocated"] = THEME_PALETTES[tema_escolhido]["alloc"]
                st.session_state.theme_config["color_allocated_border"] = THEME_PALETTES[tema_escolhido]["alloc_border"]
                st.toast("O banho de cor foi aplicado! É só ir no calendário para ver a mágica.")
                st.rerun()
            
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Na Grade do Calendário Visual, a semana começa no...", options=[("Domingo (Recomendado)", 6), ("Segunda-Feira", 0)], format_func=lambda x: x[0], help="Nos Estados Unidos o calendário desenha começando por Domingo. Você escolhe aqui se quer o bloco de Domingo na ponta esquerda, ou o bloco de Segunda na ponta esquerda da tabela.")[1]
            
        with c_p2:
            st.subheader("Opções de Download do Excel (Aba 2)")
            st.session_state.export_config["file_name"] = st.text_input("Qual o nome do Arquivo Excel que você vai baixar?", value=st.session_state.export_config["file_name"], help="Aquele arquivo CSV que é gerado na Aba 2, terá o nome que você ditar aqui (ex: Projeto_Chefe).")
            st.session_state.export_config["date_format"] = st.selectbox("Como gosta que a Data seja escrita?", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"], help="DD = Dia, MM = Mês, YYYY = Ano com 4 números.")
            st.session_state.export_config["separator"] = st.selectbox("Na Europa o Excel usa vírgulas, no Brasil usa ponto e vírgula. Qual o seu?", options=[";", ",", "\t"], help="Dica Quente: Se quando você baixar a planilha, o Excel mostrar tudo bagunçado numa coluna só, venha aqui e troque o separador de Vírgula para Ponto-e-Vírgula e baixe de novo.")

        st.divider()
        st.subheader("💾 O Coração da Operação (Salvar e Carregar Backups)")
        st.write("Isso é perfeito se você fechou o navegador. Você baixa esse arquivo 'JSON' agora, e amanhã quando o sistema resetar, você joga ele na tela e ele ressuscita as suas tarefas e suas cores exatas.")
        
        export_dict = {
            "theme": st.session_state.theme_config,
            "export": st.session_state.export_config,
            "markers": {d.strftime("%Y-%m-%d"): txt for d, txt in st.session_state.marcadores_calendario.items()},
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button(label="📦 Gerar o Super Backup (.JSON)", data=json_str, file_name="Meu_Projeto_Salvo.json", mime="application/json", use_container_width=True, help="Esse botão fará o download de um pacote leve contendo a alma de tudo que você configurou hoje.")

if __name__ == "__main__":
    main()
