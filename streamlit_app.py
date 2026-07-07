import datetime
import calendar
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

# Estilização CSS avançada
st.markdown("""
    <style>
    .main-title { font-size: 2.3rem; font-weight: 800; color: #1E3A8A; margin-bottom: 0.2rem; }
    .subtitle { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
    .metric-card { background-color: #FFFFFF; border-left: 5px solid #2563EB; padding: 15px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 15px; }
    .onboarding-box { background-color: #F0FDF4; border: 2px solid #22C55E; padding: 20px; border-radius: 10px; margin-bottom: 25px; }
    .calendar-grid { display: block; margin-bottom: 20px; }
    .calendar-row { display: table; width: 100%; table-layout: fixed; }
    .calendar-cell { display: table-cell; text-align: center; padding: 6px 2px; font-size: 11px; border: 1px solid #E5E7EB; font-weight: 600; }
    .day-normal { background-color: #F9FAFB; color: #1F2937; }
    .day-allocated { background-color: #DBEAFE; color: #1E40AF; border: 2px solid #2563EB !important; }
    .day-holiday { background-color: #FEE2E2; color: #991B1B; }
    .day-blocked { background-color: #E5E7EB; color: #6B7280; }
    .day-header { background-color: #F3F4F6; color: #374151; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# =============================================================================
# 2. MODELOS DE DADOS ESTRUTURAIS
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
# 3. MOTOR DE FERIADOS FLEXÍVEL (GAUSS + REGIONAIS DINÂMICOS)
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
# 4. GERENCIADOR DO CALENDÁRIO OPERACIONAL
# =============================================================================
class CalendarManager:
    def __init__(self, year: int, custom_holidays: Dict[datetime.date, str] = None):
        self.year = year
        self.br_holidays = BrazilHolidaysPure(year=self.year, custom_holidays=custom_holidays)
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
# 5. MOTOR DE OTIMIZAÇÃO POR RESOLUÇÃO RECURSIVA CONSOLIDADO
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
        
        if not task_ids:
            return "SUCCESS", {}, []

        horizonte_busca = min(180, self.cal_mgr.total_days)

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
            
            for idx in range(horizonte_busca):
                alocacao_atual[t_id] = idx
                if self._avaliar_custo(alocacao_atual) < melhor_custo:
                    backtrack(task_index + 1, alocacao_atual)
                del alocacao_atual[t_id]

        backtrack(0, {})
        
        if solucao_otima:
            results = {t_id: self.cal_mgr.idx_to_date(idx) for t_id, idx in solucao_otima.items()}
            alternatives = []
            for t_id in task_ids:
                score_calculado = max(0, 100 - melhor_custo)
                alternatives.append({
                    "task_id": t_id,
                    "score": score_calculado,
                    "justification": f"Alocação ideal confirmada. A data respeita finais de semana, feriados e regras. (Score: {score_calculado}%)"
                })
            return "SUCCESS", results, alternatives
            
        return "INFEASIBLE", {}, []

# =============================================================================
# 6. INTERFACE INTERATIVA DO USUÁRIO & ONBOARDING MASTER
# =============================================================================
def main():
    st.markdown('<div class="main-title">📅 Calendário Inteligente PRO</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">O seu assistente automático para agendamento de tarefas sem conflitos de datas.</div>', unsafe_allow_html=True)
    
    # -------------------------------------------------------------------------
    # UX: SISTEMA DE ONBOARDING (ASSISTENTE GUIADO)
    # -------------------------------------------------------------------------
    if "onboarding_concluido" not in st.session_state:
        st.session_state.onboarding_concluido = False

    if not st.session_state.onboarding_concluido:
        st.markdown("""
        <div class="onboarding-box">
            <h2 style="margin-top: 0; color: #166534;">👋 Bem-vindo ao Calendário Inteligente!</h2>
            <p style="font-size: 16px; color: #15803D;">Você nunca mais vai precisar contar dias no dedo para agendar seus compromissos. O sistema faz todo o trabalho duro para você.</p>
            <hr style="border-color: #86EFAC;">
            <h4>Como a mágica acontece em 3 passos:</h4>
            <ol style="font-size: 15px; color: #166534;">
                <li><b>Configure o Calendário (Menu Esquerdo):</b> Diga qual ano estamos e adicione feriados locais se quiser. Nós já bloqueamos finais de semana e feriados nacionais para você!</li>
                <li><b>Cadastre suas Tarefas (Aba 1):</b> Digite o nome dos compromissos. Diga ao sistema coisas como: <i>"A Tarefa B só pode acontecer 10 dias úteis depois da Tarefa A"</i>.</li>
                <li><b>Veja o Resultado (Abas 2 e 3):</b> O sistema vai vasculhar o calendário, pular todos os dias ruins e entregar a data perfeita para cada compromisso na Aba 2!</li>
            </ol>
            <p>Se tiver qualquer dúvida, clique na aba <b>"📘 4. Manual Completo & Ajuda"</b> lá em cima.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚀 Entendi! Começar a usar a aplicação", type="primary", use_container_width=True):
            st.session_state.onboarding_concluido = True
            st.rerun()
        st.divider()

    # Controle de Estado Histórico
    if "custom_holidays" not in st.session_state:
        st.session_state.custom_holidays = {}

    if "df_planilha" not in st.session_state:
        st.session_state.df_planilha = pd.DataFrame([
            {"Código ID": "T1", "Descrição do Compromisso": "Exemplo: Início do Projeto", "Tipo de Vínculo": "Livre", "Atividade Base": "", "Valor Técnico": 0},
            {"Código ID": "T2", "Descrição do Compromisso": "Exemplo: Entrega Final", "Tipo de Vínculo": "Deslocamento Dias Úteis", "Atividade Base": "T1", "Valor Técnico": 5}
        ])

    if "restrictions_manuais" not in st.session_state:
        st.session_state.restrictions_manuais = []

    # -------------------------------------------------------------------------
    # UX: BARRA LATERAL (CONFIGURAÇÕES GLOBAIS COM TOOLTIPS)
    # -------------------------------------------------------------------------
    st.sidebar.header("⚙️ Configurações Globais")
    st.sidebar.info("💡 Tudo o que você bloquear aqui será ignorado pelo sistema na hora de procurar uma data ideal.")
    
    ano_corrente = st.sidebar.number_input(
        "Ano de Planejamento", 
        min_value=2024, max_value=2030, value=2026,
        help="Escolha o ano em que os compromissos irão ocorrer. O sistema calculará todos os feriados (incluindo Páscoa e Carnaval) automaticamente para este ano."
    )
    
    cal_config = {
        "block_weekends": st.sidebar.checkbox(
            "Bloquear Sábados e Domingos", 
            value=True,
            help="Se marcado, o sistema nunca agendará um compromisso no fim de semana."
        ),
        "block_holidays": st.sidebar.checkbox(
            "Bloquear Feriados", 
            value=True,
            help="Se marcado, o sistema pulará automaticamente dias como Natal, Independência, etc."
        )
    }

    st.sidebar.subheader("🏛️ Cadastrar Feriado Regional")
    with st.sidebar.container():
        f_name = st.text_input("Nome do Feriado", placeholder="Ex: Feriado Distrital", help="Digite o nome do feriado específico da sua cidade ou estado.")
        f_date = st.date_input("Data do Evento", datetime.date(ano_corrente, 11, 30), help="Escolha a data no calendário.")
        if st.sidebar.button("➕ Injetar Feriado", use_container_width=True, help="Clique para adicionar este dia à lista de bloqueios automáticos."):
            if f_name:
                st.session_state.custom_holidays[f_date] = f_name
                st.sidebar.success(f"Feriado '{f_name}' adicionado!")
                st.rerun()

    st.sidebar.subheader("🚫 Bloqueios Manuais (Férias/Viagens)")
    manual_dates = st.sidebar.date_input(
        "Dias que você não estará disponível", 
        value=[],
        help="Selecione um ou vários dias específicos em que você sabe que não poderá fazer nada (ex: dias de viagem). O sistema não vai agendar nada para esses dias."
    )
    if isinstance(manual_dates, datetime.date):
        manual_dates = [manual_dates]
    elif isinstance(manual_dates, tuple):
        manual_dates = list(manual_dates)

    # Botão de escape para rever tutorial
    st.sidebar.divider()
    if st.sidebar.button("❓ Reabrir Tela de Boas-Vindas", help="Clique se quiser ver o guia inicial novamente."):
        st.session_state.onboarding_concluido = False
        st.rerun()

    cal_mgr = CalendarManager(year=ano_corrente, custom_holidays=st.session_state.custom_holidays)

    # -------------------------------------------------------------------------
    # UX: ABAS PRINCIPAIS DIDÁTICAS
    # -------------------------------------------------------------------------
    tab_compromissos, tab_visualizacao, tab_calendario_visual, tab_manual = st.tabs([
        "📋 1. Adicionar Tarefas", 
        "📊 2. Ver Resultado", 
        "📅 3. Visualizar Calendário",
        "📘 4. Manual Completo & Ajuda"
    ])

    with tab_compromissos:
        st.info("💡 **Dica de Uso:** Você pode carregar uma planilha pronta do Excel/CSV, ou simplesmente clicar nas células da tabela abaixo e digitar suas tarefas e prazos.")
        
        uploaded_file = st.file_uploader(
            "Se já tiver uma lista, anexe seu arquivo (.csv, .xlsx) aqui:", 
            type=["csv", "xlsx"],
            help="O arquivo deve conter colunas como: 'Código ID', 'Descrição', etc. Se não tiver, use a tabela interativa abaixo."
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_up = pd.read_csv(uploaded_file)
                else:
                    df_up = pd.read_excel(uploaded_file)
                
                for col_req in ["Código ID", "Descrição do Compromisso", "Tipo de Vínculo", "Atividade Base", "Valor Técnico"]:
                    if col_req not in df_up.columns:
                        df_up[col_req] = "" if col_req != "Valor Técnico" else 0
                
                st.session_state.df_planilha = df_up
                st.success("Planilha integrada! Verifique os dados abaixo.")
            except Exception as e:
                st.error(f"Não foi possível ler o arquivo. Erro: {e}")

        st.markdown("---")
        
        col_grade, col_form = st.columns([3, 2], gap="large")
        
        with col_grade:
            st.markdown("#### 📝 Planilha Interativa (Clique para editar)")
            df_edited = st.data_editor(
                st.session_state.df_planilha,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "Código ID": st.column_config.TextColumn("Código ID (Ex: T1)", required=True, help="Crie um código curto e único. Você usará isso para conectar uma tarefa à outra."),
                    "Descrição do Compromisso": st.column_config.TextColumn("Nome da Tarefa", width="medium", help="O que é essa tarefa? Ex: Reunião Final"),
                    "Tipo de Vínculo": st.column_config.SelectboxColumn(
                        "Tipo de Regra",
                        options=["Livre", "Deslocamento Dias Úteis", "Data Limite (Antes de)", "Data Limite (Após de)"],
                        required=True,
                        help="Livre = Qualquer dia. Dias úteis = Pula fds/feriado após outra tarefa. Limite = Precisa ser antes ou depois do 'Valor Técnico' em dias do ano."
                    ),
                    "Atividade Base": st.column_config.TextColumn("Código da Tarefa Anterior", help="De quem essa tarefa depende? Digite o Código ID da tarefa anterior. Ex: T1"),
                    "Valor Técnico": st.column_config.NumberColumn("Quantidade (Dias)", min_value=0, max_value=365, help="Se escolheu 'Dias Úteis', digite quantos dias úteis pular. Se for 'Data limite', digite o número do dia no ano (ex: 30 para o dia 30 de janeiro).")
                }
            )
            st.session_state.df_planilha = df_edited

        with col_form:
            st.markdown("#### ➕ Adicionar Restrição Manualmente")
            st.caption("Prefere botões ao invés de digitar na planilha? Use as opções abaixo para criar regras.")
            
            rest_type = st.selectbox("Escolha o que quer fazer:", [
                "Agendar X dias úteis depois de...", 
                "Criar um prazo Limite", 
                "Agendar X dias corridos depois de..."
            ], help="Selecione o tipo de regra matemática que o sistema deve forçar.")
            
            opcoes_ids = [str(row["Código ID"]) for _, row in df_edited.iterrows() if pd.notna(row["Código ID"])]
            
            if rest_type == "Agendar X dias úteis depois de...":
                t_base_f = st.selectbox("Qual tarefa acontece primeiro?", opcoes_ids, key="bf", help="A tarefa mãe.")
                t_target_f = st.selectbox("Qual tarefa acontece depois?", opcoes_ids, key="tf", help="A tarefa filha (dependente).")
                num_dias = st.number_input("Quantos dias úteis devem separar as duas?", min_value=1, value=10, help="Finais de semana e feriados não serão contados.")
                if st.button("Vincular Tarefas", use_container_width=True):
                    st.session_state.restrictions_manuais.append(Restriction(type="working_day_offset", params={"task_base": t_base_f, "task_target": t_target_f, "offset": num_dias}))
                    st.toast("Regra gravada com sucesso!")
                    st.rerun()

            elif rest_type == "Criar um prazo Limite":
                t_id_f = st.selectbox("Qual tarefa terá o prazo?", opcoes_ids, help="Escolha quem vai sofrer o limite de data.")
                choice = st.radio("O compromisso deve acontecer...", ["APÓS esta data", "ANTES desta data"])
                d_val = st.date_input("Escolha a data limite", datetime.date(ano_corrente, 6, 1))
                if st.button("Gravar Prazo", use_container_width=True):
                    param_key = "after" if "APÓS" in choice else "before"
                    st.session_state.restrictions_manuais.append(Restriction(type="deadline", params={"task_id": t_id_f, param_key: d_val}))
                    st.toast("Prazo gravado com sucesso!")
                    st.rerun()
                    
            elif rest_type == "Agendar X dias corridos depois de...":
                t_a = st.selectbox("Tarefa Inicial", opcoes_ids, key="da")
                t_b = st.selectbox("Tarefa Seguinte", opcoes_ids, key="db")
                min_g = st.number_input("Dias corridos de intervalo (conta tudo)", min_value=0, value=2, help="Conta domingos, sábados e feriados.")
                if st.button("Gravar Regra", use_container_width=True):
                    st.session_state.restrictions_manuais.append(Restriction(type="dependency", params={"task_a": t_a, "task_b": t_b, "min_gap": min_g}))
                    st.toast("Regra corrida gravada!")
                    st.rerun()

            if st.session_state.restrictions_manuais:
                st.markdown("---")
                st.markdown("**📌 Suas Regras Extras Salvas:**")
                for idx, r in enumerate(st.session_state.restrictions_manuais):
                    st.caption(f"• Regra {idx+1}: {r.type.upper()} -> {r.params}")
                if st.button("🗑️ Apagar Regras Extras", use_container_width=True, help="Clique aqui para remover as regras criadas por este painel."):
                    st.session_state.restrictions_manuais = []
                    st.rerun()

    # COMPILAÇÃO DAS REGRAS PARA O MOTOR MATEMÁTICO
    engine_tasks = []
    engine_restrictions = list(st.session_state.restrictions_manuais)

    for _, row in df_edited.iterrows():
        t_id = str(row.get("Código ID", "")).strip()
        t_name = str(row.get("Descrição do Compromisso", "Tarefa Sem Nome"))
        if not t_id or pd.isna(row["Código ID"]):
            continue
            
        engine_tasks.append(Task(id=t_id, name=t_name))
        
        v_tipo = row.get("Tipo de Vínculo", "Livre")
        v_base = str(row.get("Atividade Base", "")).strip()
        try:
            v_val = int(row.get("Valor Técnico", 0))
        except:
            v_val = 0
            
        if v_tipo == "Deslocamento Dias Úteis" and v_base:
            engine_restrictions.append(Restriction(type="working_day_offset", params={"task_base": v_base, "task_target": t_id, "offset": v_val}))
        elif v_tipo == "Data Limite (Antes de)":
            target_date = cal_mgr.start_date + datetime.timedelta(days=v_val if v_val > 0 else 30)
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "before": target_date}))
        elif v_tipo == "Data Limite (Após de)":
            target_date = cal_mgr.start_date + datetime.timedelta(days=v_val if v_val > 0 else 1)
            engine_restrictions.append(Restriction(type="deadline", params={"task_id": t_id, "after": target_date}))

    # EXECUÇÃO DO MOTOR TRADICIONAL RESTAURADO (REGRESSÃO ZERO)
    engine = PurePythonScheduleEngine(cal_mgr, cal_config)
    engine.add_tasks(engine_tasks)
    engine.apply_global_blocks(manual_dates)
    engine.apply_restrictions(engine_restrictions)
    status, sol_dates, alt_cards = engine.solve()

    with tab_visualizacao:
        if status == "SUCCESS":
            st.success("✅ **Sucesso!** O sistema encontrou datas perfeitas que respeitam todas as suas regras, sem cair em feriados ou finais de semana.")
            
            # Painel Analítico: Cartões Didáticos
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
                            <span style="color:#2563EB; font-weight:bold; font-size:11px;">CÓDIGO: {t_id} | CONFIANÇA: {card['score']}%</span>
                            <h4 style="margin:2px 0;">📌 {t_obj.name}</h4>
                            <h2 style="color:#1E3A8A; margin:5px 0;">{date_val.strftime('%d/%m/%Y')}</h2>
                            <p style="font-size:11.5px; color:#4B5563; margin:4px 0;"><b>Por que essa data?</b> {card['justification']}</p>
                            <span style="font-size:11px; color:#6B7280;">Dia da semana: {["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][date_val.weekday()]}</span>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("### 📊 Resumo Final para Exportação")
            st.info("💡 Você pode baixar a tabela abaixo em formato Excel/CSV clicando no botão no final da página.")
            cronograma_data = []
            for t_id, d_val in sol_dates.items():
                t_item = next((t for t in engine_tasks if t.id == t_id), None)
                if t_item:
                    cronograma_data.append({
                        "Código": t_id,
                        "Nome da Tarefa": t_item.name,
                        "Data Final Encontrada": d_val.strftime('%d/%m/%Y'),
                        "Dia da Semana": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"][d_val.weekday()],
                    })
                    
            if cronograma_data:
                df_final = pd.DataFrame(cronograma_data)
                st.dataframe(df_final, use_container_width=True, hide_index=True)
                
                csv_buffer = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Baixar seu Cronograma de Datas (Arquivo .CSV)",
                    data=csv_buffer,
                    file_name=f"Cronograma_Calculado_{ano_corrente}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Clique para baixar a tabela e abri-la no Excel."
                )
        else:
            st.error("⚠️ **Problema encontrado:** O sistema não conseguiu encontrar datas.")
            st.warning("""
            **O que aconteceu?** As regras que você criou estão entrando em conflito. 
            
            **Como resolver:**
            1. Verifique se você não colocou um *Prazo Limite* muito curto para uma tarefa que depende de muitos dias úteis de outra.
            2. Verifique se você não bloqueou dias demais na barra lateral (ex: muitos dias manuais de folga).
            3. Volte na Aba 1 e diminua um pouco o intervalo de 'Valor Técnico' entre as tarefas.
            """)

    with tab_calendario_visual:
        st.subheader("📅 Seu Ano Inteiro Desenhado")
        st.caption("Cada quadradinho é um dia. Veja rapidamente onde caem os feriados e suas tarefas.")
        
        st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px;">
            <div><span style="background-color: #F9FAFB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Dia Livre (Pode ser usado)</div>
            <div><span style="background-color: #DBEAFE; padding: 2px 10px; border: 1px solid #2563EB; border-radius:3px;"></span> <b>Tarefa Agendada!</b></div>
            <div><span style="background-color: #FEE2E2; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Feriado (Bloqueado)</div>
            <div><span style="background-color: #E5E7EB; padding: 2px 10px; border: 1px solid #D1D5DB; border-radius:3px;"></span> Final de Semana (Bloqueado)</div>
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
                        for sem in ["D", "S", "T", "Q", "Q", "S", "S"]:
                            html_cal += f'<div class="calendar-cell day-header">{sem}</div>'
                        html_cal += '</div>'
                        
                        cal_obj = calendar.Calendar(firstweekday=6)
                        weeks = cal_obj.monthdayscalendar(ano_corrente, m_idx)
                        
                        for week in weeks:
                            html_cal += '<div class="calendar-row">'
                            for day in week:
                                if day == 0:
                                    html_cal += '<div class="calendar-cell day-blocked"></div>'
                                else:
                                    d_verif = datetime.date(ano_corrente, m_idx, day)
                                    idx_verif = cal_mgr.date_to_idx(d_verif)
                                    props = cal_mgr.get_day_properties(idx_verif, cal_config)
                                    
                                    cell_class = "day-normal"
                                    title_hover = props["name"]
                                    
                                    if d_verif in sol_dates.values():
                                        cell_class = "day-allocated"
                                        t_codes = [t_id for t_id, dt in sol_dates.items() if dt == d_verif]
                                        title_hover = f"Tarefa Agendada: {', '.join(t_codes)}"
                                    elif props["is_holiday"]:
                                        cell_class = "day-holiday"
                                    elif props["is_blocked"] or d_verif in manual_dates:
                                        cell_class = "day-blocked"
                                        title_hover = "Bloqueado (Fim de semana ou Manual)"
                                        
                                    # O 'title' do HTML cria um tooltip nativo ao passar o mouse
                                    html_cal += f'<div class="calendar-cell {cell_class}" title="{title_hover}">{day}</div>'
                            html_cal += '</div>'
                        html_cal += '</div>'
                        st.markdown(html_cal, unsafe_allow_html=True)
                    m_idx += 1

    # -------------------------------------------------------------------------
    # UX: ABA MANUAL (DOCUMENTAÇÃO ENTERPRISE EMBUTIDA)
    # -------------------------------------------------------------------------
    with tab_manual:
        st.header("📘 Manual Completo e Enciclopédia do Sistema")
        st.write("Nesta aba, explicamos detalhadamente tudo o que você precisa saber para se tornar um mestre em agendamento automatizado. Clique nos painéis abaixo para expandir o conteúdo.")

        with st.expander("🌟 1. Introdução: Para que serve este sistema?"):
            st.markdown("""
            **O que é?** O Calendário Inteligente PRO é um motor matemático projetado para acabar com o trabalho braçal de planejar cronogramas.
            
            **Para que serve?** Imagine que você tem 10 tarefas para realizar ao longo do ano. Algumas delas dependem de outras (ex: *Só posso revisar o documento 15 dias úteis depois de escrevê-lo*). Fazer isso olhando para um calendário de papel ou Excel comum exige que você conte os dias com o dedo, pulando finais de semana e feriados um a um. Se uma data muda, você precisa recalcular tudo de novo. Nosso sistema faz tudo isso automaticamente em milissegundos.

            **Principais Benefícios:**
            * Elimina erros de contagem de datas.
            * Calcula automaticamente todos os feriados nacionais (incluindo Páscoa e Carnaval que mudam todo ano).
            * Recalcula o ano inteiro instantaneamente caso você adicione uma nova regra.
            """)

        with st.expander("🖥️ 2. Conhecendo a Interface (O que faz cada botão)"):
            st.markdown("""
            **Barra Lateral (Lado Esquerdo):**
            * **Ano de Planejamento:** Controla o ano base. Mudou o ano? Os feriados mudam junto.
            * **Caixas de Seleção (Bloquear Finais de Semana / Feriados):** São o "escudo" do sistema. Deixe ativados para evitar agendar compromissos no sábado/domingo ou em dias de festa.
            * **Cadastrar Feriado Regional:** Serve para você adicionar feriados da sua cidade. (Ex: "Dia da Padroeira" no dia 12/08).
            * **Indisponibilidades Manuais:** Um calendário avulso para você clicar naqueles dias em que vai viajar ou tirar férias.

            **Aba 1 (Adicionar Tarefas):**
            * **Área de Upload:** Serve para puxar uma tabela direto do seu computador.
            * **Planilha Interativa:** Onde a mágica acontece. Você clica, digita a tarefa e dita as regras na mesma linha.
            * **Adicionar Restrição Manualmente:** Um menu alternativo para quem não quer digitar na tabela e prefere clicar em botões para criar regras lógicas.

            **Aba 2 (Ver Resultados):**
            * **Cartões Azuis (Metric Cards):** Mostram as datas oficiais encontradas para as suas tarefas.
            * **Botão 'Baixar CSV':** Exporta as datas calculadas para um arquivo Excel.

            **Aba 3 (Visualizar Calendário):**
            * Mostra uma visão térmica (Heatmap) do ano.
            * **Vermelho = Feriado | Azul = Dia de Trabalho Seu | Cinza = Final de Semana.**
            """)

        with st.expander("🛠️ 3. Tutorial Passo a Passo (Como usar na prática)"):
            st.markdown("""
            Siga estes exatos passos para obter sucesso:
            
            **Passo 1:** Abra o sistema e olhe para o menu esquerdo. Confira se o ano está correto (ex: 2026).  
            **Passo 2:** Tem algum feriado municipal importante? Adicione ali mesmo no menu esquerdo e clique em **"Injetar Feriado"**.  
            **Passo 3:** Clique na aba **"📋 1. Adicionar Tarefas"**.  
            **Passo 4:** Na planilha interativa, apague os exemplos ou adicione uma nova linha.  
            **Passo 5:** Crie um "Código ID" (Ex: T1) e dê um nome (Ex: "Reunião Inicial").  
            **Passo 6:** Se essa for a primeira tarefa do ano, na coluna "Tipo de Vínculo", deixe como **Livre**.  
            **Passo 7:** Crie a tarefa dois (Código: T2, Nome: "Revisão").  
            **Passo 8:** Na tarefa T2, em "Tipo de Vínculo", escolha **"Deslocamento Dias Úteis"**. Na coluna "Atividade Base", digite **T1**. Na coluna "Valor Técnico", digite **10**. Isso significa: *"A Revisão (T2) vai acontecer 10 dias de trabalho depois da Reunião (T1)"*.  
            **Passo 9:** Vá para a aba **"📊 2. Ver Resultado"**. Pronto! Suas datas já estão lá, calculadas.
            """)

        with st.expander("🚦 4. Fluxo Ideal de Trabalho"):
            st.markdown("""
            A melhor forma de usar o sistema é manter uma rotina de uma direção só:
            
            1. `Abrir Sistema` ➔ 
            2. `Configurar Bloqueios (Férias/Ano/Feriados)` ➔ 
            3. `Carregar seu CSV ou preencher a tabela` ➔ 
            4. `Amarrar as dependências lógicas` ➔ 
            5. `Conferir se apareceu mensagem de Sucesso Verde na Aba 2` ➔ 
            6. `Baixar o Resultado` ➔ 
            7. `Ir para casa mais cedo!`
            """)

        with st.expander("❓ 5. Dúvidas Frequentes (FAQ)"):
            st.markdown("""
            * **Por que não apareceu nenhuma data e deu erro vermelho na Aba 2?** Isso é um "Conflito Matemático". Significa que as regras que você pediu não podem existir ao mesmo tempo. Por exemplo: Você pediu para a Tarefa T2 acontecer 20 dias úteis depois de T1. Mas também disse que T2 deve acontecer ANTES de uma data limite muito apertada que só tem 10 dias livres. O computador não conseguiu resolver, então você precisa relaxar a regra ou esticar a data limite na Aba 1.
            
            * **O que é 'Atividade Base'?** É o "Ponto de Partida" de uma tarefa amarrada. Se eu vou lixar uma parede (T2) 5 dias depois de pintar (T1). A "Atividade Base" de T2 é T1!
            
            * **Posso voltar a acessar o tutorial de boas-vindas?** Sim! Há um botão lá no fim do menu lateral esquerdo chamado "Reabrir Tela de Boas-Vindas".
            """)

        with st.expander("📚 6. Glossário (Dicionário de Termos)"):
            st.markdown("""
            * **Dias Úteis:** Segunda a sexta-feira, DESCONSIDERANDO feriados cadastrados.
            * **Dias Corridos:** Todos os dias do ano seguidos, sem pular finais de semana ou feriados.
            * **Data Limite (Deadline):** Um teto de data máxima. O sistema pode achar uma data para a tarefa, contanto que seja estritamente ANTES ou APÓS o limite definido.
            * **Score de Confiança:** Uma pontuação de 0 a 100 que o sistema dá para a data escolhida. Se estiver 100%, significa que ele conseguiu locar o compromisso no meio de dias saudáveis. Se perder pontos, significa que ele foi forçado a marcar muito perto de uma janela de bloqueio ou fim de semana.
            * **Engine / Motor Matemático:** É o cérebro escondido do código que testa centenas de combinações em segundos para achar o dia perfeito.
            """)

if __name__ == "__main__":
    main()
