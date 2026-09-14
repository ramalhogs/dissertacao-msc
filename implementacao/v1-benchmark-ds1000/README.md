# v1: benchmark DS-1000

Piloto A0 com tarefas do DS-1000 e intervenções I0-I3. O modelo não recebe o resultado dos testes.

## Pastas

- `src/`: implementação do experimento.
- `scripts/`: execução e análise.
- `data/`: resultados em CSV.
- `docs/`: exemplo e relatório do piloto.

## Execução

A partir de `implementacao/`:

```bash
source .venv/bin/activate
cd v1-benchmark-ds1000
pip install -r requirements.txt
cp .env.example .env
python scripts/run_pilot.py --n-tasks 5 --interventions I0 I1 I2 I3
```

## Documentos

- [`docs/exemplo_teste.md`](docs/exemplo_teste.md): fluxo dos testes e exemplo do problema 71.
- [`docs/relatorio-metricas-a0-2026-09-10.md`](docs/relatorio-metricas-a0-2026-09-10.md): resultados do piloto.
