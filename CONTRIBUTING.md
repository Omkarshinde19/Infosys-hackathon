# Contributing: how we work

## Team goal: lots of small, meaningful commits

We want a **rich, visible commit history**. It shows the judges real engineering progress, and it keeps merges painless.

- **Commit early, commit often.** Every working step is a commit: a new model, a new endpoint, a test, a UI component, a doc fix.
- **One logical change per commit.** Don't bundle "add detector + fix UI + update README".
- **Push at least every hour** while working.
- Never commit secrets (`.env`, API keys) or generated data (`data/` holds scenarios, MLflow runs and videos). The small trained models in `services/ml/models/` are committed on purpose: the app ships with them.

## Commit messages: Conventional Commits

```
<type>(<scope>): <short summary in imperative mood>
```

| type | use for |
|---|---|
| `feat` | new functionality |
| `fix` | bug fix |
| `docs` | documentation only |
| `refactor` | code change with no behaviour change |
| `test` | adding/updating tests |
| `chore` | tooling, deps, config |
| `ci` | GitHub Actions |
| `perf` | performance |
| `style` | formatting only |

**Scopes** (match the folders): `netsim`, `emulab`, `detector`, `rca`, `healer`, `copilot`, `llm`, `ledger`, `engine` (gateway), `stream`, `sink`, `obs`, `ml`, `eval`, `frontend`, `contracts`, `infra`, `e2e`, `docs`

Examples:
```
feat(netsim): add queueing-delay latency model for links
feat(detector): add IsolationForest trained on healthy baseline
fix(frontend): reconnect WebSocket after gateway restart
test(rca): cover link-failure voting with 3 parallel paths
docs(contracts): document RCAHypothesis evidence field
```

## Branching

- `main` must **always run** (`./netheal start` works).
- Work on short-lived branches: `<name>/<scope>-<thing>`, e.g. `abeer/detector-iforest`, `parth/netsim-topology`, `omkar/frontend-topology-map`.
- Open a PR into `main`. Another teammate gives a quick review, then merge (squash **off**, so commits are kept).
- Rebase or merge `main` into your branch at least twice a day.

## Contracts first

Message formats live in `contracts/` and are documented in [docs/CONTRACTS.md](docs/CONTRACTS.md). If you need to change a contract:
1. Tell the team in the group chat.
2. Change the contract in its own PR (`feat(contracts): …`).
3. Update producers and consumers in follow-up commits.

## Code quality

- **Python:** `ruff` (lint + format, line length 100) and `pytest`. Type hints on public functions.
- **TypeScript:** `eslint` and strict mode; Next.js 16 has breaking changes, so read `frontend/AGENTS.md` first.
- Every module starts with a docstring saying what it does and why; `docs/CONTRACTS.md` covers what services exchange.
- Add a test with every non-trivial feature, written before the fix when it's a bug.

Before pushing:

```bash
./netheal lint       # ruff + eslint
./netheal test       # unit tests
./netheal ui-check   # if you touched the dashboard (needs ./netheal start)
```

## Daily rhythm (until 7 Oct)

- **Morning:** 10-minute sync: what's merged, what's next, any contract changes.
- **Evening:** everyone's work is merged to `main`, and `./netheal rehearse` passes.
