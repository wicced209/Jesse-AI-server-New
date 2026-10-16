"""
CRSMCPAI Alpha - Video Game Engine & AAA Rendering Pipeline (crs.engines.game_engine)

2D software-rendered game engine core:
- Entity/component scene graph
- Deterministic fixed-timestep game loop (update + render)
- Software framebuffer rasterization (rects, sprites, particles)
- AABB collision detection
- Input action queue
- Framebuffer export to 24-bit BMP bytes

Crash-proof guarantees:
- Standard library only (struct, math)
- NO FastAPI / web imports
- NO module-level I/O, deterministic (integer seeds only)
- All methods defensive: bad input is ignored safely, never raises

Built per Jesse AI specification, supreme hyper immaculate God mode standards.
Owner: SLMK Jesse Martinez Junior.
"""

import struct
import math

GENESIS_HASH = "92038cafccc7192535bd475cca985d03000d89962b8dc96f6664081663559b1b"
MAX_W = 320
MAX_H = 240
MAX_ENTITIES = 256
MAX_PARTICLES = 512


def _clamp_int(v, lo, hi, default=None):
    try:
        i = int(v)
    except Exception:
        return default if default is not None else lo
    return max(lo, min(hi, i))


def _rgb(c, default=(255, 255, 255)):
    try:
        r, g, b = c
        return (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))
    except Exception:
        return default


class LCGPRNG:
    """Deterministic pseudo-random generator."""

    def __init__(self, seed=42):
        try:
            self._x = int(seed) & 0x7FFFFFFF
        except Exception:
            self._x = 42
        if self._x == 0:
            self._x = 42

    def next_int(self, low, high):
        try:
            lo = int(low)
            hi = int(high)
        except Exception:
            return 0
        if hi < lo:
            lo, hi = hi, lo
        self._x = (1103515245 * self._x + 12345) & 0x7FFFFFFF
        span = hi - lo + 1
        return lo + (self._x % span) if span > 0 else lo

    def next_float(self):
        try:
            self._x = (1103515245 * self._x + 12345) & 0x7FFFFFFF
            return self._x / 0x7FFFFFFF
        except Exception:
            return 0.0


class Rect:
    """Axis-aligned bounding box."""

    def __init__(self, x=0.0, y=0.0, w=0.0, h=0.0):
        try:
            self.x = float(x)
            self.y = float(y)
            self.w = float(w)
            self.h = float(h)
        except Exception:
            self.x = self.y = 0.0
            self.w = self.h = 0.0

    def collides_with(self, other):
        try:
            return (self.x < other.x + other.w and self.x + self.w > other.x
                    and self.y < other.y + other.h and self.y + self.h > other.y)
        except Exception:
            return False

    def center(self):
        try:
            return (self.x + self.w / 2.0, self.y + self.h / 2.0)
        except Exception:
            return (0.0, 0.0)


class TransformComponent:
    def __init__(self, x=0.0, y=0.0, vx=0.0, vy=0.0):
        try:
            self.x = float(x)
            self.y = float(y)
            self.vx = float(vx)
            self.vy = float(vy)
        except Exception:
            self.x = self.y = self.vx = self.vy = 0.0


class SpriteComponent:
    def __init__(self, width=8, height=8, color_matrix=None, transparent_color=None):
        self.width = _clamp_int(width, 1, 128, 8)
        self.height = _clamp_int(height, 1, 128, 8)
        self.transparent_color = _rgb(transparent_color, None) if transparent_color else None
        self.color_matrix = []
        try:
            if isinstance(color_matrix, (list, tuple)):
                for row in color_matrix[:self.height]:
                    self.color_matrix.append([_rgb(px) for px in list(row)[:self.width]])
            while len(self.color_matrix) < self.height:
                self.color_matrix.append([_rgb((200, 200, 200))] * self.width)
            for row in self.color_matrix:
                while len(row) < self.width:
                    row.append(_rgb((200, 200, 200)))
        except Exception:
            self.color_matrix = [[_rgb((200, 200, 200))] * self.width
                                 for _ in range(self.height)]


class ColliderComponent:
    def __init__(self, width=8.0, height=8.0, is_trigger=False):
        try:
            self.width = float(width)
            self.height = float(height)
        except Exception:
            self.width = self.height = 8.0
        self.is_trigger = bool(is_trigger)


class ParticleEmitterComponent:
    def __init__(self, emit_rate=10.0, particle_lifetime=1.0,
                 color=(255, 200, 80), speed_range=(20.0, 60.0)):
        try:
            self.emit_rate = max(0.0, float(emit_rate))
            self.particle_lifetime = max(0.01, float(particle_lifetime))
        except Exception:
            self.emit_rate = 10.0
            self.particle_lifetime = 1.0
        self.color = _rgb(color)
        try:
            lo, hi = speed_range
            self.speed_range = (float(lo), float(hi))
        except Exception:
            self.speed_range = (20.0, 60.0)


