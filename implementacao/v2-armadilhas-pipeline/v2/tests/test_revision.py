from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from problems.revision import TASKS, get_task
from src.llm import LLMResponse
from src.revision import INTERVENTIONS, evaluate, expected, first_prompt, oracle, second_message, validate_corpus
from scripts import run_revision
from scripts.evaluate_revision import load, summarize

class FakeClient:
    calls = 0
    def __init__(self, model, args, effort):
        pass
    def chat(self, messages):
        FakeClient.calls += 1
        public=messages[1]['content']
        task=get_task(re.search(r'Tarefa ([a-z0-9-]+)\.', public).group(1))
        intervention='evidence' if len(messages)==4 and 'Informação técnica adicional' in messages[-1]['content'] else None
        canonical=oracle(task, intervention)
        choice=('informacao_insuficiente' if canonical=='insufficient' else
                'A' if f'Candidato A: {task.candidates[canonical]}' in public else 'B')
        payload={'escolha':choice,'justificativa':'Decisão pelo critério informado.',
                 'fatos_decisivos':['ordem temporal, grupos ou custo'],
                 'informacao_adicional':'dado ausente' if choice=='informacao_insuficiente' else None,
                 'confianca':80}
        return LLMResponse(text=json.dumps(payload),prompt_tokens=100,
                           completion_tokens=50,finish_reason='stop')

