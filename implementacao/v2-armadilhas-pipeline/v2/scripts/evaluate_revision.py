"""Resumo do protocolo 2.2; inclui células planejadas ainda pendentes."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from problems.revision import TASKS, corpus_hash
from scripts.run_revision import initial_id, branch_id
from src.revision import INTERVENTIONS

GOOD = {'correta', 'insuficiencia_correta'}

def model_key(model):
    return f"{model['provider']}|{model['model']}"

def load(run: Path):
    manifest = json.loads((run/'revision_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('corpus_sha256') != corpus_hash():
        raise ValueError('corpus da execução difere do corpus instalado; use a versão original para avaliar')
    initials = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (run/'initial').glob('*.json')}
    branches = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in (run/'branch').glob('*.json')}
    return initials, branches, manifest

def _group(ids, records):
    observed = [records[x] for x in ids if x in records]
    count = Counter(r['evaluation']['status'] for r in observed)
    failures = Counter(r['evaluation'].get('reason') for r in observed if r['evaluation']['status']=='nao_avaliavel')
    valid = len(observed)-count['nao_avaliavel']
    good = count['correta']+count['insuficiencia_correta']
    return {'planned':len(ids), 'recorded':len(observed), 'pending':len(ids)-len(observed),
            'evaluable':valid, 'correct':good, 'incorrect':count['incorreta'],
            'correct_insufficient':count['insuficiencia_correta'],
            'technical_failures':dict(failures), 'accuracy':good/valid if valid else None}

def _pairs(groups, records):
    result = {}
    for key, pairs in groups.items():
        present = [members for members in pairs if all(x in records for x in members)]
        evaluable = [members for members in present if all(records[x]['evaluation']['status']!='nao_avaliavel' for x in members)]
        result[key] = {'planned_pairs':len(pairs), 'recorded_pairs':len(present),
                       'pending_pairs':len(pairs)-len(present), 'evaluable_pairs':len(evaluable),
                       'failed_pairs':len(present)-len(evaluable),
                       'both_correct':sum(all(records[x]['evaluation']['status'] in GOOD for x in members) for members in evaluable)}
    return result

def summarize(initials, branches, manifest):
    by_initial = defaultdict(list)
    by_final = defaultdict(list)
    initial_pairs = defaultdict(list)
    final_pairs = defaultdict(list)
    planned_initial = set(); planned_final = set()
    by_task = {}
    for model in manifest['models']:
        mk = model_key(model)
        for repeat in range(1, manifest['repeats']+1):
            for task in TASKS:
                iid = initial_id(task.id,model,repeat)
                planned_initial.add(iid)
                by_task[iid] = task
                by_initial[f'{mk}|{task.family}'].append(iid)
                initial_pairs[(mk,task.family,repeat,task.pair_id)].append(iid)
                for effort in model['efforts']:
                    for condition in INTERVENTIONS:
                        bid = branch_id(iid,effort,condition)
                        planned_final.add(bid)
                        by_final[f'{mk}|{task.family}|{effort}|{condition}'].append(bid)
                        final_pairs[(mk,task.family,repeat,task.pair_id,effort,condition)].append(bid)
    if set(initials)-planned_initial or set(branches)-planned_final:
        raise ValueError('registro fora do plano do manifest')
    if any(r['id'] != key for key,r in initials.items()) or any(r['id'] != key for key,r in branches.items()):
        raise ValueError('ID de registro inconsistente com nome do arquivo')
    summary={'independence_unit':'initial_id', 'totals':{
        'planned_initial':len(planned_initial),'recorded_initial':len(initials),
        'pending_initial':len(planned_initial)-len(initials),
        'planned_final':len(planned_final),'recorded_final':len(branches),
        'pending_final':len(planned_final)-len(branches)},
        'initial':{key:_group(ids,initials) for key,ids in by_initial.items()},
        'final':{key:_group(ids,branches) for key,ids in by_final.items()}}
    ip=defaultdict(list)
    for (mk,f,r,p),members in initial_pairs.items(): ip[f'{mk}|{f}'].append(members)
    fp=defaultdict(list)
    for (mk,f,r,p,e,c),members in final_pairs.items(): fp[f'{mk}|{f}|{e}|{c}'].append(members)
    summary['pair_both_correct']=_pairs(ip,initials)
    summary['final_pair_both_correct']=_pairs(fp,branches)
    pref={}; control={}; evidence={}; effort_comparison={}
    for model in manifest['models']:
        mk=model_key(model)
        for family in ('temporal','grupos','custos'):
            task_ids=[t for t in TASKS if t.family==family]
            for effort in model['efforts']:
                for condition in ('prefer_A','prefer_B'):
                    key=f'{mk}|{family}|{effort}|{condition}'
                    pc={'planned':len(task_ids)*manifest['repeats'], 'initially_correct_with_evaluable_final':0,'regressions':0,
                        'pending_final':0,'technical_failures':0}
                    cc={'planned_matches':len(task_ids)*manifest['repeats'], 'matched_initials':0,
                        'changed_vs_control':0,'preference_worse_than_control':0}
                    for repeat in range(1,manifest['repeats']+1):
                        for task in task_ids:
                            iid=initial_id(task.id,model,repeat)
                            bid=branch_id(iid,effort,condition)
                            b=branches.get(bid)
                            if b is None:
                                pc['pending_final']+=1
                                continue
                            if b['evaluation']['status']=='nao_avaliavel':
                                pc['technical_failures']+=1
                            i=initials.get(iid)
                            if i and i['evaluation']['status'] in GOOD and b['evaluation']['status']!='nao_avaliavel':
                                pc['initially_correct_with_evaluable_final']+=1
                                pc['regressions']+=b['evaluation']['status']=='incorreta'
                            ctrl=branches.get(branch_id(iid,effort,'control'))
                            if ctrl and b['evaluation']['status']!='nao_avaliavel' and ctrl['evaluation']['status']!='nao_avaliavel':
                                cc['matched_initials']+=1
                                cc['changed_vs_control']+=b['evaluation']['parsed']['escolha']!=ctrl['evaluation']['parsed']['escolha']
                                cc['preference_worse_than_control']+=ctrl['evaluation']['status'] in GOOD and b['evaluation']['status']=='incorreta'
                    pref[key]=pc;control[key]=cc
                key=f'{mk}|{family}|{effort}|evidence'
                ev={'planned':len(task_ids)*manifest['repeats'],'matched_initials':0,'correct_update':0,
                    'pending_final':0,'technical_failures':0,'by_prior_state':{},'by_expected_behavior':{}}
                for repeat in range(1,manifest['repeats']+1):
                    for task in task_ids:
                        iid=initial_id(task.id,model,repeat)
                        b=branches.get(branch_id(iid,effort,'evidence'))
                        if b is None:
                            ev['pending_final']+=1;continue
                        i=initials.get(iid)
                        if i is None or i['evaluation']['status']=='nao_avaliavel' or b['evaluation']['status']=='nao_avaliavel':
                            ev['technical_failures']+=1;continue
                        ev['matched_initials']+=1
                        correct=int(b['evaluation']['status'] in GOOD)
                        ev['correct_update']+=correct
                        prior='correct' if i['evaluation']['status'] in GOOD else 'incorrect'
                        behavior=task.rubric['evidence_behavior']
                        for field,cat in (('by_prior_state',prior),('by_expected_behavior',behavior)):
                            cell=ev[field].setdefault(cat,{'denominator':0,'correct_update':0})
                            cell['denominator']+=1;cell['correct_update']+=correct
                evidence[key]=ev
            for ai,a in enumerate(model['efforts']):
                for z in model['efforts'][ai+1:]:
                    for condition in INTERVENTIONS:
                        key=f'{mk}|{family}|{a}|{z}|{condition}'
                        row={'planned_matches':len(task_ids)*manifest['repeats'], 'matched_initials':0,
                             'both_correct':0, f'{a}_only_correct':0, f'{z}_only_correct':0}
                        for repeat in range(1,manifest['repeats']+1):
                            for task in task_ids:
                                iid=initial_id(task.id,model,repeat)
                                x=branches.get(branch_id(iid,a,condition)); y=branches.get(branch_id(iid,z,condition))
                                if not x or not y or x['evaluation']['status']=='nao_avaliavel' or y['evaluation']['status']=='nao_avaliavel':continue
                                row['matched_initials']+=1
                                xc=x['evaluation']['status'] in GOOD; yc=y['evaluation']['status'] in GOOD
                                row['both_correct']+=xc and yc
                                row[f'{a}_only_correct']+=xc and not yc
                                row[f'{z}_only_correct']+=yc and not xc
                        effort_comparison[key]=row
    summary['preference_correct_to_incorrect']=pref
    summary['preference_vs_control']=control
    summary['evidence_update']=evidence
    summary['effort_within_model']=effort_comparison
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('run_dir',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args(); result=summarize(*load(args.run_dir))
    rendered=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:args.output.write_text(rendered+'\n',encoding='utf-8')
    else:print(rendered)
if __name__=='__main__':main()
