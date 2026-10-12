#!/usr/bin/env python3
"""One-shot migration to CONTENT IDENTITY (D-CI) - REUSES the vectors, ZERO re-embedding.

Before: a book's id (and its Qdrant point id) was derived from its PATH. The code moves to id =
fingerprint of the .md's CONTENT. This migration re-keys the existing points (reads each vector,
re-inserts it under the new content-id + the current shelf's domain, deletes the old one) and
re-keys the manifest to match. The embedding is REUSED, never recomputed.

Safety net: the TRUTH (raw/*.md) is never touched; the index is reconstructible from it. Backs up
the manifest before writing. DRY-RUN by default.

  dry-run       : PYTHONPATH=system/lib uv run --extra bricks python scripts/migrate_to_content_identity.py
  count (Qdrant): ... scripts/migrate_to_content_identity.py --connect
  apply         : ... scripts/migrate_to_content_identity.py --apply
Prerequisites: Qdrant running (localhost:6333) + `uv sync --extra bricks`.

IMPORTANT: the fingerprint must stay identical to `library._content_doc` (blake2b utf-8, digest_size=8).
If the identity() code evolves, update it HERE too.
"""

import hashlib
import json
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = REPO / "knowledge" / "raw"
MANIFEST = REPO / "knowledge" / "library_manifest.json"
COLLECTIONS = ["mnemosyne_public", "mnemosyne_perso", "mnemosyne_sensible"]
_UUID_NS = uuid.UUID("6f4b2c9e-3a1d-4e5f-8b7a-0c1d2e3f4a5b")  # same NS as _QdrantBackend._pid
_UPSERT_BATCH = (
    256  # upsert sub-batches: a big book (>3000 chunks) exceeds Qdrant's HTTP limit (32 MiB)
)


def _blake(s: bytes) -> str:
    return hashlib.blake2b(s, digest_size=8).hexdigest()


def content_id(md: Path) -> str:
    return f"library/{_blake(md.read_text(encoding='utf-8').encode('utf-8'))}"


def path_id(rel: str) -> str:
    return f"library/{_blake(rel.encode('utf-8'))}"  # path fallback (mirror absent) = identity() fallback


def pid(doc_ordinal: str) -> str:
    return str(uuid.uuid5(_UUID_NS, doc_ordinal))


def _all_points(client, coll, doc, models):
    pts, offset = [], None
    while True:
        batch, offset = client.scroll(
            coll,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="doc", match=models.MatchValue(value=doc))]
            ),
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        pts.extend(batch)
        if offset is None:
            break
    return pts


def main():
    apply = "--apply" in sys.argv
    connect = apply or "--connect" in sys.argv
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = data["records"]

    client = None
    if connect:
        from qdrant_client import QdrantClient

        client = QdrantClient(url="http://localhost:6333")

    # plan: manifest key (path) -> new id (content if the .md is readable, otherwise path fallback)
    plan = []  # (rel, old_doc, new_doc, domain, kind)
    for old_key, rec in records.items():
        rel = rec.get("rel", old_key)
        domain = rec["domain"]
        old_doc = rec["doc"]
        md = RAW / rel
        if rec.get("status") == "done" and md.exists():
            try:
                plan.append((rel, old_doc, content_id(md), domain, "rekey"))
            except (
                OSError,
                ValueError,
            ):  # .md not utf-8 / unreadable => path-id (mirrors the identity() safety net, audit F1)
                print(f"  .md unreadable, falling back to path-id (non-blocking) : {rel}")
                plan.append((rel, old_doc, path_id(rel), domain, "keep-path"))
        else:
            plan.append(
                (rel, old_doc, path_id(rel), domain, "keep-path")
            )  # NEEDS_OCR/UNDECLARED/md absent

    kinds = Counter(k for *_, k in plan)
    dups = [nd for nd, n in Counter(nd for _, _, nd, _, k in plan if k == "rekey").items() if n > 1]
    print(f"{'APPLY' if apply else 'DRY-RUN'} - {len(plan)} manifest entries : {dict(kinds)}")
    if dups:
        print(f"  dedup (identical contents -> same id, merged) : {len(dups)} group(s)")

    moved = 0
    if client is not None:
        from qdrant_client import models

        for rel, old_doc, new_doc, domain, kind in plan:
            if kind != "rekey" or old_doc == new_doc:
                continue
            for coll in COLLECTIONS:
                if not client.collection_exists(coll):
                    continue
                pts = _all_points(client, coll, old_doc, models)
                if not pts:
                    continue
                new_points = []
                for p in pts:
                    payload = dict(p.payload or {})
                    chunk = payload.get("chunk")
                    if not isinstance(chunk, int) or isinstance(
                        chunk, bool
                    ):  # no int chunk => collision at #0 (audit F4)
                        print(
                            f"  WARNING : point without a valid 'chunk' (doc={old_doc}) - skipped (avoids the collision)"
                        )
                        continue
                    new_points.append(
                        models.PointStruct(
                            id=pid(f"{new_doc}#{chunk}"),
                            vector=p.vector,  # REUSED - never recomputed
                            payload={**payload, "doc": new_doc, "domains": [domain]},
                        )
                    )
                if apply:
                    for i in range(
                        0, len(new_points), _UPSERT_BATCH
                    ):  # sub-batches: a big book exceeds 32 MiB in a single call
                        client.upsert(coll, points=new_points[i : i + _UPSERT_BATCH])
                    client.delete(
                        coll,
                        points_selector=models.FilterSelector(  # AFTER all sub-batches (upsert-before-delete is preserved)
                            filter=models.Filter(
                                must=[
                                    models.FieldCondition(
                                        key="doc", match=models.MatchValue(value=old_doc)
                                    )
                                ]
                            )
                        ),
                    )
                moved += len(new_points)
        print(
            f"  points {'re-inserted' if apply else 'to re-insert'} (vectors reused) : {moved}"
        )

    if apply:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(MANIFEST, MANIFEST.with_name(f"library_manifest.pre-DCI.{ts}.json"))
        new_records = {}
        for rel, old_doc, new_doc, domain, _ in plan:
            src = records.get(rel) or next(r for k, r in records.items() if r.get("rel", k) == rel)
            new_records[new_doc] = {**src, "rel": rel, "doc": new_doc, "domain": domain}
        data["records"] = {k: new_records[k] for k in sorted(new_records)}
        tmp = MANIFEST.with_name(MANIFEST.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(MANIFEST)
        print(
            f"  manifest re-keyed by content-identity ({len(new_records)} entries). Pre-DCI backup written."
        )
    elif not connect:
        print(
            "  (dry-run - nothing touched. --connect to count the points without writing, --apply to execute.)"
        )


if __name__ == "__main__":
    main()
