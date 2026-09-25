"""Corpus pareado da revisão 2.3. Campos privados nunca entram nos prompts."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

VERSION = '2.3.0'

@dataclass(frozen=True)
class Task:
    id: str
    pair_id: str
    family: str
    member: int
    context: str
    candidates: dict[str, str]  # IDs canônicos, independentemente de A/B
    fact: str
    evidence: str
    rubric: dict

    def labels(self, seed: int, repeat: int = 1) -> dict[str, str]:
        # Ordem idêntica nos dois membros; alterna entre repetições e balanceia pares.
        flip = (int(self.pair_id[1:]) % 2) ^ (seed % 2) ^ ((repeat - 1) % 2)
        ids = list(self.candidates)
        return {'A': ids[flip], 'B': ids[1-flip]}

    def public(self, seed: int, repeat: int = 1) -> str:
        labels = self.labels(seed, repeat)
        return (f'Tarefa {self.id}. {self.context}\n\n'
                f'Candidato A: {self.candidates[labels["A"]]}\n'
                f'Candidato B: {self.candidates[labels["B"]]}\n\n'
                f'Documentação do caso: {self.fact}\n'
                'Escolha pelo objetivo declarado e pelos fatos disponíveis. Se faltar um dado indispensável, responda informação insuficiente.')


def _task(pair, family, member, context, candidates, fact, evidence, rubric):
    return Task(f'{pair}-{member+1}', pair, family, member, context,
                dict(candidates), fact, evidence, dict(rubric))

TASKS: list[Task] = []

def add(pair, family, context, candidates, cases):
    for i, (fact, evidence, gold, after, decisive) in enumerate(cases):
        TASKS.append(_task(pair, family, i, context, candidates, fact, evidence,
                           {'initial': gold, 'after': after, 'decisive': decisive,
                            'evidence_behavior': 'confirmar' if gold == after else 'atualizar'}))

# Comparação de desempenho só se aplica entre candidatos metodologicamente válidos.
add('t01', 'temporal',
    'Na triagem, prever complicação antes da decisão clínica. O relatório de validação temporal, com mesmos pacientes e janela, indica perda 8 para o candidato com laudo e 12 para o sem laudo. Escolha a menor perda entre pipelines executáveis no instante da previsão.',
    {'with': 'Usa o resultado do laudo de admissão, obtido por timestamp, e valida em admissões futuras.',
     'without': 'Não usa esse laudo e valida em admissões futuras.'}, [
    ('O laudo é liberado 30 minutos antes da triagem.', 'Auditoria de timestamps confirma liberação 30 minutos antes da triagem.', 'with', 'with', 'disponibilidade do laudo'),
    ('O laudo é liberado 30 minutos depois da triagem.', 'Auditoria de timestamps confirma liberação 30 minutos depois da triagem.', 'without', 'without', 'disponibilidade do laudo')])
add('t02', 'temporal',
    'Prever fraude no instante de autorização de uma compra. Perda validada em fluxo cronológico: 6 para usar status de liquidação e 10 para ignorá-lo. Escolha a menor perda apenas entre pipelines executáveis na autorização.',
    {'settle': 'Inclui status de liquidação no vetor de atributos no momento da autorização; valida em compras futuras.',
     'snapshot': 'Usa somente o retrato dos dados no momento da autorização; valida em compras futuras.'}, [
    ('Liquidação às 10h, materialização do status no feed às 10h01 e autorização às 10h05; o status está no retrato.', 'Log de eventos confirma a liquidação anterior à autorização.', 'settle', 'settle', 'ordem autorização/liquidação'),
    ('Liquidação às 10h, autorização às 10h05 e materialização do status no feed apenas no dia seguinte.', 'Auditoria do feed confirma que o status só foi materializado no dia seguinte à autorização.', 'snapshot', 'snapshot', 'ordem autorização/liquidação')])
add('t03', 'temporal',
    'Prever demanda de amanhã às 18h. Backtest por origem de previsão mostra erro 4 para usar a série revisada e 7 para usar a versão original. Escolha menor erro somente se os valores usados existem na origem.',
    {'revised': 'Usa a versão revisada do estoque de hoje; treino e teste respeitam a origem de cada previsão.',
     'asof': 'Usa o estoque de hoje salvo às 18h; treino e teste respeitam a origem de cada previsão.'}, [
    ('O arquivo versionado preserva, para cada origem histórica e para hoje, a revisão publicada às 17h antes da previsão das 18h.', 'Carimbo de publicação auditado: 17h do mesmo dia.', 'revised', 'revised', 'publicação da revisão'),
    ('O arquivo histórico foi sobrescrito pela versão final, publicada dois dias após cada origem de previsão; não há revisão disponível às 18h.', 'Auditoria confirma publicação dois dias após cada origem histórica e após a previsão de hoje.', 'asof', 'asof', 'publicação da revisão')])
add('t04', 'temporal',
    'No momento da alta, prever retorno em 30 dias. A validação prospectiva indica perda 5 com código de alta consolidado e 9 sem ele. Escolha a menor perda entre candidatos disponíveis na alta.',
    {'coded': 'Usa o código de alta consolidado como atributo; valida em altas posteriores.',
     'plain': 'Usa apenas sinais clínicos fechados antes da alta; valida em altas posteriores.'}, [
    ('O código é assinado antes da decisão de alta.', 'Trilha de assinatura confirma assinatura antes da decisão.', 'coded', 'coded', 'assinatura do código'),
    ('O código é consolidado após o fechamento da internação, no dia seguinte.', 'Trilha de assinatura confirma fechamento no dia seguinte.', 'plain', 'plain', 'assinatura do código')])

add('g01', 'grupos',
    'Avaliar diagnóstico em visitas futuras. As visitas são ordenadas por data; nenhum exemplo posterior pode treinar uma previsão anterior. Erro validado: 12 no holdout de pacientes e 9 no holdout cronológico dentro de paciente. Escolha o menor erro entre esquemas que representam a implantação.',
    {'new': 'Reserva pacientes inteiros para teste em visitas após o corte; treina só com visitas anteriores de outros pacientes. Pode usar histórico do paciente como entrada, mas não ajusta parâmetros com seus rótulos.',
     'known': 'Modelo personalizado: para cada paciente acompanhado, treina com visitas rotuladas anteriores e testa em visitas posteriores do mesmo paciente.'}, [
    ('A implantação atende pacientes inteiramente novos.', 'Cadastro de implantação confirma que nenhum paciente avaliado tem visita no treino.', 'new', 'new', 'população nova e ordem temporal'),
    ('A implantação prevê próximas visitas dos pacientes já acompanhados.', 'Cadastro confirma histórico anterior de cada paciente avaliado.', 'known', 'known', 'pacientes conhecidos e ordem temporal')])
add('g02', 'grupos',
    'Prever falha de equipamentos instalados no futuro. Ambos os esquemas treinam apenas com medições anteriores ao corte temporal. Erro 6 no corte por linha, 8 no corte por equipamento. Escolha menor erro entre esquemas sem contaminação da população futura.',
    {'row': 'Separa medições por data, permitindo o mesmo equipamento nos dois lados.',
     'device': 'Separa equipamentos inteiros instalados após o corte; datas de treino anteriores às de teste.'}, [
    ('Cada equipamento aparece uma única vez na base e na implantação.', 'Inventário auditado confirma uma linha por equipamento.', 'row', 'row', 'multiplicidade por equipamento'),
    ('Cada equipamento tem dezenas de medições; a implantação cobre equipamentos ainda não observados.', 'Inventário confirma múltiplas linhas por equipamento.', 'device', 'device', 'multiplicidade por equipamento')])
add('g03', 'grupos',
    'Estimar risco para novos domicílios no trimestre seguinte. Os dois candidatos usam treino anterior ao trimestre de teste. Erro 7 para separação por pessoa e 10 por domicílio. Escolha menor erro sem compartilhar domicílio entre treino e teste.',
    {'person': 'Mantém pessoas disjuntas, mas pessoas do mesmo domicílio podem cair em treino e teste.',
     'house': 'Mantém domicílios inteiros disjuntos entre treino e trimestre de teste.'}, [
    ('Há exatamente uma pessoa cadastrada por domicílio.', 'Cadastro auditado confirma uma pessoa por domicílio.', 'person', 'person', 'pessoas por domicílio'),
    ('Há várias pessoas por domicílio, com renda compartilhada.', 'Cadastro auditado confirma várias pessoas por domicílio.', 'house', 'house', 'pessoas por domicílio')])
add('g04', 'grupos',
    'Prever renovação de empresas novas no próximo ano. As duas validações reservam empresas inteiras; a validação por sorteio tem erro 5 e a temporal tem erro 8. Escolha a de menor erro que represente a implantação futura.',
    {'random': 'Sorteia empresas inteiras entre treino e teste usando anos históricos anteriores à implantação.',
     'forward': 'Reserva empresas do último ano histórico para teste e treina só com anos anteriores, preservando grupos e tempo.'}, [
    ('A documentação sobre estabilidade da política de renovação entre anos não está disponível.', 'Auditoria da política confirma regras e distribuição estáveis entre os anos históricos e o próximo ano.', 'insufficient', 'random', 'estabilidade temporal da política'),
    ('A política, as covariáveis e a distribuição dos desfechos mudaram em cada virada anual histórica; uma mudança comparável está prevista antes do próximo ano. Assim, o último ano histórico representa uma implantação após mudança.', 'Auditoria corrige o registro: a política foi a mesma em todos os anos históricos e seguirá no próximo ano; as distribuições de covariáveis e desfechos foram estáveis e devem permanecer assim no próximo ano.', 'forward', 'random', 'estabilidade temporal da política')])

# Quatro mecanismos: custo direto, transporte por prevalência, capacidade e
# normalização por coortes de tamanhos distintos.
_COST_CASES = [
    ('c01', 'custos',
     'Escolher limiar de alerta em 1000 casos. Custo por erro = FP × custo_FP + FN × custo_FN; as demais condições são iguais.',
     {'strict': 'Limiar estrito: FP=5, FN=30, TP=70, TN=895.',
      'loose': 'Limiar permissivo: FP=25, FN=10, TP=90, TN=875.'}, [
      ('Custo_FP=1 e custo_FN=10.', 'Planilha auditada confirma custo_FP=1 e custo_FN=10.', 'loose', 'loose', {'rule':'direct','cost_fp':1,'cost_fn':10}, {'rule':'direct','cost_fp':1,'cost_fn':10}),
      ('Custo_FP=10 e custo_FN=1.', 'Planilha auditada corrige custo_FP para 1 e custo_FN para 10.', 'strict', 'loose', {'rule':'direct','cost_fp':10,'cost_fn':1}, {'rule':'direct','cost_fp':1,'cost_fn':10})]),
    ('c02', 'custos',
     'Escolher modelo para implantação com prevalência diferente da validação. Holdout de 100 positivos e 900 negativos; custo_FP=2 e custo_FN=10. Calcule o custo esperado por caso usando FPR=FP/900, FNR=FN/100 e a prevalência de implantação; demais custos iguais.',
     {'precise': 'Modelo preciso: FP=9, FN=30, TP=70, TN=891.',
      'sensitive': 'Modelo sensível: FP=45, FN=10, TP=90, TN=855.'}, [
      ('Prevalência esperada na implantação: 2%.', 'Auditoria da população corrige a prevalência esperada para 20%.', 'precise', 'sensitive', {'rule':'prevalence','cost_fp':2,'cost_fn':10,'prevalence':0.02}, {'rule':'prevalence','cost_fp':2,'cost_fn':10,'prevalence':0.20}),
      ('Prevalência esperada na implantação: 20%.', 'Auditoria da população confirma prevalência esperada de 20%.', 'sensitive', 'sensitive', {'rule':'prevalence','cost_fp':2,'cost_fn':10,'prevalence':0.20}, {'rule':'prevalence','cost_fp':2,'cost_fn':10,'prevalence':0.20})]),
    ('c03', 'custos',
     'Escolher política de revisão humana para 1000 casos que chegam por dia. As matrizes de confusão representam esse volume diário. Custo_FP=1 e custo_FN=12. Cada TP ou FP gera uma revisão; uma política acima da capacidade diária é inadmissível. Entre as admissíveis, minimize FP × custo_FP + FN × custo_FN.',
     {'wide': 'Revisão ampla: FP=80, FN=5, TP=95, TN=820; gera TP+FP revisões.',
      'narrow': 'Revisão restrita: FP=10, FN=30, TP=70, TN=890; gera TP+FP revisões.'}, [
      ('Capacidade diária documentada: 200 revisões.', 'Escala operacional auditada corrige a capacidade diária para 100 revisões.', 'wide', 'narrow', {'rule':'capacity','cost_fp':1,'cost_fn':12,'capacity':200}, {'rule':'capacity','cost_fp':1,'cost_fn':12,'capacity':100}),
      ('Capacidade diária documentada: 100 revisões.', 'Escala operacional auditada confirma capacidade diária de 100 revisões.', 'narrow', 'narrow', {'rule':'capacity','cost_fp':1,'cost_fn':12,'capacity':100}, {'rule':'capacity','cost_fp':1,'cost_fn':12,'capacity':100})]),
    ('c04', 'custos',
     'Escolher modelo para o mesmo público de implantação. Os holdouts têm tamanhos diferentes; compare custo por 1000 casos, não totais brutos. Custo por caso = (FP × custo_FP + FN × custo_FN) / N; para comparar por 1000 casos, multiplique o resultado por 1000. Demais custos iguais.',
     {'small': 'Modelo de coorte menor: N=1000, FP=10, FN=25, TP=75, TN=890.',
      'large': 'Modelo de coorte maior: N=2000, FP=50, FN=20, TP=180, TN=1750.'}, [
      ('A relação entre custos de FP e FN não foi informada.', 'Contrato auditado informa custo_FP=4 e custo_FN=10.', 'insufficient', 'large', {'rule':'normalized','unknown':True}, {'rule':'normalized','cost_fp':4,'cost_fn':10}),
      ('Custo_FP=10 e custo_FN=1.', 'Contrato auditado corrige os custos: custo_FP=4 e custo_FN=10.', 'small', 'large', {'rule':'normalized','cost_fp':10,'cost_fn':1}, {'rule':'normalized','cost_fp':4,'cost_fn':10})]),
]
for pair, family, context, candidates, cases in _COST_CASES:
    for i, (fact, evidence, gold, after, initial_state, after_state) in enumerate(cases):
        TASKS.append(_task(pair, family, i, context, candidates, fact, evidence,
            {'initial':gold, 'after':after,
             'decisive':'FP, FN, custos e restrição declarada',
             'evidence_behavior':'resolver_lacuna' if gold=='insufficient' else ('confirmar' if gold==after else 'atualizar'),
             'initial_state':initial_state, 'after_state':after_state}))

# Correções auditadas preservam o objetivo e modificam apenas fatos do caso.
from dataclasses import replace
_EVIDENCE_OVERRIDES = {
    't01-2': ('Auditoria de timestamps corrige o registro: o laudo é liberado 30 minutos antes da triagem.', 'with', 'available'),
    't02-1': ('Auditoria do feed corrige a documentação: a liquidação ocorreu às 10h, mas o status só foi materializado no dia seguinte à autorização.', 'snapshot', 'late'),
    't03-1': ('Auditoria do arquivo versionado corrige a documentação: as revisões das origens históricas e de hoje só foram publicadas dois dias após cada previsão.', 'asof', 'late'),
    't04-2': ('Trilha de assinatura corrige o horário: o código é assinado antes da decisão de alta.', 'coded', 'available'),
    'g01-2': ('Auditoria dos índices do modelo personalizado: parte das visitas usadas no treino de cada paciente ocorreu depois de suas visitas de teste. O corte cronológico documentado não foi aplicado.', 'new', 'invalid_personalized_split'),
    'g02-1': ('Inventário auditado corrige a contagem: existem dezenas de medições por equipamento e a implantação é em equipamentos novos.', 'device', 'repeated_new_entities'),
    'g03-1': ('Cadastro auditado corrige a estrutura: vários moradores compartilham domicílio e renda.', 'house', 'shared_household'),
}
_STATE = {
    't01': ('available', 'late'), 't02': ('available', 'late'),
    't03': ('available', 'late'), 't04': ('unknown', 'late'),
    'g01': ('new_entities', 'known_entities'),
    'g02': ('single_record', 'repeated_new_entities'),
    'g03': ('single_person', 'shared_household'),
    'g04': ('unknown', 'shifting_policy'),
}
for j, task in enumerate(TASKS):
    if task.pair_id not in _STATE:
        continue
    state = _STATE[task.pair_id][task.member]
    after_state = {'t04-1':'available','g04-1':'stable_policy','g04-2':'stable_policy'}.get(task.id,state)
    rubric = {**task.rubric,'initial_state':state,'after_state':after_state}
    if task.id == 't04-1':
        task = replace(task, fact='O horário da assinatura do código não consta da documentação.')
        rubric['initial'] = 'insufficient'
    if task.id in _EVIDENCE_OVERRIDES:
        evidence, after, after_state = _EVIDENCE_OVERRIDES[task.id]
        rubric.update(after=after,after_state=after_state,evidence_behavior='atualizar')
        task = replace(task,evidence=evidence)
    elif rubric['initial']=='insufficient':
        rubric['evidence_behavior']='resolver_lacuna'
    TASKS[j] = replace(task,rubric=rubric)

assert len(TASKS) == 24

def get_task(task_id: str) -> Task:
    return next(t for t in TASKS if t.id == task_id)

def corpus_hash() -> str:
    from dataclasses import asdict
    return sha256(json.dumps([asdict(t) for t in TASKS], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
