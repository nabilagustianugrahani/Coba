"""Relationship graph for tracking Creator→Content→Campaign→Affiliate.

Inspired by colbymchenry/codegraph (MIT, 42k stars):
  - SQLite + FTS5 for full-text + structured queries
  - Tree-sitter-style typed relations
  - One-call "explore" API for architecture-style answers

Our model:
  - NODES: Creator, Content, Campaign, AffiliateLink, Niche, Platform, Account
  - EDGES: typed relationships with metadata
  - FTS5: full-text search across all node properties
  - GRAPH QUERIES: find_related, shortest_path, subgraph

Use cases:
  - "What content did Sari post this week?" → Content nodes
  - "What's the best performing niche for @rizky?" → Niche→Content aggregate
  - "Which affiliate links are linked to beauty campaign X?" → AffiliateLink nodes
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)


DEFAULT_DB_PATH = Path.home() / ".9router" / "relationship_graph.db"


class NodeType(str, Enum):
    CREATOR = "creator"
    CONTENT = "content"
    CAMPAIGN = "campaign"
    AFFILIATE_LINK = "affiliate_link"
    NICHE = "niche"
    PLATFORM = "platform"
    ACCOUNT = "account"
    PERSONA = "persona"


class EdgeType(str, Enum):
    POSTED = "posted"
    MENTIONED = "mentioned"
    TARGETS = "targets"
    PROMOTES = "promotes"
    CREATED = "created"
    ADAPTED_FROM = "adapted_from"
    USES_AFFILIATE = "uses_affiliate"
    ON_PLATFORM = "on_platform"
    HAS_PERSONA = "has_persona"
    BELONGS_TO = "belongs_to"
    ENGAGED_WITH = "engaged_with"


@dataclass
class Node:
    node_id: str
    node_type: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    edge_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RelationshipGraph:
    """SQLite + FTS5 relationship graph for UGC entities."""

    def __init__(self, path: Optional[Path] = None) -> None:
        env_path = os.environ.get("UGC_GRAPH_DB", "")
        self.path = path or (Path(env_path) if env_path else DEFAULT_DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nodes (
                    node_id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edges (
                    edge_id TEXT PRIMARY KEY,
                    from_node TEXT NOT NULL,
                    to_node TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    properties TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    UNIQUE(from_node, to_node, edge_type)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_node)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_node)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type)")

            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                        node_id UNINDEXED, node_type UNINDEXED, name,
                        properties_text, tokenize='porter unicode61'
                    )
                    """
                )
            except sqlite3.OperationalError as e:
                log.warning("FTS5 not available: %s", e)

            conn.commit()

    def add_node(
        self,
        node_type: str,
        name: str,
        properties: Optional[dict[str, Any]] = None,
        node_id: Optional[str] = None,
    ) -> Node:
        with self._lock:
            nid = node_id or f"{node_type}_{uuid.uuid4().hex[:12]}"
            node = Node(
                node_id=nid,
                node_type=node_type,
                name=name,
                properties=properties or {},
            )
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO nodes (node_id, node_type, name, properties, created_at) VALUES (?, ?, ?, ?, ?)",
                    (nid, node_type, name, json.dumps(node.properties), node.created_at),
                )
                try:
                    props_text = json.dumps(node.properties, ensure_ascii=False)
                    conn.execute(
                        "INSERT OR REPLACE INTO nodes_fts (node_id, node_type, name, properties_text) VALUES (?, ?, ?, ?)",
                        (nid, node_type, name, props_text),
                    )
                except sqlite3.OperationalError:
                    pass
            return node

    def add_edge(
        self,
        from_node: str,
        to_node: str,
        edge_type: str,
        properties: Optional[dict[str, Any]] = None,
        weight: float = 1.0,
        edge_id: Optional[str] = None,
    ) -> Edge:
        with self._lock:
            eid = edge_id or f"edge_{uuid.uuid4().hex[:12]}"
            edge = Edge(
                edge_id=eid,
                from_node=from_node,
                to_node=to_node,
                edge_type=edge_type,
                properties=properties or {},
                weight=weight,
            )
            with self._conn() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO edges
                    (edge_id, from_node, to_node, edge_type, properties, weight, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (eid, from_node, to_node, edge_type, json.dumps(edge.properties), weight, edge.created_at),
                )
            return edge

    def get_node(self, node_id: str) -> Optional[Node]:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM nodes WHERE node_id=?", (node_id,)
                ).fetchone()
                if not row:
                    return None
                return Node(
                    node_id=row["node_id"],
                    node_type=row["node_type"],
                    name=row["name"],
                    properties=json.loads(row["properties"]),
                    created_at=row["created_at"],
                )

    def get_edge(self, edge_id: str) -> Optional[Edge]:
        with self._lock:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM edges WHERE edge_id=?", (edge_id,)
                ).fetchone()
                if not row:
                    return None
                return self._row_to_edge(row)

    def _row_to_edge(self, row: sqlite3.Row) -> Edge:
        return Edge(
            edge_id=row["edge_id"],
            from_node=row["from_node"],
            to_node=row["to_node"],
            edge_type=row["edge_type"],
            properties=json.loads(row["properties"]),
            weight=row["weight"],
            created_at=row["created_at"],
        )

    def find_nodes(
        self, node_type: Optional[str] = None, name_pattern: Optional[str] = None,
        limit: int = 100,
    ) -> list[Node]:
        with self._lock:
            sql = "SELECT * FROM nodes"
            params: list[Any] = []
            if node_type or name_pattern:
                sql += " WHERE"
                if node_type:
                    sql += " node_type=?"
                    params.append(node_type)
                if name_pattern:
                    if params:
                        sql += " AND"
                    sql += " name LIKE ?"
                    params.append(f"%{name_pattern}%")
            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            with self._conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                return [
                    Node(
                        node_id=r["node_id"],
                        node_type=r["node_type"],
                        name=r["name"],
                        properties=json.loads(r["properties"]),
                        created_at=r["created_at"],
                    )
                    for r in rows
                ]

    def find_related(
        self, node_id: str, edge_types: Optional[list[str]] = None,
        direction: str = "out", limit: int = 50,
    ) -> list[tuple[Edge, Node]]:
        with self._lock:
            where_field = "from_node" if direction == "out" else "to_node"
            join_field = "to_node" if direction == "out" else "from_node"
            sql = f"""
                SELECT e.*, n.node_id AS n_id, n.node_type AS n_type, n.name AS n_name,
                       n.properties AS n_props, n.created_at AS n_created
                FROM edges e
                JOIN nodes n ON n.node_id = e.{join_field}
                WHERE e.{where_field} = ?
            """
            params: list[Any] = [node_id]
            if edge_types:
                placeholders = ",".join("?" * len(edge_types))
                sql += f" AND e.edge_type IN ({placeholders})"
                params.extend(edge_types)
            sql += " ORDER BY e.weight DESC LIMIT ?"
            params.append(limit)
            with self._conn() as conn:
                rows = conn.execute(sql, params).fetchall()
                out: list[tuple[Edge, Node]] = []
                for r in rows:
                    edge = self._row_to_edge(r)
                    node = Node(
                        node_id=r["n_id"],
                        node_type=r["n_type"],
                        name=r["n_name"],
                        properties=json.loads(r["n_props"]),
                        created_at=r["n_created"],
                    )
                    out.append((edge, node))
                return out

    def search(self, query: str, node_type: Optional[str] = None,
               limit: int = 20) -> list[Node]:
        with self._lock:
            try:
                sql = "SELECT node_id, node_type, name FROM nodes_fts WHERE nodes_fts MATCH ?"
                params: list[Any] = [query]
                if node_type:
                    sql += " AND node_type=?"
                    params.append(node_type)
                sql += " LIMIT ?"
                params.append(limit)
                with self._conn() as conn:
                    rows = conn.execute(sql, params).fetchall()
                    out: list[Node] = []
                    for r in rows:
                        node = self.get_node(r["node_id"])
                        if node:
                            out.append(node)
                    return out
            except sqlite3.OperationalError:
                return self.find_nodes(node_type=node_type, name_pattern=query, limit=limit)

    def subgraph(self, root_id: str, depth: int = 2) -> dict[str, Any]:
        if depth < 1:
            return {"nodes": [], "edges": []}
        visited: set[str] = set()
        all_nodes: dict[str, Node] = {}
        all_edges: list[Edge] = []

        def _walk(nid: str, d: int) -> None:
            if nid in visited or d < 0:
                return
            visited.add(nid)
            node = self.get_node(nid)
            if not node:
                return
            all_nodes[nid] = node
            if d == 0:
                return
            for direction in ("out", "in"):
                for edge, neighbor in self.find_related(nid, direction=direction, limit=50):
                    all_edges.append(edge)
                    _walk(neighbor.node_id, d - 1)

        _walk(root_id, depth)
        return {
            "root": root_id,
            "depth": depth,
            "nodes": [n.to_dict() for n in all_nodes.values()],
            "edges": [e.to_dict() for e in all_edges],
        }

    def stats(self) -> dict[str, Any]:
        with self._lock:
            with self._conn() as conn:
                node_rows = conn.execute(
                    "SELECT node_type, COUNT(*) as cnt FROM nodes GROUP BY node_type"
                ).fetchall()
                edge_rows = conn.execute(
                    "SELECT edge_type, COUNT(*) as cnt FROM edges GROUP BY edge_type"
                ).fetchall()
                total_nodes = conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()["c"]
                total_edges = conn.execute("SELECT COUNT(*) as c FROM edges").fetchone()["c"]
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_by_type": {r["node_type"]: r["cnt"] for r in node_rows},
            "edges_by_type": {r["edge_type"]: r["cnt"] for r in edge_rows},
        }

    def clear(self) -> None:
        with self._lock:
            with self._conn() as conn:
                conn.execute("DELETE FROM edges")
                conn.execute("DELETE FROM nodes")
                try:
                    conn.execute("DELETE FROM nodes_fts")
                except sqlite3.OperationalError:
                    pass


__all__ = [
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "RelationshipGraph",
    "DEFAULT_DB_PATH",
]
