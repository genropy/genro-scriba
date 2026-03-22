# Piano: genro-juggler

## Concetto

genro-juggler e' il layer che trasforma genro-scriba da "generatore di file" a
"bus reattivo verso target live". La Bag resta il centro: ogni mutazione
scatena un compile → push diretto verso il target (API Kubernetes, ansible-runner)
senza passare da file YAML intermedi.

## Architettura

```
                    ┌─────────────┐
                    │   Bag (data) │
                    └──────┬──────┘
                           │ trigger on change
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ K8s      │ │ Ansible  │ │ Traefik  │
        │ Builder  │ │ Builder  │ │ Builder  │
        │ (scriba) │ │ (scriba) │ │ (scriba) │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │ dict        │ dict       │ dict
             ▼             ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ K8sTarget│ │ Ansible  │ │ FileTarget│ ← to_yaml (scriba classico)
        │ (juggler)│ │ Target   │ │ (scriba)  │
        └────┬─────┘ └────┬─────┘ └──────────┘
             │             │
             ▼             ▼
        K8s API       ansible-runner
        server
```

## Struttura package

```
packages/genro-juggler/
├── pyproject.toml
├── src/genro_juggler/
│   ├── __init__.py
│   ├── target.py              # TargetBase (interfaccia astratta)
│   ├── kubernetes_target.py   # K8sTarget — dict → API server
│   ├── ansible_target.py      # AnsibleTarget — dict → ansible-runner
│   └── juggler_app.py         # JugglerApp — wiring Bag + builders + targets
└── tests/
    ├── __init__.py
    ├── test_target.py
    ├── test_kubernetes_target.py
    ├── test_ansible_target.py
    └── test_juggler_app.py
```

## Step di implementazione

### Step 1: Scaffold del package

- Creare `packages/genro-juggler/` con pyproject.toml
- Dipendenze: `genro-scriba`, `kubernetes>=28.0` (optional), `ansible-runner>=2.3` (optional)
- Setup base: __init__.py, struttura directory

### Step 2: TargetBase — interfaccia astratta

```python
class TargetBase:
    """Un target riceve un dict compilato e lo applica da qualche parte."""

    def apply(self, resource_dict: dict) -> dict:
        """Applica la risorsa. Ritorna lo stato risultante."""
        raise NotImplementedError

    def apply_many(self, resources: list[dict]) -> list[dict]:
        """Applica piu' risorse."""
        return [self.apply(r) for r in resources]

    def diff(self, desired: dict) -> dict | None:
        """Opzionale: ritorna il delta tra stato attuale e desiderato."""
        return None
```

### Step 3: K8sTarget — Kubernetes API client

- Wrappa il `kubernetes` Python client
- `apply()` fa create-or-patch per singola risorsa (server-side apply)
- Usa `kind` + `apiVersion` per scegliere l'API giusta
- Gestione namespace
- Auth: `load_kube_config()` o `load_incluster_config()`

```python
class K8sTarget(TargetBase):
    def __init__(self, kubeconfig=None, context=None, namespace="default"):
        ...

    def apply(self, resource_dict):
        # detect kind → call right API
        # use server-side apply (PATCH with fieldManager)
        ...
```

### Step 4: AnsibleTarget — ansible-runner

- Wrappa `ansible_runner.run()`
- `apply()` riceve il dict del playbook compilato
- Lo passa direttamente come playbook inline (ansible-runner supporta `playbook` come lista di dict)
- Ritorna il risultato dell'esecuzione (status, stdout, eventi)

```python
class AnsibleTarget(TargetBase):
    def __init__(self, inventory=None, private_data_dir=None):
        ...

    def apply(self, playbook_dict):
        # ansible_runner.run(playbook=playbook_dict, ...)
        ...
```

### Step 5: JugglerApp — il wiring

- Estende/compone `ScribaApp`
- Ogni builder ha un target associato (invece di o in aggiunta a un file output)
- Sul trigger della Bag: `compile_to_dict()` → `target.apply()`
- Stesso meccanismo di selective recompile gia' presente in ScribaApp

