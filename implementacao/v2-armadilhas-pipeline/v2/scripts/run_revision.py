"""Coleta pareada da revisão 2.1; dry-run nunca instancia clientes."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from problems.revision import TASKS, VERSION, corpus_hash
VERSION_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = VERSION_ROOT.parent
RUNS_DIR = VERSION_ROOT / "runs"
from src.llm import LLMClient
from src.revision import INTERVENTIONS, evaluate, first_prompt, second_message, turn_record, validate_corpus

PROMPT_VERSION = '2.3.0'
KNOWN_EFFORTS = {
    ('openrouter', 'deepseek/deepseek-v4-flash'): {'high', 'xhigh'},
    ('openrouter', 'qwen/qwen3.8-27b'): {'low', 'xhigh'},
    ('openrouter', 'upstage/solar-pro4'): {'low', 'high'},
}
ALL_EFFORTS = {'default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'}

def model_spec(raw: str) -> dict:
    parts = raw.split('|')
    if len(parts) != 3:
        raise argparse.ArgumentTypeError('use provedor|modelo|effort1,effort2')
    provider, model, efforts = parts
    levels = efforts.split(',')
    if not provider or not model or not levels or len(set(levels)) != len(levels) or any(e not in ALL_EFFORTS for e in levels):
        raise argparse.ArgumentTypeError('modelo ou esforços inválidos')
    known = KNOWN_EFFORTS.get((provider, model))
    if known is not None and any(e not in known for e in levels):
        raise argparse.ArgumentTypeError(f'{provider}/{model}: níveis conhecidos {sorted(known)}')
    return {'provider': provider, 'model': model, 'efforts': levels, 'effort_validation': 'known' if known else 'unverified'}

def args_parser():
    p = argparse.ArgumentParser(description='Protocolo pareado v2.1')
    p.add_argument('--model-spec', action='append', type=model_spec, required=True, help='provedor|modelo|low,high; repetir para vários modelos')
    p.add_argument('--initial-effort', default='default', choices=sorted(ALL_EFFORTS))
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--max-tokens', type=int, default=4096)
    p.add_argument('--temperature', type=float, default=0)
    p.add_argument('--run-id', required=True)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--max-cost-usd', type=float)
    p.add_argument('--input-price-per-million', type=float)
    p.add_argument('--output-price-per-million', type=float)
    return p

def _key(model: dict) -> str:
    return sha256(f'{model["provider"]}|{model["model"]}'.encode()).hexdigest()[:12]

def initial_id(task_id, model, repeat):
    return f'{task_id}__{_key(model)}__r{repeat}'

def branch_id(initial, effort, intervention):
    return f'{initial}__{effort}__{intervention}'

def _write_new(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))

def _fingerprint(manifest: dict) -> str:
    return sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def _call(client, messages, prices):
    start = time.monotonic()
    try:
        response = client.chat(messages)
    except Exception as exc:
        return {'error': f'{type(exc).__name__}: {exc}', 'messages': messages,
                'latency_seconds': time.monotonic()-start, 'text': '', 'finish_reason': None,
                'estimated_cost_usd': None if None in prices else 0, 'effort_applied': None,
                'effort_confirmation': 'provider_nao_confirma'}
    return turn_record(response, messages, time.monotonic()-start, prices)

def _client(model, args, effort):
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / '.env')
    except ImportError:
        pass
    return LLMClient(provider=model['provider'], model=model['model'],
                     temperature=args.temperature, max_tokens=args.max_tokens,
                     seed=args.seed, reasoning_effort=None if effort == 'default' else effort)

def _planned(args):
    initials = [(t, m, r) for m in args.model_spec for t in TASKS for r in range(1, args.repeats+1)]
    branches = [(t, m, r, e, i) for t, m, r in initials for e in m['efforts'] for i in INTERVENTIONS]
    return initials, branches

def main(argv=None, client_factory=None):
    args = args_parser().parse_args(argv)
    validate_corpus(TASKS)
    if args.repeats < 1 or args.max_tokens < 1 or '/' in args.run_id or args.run_id in ('.', '..'):
        raise SystemExit('repetições, tokens ou run-id inválidos')
    if args.max_cost_usd is not None and (args.input_price_per_million is None or args.output_price_per_million is None):
        raise SystemExit('limite de custo exige as duas tarifas')
    if any(v is not None and v < 0 for v in (args.max_cost_usd, args.input_price_per_million, args.output_price_per_million)):
        raise SystemExit('custos devem ser não negativos')
    if len({_key(m) for m in args.model_spec}) != len(args.model_spec):
        raise SystemExit('modelo duplicado')
    for m in args.model_spec:
        known = KNOWN_EFFORTS.get((m['provider'], m['model']))
        if known and args.initial_effort not in known | {'default'}:
            raise SystemExit(f'effort inicial inválido para {m["model"]}')
    prompt_digest = sha256(json.dumps([(first_prompt(t, args.seed, r), [second_message(t, i) for i in INTERVENTIONS]) for r in range(1,args.repeats+1) for t in TASKS], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    manifest = {'protocol': VERSION, 'prompt_version': PROMPT_VERSION, 'prompt_sha256': prompt_digest,
                'corpus_sha256': corpus_hash(), 'models': args.model_spec,
                'initial_effort': args.initial_effort, 'repeats': args.repeats,
                'seed': args.seed, 'max_tokens': args.max_tokens,
                'temperature': args.temperature, 'interventions': INTERVENTIONS,
                'input_price_per_million': args.input_price_per_million,
                'output_price_per_million': args.output_price_per_million,
                'max_cost_usd': args.max_cost_usd}
    run = RUNS_DIR / args.run_id
    manifest_path = run / 'revision_manifest.json'
    if manifest_path.exists():
        old = _read(manifest_path)
        if old['fingerprint'] != _fingerprint(manifest):
            raise SystemExit('run-id existente com configuração diferente; escolha outro run-id')
    elif run.exists() and any(run.iterdir()):
        raise SystemExit('run-id ocupado por outra coleta; escolha outro run-id')
    initials, branches = _planned(args)
    remaining_initials = [x for x in initials if not (run/'initial'/f'{initial_id(x[0].id,x[1],x[2])}.json').exists()]
    remaining_branches = [x for x in branches if not (run/'branch'/f'{branch_id(initial_id(x[0].id,x[1],x[2]),x[3],x[4])}.json').exists()]
    prices = (args.input_price_per_million, args.output_price_per_million)
    # Reserva conservadora por chamada: contexto até 10k + resposta inicial completa.
    reserve = ((10_000 + args.max_tokens)*prices[0] + args.max_tokens*prices[1])/1_000_000 if None not in prices else None
    print(json.dumps({'run_id': args.run_id, 'initial_calls': len(initials),
                      'branch_calls': len(branches), 'total_calls': len(initials)+len(branches),
                      'remaining_calls': len(remaining_initials)+len(remaining_branches),
                      'reserve_remaining_usd': round(reserve*(len(remaining_initials)+len(remaining_branches)), 6) if reserve is not None else None,
                      'effort_validation': {f"{m['provider']}|{m['model']}": m['effort_validation'] for m in args.model_spec}}, ensure_ascii=False))
    if args.dry_run:
        return
    if not manifest_path.exists():
        _write_new(manifest_path, {'run_id': args.run_id, **manifest, 'fingerprint': _fingerprint(manifest),
                                   'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')})
    spent = sum((_read(p)['turn'].get('estimated_cost_usd') or 0) for d in ('initial','branch') for p in (run/d).glob('*.json'))
    def budget():
        if args.max_cost_usd is not None and spent + reserve > args.max_cost_usd:
            raise SystemExit(f'limite de custo atingido: gasto={spent:.6f}, reserva={reserve:.6f}')
    factory = client_factory or _client
    for task, model, repeat in initials:
        iid = initial_id(task.id, model, repeat)
        path = run/'initial'/f'{iid}.json'
        if path.exists():
            continue
        budget()
        messages = first_prompt(task, args.seed, repeat)
        turn = _call(factory(model, args, args.initial_effort), messages, prices)
        spent += turn['estimated_cost_usd'] or 0
        _write_new(path, {'id': iid, 'task_id': task.id, 'pair_id': task.pair_id,
                          'family': task.family, 'candidate_labels': task.labels(args.seed, repeat),
                          'model': model, 'repeat': repeat, 'initial_effort': args.initial_effort,
                          'turn': turn, 'evaluation': evaluate(task, args.seed, turn['text'], turn['finish_reason'], error=turn.get('error'), repeat=repeat)})
    for task, model, repeat, effort, intervention in branches:
        iid = initial_id(task.id, model, repeat)
        path = run/'branch'/f'{branch_id(iid,effort,intervention)}.json'
        if path.exists():
            continue
        initial = _read(run/'initial'/f'{iid}.json')
        if initial['evaluation']['status'] == 'nao_avaliavel':
            _write_new(path, {'id': path.stem, 'initial_id': iid, 'task_id': task.id,
                              'pair_id': task.pair_id, 'family': task.family, 'model': model,
                              'repeat': repeat, 'effort': effort, 'intervention': intervention,
                              'turn': {'error': 'initial_unusable', 'text': '', 'finish_reason': None},
                              'evaluation': {'status': 'nao_avaliavel', 'reason': 'initial_unusable',
                                             'expected': None, 'parsed': None}})
            continue
        budget()
        messages = first_prompt(task, args.seed, repeat) + [
            {'role':'assistant', 'content': initial['turn']['text']}, second_message(task, intervention)]
        turn = _call(factory(model, args, effort), messages, prices)
        spent += turn['estimated_cost_usd'] or 0
        _write_new(path, {'id': path.stem, 'initial_id': iid, 'task_id': task.id,
                          'pair_id': task.pair_id, 'family': task.family,
                          'candidate_labels': task.labels(args.seed, repeat), 'model': model,
                          'repeat': repeat, 'initial_effort': args.initial_effort,
                          'effort': effort, 'intervention': intervention,
                          'turn': turn, 'evaluation': evaluate(task, args.seed, turn['text'],
                                               turn['finish_reason'], intervention, turn.get('error'), repeat=repeat)})
    print(f'Coleta concluída. Custo estimado: {f"US${spent:.6f}" if None not in prices else "indisponível sem tarifas"}.')

if __name__ == '__main__':
    main()
