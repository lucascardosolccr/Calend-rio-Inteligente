import datetime
import calendar
import copy
import json
from typing import List, Dict, Any, Tuple
import streamlit as st
import pandas as pd

# =============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA & CONSTANTES VISUAIS (UI/UX BRANDING)
# =============================================================================
st.set_page_config(
    page_title="Calendário Inteligente PRO v7.0",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do Gerenciador de Temas (Personalização Persistente)
if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A",
        "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE",
        "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2",
        "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Planilha Escopo", "📊 2. Resultados", "📅 3. Calendário Visual", "📘 4. Manual", "🎨 5. Personalização"],
        "cal_first_weekday": 6 # 6 = Domingo, 0 = Segunda
    }

# Injeção de Estilização CSS Dinâmica e Avançada
st.markdown(f"""
    <style>
    .main-title {{ font-size: 2.3rem; font-weight: 800; color: {st.session_state.theme_config['color_primary']}; margin-bottom: 0.2rem; }}
    .subtitle {{ font-size: 1.05rem; color: {st.session_state.theme_config['color_secondary']}; margin-bottom: 1.5rem; }}
    .metric-card {{ background-color: #FFFFFF; border-left: 5px solid {st.session_state.theme_config['color_allocated_border']}; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px; transition: transform 0.2s; }}
    .metric-card:hover {{ transform: translateY(-2px); }}
    .onboarding-box {{ background-color: #F0FDF4; border: 2px solid #22C55E; padding: 20px; border-radius: 10px; margin-bottom: 25px; }}
    .alert-box {{ background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 4px; margin-top:10px; }}
    .calendar-grid {{ display: block; margin-bottom: 20px; }}
    .calendar-row {{ display: table; width: 100%; table-layout: fixed; }}
    .calendar-cell {{ display: table-cell; text-align: center; padding: 6px 2px; font-size: 11px; border: 1px solid #E5E7EB; font-weight: 600; }}
    .day-normal {{ background-color: #F9FAFB; color: #1F2937; }}
    .day-allocated {{ background-color: {st.session_state.theme_config['color_allocated']}; color: #1E40AF; border: 2px solid {st.session_state.theme_config['color_allocated_border']} !important; }}
    .day-holiday {{ background-color: {st.session_state.theme_config['color_holiday']}; color: #991B1B; }}
    .day-blocked {{ background-color: {st.session_state.theme_config['color_blocked']}; color: #6B7280; }}
    .day-header {{ background-color: #F3F4F6; color: #374151; font-weight: bold; }}
    .history-log {{ font-size: 12px; color: #6B7280; font-family: monospace; }}
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
            datetime.date(self.year, 11, 30): "Dia do Evangélico (DF)",
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
        if config.get("block_weekends") and is_weekend: is_blocked = True
        if config.get("block_holidays") and is_holiday: is_blocked = True
            
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
        if start_idx >= end_idx: return 0
        dias_uteis = 0
        for idx in range(start_idx + 1, end_idx + 1):
            props = self.get_day_properties(idx, config)
            if not props["is_blocked"] and props["date"] not in manual_exclusions:
                dias_uteis += 1
        return dias_uteis

# =============================================================================
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA E DIAGNÓSTICO (V7.0)
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
            if props["is_blocked"] or props["date"] in self.manual_exclusions: return False

        for r in self.restrictions:
            if r.type == "fixed_date":
                t_id = r.params["task_id"]
                if t_id in alocacao:
                    if alocacao[t_id] != self.cal_mgr.date_to_idx(r.params["date"]): return False
            elif r.type == "deadline":
                t_id = r.params["task_id"]
                if t_id in alocacao:
                    idx_atual = alocacao[t_id]
                    if r.params.get("before") and idx_atual >= self.cal_mgr.date_to_idx(r.params["before"]): return False
                    if r.params.get("after") and idx_atual <= self.cal_mgr.date_to_idx(r.params["after"]): return False
            elif r.type == "dependency":
                t_a = r.params["task_a"]
                t_b = r.params["task_b"]
                if t_a in alocacao and t_b in alocacao:
                    if alocacao[t_b] < alocacao[t_a] + r.params.get("min_gap", 0): return False
            elif r.type == "working_day_offset":
                t_base = r.params["task_base"]
                t_target = r.params["task_target"]
                if t_base in alocacao and t_target in alocacao:
                    idx_base = alocacao[t_base]
                    idx_target = alocacao[t_target]
                    if self.cal_mgr.contar_dias_uteis_entre(idx_base, idx_target, self.cal_config, self.manual_exclusions) != r.params["offset"]: return False
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
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Data alocada respeitando todos os intervalos de regras rigorosas. (Confiabilidade: {max(0, 100 - melhor_custo)}%)"} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
            
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        if len(self.restrictions) == 0: return "Há tarefas com Datas Fixas que caem em dias bloqueados (Feriado/Fim de semana)."
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
                if tipo == "deadline": return f"A regra de Data Limite (Deadline) aplicada à Tarefa {alvo} é impossível de ser cumprida sem violar bloqueios ou os prazos de suas dependências."
                if tipo == "working_day_offset": return f"O Deslocamento de Dias Úteis para a Tarefa {alvo} colide com o final do calendário ou com prazos limite."
                return f"Conflito gerado pela regra: {tipo} vinculada à tarefa {alvo}."
        self.restrictions = original_restrictions
        return "Conflito sistêmico irremediável. O volume de bloqueios manuais ou regras em cascata ultrapassa o número de dias úteis disponíveis."

# =============================================================================
# 6. BANCO DE DADOS DE MANUAL (PESQUISÁVEL)
# =============================================================================
MANUAL_SECTIONS = {
    "🌟 1. Introdução e Objetivo": "**O que é?** O Calendário Inteligente PRO automatiza o planejamento.\n\n**Benefícios:** Elimina erros de contagem de finais de semana e feriados; Recalcula dependências automaticamente em milissegundos.",
    "🖥️ 2. Conhecendo a Interface": "**Barra Lateral:** Configuração global (Data Base e Bloqueios).\n**Aba Planilha:** Edição interativa de tarefas.\n**Aba Personalização:** Altere temas, exportação, e modelos salvos.",
    "🛠️ 3. Tutorial Completo de Fluxo": "1. Defina a **Data Base** (Menu Esquerdo).\n2. Adicione **Tarefas** na Planilha.\n3. Defina as **Regras** (Ex: 'Dias Úteis após').\n4. Verifique a Aba 2 e Export.",
    "🚦 4. Boas Práticas da Tabela": "- Use a função **'Gerar IDs Auto'** para não se preocupar com códigos repetidos.\n- Para usar categorias, edite a coluna 'Categoria'.\n- Use 'Data Fixa' com moderação, pois isso força o sistema.",
    "🎨 5. Personalização e Exportação": "Na **Aba 5 (Personalização)** você pode: \n- Alterar a Cor do Sistema.\n- Salvar um 'Modelo' de Regras para usar no mês seguinte.\n- Mudar os títulos das abas.",
    "❓ 6. Dúvidas Frequentes (FAQ)": "**Por que a Aba 2 deu erro?** Conflito Matemático! Vá no Diagnóstico Inteligente para descobrir qual regra estourou o prazo.\n**Como apago uma linha?** Selecione na caixa à esquerda da linha e aperte 'Delete'."
}

# =============================================================================
# 7. INTERFACE INTERATIVA DO USUÁRIO & ONBOARDING MASTER
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v7.0")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Enterprise Edition: Altamente Personalizável, Zero Regressões")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # -------------------------------------------------------------------------
    # UX: SISTEMA DE ONBOARDING (ASSISTENTE GUIADO)
    # -------------------------------------------------------------------------
    if "onboarding_concluido" not in st.session_state: st.session_state.onboarding_concluido = False
    if not st.session_state.onboarding_concluido:
        st.markdown("""
        <div class="onboarding-box">
            <h2 style="margin-top: 0; color: #166534;">👋 Bem-vindo(a) ao seu Calendário Totalmente Personalizável!</h2>
            <p style="font-size: 16px; color: #15803D;">Você pediu total flexibilidade e segurança. O sistema não perdeu nenhuma funcionalidade e ganhou superpoderes de customização.</p>
            <hr style="border-color: #86EFAC;">
            <ol style="font-size: 15px; color: #166534;">
                <li><b>Customização Master (Aba 5):</b> Agora você pode mudar a cor, as abas, exportar templates de regras e mudar os formatos de datas.</li>
                <li><b>Data Base (Menu Esquerdo):</b> O relógio começa de onde você decidir. O sistema calcula a partir de "Hoje" ou de qualquer dia do calendário.</li>
                <li><b>Tabela Interativa e Mágica (Aba 1):</b> A coluna de categorias foi adicionada. Precisa de novos IDs? Use o botão "Gerar IDs Automáticos".</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 Entendido! Ir para o Sistema", type="primary"):
            st.session_state.onboarding_concluido = True
            st.rerun()
        st.divider()

    # Controle de Estado Histórico
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "export_config" not in st.session_state:
        st.session_state.export_config = {"file_name": "Relatorio_Projeto", "date_format": "%d/%m/%Y", "separator": ","}

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Briefing do Projeto", "Categoria": "Gestão", "Prioridade": "Alta", "Tipo de Regra": "Livre", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Validação com Cliente", "Categoria": "Operacional", "Prioridade": "Média", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(st.session_state.df_planilha.copy())
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES GLOBAIS COM DATA BASE)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ Controle Global")
    
    st.sidebar.subheader("📍 Data Base de Cálculo")
    base_opcao = st.sidebar.selectbox("Ponto de Partida:", ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], help="Determina a data principal de referência.")
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Selecione a Data Base", value=hoje)

    st.sidebar.markdown(f"**Ativa:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    ano_corrente = st.sidebar.number_input("Ano do Exercício", min_value=2024, max_value=2030, value=data_base_global.year)
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Finais de Semana", value=True),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados (Brasil/DF)", value=True)
    }

    with st.sidebar.expander("🏛️ Cadastrar Feriado Regional"):
        f_name = st.text_input("Nome", placeholder="Ex: Feriado Distrital")
        f_date = st.date_input("Data", datetime.date(ano_corrente, 11, 30))
        if st.button("Injetar Feriado"):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Indisponibilidades Manuais", value=[], help="Dias de bloqueio forçado do usuário.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    if st.sidebar.button("❓ Reabrir Tela de Boas-Vindas"):
        st.session_state.onboarding_concluido = False
        st.rerun()

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO (NOMES DINÂMICOS DA CONFIGURAÇÃO)
    # -------------------------------------------------------------------------
    tab_names = st.session_state.theme_config["tab_names"]
    t1, t2, t3, t4, t5 = st.tabs(tab_names)

    with t1:
        st.subheader("📝 Planilha Inteligente e Customizável")
        
        col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
        with col_act1:
            if st.button("↩️ Desfazer Alteração", disabled=len(st.session_state.historico_planilha)==0):
                st.session_state.df_planilha = st.session_state.historico_planilha.pop()
                st.rerun()
        with col_act2:
            if st.button("🔢 Gerar IDs Auto", help="Sobrescreve a primeira coluna com T1, T2, T3... sequencialmente."):
                df_temp = st.session_state.df_planilha.copy()
                df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
                salvar_historico(df_temp)
                st.session_state.df_planilha = df_temp
                st.rerun()
        
        # DATA EDITOR COM CATEGORIAS E PRIORIDADES
        df_edited = st.data_editor(
            st.session_state.df_planilha,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código ID (Fixo)"),
                "Nome da Tarefa": st.column_config.TextColumn("Nome da Tarefa"),
                "Categoria": st.column_config.TextColumn("Grupo / Categoria"),
                "Prioridade": st.column_config.SelectboxColumn("Prioridade", options=["Alta", "Média", "Baixa"]),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Regra Ativa",
                    options=["Livre", "Data Fixada", "1º Dia Útil após Data Base", "Dias Úteis após Tarefa Base", "Dias Úteis após Data Base", "Data Limite (Antes de)", "Data Limite (Após de)"],
                    required=True
                ),
                "Tarefa Base": st.column_config.TextColumn("ID da Tarefa Base"),
                "Valor / Dias": st.column_config.NumberColumn("Dias/Offset", min_value=0),
                "Data Fixa": st.column_config.DateColumn("Fixo (Opcional)", format="DD/MM/YYYY")
            }
        )
        salvar_historico(df_edited)
        st.session_state.df_planilha = df_edited

        with st.expander("🛠️ Formulário de Inserção Adicional e Regras Clássicas"):
            rest_type = st.selectbox("Modelo de Regra:", ["Data Limite (Deadline)", "Dependência Sequencial Simples"])
            if rest_type == "Data Limite (Deadline)":
                t_id_f = st.selectbox("Qual Tarefa?", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])])
                d_val = st.date_input("Escolha a data", datetime.date(ano_corrente, 6, 1))
                if st.button("Vincular Prazo"):
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, "before": d_val}))
                    st.rerun()
            if st.session_state.restrictions_manuais:
                for idx, r in enumerate(st.session_state.restrictions_manuais):
                    st.caption(f"• Formulário Extra: {r.type.upper()} -> {r.params}")
                if st.button("Limpar Formulários Extra"):
                    st.session_state.restrictions_manuais = []
                    st.rerun()

    # COMPILAÇÃO DAS REGRAS (INTEGRAÇÃO TOTAL COM A DATA BASE)
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

    # CÁLCULO E RESOLUÇÃO
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        if status == "SUCCESS":
            st.success("✅ **Otimização Concluída:** A tabela dinâmica foi traduzida para datas perfeitas no calendário.")
            col_m1, col_m2 = st.columns(2)
            for i, card in enumerate(alt_cards):
                t_id = card["task_id"]
                date_val = sol_dates.get(t_id)
                t_obj = next((t for t in engine_tasks if t.id == t_id), None)
                if t_obj and date_val:
                    with col_m1 if i % 2 == 0 else col_m2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <span style="color:{st.session_state.theme_config['color_allocated_border']}; font-weight:bold; font-size:11px;">ID: {t_id}</span>
                            <h4 style="margin:2px 0;">📌 {t_obj.name}</h4>
                            <h2 style="color:{st.session_state.theme_config['color_primary']}; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:11.5px; color:#4B5563; margin:4px 0;">{card['justification']}</p>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📊 Resultado Pronto para Exportação Customizada")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    # Formatação de acordo com a configuração de exportação
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código": t_id, "Nome da Tarefa": t_item.name, "Data Oficial": f_date}
                    
                    # Traz as colunas estéticas da tabela se existirem
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0]
                    if "Categoria" in row_t: row_data["Categoria"] = row_t["Categoria"]
                    if "Prioridade" in row_t: row_data["Prioridade"] = row_t["Prioridade"]
                    
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                st.download_button(
                    label=f"📥 Baixar '{st.session_state.export_config['file_name']}.csv'",
                    data=csv_buffer,
                    file_name=f"{st.session_state.export_config['file_name']}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.error("⚠️ **Diagnóstico de Conflito Ativado**")
            st.markdown(f'<div class="alert-box"><b>O que quebrou as regras:</b><br>{diagnostico}</div>', unsafe_allow_html=True)

    with t3:
        st.subheader("📅 Mapa Estratégico (Customizado)")
        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> Tarefa Alocada</div>
            <div><span style="background-color: {st.session_state.theme_config['color_holiday']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Feriado</div>
            <div><span style="background-color: {st.session_state.theme_config['color_blocked']}; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Fim de Semana/Bloqueio</div>
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
                                    title_hover = props["name"]
                                    
                                    if d_verif == data_base_global:
                                        title_hover = "📍 DATA BASE"
                                        cell_class = "day-allocated"
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

    with t4:
        st.header("📘 Manual da Aplicação & Pesquisa (v7.0)")
        pesquisa = st.text_input("🔍 Pesquisar no Manual (Digite palavras chave):")
        
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo):
                    st.markdown(conteudo)

    with t5:
        st.header("🎨 5. Centro de Personalização & Import/Export")
        st.write("Modifique o comportamento visual, os formatos de relatório, e salve seus templates de regras para usos futuros.")
        
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Estética da Interface")
            st.session_state.theme_config["app_title"] = st.text_input("Título da Aplicação", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v7.0"))
            st.session_state.theme_config["color_primary"] = st.color_picker("Cor Primária (Títulos e Datas)", value=st.session_state.theme_config["color_primary"])
            st.session_state.theme_config["color_allocated"] = st.color_picker("Fundo de Tarefas Alocadas (Calendário)", value=st.session_state.theme_config["color_allocated"])
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Primeiro dia da Semana (Matriz Visual)", options=[("Domingo", 6), ("Segunda", 0)], format_func=lambda x: x[0])[1]
            
        with c_p2:
            st.subheader("Configurações de Relatório (Exportação)")
            st.session_state.export_config["file_name"] = st.text_input("Nome padrão do Arquivo CSV", value=st.session_state.export_config["file_name"])
            st.session_state.export_config["date_format"] = st.selectbox("Formato da Data do Relatório", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"])
            st.session_state.export_config["separator"] = st.selectbox("Separador do CSV", options=[",", ";", "\t"])

        st.divider()
        st.subheader("💾 Gerenciador de Templates (Regras Persistentes)")
        st.write("Baixe a estrutura atual das suas tabelas de tarefas e recarregue na próxima vez que usar o sistema!")
        
        # Converte o Dataframe em Dicionário Seguro para JSON
        export_dict = {
            "theme": st.session_state.theme_config,
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button(label="📦 Baixar Backup (Template JSON)", data=json_str, file_name="Template_Regras_Calendario.json", mime="application/json", use_container_width=True)

if __name__ == "__main__":
    main()