```python
class JugglerApp(ScribaApp):
    def __init__(self, targets=None, **kwargs):
        super().__init__(**kwargs)
        self._targets = targets or {}  # {"kubernetes": K8sTarget(...), ...}

    def _on_data_changed(self, ...):
        # compile → apply to target instead of (or in addition to) file
        ...
```

### Step 6: Test

- K8sTarget: mock del kubernetes client, verifica che le API call siano corrette
- AnsibleTarget: mock di ansible_runner.run(), verifica il playbook passato
- JugglerApp: test integrazione — mutazione Bag → target.apply() chiamato
- Usare l'esempio SimpleDeployment esistente come caso di test

### Step 7: Esempio funzionante

Un esempio che:
1. Definisce un deployment K8s con la recipe esistente
2. Collega un K8sTarget
3. Modifica `data["web.replicas"]`
4. Verifica che il PATCH parta verso il cluster

## Nota: collegamento Traefik ↔ Kubernetes Ingress

Traefik puo' funzionare in due modalita':

1. **Standalone (bare metal)**: legge la config da file (YAML/TOML).
   → Bag → TraefikBuilder → FileTarget (scriba classico)

2. **Come Ingress Controller in K8s**: legge le risorse Ingress e CRD
   (IngressRoute, Middleware, ecc.) direttamente dall'API server Kubernetes.
   Non serve piu' il file di config Traefik.
   → Bag → KubernetesBuilder (Ingress/IngressRoute) → K8sTarget (API)

Juggler gestisce entrambi i casi dallo stesso punto. Stessa Bag, stesso dato,
target diverso. Questo unifica genro-traefik e genro-kubernetes quando Traefik
gira dentro il cluster: la configurazione di routing diventa una risorsa
Kubernetes (Ingress) invece di un file Traefik.

Implicazione: il KubernetesBuilder potrebbe avere bisogno di supportare le CRD
Traefik (IngressRoute, Middleware, ServersTransport) per coprire i casi avanzati
che un semplice Ingress non gestisce.

## Nota: caso d'uso concreto — Ansible + Hetzner Cloud

Primo terreno di sperimentazione per AnsibleTarget: infrastruttura su Hetzner Cloud.

Flusso:
```
Bag (infra desiderata: VM, reti, firewall)
  → AnsibleBuilder (scriba: genera playbook come dict)
    → AnsibleTarget (juggler: ansible-runner)
      → Hetzner Cloud API (via collection hetzner.hcloud)
```

Requisiti:
- Collection Ansible: `hetzner.hcloud` (`ansible-galaxy collection install hetzner.hcloud`)
- Autenticazione: `HCLOUD_TOKEN` (variabile d'ambiente o nell'inventory)

Risorse Hetzner gestibili dalla Bag:
- `hetzner.hcloud.server` — VM (tipo, immagine, location, SSH key)
- `hetzner.hcloud.network` / `subnet` — reti private
- `hetzner.hcloud.firewall` — regole firewall
- `hetzner.hcloud.volume` — volumi persistenti
- `hetzner.hcloud.load_balancer` — bilanciamento
- `hetzner.hcloud.ssh_key` — chiavi SSH

Scenario tipico: la Bag descrive N server con tipo/immagine/rete, ogni modifica
(aggiunta server, cambio tipo, nuova regola firewall) scatena ansible-runner
che converge lo stato Hetzner verso quello desiderato.

Dopo il provisioning Hetzner, un secondo passaggio Ansible configura i server
(apt, docker, utenti, deploy applicativo) — stesso meccanismo, playbook diverso.

## Cosa NON fa il primo prototipo

- Niente feedback loop (watch dal cluster → Bag) — viene dopo
- Niente UI (genro-textual o webapp) — viene dopo
- Niente retry/error handling sofisticato — viene dopo
- Niente multi-cluster — viene dopo

## Dipendenze esterne

- `kubernetes` (Python client): pip install kubernetes
- `ansible-runner`: pip install ansible-runner
- Entrambe opzionali (optional-dependencies nel pyproject.toml)
