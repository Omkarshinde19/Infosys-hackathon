"""Train the RL routing agent (PPO, Stable-Baselines3) in the digital twin.

Each episode is one healing decision. A warmed-up campus gets a random link or device fault
(the same generator as the GNN's training data) and runs for a few ticks; the agent sees the
telemetry and where the fault is, and picks a path for every flow. The action is judged the
way NetHeal judges every candidate fix: a twin dry run plus the OPA guardrails.

  reward = +1 if the affected traffic is healthy again and the guardrails allow the fix
           - packet loss of the affected traffic (as a fraction)
           - 0.02 per flow moved (smaller changes are safer)
           - 1 if the guardrails deny it

Evaluated on held-out networks and seeds against the rule-based planner (the twin's best
allowed rule candidate). Run: make train-rl
"""

import copy
import json
import time
from statistics import fmean, median

import gymnasium as gym
import mlflow
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv

from contracts.models import ActionCandidate, RCAHypothesis
from ml.datagen import FAULT_TO_CAUSE, random_fault
from services.detector.detector import WARMUP_TICKS
from services.healer.healer import HEALTHY_LOSS_PCT, LATENCY_TOLERANCE, Healer
from services.ml.rl import MODEL_PATH, K, RoutingSpace
from services.netsim.engine import Network

TRAIN_BASES = (101, 202, 303, 404)  # same healthy networks as the other models
TEST_BASES = (505, 606, 707, 808)  # held out (also used by the evaluation harness)
EVAL_PATH = MODEL_PATH.parent / "rl_eval.json"
STEPS = 300_000
TEST_EPISODES = 600

_bases: dict[int, tuple] = {}


def base(seed: int) -> tuple[Network, dict[str, float]]:
    """A warmed-up network and each flow's healthy latency (cached per process)."""
    if seed not in _bases:
        net, seen = Network(seed=seed), {}
        for _ in range(WARMUP_TICKS):
            for s in net.step():
                if s.entity_type == "flow":
                    seen.setdefault(s.entity_id, []).append(s.latency_ms)
        _bases[seed] = net, {f: median(v) for f, v in seen.items()}
    return _bases[seed]


def affected_flows(net: Network, target: str) -> list[str]:
    if target in net.links:
        return [f for f, p in net.routes.items() if target in net.path_links(p)]
    return [f for f, p in net.routes.items() if target in p]


def judge(healer: Healer, net: Network, routes: dict, target: str, affected, baseline) -> dict:
    """Twin dry run + guardrails for one set of routes, scored as the reward."""
    kind = "reroute" if target in net.links else "drain_node"
    c = ActionCandidate(incident_id="rl", type=kind, params={"avoid": [target], "routes": routes})
    healer._predict(c, net, affected)
    p, allowed = c.twin_prediction, c.opa_decision == "allow"
    healthy = p.loss_pct < HEALTHY_LOSS_PCT and p.latency_ms <= LATENCY_TOLERANCE * fmean(
        baseline[f] for f in affected
    )
    reward = float(healthy and allowed) - p.loss_pct / 100 - 0.02 * len(routes) - (not allowed)
    return {"reward": reward, "healthy": healthy, "allowed": allowed, "moved": len(routes)}


class HealEnv(gym.Env):
    """One step per episode: observe the faulty network, choose routes, get judged."""

    def __init__(self, bases=TRAIN_BASES):
        self.bases = bases
        self.space = RoutingSpace(base(bases[0])[0])
        self.observation_space = gym.spaces.Box(-np.inf, np.inf, (self.space.size,), np.float32)
        self.action_space = gym.spaces.MultiDiscrete([K] * len(self.space.flows))
        self.healer = Healer()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        rng = self.np_random
        while True:
            net, self.baseline = base(self.bases[rng.integers(len(self.bases))])
            net = copy.deepcopy(net)
            net.rng = np.random.default_rng(int(rng.integers(2**31)))
            fault = random_fault(rng, net)
            if fault is None or fault[0] == "misconfig":  # misconfig is fixed by rollback
                continue
            net.inject_fault(*fault)
            for _ in range(int(rng.integers(2, 7))):
                samples = net.step()
            self.affected = affected_flows(net, fault[1])
            if self.affected:
                break
        self.net, self.fault, self.target = net, fault, fault[1]
        self.latest = {s.entity_id: s for s in samples}
        return self.space.observe(net, self.latest, self.target), {}

    def step(self, action):
        routes = self.space.routes(action, self.net)
        info = judge(self.healer, self.net, routes, self.target, self.affected, self.baseline)
        return (
            self.space.observe(self.net, self.latest, self.target),
            info["reward"],
            True,
            False,
            info,
        )


