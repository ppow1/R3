"""PostgreSQL persistence for the existing institutional knowledge authority."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


_NON_INGESTIBLE_FLAGS = {"secret", "credential", "private-hr", "private_hr",
                         "protected-relationship", "protected_relationship"}


def validate_item_decision(item: dict[str, Any], selection: dict[str, Any]) -> None:
    """Enforce item-level review for flagged material and never ingest protected content."""
    flags = set(item.get("flags") or [])
    if flags & _NON_INGESTIBLE_FLAGS and selection.get("decision") == "approve":
        raise PermissionError("sensitive or protected material cannot be promoted by general Knowledge ingestion")
    if (flags or item.get("conflicts")) and (selection.get("individual_review") is not True
                                               or not selection.get("rationale")):
        raise ValueError("Flagged proposal requires individual review and a rationale")


class KnowledgeReviewStore:
    def __init__(self, dsn: str):
        if not isinstance(dsn, str) or not dsn.strip():
            raise ValueError("Knowledge database DSN is required")
        self.dsn = dsn

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def import_catalog(self, catalog: dict[str, Any]) -> dict[str, int]:
        """Import proposals only; existing decisions and their content are immutable."""
        batches = {b["batch_id"]: b for b in catalog["batches"]}
        inserted = updated = unchanged = 0
        with self._connect() as conn:
            with conn.transaction():
                for batch in batches.values():
                    digest = canonical_digest(batch)
                    conn.execute("INSERT INTO r3a.knowledge_review_batches(batch_id,source_digest,content) VALUES (%s,%s,%s) ON CONFLICT(batch_id) DO UPDATE SET source_digest=EXCLUDED.source_digest,content=EXCLUDED.content,updated_at=clock_timestamp() WHERE r3a.knowledge_review_batches.source_digest<>EXCLUDED.source_digest", (batch["batch_id"],digest,json.dumps(batch)))
                for item in catalog["entries"]:
                    proposal_id = item["entry_id"]
                    revision = item["version"]
                    digest = canonical_digest({k: v for k, v in item.items() if k != "decision"})
                    batch = next((b for b in batches.values() if proposal_id in b["entry_ids"]), None)
                    if batch is None:
                        raise ValueError(f"Proposal {proposal_id} has no catalog batch")
                    row = conn.execute("SELECT proposal_revision,source_digest,state FROM r3a.knowledge_proposals WHERE proposal_id=%s FOR UPDATE", (proposal_id,)).fetchone()
                    if row is None:
                        conn.execute("INSERT INTO r3a.knowledge_proposals(proposal_id,batch_id,proposal_revision,source_digest,content) VALUES (%s,%s,%s,%s,%s)", (proposal_id,batch["batch_id"],revision,digest,json.dumps(item)))
                        inserted += 1
                    elif row["proposal_revision"] == revision and row["source_digest"].strip() == digest:
                        unchanged += 1
                    else:
                        if row["state"] in {"approved", "rejected", "deferred"}:
                            raise ValueError(f"Cannot replace decided proposal {proposal_id}; create a successor revision")
                        if revision <= row["proposal_revision"]:
                            revision = row["proposal_revision"] + 1
                            item = {**item, "version": revision}
                            digest = canonical_digest({k: v for k, v in item.items() if k != "decision"})
                        conn.execute("UPDATE r3a.knowledge_proposals SET batch_id=%s,proposal_revision=%s,source_digest=%s,content=%s,updated_at=clock_timestamp() WHERE proposal_id=%s", (batch["batch_id"],revision,digest,json.dumps(item),proposal_id))
                        updated += 1
        return {"inserted": inserted, "updated": updated, "unchanged": unchanged}

    def list_proposals(self, batch_id: str | None = None, include_decided: bool = True,
                       limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            params: list[Any] = []
            where = []
            if batch_id:
                where.append("p.batch_id=%s")
                params.append(batch_id)
            if not include_decided:
                where.append("p.state='pending'")
            if cursor:
                where.append("p.proposal_id>%s")
                params.append(cursor)
            query = "SELECT p.proposal_id,p.batch_id,p.proposal_revision,p.source_digest,p.content,p.state,p.created_at,p.updated_at, COALESCE(json_agg(json_build_object('decision_id',d.decision_id,'decision',d.decision,'reviewer_principal',d.reviewer_principal,'rationale',d.rationale,'source_digest',d.source_digest,'decided_at',d.decided_at,'knowledge_item_id',d.knowledge_item_id) ORDER BY d.decision_id) FILTER (WHERE d.decision_id IS NOT NULL),'[]'::json) AS decisions FROM r3a.knowledge_proposals p LEFT JOIN r3a.knowledge_review_decisions d USING(proposal_id)"
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " GROUP BY p.proposal_id ORDER BY p.proposal_id LIMIT %s"
            params.append(limit + 1)
            rows = conn.execute(query, params).fetchall()
            batch_params: list[Any] = []
            batch_where = "WHERE b.batch_id=%s" if batch_id else ""
            if batch_id:
                batch_params.append(batch_id)
            batches = conn.execute("SELECT b.batch_id,b.source_digest,b.content,count(p.proposal_id) AS entry_count,count(p.proposal_id) FILTER (WHERE p.state='pending') AS pending_count,count(p.proposal_id) FILTER (WHERE p.state='approved') AS approved_count,count(p.proposal_id) FILTER (WHERE p.state='rejected') AS rejected_count,count(p.proposal_id) FILTER (WHERE p.state='deferred') AS deferred_count FROM r3a.knowledge_review_batches b LEFT JOIN r3a.knowledge_proposals p USING(batch_id) " + batch_where + " GROUP BY b.batch_id ORDER BY b.batch_id", batch_params).fetchall()
        next_cursor = rows[limit - 1]["proposal_id"] if len(rows) > limit else None
        rows = rows[:limit]
        return {"schema_id": "r3a.knowledge-review-proposals.v1", "schema_version": 1,
                "next_cursor": next_cursor,
                "batches": [{**row["content"],"source_digest":row["source_digest"].strip(),"entry_count":row["entry_count"],"pending_count":row["pending_count"],"approved_count":row["approved_count"],"rejected_count":row["rejected_count"],"deferred_count":row["deferred_count"]} for row in batches],
                "proposals": [{**row["content"], "proposal_id": row["proposal_id"],
                               "batch_id": row["batch_id"], "proposal_revision": row["proposal_revision"],
                               "source_digest": row["source_digest"].strip(), "state": row["state"],
                               "created_at": row["created_at"].isoformat(),
                               "updated_at": row["updated_at"].isoformat(), "decisions": row["decisions"]}
                              for row in rows]}

    def decide(self, arguments: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        caller = context.get("caller") or {}
        auth = context.get("authorization") or {}
        principal = caller.get("principal_id")
        if context.get("effect_class") != "steward_write" or not principal or auth.get("allowed") is not True or not auth.get("decision_id") or not auth.get("audit_event_id"):
            raise PermissionError("binding proposal decisions require an authenticated CME Steward authorization")
        selected = arguments.get("decisions")
        if not isinstance(selected, list) or not selected:
            raise ValueError("decisions must contain at least one selected proposal")
        if len(selected) > 100:
            raise ValueError("a review invocation is limited to 100 proposals")
        ids = [item.get("proposal_id") for item in selected if isinstance(item, dict)]
        if len(ids) != len(selected) or len(ids) != len(set(ids)):
            raise ValueError("each proposal may appear once per decision batch")
        outer_key = context.get("idempotency_key")
        if not outer_key:
            raise ValueError("decision invocation requires an idempotency key")
        results = []
        with self._connect() as conn:
            with conn.transaction():
                for selection in selected:
                    proposal_id = selection.get("proposal_id")
                    decision = selection.get("decision")
                    if decision not in {"approve", "reject", "defer"}:
                        raise ValueError("decision must be approve, reject, or defer")
                    key = f"{outer_key}:{proposal_id}"
                    previous = conn.execute("SELECT * FROM r3a.knowledge_review_decisions WHERE idempotency_key=%s", (key,)).fetchone()
                    if previous:
                        if previous["proposal_revision"] != selection.get("proposal_revision") or previous["source_digest"].strip() != selection.get("source_digest") or previous["decision"] != decision:
                            raise ValueError("decision idempotency key was replayed with different content")
                        results.append({"proposal_id":proposal_id,"decision_id":previous["decision_id"],"decision":previous["decision"],"reviewer_principal":previous["reviewer_principal"],"decided_at":previous["decided_at"].isoformat(),"knowledge_item_id":previous["knowledge_item_id"],"source_digest":previous["source_digest"].strip(),"authorization":previous["authorization_ref"],"replayed":True})
                        continue
                    proposal = conn.execute("SELECT * FROM r3a.knowledge_proposals WHERE proposal_id=%s FOR UPDATE", (proposal_id,)).fetchone()
                    if proposal is None:
                        raise KeyError(f"Unknown proposal: {proposal_id}")
                    if proposal["state"] not in {"pending", "deferred"}:
                        raise ValueError(f"Proposal {proposal_id} is already {proposal['state']}")
                    if proposal["proposal_revision"] != selection.get("proposal_revision") or proposal["source_digest"].strip() != selection.get("source_digest"):
                        raise ValueError(f"Proposal {proposal_id} changed after review; reload it")
                    item = proposal["content"]
                    validate_item_decision(item, selection)
                    item_id = f"institutional:{proposal_id}:v{proposal['proposal_revision']}" if decision == "approve" else None
                    stamp = conn.execute("INSERT INTO r3a.knowledge_review_decisions(idempotency_key,proposal_id,proposal_revision,decision,reviewer_principal,authorization_ref,invocation_id,correlation_id,batch_id,rationale,source_digest,knowledge_item_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING decision_id,decided_at", (key,proposal_id,proposal["proposal_revision"],decision,principal,json.dumps(auth),context["invocation_id"],uuid.UUID(context["correlation_id"]),proposal["batch_id"],selection.get("rationale"),proposal["source_digest"],item_id)).fetchone()
                    conn.execute("UPDATE r3a.knowledge_proposals SET state=%s,updated_at=clock_timestamp() WHERE proposal_id=%s", ({"approve":"approved","reject":"rejected","defer":"deferred"}[decision],proposal_id))
                    if decision == "approve":
                        content = item["proposed_canonical_knowledge"]
                        content_digest = hashlib.sha256(content.encode()).hexdigest()
                        sources = item.get("sources", [])
                        source_refs = [{k: s.get(k) for k in ("repository","path","revision","commit","git_blob","sha256","url","location")} for s in sources]
                        supersedes = selection.get("supersedes_knowledge_item_id")
                        if supersedes:
                            old = conn.execute("SELECT knowledge_item_id FROM r3a.institutional_knowledge_items WHERE knowledge_item_id=%s AND active FOR UPDATE",(supersedes,)).fetchone()
                            if old is None:
                                raise ValueError("superseded item must identify an active authoritative item")
                            conn.execute("UPDATE r3a.institutional_knowledge_items SET active=false WHERE knowledge_item_id=%s",(supersedes,))
                        conn.execute("INSERT INTO r3a.institutional_knowledge_items(knowledge_item_id,proposal_id,proposal_revision,title,category,content,content_sha256,source_digest,source_references,approval_decision_id,reviewer_principal,approved_at,supersedes_item_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (item_id,proposal_id,proposal["proposal_revision"],item["title"],item["category"],content,content_digest,proposal["source_digest"],json.dumps(source_refs),stamp["decision_id"],principal,stamp["decided_at"],supersedes))
                    results.append({"proposal_id": proposal_id,"decision_id":stamp["decision_id"],"decision":decision,"reviewer_principal":principal,"decided_at":stamp["decided_at"].isoformat(),"knowledge_item_id":item_id,"source_digest":proposal["source_digest"].strip(),"authorization":auth,"replayed":False})
                for result in results:
                    if not result.get("replayed"):
                        config_revision = auth.get("config_revision")
                        if config_revision and not conn.execute("SELECT 1 FROM r3a.config_revisions WHERE revision_id=%s", (config_revision,)).fetchone():
                            config_revision = None
                        conn.execute("INSERT INTO r3a.institution_events(event_id,event_type,schema_version,subject_type,subject_id,occurred_at,actor,correlation_id,reason,outcome,config_revision,implementation_revision,evidence) VALUES (%s,'knowledge.proposal.decided',1,'knowledge_proposal',%s,%s,%s,%s,%s,%s,%s,'governed-knowledge-v1',%s)", (uuid.uuid4(),result["proposal_id"],datetime.now(timezone.utc),principal,uuid.UUID(context["correlation_id"]),result.get("decision"),result["decision"],config_revision,json.dumps(result)))
        return {"schema_id":"r3a.knowledge-review-decisions.v1","schema_version":1,"decisions":results}

    def retrieve_approved(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        terms = [term.lower() for term in re.findall(r"[\w-]{3,}", query)]
        if not terms:
            return []
        with self._connect() as conn:
            rows = conn.execute("SELECT k.*,d.decision,d.decision_id FROM r3a.institutional_knowledge_items k JOIN r3a.knowledge_review_decisions d ON d.decision_id=k.approval_decision_id WHERE k.active ORDER BY k.created_at DESC LIMIT 500").fetchall()
        matches = []
        for row in rows:
            score = sum(row["content"].lower().count(term) for term in set(terms))
            if not score:
                continue
            matches.append({"source_id":row["knowledge_item_id"],"source":row["title"],"uri":f"institutional-knowledge://{row['knowledge_item_id']}","source_path":row["proposal_id"],"content":row["content"],"sha256":row["content_sha256"].strip(),"excerpt_sha256":row["content_sha256"].strip(),"document_revision":str(row["proposal_revision"]),"source_sha256":row["source_digest"].strip(),"source_references":row["source_references"],"approval":{"decision_id":row["decision_id"],"decision":row["decision"],"reviewer_principal":row["reviewer_principal"],"approved_at":row["approved_at"].isoformat()},"matched_terms":[term for term in dict.fromkeys(terms) if term in row["content"].lower()],"_score":score})
        matches.sort(key=lambda item:(-item["_score"],item["source_id"]))
        for item in matches:
            item.pop("_score",None)
        return matches[:limit]
