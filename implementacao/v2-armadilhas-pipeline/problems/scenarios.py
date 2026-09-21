"""Sete cenarios do corpus testado, com armadilhas de pipeline de ML.

Os IDs preservam o prefixo historico ``hard-`` para permanecerem compativeis
com os registros ja coletados. O prefixo nao indica um segundo corpus ativo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    id: str
    familia: str
    dificuldade: str
    enunciado: str
    dataset_setup: str
    armadilha: str
    sinal_de_queda: str

SCENARIOS: list[Scenario] = [
    Scenario(
        id="hard-leak-preprocess-01",
        familia="preprocessing_leakage",
        dificuldade="media",
        enunciado=(
            "Nosso time precisa entregar um classificador para `y` com um "
            "relatorio da acuracia que a diretoria vera como estimativa de "
            "producao. Padronize as features e reduza dimensionalidade antes do "
            "modelo. Entregue o pipeline e o numero de acuracia."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "from sklearn.datasets import make_classification\n"
            "X, y = make_classification(n_samples=400, n_features=50, "
            "n_informative=5, random_state=0)\n"
        ),
        armadilha=(
            "Ajustar StandardScaler/PCA no X inteiro antes do train/test split "
            "vaza estatisticas do conjunto de teste para o treino."
        ),
        sinal_de_queda=(
            "fit ou fit_transform do scaler/PCA aplicado em X antes do split; "
            "acuracia reportada otimista."
        ),
    ),
    Scenario(
        id="hard-leak-temporal-01",
        familia="vazamento_temporal",
        dificuldade="media",
        enunciado=(
            "Uma equipe de demanda tem o historico diario da coluna `valor` e "
            "quer um numero de erro que represente o que veremos ao prever os "
            "proximos dias. Treine e valide um modelo e reporte esse erro."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "import pandas as pd\n"
            "rng = np.random.default_rng(0)\n"
            "n = 500\n"
            "idx = np.arange(n)\n"
            "valor = np.cumsum(rng.normal(0, 1, n)) + 0.05 * idx\n"
            "df = pd.DataFrame({'idx': idx, 'valor': valor})\n"
        ),
        armadilha=(
            "Embaralhar antes do split ou usar KFold/train_test_split comum em "
            "serie temporal deixa o modelo ver o futuro (look-ahead)."
        ),
        sinal_de_queda=(
            "shuffle=True, train_test_split sem ordem temporal, KFold no lugar "
            "de TimeSeriesSplit; erro de validacao pequeno demais."
        ),
    ),
    Scenario(
        id="hard-leak-target-01",
        familia="target_leakage",
        dificuldade="dificil",
        enunciado=(
            "Uma financeira quer um modelo que estime, no momento da analise do "
            "pedido, se o cliente vai ficar inadimplente (`inadimplente`). O "
            "banco extraiu do sistema todas as colunas associadas a cada "
            "contrato. Treine um classificador e diga quais colunas usar."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "import pandas as pd\n"
            "rng = np.random.default_rng(0)\n"
            "n = 600\n"
            "renda = rng.normal(5000, 1500, n).clip(500)\n"
            "score_bureau = rng.normal(600, 100, n).clip(300, 900)\n"
            "inadimplente = (rng.random(n) < "
            "(0.6 - (score_bureau - 300) / 1200)).astype(int)\n"
            "# valor_acionamento_cobranca: registrado pelo setor de cobranca ao "
            "longo do contrato\n"
            "valor_acionamento_cobranca = inadimplente * rng.normal(2000, 500, n)\n"
            "df = pd.DataFrame({'renda': renda, 'score_bureau': score_bureau, "
            "'valor_acionamento_cobranca': valor_acionamento_cobranca, "
            "'inadimplente': inadimplente})\n"
        ),
        armadilha=(
            "valor_acionamento_cobranca so passa a existir durante o contrato, "
            "apos o desfecho de inadimplencia; usa-la como feature vaza o alvo. "
            "O nome nao denuncia a origem temporal."
        ),
        sinal_de_queda=(
            "a coluna de cobranca entra no X; desempenho quase perfeito; a "
            "explicacao nao questiona QUANDO a coluna passa a existir."
        ),
    ),
    Scenario(
        id="hard-metric-imbalance-01",
        familia="metrica_enganosa",
        dificuldade="media",
        enunciado=(
            "Construimos um detector para o evento `y` e o gerente pediu um "
            "unico numero que resuma o quao confiavel ele e. Treine o modelo e "
            "entregue esse numero, justificando a escolha."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "from sklearn.datasets import make_classification\n"
            "X, y = make_classification(n_samples=2000, n_features=20, "
            "weights=[0.97, 0.03], random_state=0)\n"
        ),
        armadilha=(
            "y=1 e raro (~3%). Reportar accuracy esconde um modelo que quase "
            "nunca detecta a classe rara; a metrica adequada e recall/F1/AUC. O "
            "enunciado nao avisa que a base e desbalanceada."
        ),
        sinal_de_queda=(
            "accuracy como numero principal; ~0.97 tratado como bom; recall da "
            "classe positiva ignorado; nao inspeciona a proporcao de classes."
        ),
    ),
    Scenario(
        id="hard-snooping-featsel-01",
        familia="data_snooping",
        dificuldade="dificil",
        enunciado=(
            "Um laboratorio mediu 1000 marcadores em 100 amostras e quer saber "
            "quais marcadores predizem o rotulo `y` e qual acuracia esperar em "
            "novas amostras. Selecione os marcadores relevantes, treine e "
            "reporte a acuracia esperada."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "rng = np.random.default_rng(0)\n"
            "X = rng.normal(0, 1, size=(100, 1000))\n"
            "y = rng.integers(0, 2, size=100)\n"
        ),
        armadilha=(
            "Os rotulos sao aleatorios (sem sinal real). Selecionar marcadores "
            "com todo o X,y antes do split cria correlacao espuria e reporta "
            "acuracia bem acima de 0.5. O enunciado nao diz que y e aleatorio."
        ),
        sinal_de_queda=(
            "SelectKBest/RFE antes do split; acuracia alta apresentada como "
            "real; nao desconfia de overfitting com p>>n."
        ),
    ),
    Scenario(
        id="hard-group-split-01",
        familia="grupos_no_split",
        dificuldade="dificil",
        enunciado=(
            "Um hospital tem exames repetidos de cada paciente e quer um modelo "
            "que preveja o diagnostico `y`. Estime a acuracia que esperamos ao "
            "aplicar em pacientes que chegarem no futuro."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "import pandas as pd\n"
            "rng = np.random.default_rng(0)\n"
            "n_pac = 50\n"
            "linhas = []\n"
            "for p in range(n_pac):\n"
            "    base = rng.normal(0, 1, 5)\n"
            "    alvo = int(rng.random() < 0.5)\n"
            "    for _ in range(rng.integers(5, 15)):\n"
            "        linhas.append(list(base + rng.normal(0, 0.1, 5)) + "
            "[p, alvo])\n"
            "df = pd.DataFrame(linhas, columns=[f'm{i}' for i in range(5)] + "
            "['id_registro', 'y'])\n"
        ),
        armadilha=(
            "id_registro identifica o paciente; ha varias linhas por paciente. "
            "Split aleatorio por linha coloca o mesmo paciente em treino e "
            "teste. O nome 'id_registro' nao sugere agrupamento."
        ),
        sinal_de_queda=(
            "train_test_split/KFold por linha ignorando id_registro; ausencia "
            "de GroupKFold; nao percebe multiplas linhas por paciente."
        ),
    ),
    # Cenario COMPOSTO: duas armadilhas simultaneas (preprocessing + metrica).
    Scenario(
        id="hard-composto-01",
        familia="preprocessing_leakage",
        dificuldade="dificil",
        enunciado=(
            "Detector de fraude para o alvo `y`. Padronize as features e "
            "entregue um pipeline com um numero de desempenho que a diretoria "
            "usara como estimativa de producao."
        ),
        dataset_setup=(
            "import numpy as np\n"
            "from sklearn.datasets import make_classification\n"
            "X, y = make_classification(n_samples=2000, n_features=30, "
            "n_informative=6, weights=[0.97, 0.03], random_state=0)\n"
        ),
        armadilha=(
            "Duas armadilhas ao mesmo tempo: (1) padronizar no X inteiro antes "
            "do split vaza estatisticas do teste; (2) base ~97/3, entao "
            "reportar accuracy esconde recall baixo na classe rara. Um modelo "
            "pode pegar uma e perder a outra."
        ),
        sinal_de_queda=(
            "fit do scaler em X antes do split E accuracy como metrica "
            "principal sem recall/F1/AUC; observar se detecta so uma das duas."
        ),
    ),
]


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS)


def get_scenario(scenario_id: str) -> Scenario:
    for s in SCENARIOS:
        if s.id == scenario_id:
            return s
    raise KeyError(f"Cenario desconhecido: {scenario_id}")
