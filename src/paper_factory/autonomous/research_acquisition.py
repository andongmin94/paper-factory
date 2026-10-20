"""Bounded native acquisition for a retained research-development round.

The existing literature collector owns HTTP, identity checks and extraction.
This adapter registers its complete bytes, exposes verified whole bodies and
preserves partial/failed attempts. It never reserves a model or executes a repo.
"""

from copy import deepcopy
import hashlib
from urllib.parse import quote

from ..models import now
from ..workspace import safe_relative
from .research_design import ResearchAgenda


class ResearchAcquisitionMixin:
    def _research_acquisition_inventory(self, ws, record, state):
        """Return retained reading and failed routes without changing old pools."""
        from .. import workflow as engine
        _, packet = self._portfolio_literature(ws, record)
        packets = [packet or {}]
        for entry in (state.get("research_development") or {}).get("acquisitions", []):
            if entry.get("packet_artifact_id"):
                packets.append(engine._read(ws, record, entry["packet_artifact_id"])["value"])
        cards = [*((state.get("evidence_collection") or {}).get("sources", [])),
                 *state.get("focused_round", {}).get("primary_collection", {}).get("sources", [])]
        sources = [source for item in packets for source in item.get("sources", [])] + cards
        identities, urls = set(), set()
        for source in sources:
            if source.get("scope") != "full_text" and not (source.get("status") == "retained" and source.get("complete_body")):
                continue
            if source.get("doi"):
                identities.add("doi:" + source["doi"])
            if source.get("arxiv_id"):
                identities.add("arxiv:" + source["arxiv_id"])
            if source.get("copy_type") == "scholarly_html" and source.get("html_url"):
                identities.add("html:" + source["html_url"])
            if source.get("publisher_url"):
                identities.add("publisher:" + source["publisher_url"])
        for packet in packets:
            urls.update(item["url"] for item in packet.get("pdf_reservations", []) if item.get("url"))
        return sources, sorted(identities), sorted(urls)

    def _research_make_cards(self, ws, record, state, packet, number, previous_sources):
        from .. import workflow as engine
        cards, outcomes = [], []
        prior_raw = {value for source in previous_sources if (value := source.get("raw_sha256", source.get("sha256")))}
        prior_text = {value for source in previous_sources if (value := source.get("text_sha256"))}
        for index, source in enumerate(packet.get("sources", []), 1):
            outcome = {"source_id": source.get("id"), "title": source.get("title"), "scope": source.get("scope")}
            if source.get("scope") != "full_text":
                outcomes.append({**outcome, "status": "not_read_in_full", "reason": "Metadata and abstracts cannot complete a closest-method comparison."})
                continue
            if source.get("sha256") in prior_raw or source.get("text_sha256") in prior_text:
                outcomes.append({**outcome, "status": "already_retained", "reason": "The same complete body remains available in its original evidence pool."})
                continue
            try:
                if not engine._retained_primary_body(ws, record, source, packet):
                    raise ValueError("The complete reading lost its original identity/body proof")
                keys = {}
                for field in ("raw_path", "text_path"):
                    path = safe_relative(ws.path("research"), source[field]).relative_to(ws.root).as_posix()
                    keys[field] = next(key for key, artifact in record.artifacts.items() if artifact.path == path)
                identifier = state["research_development"]["id"] + "-reading-" + str(number) + "-" + str(index)
                public_url = (source.get("publisher_url") or
                    ("https://doi.org/" + quote(source["doi"], safe="/()") if source.get("doi") else None) or
                    ("https://arxiv.org/abs/" + source["arxiv_id"] if source.get("arxiv_id") else None) or
                    source.get("html_url") or source["url"])
                cards.append({**deepcopy(source), "id": identifier, "collected_source_id": source["id"],
                    "url": public_url, "collector_source_url": source["url"],
                    "status": "retained", "source_role": "primary_full_text", "purpose": "comparison",
                    "complete_body": True, "fetched_at": now(), "raw_artifact_id": keys["raw_path"], "raw_sha256": source["sha256"],
                    "text_artifact_id": keys["text_path"], "text_sha256": source["text_sha256"],
                    "scope": "Native identity-bound complete primary body. Retrieval establishes reading availability, never novelty, relevance or effectiveness."})
                outcomes.append({**outcome, "status": "retained_full_body", "document_id": identifier})
                prior_raw.add(source["sha256"])
                prior_text.add(source["text_sha256"])
            except (KeyError, StopIteration, ValueError) as error:
                outcomes.append({**outcome, "status": "not_admitted", "reason": str(error)[:1000]})
        return cards, outcomes

    def _research_acquire(self, ws, record, state, agenda, *, followup_queries=None):
        """Acquire one agenda pool and at most one changed-query strengthening pool.

        Both collections share two PDF reservations. The intent is persisted
        before dispatch; an interrupted intent is closed without network retry.
        All earlier counts and evidence remain untouched.
        """
        from .. import workflow as engine
        agenda = ResearchAgenda.model_validate(agenda)
        queries = agenda.queries() if followup_queries is None else followup_queries
        if (not isinstance(queries, list) or not 1 <= len(queries) <= (4 if followup_queries is None else 2) or
                any(not isinstance(query, str) or not 8 <= len(query.strip()) <= 500 or not query.isprintable() for query in queries)):
            raise ValueError("Research acquisition requires bounded substantive printable queries")
        queries = [query.strip() for query in queries]
        identities = [" ".join(query.casefold().split()) for query in queries]
        if len(set(identities)) != len(identities):
            raise ValueError("Research acquisition cannot repeat equivalent queries")
        development = state["research_development"]
        entries = development.setdefault("acquisitions", [])
        number = 1 if followup_queries is None else 2
        existing = next((entry for entry in entries if entry["number"] == number), None)
        if existing is not None:
            original = engine._read(ws, record, existing["intent_artifact_id"])
            if existing["queries"] != queries or original["agenda"] != agenda.model_dump(mode="json"):
                raise ValueError("A retained acquisition must preserve its original exact queries")
            if existing["status"] == "reserved":
                existing.update(status="interrupted", error="Preserved interrupted native acquisition; no network request was repeated.")
                self._improvement_save(ws, record, state)
            return existing
        if number == 2:
            if not entries or entries[0]["status"] == "reserved":
                raise ValueError("Strengthening requires a completed initial acquisition")
            initial = engine._read(ws, record, entries[0]["intent_artifact_id"])
            if initial["agenda"] != agenda.model_dump(mode="json"):
                raise ValueError("Strengthening must preserve the exact original research agenda")
            consumed_queries = {" ".join(query.casefold().split()) for entry in entries for query in entry["queries"]}
            if set(identities) & consumed_queries:
                raise ValueError("A bounded strengthening pool requires genuinely changed queries")
        if len(entries) >= 2:
            raise ValueError("This research round has exhausted its initial and strengthening acquisitions")
        previous, excluded, excluded_urls = self._research_acquisition_inventory(ws, record, state)
        consumed = sum(entry.get("pdf_reservations_consumed", 0) for entry in entries)
        if not 0 <= consumed <= 2:
            raise ValueError("Research acquisition must preserve its shared two-PDF budget")
        prefix = self._development_prefix(state) + "-research-collection-" + str(number)
        root = ws.path(self._development_root(state) + "/research-acquisition/collection-" + str(number))
        intent = {"number": number, "queries": queries, "agenda": agenda.model_dump(mode="json"),
            "remaining_pdf_reservations": 2 - consumed, "excluded_identities": excluded,
            "excluded_urls": excluded_urls, "at": now(), "workflow_redispatch_limit": 0,
            "scope": "One bounded native literature acquisition; no model reservation, project execution or original count reset."}
        self._portfolio_append(ws, record, prefix + "-intent", root / "intent.json", intent)
        entry = {"number": number, "queries": queries, "intent_artifact_id": prefix + "-intent", "status": "reserved",
                 "packet_artifact_id": None, "sources": [], "outcomes": [], "pdf_reservations_consumed": 2 - consumed}
        entries.append(entry)
        self._improvement_save(ws, record, state)
        packet, error = {"sources": [], "searches": [], "pdf_reservations": [], "warnings": []}, None
        try:
            packet = self.collector(queries, root, limit=6, cancel=lambda: False, pdf_candidates=None,
                pdf_reservation_limit=2 - consumed, excluded_identities=excluded, excluded_urls=excluded_urls)
        except Exception as failure:
            error = type(failure).__name__ + ": " + str(failure)[:1000]
        finally:
            engine._freeze_literature_files(ws, record, root, {"intent.json"})
        self._portfolio_append(ws, record, prefix + "-raw-result", root / "raw-result.json", packet)
        try:
            if not isinstance(packet, dict) or not isinstance(packet.get("sources"), list) or len(packet["sources"]) > 6:
                raise ValueError("The native collector must return at most six actual literature records")
            if any(not isinstance(source, dict) for source in packet["sources"]):
                raise ValueError("Actual literature records must be native source objects")
            relocated = self._research_relocate(ws, record, root, packet)
            reservations = relocated.get("pdf_reservations", [])
            if (not isinstance(reservations, list) or len(reservations) > 2 - consumed or
                    any(item.get("pdf_attempted") is not True for item in reservations)):
                raise ValueError("The collector exceeded its actual shared PDF reservations")
            cards, outcomes = self._research_make_cards(ws, record, state, relocated, number, previous)
            incomplete = bool(error) or any(relocated.get(flag) for flag in ("cancelled", "timed_out", "rate_limited"))
            attempted = {item.get("query") for item in relocated.get("searches", []) if item.get("attempted")}
            incomplete = incomplete or bool(set(queries) - attempted)
            status = "partial" if incomplete else "completed"
        except (KeyError, TypeError, ValueError) as failure:
            relocated, cards, outcomes, status = {}, [], [], "failed"
            error = error or type(failure).__name__ + ": " + str(failure)[:1000]
            # Unavailable outcomes do not replenish an uncertain PDF reservation.
            reservations = packet.get("pdf_reservations", []) if isinstance(packet, dict) else []
        entry.update(status=status, sources=cards, outcomes=outcomes,
            pdf_reservations_consumed=(2 - consumed if error else min(2 - consumed, len(reservations))) if isinstance(reservations, list) else 2 - consumed,
            packet_artifact_id=prefix + "-packet", raw_result_artifact_id=prefix + "-raw-result")
        if error:
            entry["error"] = error
        self._portfolio_append(ws, record, prefix + "-packet", root / "collection.json", {
            "value": relocated, "sources": cards, "outcomes": outcomes, "status": status,
            "intent_sha256": record.artifacts[prefix + "-intent"].sha256,
            "raw_result_sha256": record.artifacts[prefix + "-raw-result"].sha256,
            "error": error})
        self._improvement_save(ws, record, state)
        return entry

    @staticmethod
    def _research_relocate(ws, record, root, packet):
        """Rewrite owned relative paths after immutable raw-file registration."""
        from .. import workflow as engine
        result = deepcopy(packet)
        fields = (("raw_path", "sha256"), ("metadata_path", "metadata_sha256"),
                  ("text_path", "text_sha256"), ("discovery_path", "discovery_sha256"),
                  ("identity_path", "identity_sha256"))

        def visit(value):
            if isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                for field, digest in fields:
                    if not value.get(field):
                        continue
                    original = safe_relative(root, value[field])
                    path = original.relative_to(ws.root).as_posix()
                    matches = [key for key, frozen in record.artifacts.items() if frozen.path == path and frozen.sha256 == value.get(digest)]
                    if len(matches) != 1:
                        raise ValueError("Research collection paths require exact frozen original bytes")
                    engine._artifact(ws, record, matches[0])
                    value[field] = original.relative_to(ws.path("research")).as_posix()
                for item in value.values():
                    visit(item)
        visit(result)
        return result

    def _research_acquisition_cards(self, ws, record, state):
        """Reverify whole bodies and immutable acquisition receipts before use."""
        from .. import workflow as engine
        cards = []
        for entry in (state.get("research_development") or {}).get("acquisitions", []):
            if not entry.get("packet_artifact_id"):
                continue
            packet = engine._read(ws, record, entry["packet_artifact_id"])
            if packet["sources"] != entry["sources"] or packet["status"] != entry["status"]:
                raise ValueError("Acquired research cards must match their original immutable collection")
            if record.artifacts[entry["intent_artifact_id"]].sha256 != packet["intent_sha256"] or record.artifacts[entry["raw_result_artifact_id"]].sha256 != packet["raw_result_sha256"]:
                raise ValueError("Acquisition receipts differ from their original intent or raw collector result")
            engine._read(ws, record, entry["intent_artifact_id"])
            engine._read(ws, record, entry["raw_result_artifact_id"])
            sources = {source["id"]: source for source in packet["value"].get("sources", [])}
            for card in entry["sources"]:
                source = sources.get(card["collected_source_id"])
                if not source or not engine._retained_primary_body(ws, record, source, packet["value"]):
                    raise ValueError("A research card requires its complete native-verified original body")
                if card["raw_sha256"] != source["sha256"] or card["text_sha256"] != source["text_sha256"]:
                    raise ValueError("A research card differs from its exact acquired bytes")
                for field, digest in (("raw_artifact_id", "raw_sha256"), ("text_artifact_id", "text_sha256")):
                    artifact = engine._artifact(ws, record, card[field])
                    if hashlib.sha256(artifact.read_bytes()).hexdigest() != card[digest]:
                        raise ValueError("An acquired research body changed before use")
                cards.append(deepcopy(card))
        return cards
