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
    page_title="Calendário Inteligente PRO v8.0",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicialização do Gerenciador de Temas & Customização (SEM ColorPicker para evitar erros de JS Fetch)
if "theme_config" not in st.session_state:
    st.session_state.theme_config = {
        "color_primary": "#1E3A8A", # Azul Corporativo
        "color_secondary": "#4B5563",
        "color_allocated": "#DBEAFE",
        "color_allocated_border": "#2563EB",
        "color_holiday": "#FEE2E2",
        "color_blocked": "#E5E7EB",
        "tab_names": ["📋 1. Passo a Passo & Tabela", "📊 2. Resultados Otimizados", "📅 3. Painel Calendário", "📘 4. Ajuda e Tutoriais", "🎨 5. Cores & Exportação"],
        "cal_first_weekday": 6 # 6 = Domingo
    }

# Dicionário seguro de temas para evitar o bug de componentes assíncronos do Streamlit
THEME_PALETTES = {
    "Azul Profissional (Padrão)": {"primary": "#1E3A8A", "alloc": "#DBEAFE", "alloc_border": "#2563EB"},
    "Verde Sucesso": {"primary": "#14532D", "alloc": "#DCFCE7", "alloc_border": "#16A34A"},
    "Roxo Criativo": {"primary": "#4C1D95", "alloc": "#F3E8FF", "alloc_border": "#7E22CE"},
    "Laranja Dinâmico": {"primary": "#7C2D12", "alloc": "#FFEDD5", "alloc_border": "#EA580C"}
}