class RevisionTests(unittest.TestCase):
    def test_corpus_gold_contrasts_and_balancing(self):
        validate_corpus(TASKS)
        for t in TASKS:
            mate=next(x for x in TASKS if x.pair_id==t.pair_id and x.id!=t.id)
            self.assertEqual(t.labels(42,1),mate.labels(42,1))
            self.assertNotEqual(t.labels(42,1),t.labels(42,2))
            for repeat in (1,2):
                self.assertEqual(expected(t,42,repeat=repeat),
                    'informacao_insuficiente' if t.rubric['initial']=='insufficient' else
                    next(k for k,v in t.labels(42,repeat).items() if v==t.rubric['initial']))
                self.assertEqual(expected(t,42,'evidence',repeat),
                    next(k for k,v in t.labels(42,repeat).items() if v==t.rubric['after']))
        for repeat in (1,2):
            self.assertEqual(sum(all(expected(t,42,repeat=repeat)=='B' for t in TASKS[i:i+2]) for i in range(0,24,2)),0)
            self.assertEqual(sum(TASKS[i].labels(42,repeat)['A']==list(TASKS[i].candidates)[0] for i in range(0,24,2)),6)
        self.assertEqual(sum(t.rubric['evidence_behavior']=='confirmar' for t in TASKS),9)
        self.assertEqual(sum(t.rubric['evidence_behavior']=='atualizar' for t in TASKS),12)
        self.assertEqual(sum(t.rubric['evidence_behavior']=='resolver_lacuna' for t in TASKS),3)
        for t in TASKS:
            if t.pair_id=='g04':
                self.assertIn('próximo ano',t.context)
                self.assertNotIn('objetivo',t.evidence.lower())
                self.assertIn('distribui',t.evidence.lower())

    def test_case_units_and_fixed_objectives(self):
        c03=get_task('c03-1')
        self.assertIn('1000 casos que chegam por dia',c03.context)
        self.assertIn('volume diário',c03.context)
        self.assertEqual(95+80,175)
        self.assertEqual(70+10,80)
        c04=get_task('c04-1')
        self.assertIn('(FP × custo_FP + FN × custo_FN) / N',c04.context)
        self.assertAlmostEqual((10*4+25*10)/1000,0.29)
        self.assertAlmostEqual((50*4+20*10)/2000,0.20)
        self.assertEqual(oracle(c04,'evidence'),'large')
        g01=get_task('g01-2')
        self.assertIn('pacientes já acompanhados',g01.fact)
        self.assertNotIn('pacientes novos',g01.evidence)
        self.assertIn('visitas de teste',g01.evidence)
        self.assertEqual(oracle(g01),'known')
        self.assertEqual(oracle(g01,'evidence'),'new')
        g04=get_task('g04-2')
        self.assertIn('mudança comparável',g04.fact)
        self.assertIn('distribuições de covariáveis e desfechos',g04.evidence)
        self.assertEqual(oracle(g04),'forward')
        self.assertEqual(oracle(g04,'evidence'),'random')

    def test_prompt_blind_preference_and_evidence(self):
        for t in TASKS:
            for repeat in (1,2):
                prompt=json.dumps(first_prompt(t,42,repeat),ensure_ascii=False)
                self.assertNotIn('rubric',prompt)
                self.assertNotIn('initial_state',prompt)
                self.assertNotIn('after_state',prompt)
            a=second_message(t,'prefer_A')['content']
            b=second_message(t,'prefer_B')['content']
            self.assertEqual(a.replace('preferência por A','preferência por X'),
                             b.replace('preferência por B','preferência por X'))
            self.assertNotIn('não acrescenta evidência',a)
            self.assertNotIn('Candidato A',second_message(t,'evidence')['content'])
        self.assertEqual(set(INTERVENTIONS),{'control','prefer_A','prefer_B','evidence'})

    def test_failure_states(self):
        t=get_task('t04-1'); label=expected(t,42)
        valid=json.dumps({'escolha':label,'justificativa':'Falta horário','fatos_decisivos':['assinatura'],'informacao_adicional':'horário','confianca':60})
        self.assertEqual(evaluate(t,42,valid,'stop')['status'],'insuficiencia_correta')
        self.assertEqual(evaluate(t,42,valid,'length')['reason'],'truncamento')
        self.assertEqual(evaluate(t,42,valid,'stop',error='API')['reason'],'api_error')
        self.assertEqual(evaluate(t,42,'{','stop')['reason'],'formato_invalido')

    def test_known_effort_rejected(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            run_revision.model_spec('openrouter|deepseek/deepseek-v4-flash|low,high')

    def test_collection_resume_partial_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            argv=['--model-spec','openrouter|upstage/solar-pro4|low,high','--run-id','mock','--repeats','2']
            FakeClient.calls=0
            with patch.object(run_revision,'RUNS_DIR',Path(directory)):
                run_revision.main(argv,client_factory=FakeClient)
                self.assertEqual(FakeClient.calls,432)
                run=Path(directory)/'mock'
                initials,branches,manifest=load(run)
                self.assertEqual((len(initials),len(branches)),(48,384))
                self.assertEqual(len({b['initial_id'] for b in branches.values()}),48)
                self.assertTrue(all(sum(b['initial_id']==iid for b in branches.values())==8 for iid in initials))
                report=summarize(initials,branches,manifest)
                self.assertEqual(sum(v['both_correct'] for v in report['pair_both_correct'].values()),24)
                self.assertEqual(sum(v['evaluable'] for v in report['final'].values()),384)
                self.assertEqual(report['totals']['pending_final'],0)
                run_revision.main(argv,client_factory=FakeClient)
                self.assertEqual(FakeClient.calls,432)
                with self.assertRaises(SystemExit):run_revision.main(argv+['--seed','55'],client_factory=FakeClient)
                # Uma revisão registrada: as demais condições ainda aparecem como pendentes.
                one=next(iter(branches.items()))
                partial=summarize(initials,{one[0]:one[1]},manifest)
                self.assertEqual(partial['totals']['planned_final'],384)
                self.assertEqual(partial['totals']['recorded_final'],1)
                self.assertEqual(partial['totals']['pending_final'],383)
                self.assertEqual(len(partial['final']),24)
                self.assertEqual(sum(v['pending'] for v in partial['final'].values()),383)
                broken=dict(one[1]);broken['evaluation']={'status':'nao_avaliavel','reason':'truncamento','parsed':None}
                failed=summarize(initials,{one[0]:broken},manifest)
                self.assertEqual(sum(v['technical_failures'].get('truncamento',0) for v in failed['final'].values()),1)

    def test_same_model_name_different_providers(self):
        with tempfile.TemporaryDirectory() as directory:
            argv=['--model-spec','p1|shared-model|low', '--model-spec','p2|shared-model|low',
                  '--run-id','providers','--repeats','1']
            with patch.object(run_revision,'RUNS_DIR',Path(directory)):
                run_revision.main(argv,client_factory=FakeClient)
                report=summarize(*load(Path(directory)/'providers'))
                self.assertEqual(len(report['initial']),6)
                self.assertEqual(sum(v['both_correct'] for v in report['pair_both_correct'].values()),24)
                self.assertTrue(all(v['pending_pairs']==0 for v in report['pair_both_correct'].values()))

if __name__=='__main__':unittest.main()
