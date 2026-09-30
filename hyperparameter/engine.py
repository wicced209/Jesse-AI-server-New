"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  HYPERPARAMETER ENGINE — Dynamic optimization and tuning                     ║
║  Bayesian | Evolutionary | Scheduled | Sovereign-tagged outputs              ║
║  OWNER: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import hashlib
import random
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event


class HyperparameterEngine:
    """
    Dynamic hyperparameter optimization engine.
    Supports Bayesian, evolutionary, and scheduled sampling strategies.
    All parameter sets are sovereign-tagged at creation.
    """

    MODULE_ID  = "HYPERPARAMETER_ENGINE"
    MODULE_VER = "hp-v2.0-alpha"
    OWNER      = SOVEREIGN_OWNER

    # Default search spaces
    SEARCH_SPACES = {
        "learning_rate":    (1e-5, 1e-1),
        "batch_size":       (8, 512),
        "dropout":          (0.0, 0.5),
        "hidden_dim":       (64, 4096),
        "num_layers":       (1, 32),
        "attention_heads":  (1, 64),
        "warmup_steps":     (100, 10000),
        "weight_decay":     (0.0, 0.1),
        "temperature":      (0.1, 2.0),
        "top_p":            (0.5, 1.0),
    }

    def __init__(self):
        self._history: list[dict] = []
        self._best: dict          = {}
        log_event("[HYPERPARAM] Engine initialized")

    def sample(self, strategy: str = "bayesian", seed: int = None) -> dict:
        """Sample a hyperparameter configuration."""
        if seed is not None:
            random.seed(seed)

        if strategy == "bayesian":
            params = self._bayesian_sample()
        elif strategy == "evolutionary":
            params = self._evolutionary_sample()
        else:
            params = self._random_sample()

        config_id = hashlib.sha3_256(
            f"{params}{time.time()}".encode()
        ).hexdigest()[:16]

        entry = {
            "config_id":  config_id,
            "strategy":   strategy,
            "params":     params,
            "owner":      self.OWNER,
            "timestamp":  time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._history.append(entry)
        log_event(f"[HYPERPARAM] Sampled — strategy={strategy} id={config_id}")
        return entry

    def _random_sample(self) -> dict:
        return {
            k: round(random.uniform(lo, hi), 6)
            for k, (lo, hi) in self.SEARCH_SPACES.items()
        }

    def _bayesian_sample(self) -> dict:
        """Simplified Bayesian-inspired sampling (biased toward center)."""
        params = {}
        for k, (lo, hi) in self.SEARCH_SPACES.items():
            center = (lo + hi) / 2
            std    = (hi - lo) / 6
            val    = max(lo, min(hi, random.gauss(center, std)))
            params[k] = round(val, 6)
        return params

    def _evolutionary_sample(self) -> dict:
        """Mutate the best known config if available, else random."""
        if not self._best:
            return self._random_sample()
        mutated = {}
        for k, (lo, hi) in self.SEARCH_SPACES.items():
            base = self._best.get(k, (lo + hi) / 2)
            mut  = base * random.uniform(0.8, 1.2)
            mutated[k] = round(max(lo, min(hi, mut)), 6)
        return mutated

    def record_score(self, config_id: str, score: float):
        """Record a performance score for a config."""
        for entry in self._history:
            if entry["config_id"] == config_id:
                entry["score"] = score
                if not self._best or score > self._best.get("score", -1e9):
                    self._best = {**entry["params"], "score": score}
                log_event(f"[HYPERPARAM] Score recorded — id={config_id} score={score}")
                return
        log_event(f"[HYPERPARAM] config_id {config_id} not found", "warning")

    def get_best(self) -> dict:
        return self._best if self._best else {"status": "no scored configs yet"}

    def status(self) -> dict:
        return {
            "module":          self.MODULE_ID,
            "version":         self.MODULE_VER,
            "owner":           self.OWNER,
            "status":          "ACTIVE",
            "configs_sampled": len(self._history),
            "search_space_dims": len(self.SEARCH_SPACES),
            "best_score":      self._best.get("score", None),
        }


hyperparameter_engine = HyperparameterEngine()