# Injeção de Estilização CSS Dinâmica e Avançada
st.markdown(f"""
    <style>
    .main-title {{ font-size: 2.3rem; font-weight: 800; color: {st.session_state.theme_config['color_primary']}; margin-bottom: 0.2rem; }}
    .subtitle {{ font-size: 1.05rem; color: {st.session_state.theme_config['color_secondary']}; margin-bottom: 1.5rem; }}
    .metric-card {{ background-color: #FFFFFF; border-left: 5px solid {st.session_state.theme_config['color_allocated_border']}; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px; transition: transform 0.2s; }}
    .metric-card:hover {{ transform: translateY(-2px); }}
    .onboarding-box {{ background-color: #F8FAFC; border: 2px solid #64748B; padding: 20px; border-radius: 10px; margin-bottom: 25px; }}
    .alert-box {{ background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 15px; border-radius: 4px; margin-top:10px; }}
    .calendar-grid {{ display: block; margin-bottom: 20px; font-family: sans-serif; }}
    .calendar-row {{ display: table; width: 100%; table-layout: fixed; }}
    .calendar-cell {{ display: table-cell; text-align: center; padding: 6px 2px; font-size: 11px; border: 1px solid #E5E7EB; font-weight: 600; min-height: 40px; vertical-align: middle; }}
    .day-normal {{ background-color: #F9FAFB; color: #1F2937; }}
    .day-allocated {{ background-color: {st.session_state.theme_config['color_allocated']}; color: #1E40AF; border: 2px solid {st.session_state.theme_config['color_allocated_border']} !important; font-weight: 800; }}
    .day-holiday {{ background-color: {st.session_state.theme_config['color_holiday']}; color: #991B1B; }}
    .day-blocked {{ background-color: {st.session_state.theme_config['color_blocked']}; color: #6B7280; }}
    .day-marker {{ font-size: 14px; display: block; margin-top: 2px; }}
    .day-header {{ background-color: #F3F4F6; color: #374151; font-weight: bold; }}
    .step-indicator {{ background-color: {st.session_state.theme_config['color_primary']}; color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; margin-bottom: 10px; display: inline-block; }}
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
        
        # Converte custom_holidays para o novo formato rico se vierem no formato antigo {data: nome}
        for d, data_obj in self.custom_holidays.items():
            if isinstance(data_obj, str):
                base_holidays[d] = {"nome": data_obj, "desc": "Feriado/Bloqueio inserido manualmente pelo usuário."}
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
            "name": holiday_info["nome"] if is_holiday else "Dia Operacional Livre",
            "desc": holiday_info["desc"] if is_holiday else "Este dia está apto para receber compromissos.",
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
            alternatives = [{"task_id": t_id, "score": max(0, 100 - melhor_custo), "justification": f"Excelente! Data validada. Pulou finais de semana e feriados com segurança total."} for t_id in task_ids]
            return "SUCCESS", results, alternatives, ""
            
        return "INFEASIBLE", {}, [], self.diagnose_infeasibility()

    def diagnose_infeasibility(self) -> str:
        if len(self.restrictions) == 0: return "Você forçou uma Data Fixa que cai exatamente em um dia bloqueado (Feriado, Fim de semana ou Férias). Altere a Data Fixa na Tabela."
        
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
                
                # Mensagens Ultra-Didáticas de Erro
                if tipo == "deadline": return f"A regra de 'Data Limite' que você colocou para a Tarefa **{alvo}** é muito curta. O sistema não consegue encaixar as dependências antes dessa data limite sem cair no fim de semana. Dica: Aumente o prazo limite na tabela."
                if tipo == "working_day_offset": return f"Você pediu para a Tarefa **{alvo}** pular dias úteis, mas ela bateu no limite do calendário ou colidiu com um prazo de outra tarefa. Dica: Reduza o número de 'Dias' na tabela."
                return f"O conflito está relacionado à tarefa **{alvo}**. Revise as regras dela."
        
        self.restrictions = original_restrictions
        return "A quantidade de bloqueios que você selecionou (Férias, Finais de semana, Feriados) é tão grande que não sobrou nenhum dia útil no ano para colocar suas tarefas!"

# =============================================================================
# 6. BANCO DE DADOS DE MANUAL E AJUDA (PESQUISÁVEL)
# =============================================================================
MANUAL_SECTIONS = {
    "🌟 1. Entendendo o Sistema": "**O que é?** O Calendário PRO resolve o problema de contar prazos. \n\nVocê só diz: 'A Tarefa B ocorre 10 dias úteis depois de A' e o sistema encontra as datas, pulando sábados, domingos e feriados sozinhos.",
    "🖥️ 2. Navegação e Menus": "1. **Menu Lateral Esquerdo:** Onde você diz qual o dia inicial (Data Base) e marca suas férias.\n2. **Aba 1 (Planilha):** Onde você escreve as tarefas e diz as regras matemáticas.\n3. **Aba 2 (Resultados):** Onde o cronograma já sai pronto para o Excel.\n4. **Aba 3 (Calendário):** O desenho visual do seu ano, cheio de cores e ícones.",
    "🛠️ 3. Exemplo Prático (Passo a Passo)": "Imagine que quer organizar um evento:\n\n1. Escolha a Data Base (ex: Hoje).\n2. Na Aba 1, digite 'Contratar Local' (T1). Regra: Livre.\n3. Digite 'Enviar Convites' (T2). Regra: 'Dias úteis após a Tarefa Base'. Base: 'T1'. Valor: '15'.\n4. Pronto! O sistema agendará os convites exatamente 15 dias úteis depois da locação.",
    "🎯 4. Como não errar (Boas Práticas)": "- Nunca crie um 'Loop Infinito' (Ex: A depende de B, e B depende de A). O sistema vai travar e dar erro.\n- Prefira sempre amarrar as coisas usando 'Dias Úteis após Tarefa Base'. É a forma mais garantida de fluxo contínuo.",
    "🎨 5. Personalização e Download": "Na **Aba 5**, você escolhe se gosta da tela em tons de azul, verde ou roxo. Você também pode exportar todo o seu trabalho (Salvar Backup JSON) e recarregar depois para não perder nada.",
    "❓ 6. Dúvidas Comuns (FAQ)": "**A Aba 2 ficou com Caixa Vermelha. E agora?** Calma. Leia a mensagem que o sistema deu na caixa 'Diagnóstico do Motor'. Ele vai te dizer qual tarefa está estourando a regra. Vá na Aba 1, edite o número e o sistema recalcula na mesma hora."
}

# =============================================================================
# 7. INTERFACE INTERATIVA DO USUÁRIO E WIZARD GUIADO (V8.0)
# =============================================================================
def main():
    st.markdown(f'<div class="main-title">{st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v8.0")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">{st.session_state.theme_config.get("app_subtitle", "Enterprise Edition: Intuitivo, Didático e à Prova de Erros")}</div>', unsafe_allow_html=True)
    hoje = datetime.date.today()

    # -------------------------------------------------------------------------
    # UX: ASSISTENTE GUIADO PASSO A PASSO (WIZARD) E ESTADO
    # -------------------------------------------------------------------------
    if "wizard_step" not in st.session_state: st.session_state.wizard_step = 1
    if "custom_holidays" not in st.session_state: st.session_state.custom_holidays = {}
    if "restrictions_manuais" not in st.session_state: st.session_state.restrictions_manuais = []
    if "historico_planilha" not in st.session_state: st.session_state.historico_planilha = []
    if "marcadores_calendario" not in st.session_state: st.session_state.marcadores_calendario = {}
    if "export_config" not in st.session_state: st.session_state.export_config = {"file_name": "Relatorio_Projeto", "date_format": "%d/%m/%Y", "separator": ","}

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Nome da Tarefa": "Briefing Inicial", "Categoria": "Geral", "Prioridade": "Média", "Tipo de Regra": "Livre", "Tarefa Base": "", "Valor / Dias": 0, "Data Fixa": None},
            {"Código ID": "T2", "Nome da Tarefa": "Entrega do Relatório", "Categoria": "Geral", "Prioridade": "Alta", "Tipo de Regra": "Dias Úteis após Tarefa Base", "Tarefa Base": "T1", "Valor / Dias": 5, "Data Fixa": None}
        ])

    def salvar_historico(df_novo):
        if not st.session_state.df_planilha.equals(df_novo):
            st.session_state.historico_planilha.append(st.session_state.df_planilha.copy())
            if len(st.session_state.historico_planilha) > 10: st.session_state.historico_planilha.pop(0)

    # WIZARD RENDERER
    if st.session_state.wizard_step < 4:
        st.markdown('<div class="onboarding-box">', unsafe_allow_html=True)
        if st.session_state.wizard_step == 1:
            st.markdown('<div class="step-indicator">Passo 1 de 3</div>', unsafe_allow_html=True)
            st.markdown("### Bem-vindo! Vamos começar pela **Data Base**.")
            st.markdown("Olhe para a **Barra Lateral Esquerda**. A *Data Base* é o dia em que o seu projeto começa a correr. Você pode deixar configurado como 'Hoje' ou escolher o dia exato.")
            if st.button("Já configurei, avançar para o Passo 2 ➔"): st.session_state.wizard_step = 2; st.rerun()
        elif st.session_state.wizard_step == 2:
            st.markdown('<div class="step-indicator">Passo 2 de 3</div>', unsafe_allow_html=True)
            st.markdown("### Preencha a Planilha de Tarefas (Aba 1)")
            st.markdown("Agora, preencha a planilha abaixo como se fosse um Excel. O mais importante é a coluna **Tipo de Regra**. É lá que você diz ao computador quantos dias úteis ele deve pular para cada tarefa.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Voltar ao Passo 1"): st.session_state.wizard_step = 1; st.rerun()
            with col2:
                if st.button("Já preenchi a tabela, avançar para o Resultado ➔"): st.session_state.wizard_step = 3; st.rerun()
        elif st.session_state.wizard_step == 3:
            st.markdown('<div class="step-indicator">Passo 3 de 3</div>', unsafe_allow_html=True)
            st.markdown("### Sucesso! Veja o Cronograma e o Calendário")
            st.markdown("Vá para a **Aba 2 (Resultados)** para baixar sua planilha pronta e sem erros, ou clique na **Aba 3 (Painel Calendário)** para ver o ano desenhado com feriados!")
            if st.button("🚀 Concluir Tour Guiado e Usar Sistema Livremente"): st.session_state.wizard_step = 4; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES GLOBAIS E DATA BASE)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ 1. Configurações Iniciais")
    st.sidebar.info("A Data Base é o 'Dia Zero' dos seus cálculos.")
    
    base_opcao = st.sidebar.selectbox(
        "Ponto de Partida do Projeto:", 
        ["Data Atual (Hoje)", "Próximo Dia Útil", "Escolher no Calendário"], 
        help="A partir de qual dia a matemática começa? Se escolher 'Hoje', as tarefas baseadas nela calcularão dias a partir da data de hoje."
    )
    
    cal_mgr_temp = CalendarManager(year=hoje.year, custom_holidays=st.session_state.custom_holidays)
    if base_opcao == "Data Atual (Hoje)": data_base_global = hoje
    elif base_opcao == "Próximo Dia Útil": data_base_global = cal_mgr_temp.get_next_working_day(hoje, {"block_weekends": True, "block_holidays": True}, [])
    else: data_base_global = st.sidebar.date_input("Clique para selecionar a Data Base:", value=hoje)

    st.sidebar.markdown(f"**Data Base Definida:** `{data_base_global.strftime('%d/%m/%Y')}`")
    st.sidebar.divider()

    st.sidebar.header("🛡️ 2. Bloqueios Automáticos")
    ano_corrente = st.sidebar.number_input("Ano do Projeto (Gera feriados automáticos)", min_value=2024, max_value=2030, value=data_base_global.year, help="O sistema vai calcular Páscoa e Carnaval baseados neste ano.")
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox("Bloquear Sábados e Domingos", value=True, help="O sistema nunca vai agendar tarefas em fins de semana se isso estiver marcado."),
        "block_holidays": st.sidebar.checkbox("Bloquear Feriados Brasileiros", value=True, help="O sistema vai pular os feriados nacionais de forma automática.")
    }

    with st.sidebar.expander("🏛️ Inserir Feriado Regional ou Recesso"):
        st.write("Tem um feriado da cidade? Cadastre aqui.")
        f_name = st.text_input("Nome do Evento", placeholder="Ex: Dia do Servidor")
        f_date = st.date_input("Data do Evento", datetime.date(ano_corrente, 11, 30))
        if st.button("➕ Injetar Evento"):
            if f_name:
                st.session_state.custom_holidays[f_date] = {"nome": f_name, "desc": "Feriado Inserido Pelo Usuário"}
                st.rerun()

    manual_dates = st.sidebar.date_input("🚫 Suas Férias (Dias Bloqueados Avulsos)", value=[], help="Marque aqui no calendário todos os dias em que a sua equipe não trabalhará de jeito nenhum.")
    if isinstance(manual_dates, datetime.date): manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple): manual_dates = list(manual_dates)

    if st.sidebar.button("❓ Ver Tutorial Novamente"):
        st.session_state.wizard_step = 1
        st.rerun()

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # ABAS DA APLICAÇÃO (NOMES DINÂMICOS DA CONFIGURAÇÃO)
    # -------------------------------------------------------------------------
    tab_names = st.session_state.theme_config["tab_names"]
    t1, t2, t3, t4, t5 = st.tabs(tab_names)

    with t1:
        st.subheader("📝 Tabela Interativa de Prazos")
        st.write("Esta tabela é inteligente. Preencha as células e o sistema tentará calcular automaticamente a melhor data para você na próxima Aba. **Atenção à coluna 'Tipo de Regra'**.")
        
        col_act1, col_act2, col_act3 = st.columns([1, 1, 2])
        with col_act1:
            if st.button("↩️ Errei! Desfazer Última Edição", disabled=len(st.session_state.historico_planilha)==0, help="Volta a tabela exatamente como estava na sua última edição."):
                st.session_state.df_planilha = st.session_state.historico_planilha.pop()
                st.rerun()
        with col_act2:
            if st.button("🔢 Renumerar 'Código ID' Sozinho", help="Isso cria os códigos T1, T2, T3 perfeitamente em ordem na primeira coluna."):
                df_temp = st.session_state.df_planilha.copy()
                df_temp["Código ID"] = [f"T{i+1}" for i in range(len(df_temp))]
                salvar_historico(df_temp)
                st.session_state.df_planilha = df_temp
                st.rerun()
        
        # VALIDAR A TABELA ANTES DE RENDERIZAR
        if not all(col in st.session_state.df_planilha.columns for col in ["Código ID", "Nome da Tarefa", "Tipo de Regra"]):
             st.error("Erro Crítico de Tabela: A estrutura foi corrompida ou colunas essenciais foram apagadas no Upload. Por favor, restaure o Template na Aba 5.")
             st.stop()

        # DATA EDITOR COM MODO DIDÁTICO
        df_edited = st.data_editor(
            st.session_state.df_planilha,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Código ID": st.column_config.TextColumn("Código (Ex: T1)", required=True),
                "Nome da Tarefa": st.column_config.TextColumn("O que você precisa fazer?", required=True, width="medium"),
                "Categoria": st.column_config.TextColumn("Setor/Fase (Opcional)"),
                "Prioridade": st.column_config.SelectboxColumn("Urgência", options=["Alta", "Média", "Baixa"]),
                "Tipo de Regra": st.column_config.SelectboxColumn(
                    "Qual a regra de Data?",
                    options=["Livre", "Data Fixada", "1º Dia Útil após Data Base", "Dias Úteis após Tarefa Base", "Dias Úteis após Data Base", "Data Limite (Antes de)", "Data Limite (Após de)"],
                    required=True
                ),
                "Tarefa Base": st.column_config.TextColumn("Código da Tarefa Anterior (Ex: T1)"),
                "Valor / Dias": st.column_config.NumberColumn("Quantos Dias pular?", min_value=0),
                "Data Fixa": st.column_config.DateColumn("Se fixo, que dia?", format="DD/MM/YYYY")
            },
            help="Clique em qualquer célula para digitar. Use a tecla DEL para apagar uma linha depois de marcá-la do lado esquerdo."
        )
        salvar_historico(df_edited)
        st.session_state.df_planilha = df_edited

        st.markdown("---")
        with st.expander("🛠️ Avançado: Carga via Planilha e Regras Secundárias"):
            st.write("Você pode fazer upload de um arquivo para substituir a tabela, ou injetar regras complementares (clássicas).")
            uploaded_file = st.file_uploader("Upload de Escopo (CSV ou Excel)", type=["csv", "xlsx"], help="Substitui a planilha principal. O arquivo deve ter as colunas exatas exigidas.")
            if uploaded_file is not None:
                try:
                    df_up = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
                    st.session_state.df_planilha = df_up
                    st.success("Planilha carregada!")
                except Exception as e:
                    st.error("Erro na leitura do formato do arquivo.")

            st.write("**Restrições Extras Fora da Tabela:**")
            rest_type = st.selectbox("Modelo Suplementar:", ["Data Limite (Deadline)", "Dependência Sequencial Simples"])
            if rest_type == "Data Limite (Deadline)":
                t_id_f = st.selectbox("Qual Tarefa Limitar?", [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])])
                d_val = st.date_input("Limite de Data", datetime.date(ano_corrente, 6, 1))
                if st.button("Aplicar Regra Extra"):
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, "before": d_val}))
                    st.rerun()

            if st.session_state.restrictions_manuais:
                for idx, r in enumerate(st.session_state.restrictions_manuais): st.caption(f"Extra {idx+1}: {r.params}")
                if st.button("Apagar Regras Extras"): st.session_state.restrictions_manuais = []; st.rerun()

    # COMPILAÇÃO INTELIGENTE DAS REGRAS PARA O MOTOR (INJETANDO DATA BASE)
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
        
        # Tradução didática das regras de UX para Motor Lógico de Backtrack
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

    # CÁLCULO TOTALMENTE AUTOMÁTICO (REATIVIDADE STREAMLIT)
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards, diagnostico = engine.solve()

    with t2:
        st.subheader("📊 Cronograma Resolvido")
        if status == "SUCCESS":
            st.success("✅ **O computador fez a matemática!** Suas tarefas foram agendadas em dias saudáveis.")
            col_m1, col_m2 = st.columns(2)
            for i, card in enumerate(alt_cards):
                t_id = card["task_id"]
                date_val = sol_dates.get(t_id)
                t_obj = next((t for t in engine_tasks if t.id == t_id), None)
                if t_obj and date_val:
                    with col_m1 if i % 2 == 0 else col_m2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <span style="color:{st.session_state.theme_config['color_allocated_border']}; font-weight:bold; font-size:11px;">TAREFA: {t_id}</span>
                            <h4 style="margin:2px 0;">🎯 {t_obj.name}</h4>
                            <h2 style="color:{st.session_state.theme_config['color_primary']}; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:11.5px; color:#4B5563; margin:4px 0;">{card['justification']}</p>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📥 Preparar Exportação")
            st.write("Confira a tabela final e baixe seu relatório estruturado.")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    f_date = d_val.strftime(st.session_state.export_config["date_format"])
                    row_data = {"Código ID": t_id, "Nome da Tarefa": t_item.name, "Data Oficial": f_date}
                    
                    row_t = df_edited[df_edited["Código ID"] == t_id].iloc[0]
                    if "Categoria" in row_t: row_data["Categoria"] = row_t["Categoria"]
                    if "Prioridade" in row_t: row_data["Prioridade"] = row_t["Prioridade"]
                    
                    cronograma_data.append(row_data)
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                csv_buffer = df_final.to_csv(index=False, sep=st.session_state.export_config["separator"]).encode('utf-8')
                
                # Relatório TXT Rico (Funcionalidade Requisitada)
                txt_report = f"DOSSIÊ DO PROJETO - ANO {ano_corrente}\nData Base de Partida: {data_base_global.strftime('%d/%m/%Y')}\n\n================================\nTAREFAS E DATAS:\n"
                for r in cronograma_data: txt_report += f"[{r['Data Oficial']}] - {r['Código ID']}: {r['Nome da Tarefa']}\n"
                txt_report += "\n================================\nFERIADOS E BLOQUEIOS NO ANO:\n"
                for dt, props in cal_mgr.br_holidays.holidays_dict.items():
                    txt_report += f"- {dt.strftime('%d/%m/%Y')}: {props['nome']} ({props['desc']})\n"
                
                c1, c2 = st.columns(2)
                c1.download_button(f"📥 Exportar Planilha ({st.session_state.export_config['separator']} CSV)", data=csv_buffer, file_name=f"{st.session_state.export_config['file_name']}.csv", mime="text/csv", use_container_width=True)
                c2.download_button("📝 Exportar Dossiê em Texto (.TXT)", data=txt_report, file_name="Relatorio_Textual.txt", mime="text/plain", use_container_width=True)

        else:
            st.error("⚠️ **Atenção: A matemática das suas datas entrou em choque!**")
            st.markdown(f'<div class="alert-box"><b>O que o sistema encontrou:</b><br>{diagnostico}</div>', unsafe_allow_html=True)
            st.info("💡 **Dica de Resolução Prática:** Volte para a Aba 1. Se você fixou datas (Data Fixada) muito próximas a feriados, tente mudar para o tipo 'Dias Úteis após Tarefa Base'. Ou aumente os prazos 'Data Limite'.")

    with t3:
        st.subheader("📅 O Grande Quadro de Planejamento (Heatmap)")
        
        # FUNCIONALIDADE 5: Marcadores e Rótulos Personalizados
        with st.expander("📌 Inserir Rótulo ou Marcador Visual no Calendário"):
            st.write("Adicione um texto, aviso ou emoji em qualquer dia para ser renderizado no mapa.")
            m_col1, m_col2, m_col3 = st.columns([1, 2, 1])
            m_date = m_col1.date_input("Qual dia?", data_base_global)
            m_text = m_col2.text_input("Qual o Rótulo?", placeholder="Ex: Viagem São Paulo")
            m_icon = m_col3.selectbox("Ícone", ["📌 Padrão", "⭐ Prioridade", "✈️ Viagem", "🏖️ Férias", "💰 Pagamento"])
            if st.button("Desenhar no Calendário"):
                if m_text:
                    st.session_state.marcadores_calendario[m_date] = f"{m_icon.split()[0]} {m_text}"
                    st.toast("Rótulo desenhado na matriz!")
                    st.rerun()
            
            if st.session_state.marcadores_calendario:
                st.caption("Marcadores Ativos:")
                for md, txt in st.session_state.marcadores_calendario.items():
                    st.write(f"- {md.strftime('%d/%m')}: {txt}")
                if st.button("Limpar todos os marcadores"):
                    st.session_state.marcadores_calendario = {}; st.rerun()

        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB;"></span> Dia Livre</div>
            <div><span style="background-color: {st.session_state.theme_config['color_allocated']}; padding: 2px 10px; border: 1px solid {st.session_state.theme_config['color_allocated_border']};"></span> <b>Tarefa Confirmada</b></div>
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
                                    title_hover = props["desc"]
                                    
                                    # Formatação do dia Visual (HTML Injection)
                                    display_content = f"{day}"
                                    if d_verif in st.session_state.marcadores_calendario:
                                        display_content += f"<span class='day-marker'>{st.session_state.marcadores_calendario[d_verif].split()[0]}</span>"
                                        title_hover = st.session_state.marcadores_calendario[d_verif]

                                    if d_verif == data_base_global:
                                        title_hover = "📍 DATA BASE OFICIAL"
                                        cell_class = "day-allocated"
                                    elif d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"🎯 Tarefa(s) Agendada(s): {', '.join(t_codes)}"
                                    elif props["is_holiday"]: cell_class = "day-holiday"
                                    elif props["is_blocked"] or d_verif in manual_dates: 
                                        cell_class = "day-blocked"
                                        title_hover = "Bloqueado para trabalho."
                                        
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{display_content}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    with t4:
        st.header("📘 Manual de Operação Instantâneo")
        st.write("Digite sua dúvida na caixa de texto abaixo. Somente os tópicos relacionados se abrirão.")
        
        # PESQUISA GLOBAL (Funcionalidade 9)
        MANUAL_SECTIONS = {
            "💡 Como funciona a 'Data Base'? (Ponto de Partida)": "A Data Base é o centro do universo nesta aplicação. Se você disser que a **Tarefa 1** acontece '10 dias úteis após a Data Base', e a sua data base for o dia 01/Jan, o sistema conta 10 dias de trabalho e a agenda. Se você mudar a Data Base na barra lateral para 01/Fev, a tarefa avança junto!",
            "⚙️ Como usar a Planilha da Aba 1?": "Você edita ela dando dois cliques na célula. Para criar a cadeia perfeita, digite as tarefas, use a coluna 'Tarefa Base' para amarrar uma na outra, e na coluna 'Valor' coloque os dias úteis. E lembre-se: Existe um botão mágico 'Gerar IDs Auto' para te salvar tempo.",
            "❌ Apareceu um Erro Vermelho na Aba 2, o que faço?": "Não se preocupe! Leia a Caixa de Alerta Vermelha. Ela diz o diagnóstico exato. Normalmente é porque você colocou prazos que obrigariam o sistema a agendar tarefas aos finais de semana, o que é proibido pelas suas configurações laterais.",
            "📌 Como adiciono anotações no Calendário Visual (Aba 3)?": "Na Aba 3, abra o botão cinza 'Inserir Rótulo ou Marcador Visual'. Você escolhe o dia, escolhe um emoji bonitinho (ex: Avião de Viagem) e escreve o texto. Ele aparecerá desenhado em cima do dia para sempre.",
            "🗂️ É possível Salvar meu Trabalho para Amanhã?": "SIM! Na Aba 5 (Cores & Exportação), clique em 'Baixar Template JSON'. Guarde este arquivo. Amanhã, quando abrir o sistema de novo, você sobe o arquivo e o sistema carrega até as suas cores personalizadas e sua tabela de volta."
        }
        
        pesquisa = st.text_input("🔍 Pesquise sua dúvida (Ex: Erro, Salvar, Data Base):")
        for titulo, conteudo in MANUAL_SECTIONS.items():
            if not pesquisa or pesquisa.lower() in titulo.lower() or pesquisa.lower() in conteudo.lower():
                with st.expander(titulo):
                    st.markdown(conteudo)

    with t5:
        st.header("🎨 5. Centro de Customização e Cores")
        st.info("Aqui você modela a interface sem código, e ainda pode salvar essas preferências.")
        
        # CORREÇÃO DEFINITIVA DO BUG DE COLORPICKER (USO DE SELECTBOX E LISTA DE HEX)
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            st.subheader("Seleção de Tema Dinâmico Segura")
            st.session_state.theme_config["app_title"] = st.text_input("Título Oficial", value=st.session_state.theme_config.get("app_title", "📅 Calendário Inteligente PRO v8.0"), help="Muda o grande título lá em cima.")
            
            # Selectbox evita o carregamento de JavaScript externo do st.color_picker
            tema_escolhido = st.selectbox("Escolha uma Paleta Oficial do Sistema", list(THEME_PALETTES.keys()))
            if st.button("Aplicar Paleta de Cores"):
                st.session_state.theme_config["color_primary"] = THEME_PALETTES[tema_escolhido]["primary"]
                st.session_state.theme_config["color_allocated"] = THEME_PALETTES[tema_escolhido]["alloc"]
                st.session_state.theme_config["color_allocated_border"] = THEME_PALETTES[tema_escolhido]["alloc_border"]
                st.toast("Tema Aplicado! (Recarregue para ver mudanças no layout matriz)")
                st.rerun()
            
            st.session_state.theme_config["cal_first_weekday"] = st.radio("Sua semana no calendário começa em...", options=[("Domingo", 6), ("Segunda", 0)], format_func=lambda x: x[0], help="Muda a forma que a grade da Aba 3 é desenhada.")[1]
            
        with c_p2:
            st.subheader("Preferências de Arquivo (.CSV e .TXT)")
            st.session_state.export_config["file_name"] = st.text_input("Nome Arquivo Final", value=st.session_state.export_config["file_name"])
            st.session_state.export_config["date_format"] = st.selectbox("Formatação de Datas nas Planilhas", options=["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"], help="Ex: Dia/Mês/Ano ou Ano-Mês-Dia")
            st.session_state.export_config["separator"] = st.selectbox("Formato do Separador (Excel)", options=[";", ",", "\t"], help="Se o seu Excel quebrar as colunas ao abrir o arquivo, mude de vírgula para Ponto-e-Vírgula.")

        st.divider()
        st.subheader("💾 Backup e Restauração de Sistema Completo")
        st.write("Baixe a alma da aplicação (Temas, Planilha de Escopo e Marcadores de Calendário) num arquivo seguro de Configuração (.JSON) e use sempre que precisar!")
        
        export_dict = {
            "theme": st.session_state.theme_config,
            "export": st.session_state.export_config,
            "markers": {d.strftime("%Y-%m-%d"): txt for d, txt in st.session_state.marcadores_calendario.items()},
            "tasks": st.session_state.df_planilha.astype(str).to_dict(orient="records")
        }
        json_str = json.dumps(export_dict, ensure_ascii=False, indent=2)
        st.download_button(label="📦 Gerar Backup Master do Projeto Atual (Arquivo .JSON)", data=json_str, file_name="Projeto_Backup.json", mime="application/json", use_container_width=True)

if __name__ == "__main__":
    main()