def rules_choice(env: HealEnv) -> dict:
    """What the rule-based planner would do: its best allowed twin-tested candidate."""
    h = RCAHypothesis(incident_id="rl", cause=FAULT_TO_CAUSE[env.fault[0]], target=env.target,
                      confidence=1.0, evidence=[], method_scores={})  # fmt: skip
    candidates, _ = env.healer.plan(h, env.net)
    allowed = [c for c in candidates if c.opa_decision == "allow"]
    return allowed[0].params["routes"] if allowed else {}


def evaluate(model: PPO, episodes: int = TEST_EPISODES) -> dict:
    env = HealEnv(TEST_BASES)
    rows = {"rl": [], "rules": [], "best_of_both": []}
    for i in range(episodes):
        obs, _ = env.reset(seed=10_000_000 + i)
        action, _ = model.predict(obs, deterministic=True)
        rl = judge(env.healer, env.net, env.space.routes(action, env.net), env.target,
                   env.affected, env.baseline)  # fmt: skip
        rules = judge(env.healer, env.net, rules_choice(env), env.target, env.affected,
                      env.baseline)  # fmt: skip
        for name, r in (("rl", rl), ("rules", rules)):
            rows[name].append({**r, "type": env.fault[0]})
        rows["best_of_both"].append({**max(rl, rules, key=lambda r: r["reward"]),
                                     "type": env.fault[0]})  # fmt: skip
    summary = {}
    for name, rs in rows.items():
        summary[name] = {
            "fixed": round(fmean(r["healthy"] and r["allowed"] for r in rs), 3),
            "denied": round(fmean(not r["allowed"] for r in rs), 3),
            "flows_moved": round(fmean(r["moved"] for r in rs), 2),
            "reward": round(fmean(r["reward"] for r in rs), 3),
            "fixed_by_fault": {
                t: round(fmean(r["healthy"] and r["allowed"] for r in rs if r["type"] == t), 3)
                for t in sorted({r["type"] for r in rs})
            },
        }
    return {"episodes": episodes, **summary}


def main() -> None:
    torch.set_num_threads(1)
    mlflow.set_experiment("netheal-rl-router")
    with mlflow.start_run(run_name="ppo-mlp-2x128"):
        params = {"steps": STEPS, "n_envs": 8, "n_steps": 256, "batch_size": 512, "k_paths": K,
                  "learning_rate": 3e-4, "ent_coef": 0.01, "net_arch": "128,128"}  # fmt: skip
        mlflow.log_params(params)
        env = make_vec_env(HealEnv, n_envs=8, vec_env_cls=SubprocVecEnv)
        model = PPO("MlpPolicy", env, n_steps=256, batch_size=512, learning_rate=3e-4,
                    ent_coef=0.01, gamma=0.0, policy_kwargs={"net_arch": [128, 128]},
                    device="cpu", seed=0, verbose=0)  # fmt: skip
        start = time.time()
        model.learn(total_timesteps=STEPS)
        env.close()
        model.save(MODEL_PATH)
        results = {"train_seconds": round(time.time() - start), **evaluate(model)}
        EVAL_PATH.write_text(json.dumps(results, indent=2))
        for name in ("rl", "rules", "best_of_both"):
            mlflow.log_metrics({f"{name}_{k}": v for k, v in results[name].items()
                                if isinstance(v, float)})  # fmt: skip
        mlflow.log_artifact(str(MODEL_PATH))
        mlflow.log_artifact(str(EVAL_PATH))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