class Entity:
    _next_id = 1

    def __init__(self, entity_id=None, tag="default"):
        try:
            self.entity_id = int(entity_id) if entity_id is not None else Entity._next_id
        except Exception:
            self.entity_id = Entity._next_id
        Entity._next_id += 1
        try:
            self.tag = str(tag)
        except Exception:
            self.tag = "default"
        self.components = {}

    def add_component(self, component_type, component):
        try:
            self.components[str(component_type)] = component
        except Exception:
            pass

    def get_component(self, component_type):
        try:
            return self.components.get(str(component_type))
        except Exception:
            return None


class GameScene:
    def __init__(self, width=320, height=240):
        self.width = _clamp_int(width, 1, MAX_W, 320)
        self.height = _clamp_int(height, 1, MAX_H, 240)
        self.entities = {}
        self.gravity = 0.0

    def add_entity(self, entity):
        try:
            if not isinstance(entity, Entity):
                return -1
            if len(self.entities) >= MAX_ENTITIES:
                return -1
            self.entities[entity.entity_id] = entity
            return entity.entity_id
        except Exception:
            return -1

    def remove_entity(self, entity_id):
        try:
            self.entities.pop(int(entity_id), None)
        except Exception:
            pass


class GameEngineCore:
    """Central deterministic simulation + software rendering pipeline."""

    def __init__(self, width=320, height=240, seed=42):
        self.scene = GameScene(width, height)
        self.rng = LCGPRNG(seed)
        self.tick_count = 0
        self.time_sec = 0.0
        self.background = (8, 10, 24)
        self._particles = []  # [x, y, vx, vy, life, max_life, color]
        self.collision_events = []

    def queue_input(self, actions):
        """Store an input action dict for the next tick. Returns stored copy."""
        try:
            if isinstance(actions, dict):
                self._pending_input = {str(k): bool(v) for k, v in actions.items()}
            else:
                self._pending_input = {}
        except Exception:
            self._pending_input = {}
        return dict(getattr(self, "_pending_input", {}))

    def update(self, dt=1.0 / 60.0, input_actions=None):
        """Advance simulation by dt seconds. Never raises."""
        try:
            try:
                step = float(dt)
            except Exception:
                step = 1.0 / 60.0
            step = max(0.0001, min(step, 1.0))
            actions = input_actions
            if actions is None:
                actions = getattr(self, "_pending_input", {})
            if not isinstance(actions, dict):
                actions = {}
            self.collision_events = []
            # integrate transforms
            for ent in list(self.scene.entities.values()):
                t = ent.get_component("transform")
                if t is None:
                    continue
                try:
                    t.vy += self.scene.gravity * step
                    t.x += t.vx * step
                    t.y += t.vy * step
                    # clamp to scene bounds
                    t.x = max(0.0, min(t.x, self.scene.width - 1))
                    t.y = max(0.0, min(t.y, self.scene.height - 1))
                except Exception:
                    pass
            # player-style input nudge for entities tagged 'player'
            for ent in list(self.scene.entities.values()):
                if getattr(ent, "tag", "") != "player":
                    continue
                t = ent.get_component("transform")
                if t is None:
                    continue
                try:
                    speed = 120.0
                    if actions.get("left"):
                        t.x -= speed * step
                    if actions.get("right"):
                        t.x += speed * step
                    if actions.get("jump"):
                        t.vy = -220.0
                    t.x = max(0.0, min(t.x, self.scene.width - 1))
                    t.y = max(0.0, min(t.y, self.scene.height - 1))
                except Exception:
                    pass
            # collisions (AABB)
            ents = list(self.scene.entities.values())
            for i in range(len(ents)):
                ci = ents[i].get_component("collider")
                ti = ents[i].get_component("transform")
                if ci is None or ti is None:
                    continue
                ri = Rect(ti.x, ti.y, ci.width, ci.height)
                for j in range(i + 1, len(ents)):
                    cj = ents[j].get_component("collider")
                    tj = ents[j].get_component("transform")
                    if cj is None or tj is None:
                        continue
                    rj = Rect(tj.x, tj.y, cj.width, cj.height)
                    if ri.collides_with(rj):
                        self.collision_events.append((ents[i].entity_id, ents[j].entity_id))
            # particles
            self._emit_particles(step)
            alive = []
            for p in self._particles:
                try:
                    p[0] += p[2] * step
                    p[1] += p[3] * step
                    p[4] -= step
                    if p[4] > 0:
                        alive.append(p)
                except Exception:
                    pass
            self._particles = alive[:MAX_PARTICLES]
            self.tick_count += 1
            self.time_sec += step
            self._pending_input = {}
            return {"tick": self.tick_count, "time": round(self.time_sec, 3),
                    "collisions": len(self.collision_events)}
        except Exception:
            return {"tick": self.tick_count, "time": round(self.time_sec, 3), "collisions": 0}

    def _emit_particles(self, step):
        try:
            for ent in list(self.scene.entities.values()):
                em = ent.get_component("emitter")
                t = ent.get_component("transform")
                if em is None or t is None:
                    continue
                count = int(em.emit_rate * step + 0.5)
                for _ in range(min(count, 8)):
                    ang = self.rng.next_float() * 2 * math.pi
                    spd = em.speed_range[0] + self.rng.next_float() * max(
                        0.0, em.speed_range[1] - em.speed_range[0])
                    self._particles.append([
                        t.x, t.y,
                        math.cos(ang) * spd, math.sin(ang) * spd,
                        em.particle_lifetime, em.particle_lifetime, em.color,
                    ])
        except Exception:
            pass

    def render(self):
        """Rasterize the scene to an RGB pixel grid (h rows x w cols)."""
        try:
            w, h = self.scene.width, self.scene.height
            fb = [[self.background for _ in range(w)] for _ in range(h)]
            # sprites sorted by entity id (stable draw order)
            for eid in sorted(self.scene.entities.keys()):
                ent = self.scene.entities[eid]
                t = ent.get_component("transform")
                s = ent.get_component("sprite")
                if t is None or s is None:
                    continue
                try:
                    ox, oy = int(t.x), int(t.y)
                    for sy in range(s.height):
                        for sx in range(s.width):
                            x, y = ox + sx, oy + sy
                            if 0 <= x < w and 0 <= y < h:
                                col = s.color_matrix[sy][sx]
                                if s.transparent_color is not None and col == s.transparent_color:
                                    continue
                                fb[y][x] = col
                except Exception:
                    pass
            # particles on top
            for p in self._particles:
                try:
                    x, y = int(p[0]), int(p[1])
                    if 0 <= x < w and 0 <= y < h:
                        fade = max(0.0, min(1.0, p[4] / max(p[5], 0.001)))
                        r, g, b = p[6]
                        fb[y][x] = (int(r * fade), int(g * fade), int(b * fade))
                except Exception:
                    pass
            return fb
        except Exception:
            return []

    def export_framebuffer_bmp(self):
        """Export the current rendered frame as 24-bit BMP bytes."""
        try:
            fb = self.render()
            h = len(fb)
            w = len(fb[0]) if h else 0
            if w <= 0 or h <= 0:
                return b""
            row_size = ((w * 3 + 3) // 4) * 4
            pad = row_size - w * 3
            img = bytearray()
            for y in range(h - 1, -1, -1):
                for x in range(w):
                    try:
                        r, g, b = fb[y][x]
                    except Exception:
                        r, g, b = 0, 0, 0
                    img.extend((max(0, min(255, int(b))),
                                max(0, min(255, int(g))),
                                max(0, min(255, int(r)))))
                img.extend(b"\x00" * pad)
            header = struct.pack("<2sIHHI", b"BM", 54 + len(img), 0, 0, 54)
            dib = struct.pack("<IIIHHIIIIII", 40, w, h, 1, 24, 0, len(img), 0, 0, 0, 0)
            return header + dib + bytes(img)
        except Exception:
            return b""


def run_demo_simulation(seed=42, ticks=60, width=160, height=120):
    """Run a small deterministic demo scene. Returns dict with BMP + stats."""
    try:
        eng = GameEngineCore(width, height, seed)
        player = Entity(tag="player")
        player.add_component("transform", TransformComponent(20, 60, 30, 0))
        player.add_component("sprite", SpriteComponent(12, 12,
            [[(240, 200, 80)] * 12 for _ in range(12)]))
        player.add_component("collider", ColliderComponent(12, 12))
        eng.scene.add_entity(player)
        wall = Entity(tag="wall")
        wall.add_component("transform", TransformComponent(100, 40))
        wall.add_component("sprite", SpriteComponent(16, 40,
            [[(90, 140, 220)] * 16 for _ in range(40)]))
        wall.add_component("collider", ColliderComponent(16, 40))
        eng.scene.add_entity(wall)
        fx = Entity(tag="fx")
        fx.add_component("transform", TransformComponent(80, 90))
        fx.add_component("emitter", ParticleEmitterComponent(30, 0.8, (255, 150, 60), (20, 70)))
        eng.scene.add_entity(fx)
        total_collisions = 0
        for _ in range(max(1, min(int(ticks), 600))):
            st = eng.update(1.0 / 60.0, {"right": True})
            total_collisions += st["collisions"]
        return {
            "bmp": eng.export_framebuffer_bmp(),
            "ticks": eng.tick_count,
            "collisions": total_collisions,
            "entities": len(eng.scene.entities),
        }
    except Exception:
        return {"bmp": b"", "ticks": 0, "collisions": 0, "entities": 0}


def module_status():
    return {
        "module": "crs.engines.game_engine",
        "status": "ACTIVE",
        "tier": "AAA_SOFTWARE_PIPELINE",
        "genesis": GENESIS_HASH[:16],
        "limits": {"max_resolution": [MAX_W, MAX_H], "max_entities": MAX_ENTITIES},
        "functions": [
            "LCGPRNG", "Rect", "TransformComponent", "SpriteComponent",
            "ColliderComponent", "ParticleEmitterComponent", "Entity",
            "GameScene", "GameEngineCore", "run_demo_simulation",
        ],
    }
