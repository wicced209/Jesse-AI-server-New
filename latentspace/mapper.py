"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  LATENT SPACE MAPPER — High-dimensional navigation and projection            ║
║  Clustering | Manifold traversal | Topology | Sovereign-tagged embeddings   ║
║  OWNER: SLMK Jesse Martinez Junior                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import hashlib
import math
import time
from core.config import SOVEREIGN_OWNER
from core.logger import log_event


class LatentSpaceMapper:
    """
    High-dimensional latent space visualization and navigation.
    All embeddings and projections are sovereign-tagged.
    Supports clustering, manifold traversal, and topological analysis.
    """

    MODULE_ID  = "LATENT_SPACE_MAPPER"
    MODULE_VER = "lsm-v2.0-alpha"
    OWNER      = SOVEREIGN_OWNER

    def __init__(self, dim: int = 128):
        self.dim          = dim
        self._embeddings: dict[str, dict] = {}
        self._clusters:   list[dict]      = []
        log_event(f"[LSM] Mapper initialized — dim={dim}")

    def embed(self, key: str, data: str) -> dict:
        """Embed a named data point into latent space."""
        raw   = hashlib.sha3_512(data.encode()).hexdigest()
        vec   = self._to_vector(raw, self.dim)
        topo  = self._topology(vec)
        entry = {
            "key":       key,
            "owner":     self.OWNER,
            "vector":    vec[:8],          # preview
            "full_dim":  self.dim,
            "hash":      raw[:32],
            "topology":  topo,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self._embeddings[key] = {"vector": vec, "meta": entry}
        log_event(f"[LSM] Embedded key='{key}' dim={self.dim}")
        return entry

    def _to_vector(self, hex_str: str, dim: int) -> list[float]:
        repeated = (hex_str * ((dim * 2 // len(hex_str)) + 1))[:dim * 2]
        return [int(repeated[i*2:i*2+2], 16) / 255.0 for i in range(dim)]

    def _topology(self, vec: list[float]) -> dict:
        n   = len(vec)
        mag = math.sqrt(sum(v**2 for v in vec))
        mu  = sum(vec) / n
        var = sum((v - mu)**2 for v in vec) / n
        return {
            "magnitude": round(mag, 6),
            "mean":      round(mu, 6),
            "variance":  round(var, 6),
        }

    def project_2d(self, key: str) -> dict:
        """Simple 2D projection via first 2 principal-like dimensions."""
        if key not in self._embeddings:
            return {"error": f"Key '{key}' not found"}
        vec = self._embeddings[key]["vector"]
        return {
            "key":   key,
            "x":     round(vec[0], 6),
            "y":     round(vec[1], 6),
            "owner": self.OWNER,
        }

    def nearest(self, key: str, top_k: int = 3) -> list[dict]:
        """Find nearest embeddings by Euclidean distance."""
        if key not in self._embeddings:
            return [{"error": f"Key '{key}' not found"}]
        source = self._embeddings[key]["vector"]
        dists  = []
        for k, v in self._embeddings.items():
            if k == key:
                continue
            d = math.sqrt(sum((a - b)**2 for a, b in zip(source, v["vector"])))
            dists.append({"key": k, "distance": round(d, 6)})
        dists.sort(key=lambda x: x["distance"])
        return dists[:top_k]

    def list_keys(self) -> list[str]:
        return list(self._embeddings.keys())

    def status(self) -> dict:
        return {
            "module":     self.MODULE_ID,
            "version":    self.MODULE_VER,
            "owner":      self.OWNER,
            "status":     "ACTIVE",
            "dim":        self.dim,
            "embeddings": len(self._embeddings),
        }


latent_mapper = LatentSpaceMapper(dim=128)
