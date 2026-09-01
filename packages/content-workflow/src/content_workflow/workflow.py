"""Pausable/resumable LangGraph Content Workflow (ADR-002: single runtime).

Graph: ValidateInput -> RetrieveProductFacts -> BuildBrief -> GenerateCopy
-> GenerateMedia -> ComplianceCheck -> HumanReview -> PackageApproved.

Trust skeleton (Phase 02 / Subphase 03, fake model/media/reviewer only):

* every node consumes/produces versioned contracts and appends a journal
  entry (hashes, workflow version);
* HumanReview pauses via ``interrupt`` and resumes with a typed
  ``ReviewDecisionV1`` — a worker restart resumes from the checkpoint;
* rejection routes rework to the responsible node only
  (``fact_issue``/``copy_issue``/``asset_issue``) and invalidates only the
  affected downstream artifacts;
* uncited claims and hard-rule violations block before human review;
* DRAFT (unapproved) skills allow the run to end as ``DRAFT`` but never as
  an approved package.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, ConfigDict, ValidationError

from content_workflow.contracts import (
    CONTENT_WORKFLOW_VERSION,
    ApprovedPackageV1,
    ComplianceReportV1,
    ComplianceViolationV1,
    ContentBriefV1,
    CopyDraftV1,
    FactBundleV1,
    MediaAssetV1,
    RetrievedFactV1,
    ReviewDecisionV1,
    ReworkTarget,
    WorkflowRequestV1,
    model_hash,
)
from content_workflow.errors import (
    InvalidNodeOutputError,
    WorkflowCancelledError,
    WorkflowStateError,
)
from content_workflow.fakes import ContentModel, MediaGenerator
from content_workflow.journal import JournalEntryV1, text_hash
from content_workflow.skills import SkillRegistry
from product_rag.index import RetrievalFilters
from product_rag.retrieval import Retriever

WorkflowStatus = Literal[
    "RUNNING",
    "AWAITING_REVIEW",
    "REWORK",
    "APPROVED_PACKAGED",
    "DRAFT",
    "REJECTED",
    "BLOCKED",
    "CANCELLED",
]

DEFAULT_RETRIEVAL_K = 5
DEFAULT_MAX_REWORK = 3


class WorkflowState(TypedDict, total=False):
    request: WorkflowRequestV1
    facts: FactBundleV1 | None
    brief: ContentBriefV1 | None
    copy_draft: CopyDraftV1 | None
    media: tuple[MediaAssetV1, ...] | None
    compliance: ComplianceReportV1 | None
    review: ReviewDecisionV1 | None
    package: ApprovedPackageV1 | None
    status: WorkflowStatus
    status_reason: str
    rework_count: int
    skills_approved: bool
    skill_versions: tuple[tuple[str, str], ...]
    journal: Annotated[list[JournalEntryV1], operator.add]


class WorkflowSnapshot(BaseModel):
    """Read model of one workflow run for callers (API wiring comes later)."""

    model_config = ConfigDict(extra="forbid", strict=False, frozen=True)

    thread_id: str
    workflow_version: str
    status: WorkflowStatus
    status_reason: str
    request: WorkflowRequestV1
    facts: FactBundleV1 | None
    brief: ContentBriefV1 | None
    copy_draft: CopyDraftV1 | None
    media: tuple[MediaAssetV1, ...] | None
    compliance: ComplianceReportV1 | None
    review: ReviewDecisionV1 | None
    package: ApprovedPackageV1 | None
    rework_count: int
    skill_versions: tuple[tuple[str, str], ...]
    journal: tuple[JournalEntryV1, ...]


def _entry(
    node: Any, input_hash: str, output_hash: str, detail: str
) -> list[JournalEntryV1]:
    return [
        JournalEntryV1(
            node=node,
            workflow_version=CONTENT_WORKFLOW_VERSION,
            input_hash=input_hash,
            output_hash=output_hash,
            detail=detail,
        )
    ]


class ContentWorkflow:
    """Owns the compiled graph plus its checkpointer.

    A new instance over the same checkpointer (worker restart) resumes any
    thread from its last checkpoint.
    """

    def __init__(
        self,
        *,
        skills: SkillRegistry,
        retriever: Retriever,
        model: ContentModel,
        media_generator: MediaGenerator,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
        retrieval_k: int = DEFAULT_RETRIEVAL_K,
        max_rework: int = DEFAULT_MAX_REWORK,
    ) -> None:
        self._skills = skills
        self._retriever = retriever
        self._model = model
        self._media = media_generator
        self._retrieval_k = retrieval_k
        self._max_rework = max_rework
        self.checkpointer: BaseCheckpointSaver[Any] = (
            checkpointer if checkpointer is not None else InMemorySaver()
        )
        self._graph = self._build().compile(checkpointer=self.checkpointer)

    # ------------------------------------------------------------------ API

    def start(self, request: WorkflowRequestV1, *, thread_id: str) -> WorkflowSnapshot:
        state = self._graph.get_state(self._config(thread_id))
        if state.values:
            raise WorkflowStateError(f"thread {thread_id!r} already started")
        initial: WorkflowState = {
            "request": request,
            "status": "RUNNING",
            "status_reason": "started",
            "rework_count": 0,
            "journal": [],
        }
        self._graph.invoke(initial, self._config(thread_id))
        return self.snapshot(thread_id)

    def resume(
        self, thread_id: str, decision: ReviewDecisionV1
    ) -> WorkflowSnapshot:
        state = self._graph.get_state(self._config(thread_id))
        if not state.values:
            raise WorkflowStateError(f"thread {thread_id!r} was never started")
        if state.values.get("status") == "CANCELLED":
            raise WorkflowCancelledError(
                f"thread {thread_id!r} is cancelled and cannot be resumed"
            )
        if not state.interrupts:
            raise WorkflowStateError(
                f"thread {thread_id!r} is not awaiting human review"
            )
        resume_command: Command[Any] = Command(resume=decision.model_dump())
        self._graph.invoke(resume_command, self._config(thread_id))
        return self.snapshot(thread_id)

    def cancel(self, thread_id: str) -> WorkflowSnapshot:
        state = self._graph.get_state(self._config(thread_id))
        if not state.values:
            raise WorkflowStateError(f"thread {thread_id!r} was never started")
        if not state.next and not state.interrupts:
            raise WorkflowStateError(f"thread {thread_id!r} already finished")
        self._graph.update_state(
            self._config(thread_id),
            {"status": "CANCELLED", "status_reason": "cancelled_by_operator"},
        )
        return self.snapshot(thread_id)

    def snapshot(self, thread_id: str) -> WorkflowSnapshot:
        state = self._graph.get_state(self._config(thread_id))
        if not state.values:
            raise WorkflowStateError(f"thread {thread_id!r} was never started")
        values = state.values
        status: WorkflowStatus = values.get("status", "RUNNING")
        if state.interrupts and status not in ("CANCELLED",):
            status = "AWAITING_REVIEW"
        return WorkflowSnapshot(
            thread_id=thread_id,
            workflow_version=CONTENT_WORKFLOW_VERSION,
            status=status,
            status_reason=values.get("status_reason", ""),
            request=values["request"],
            facts=values.get("facts"),
            brief=values.get("brief"),
            copy_draft=values.get("copy_draft"),
            media=values.get("media"),
            compliance=values.get("compliance"),
            review=values.get("review"),
            package=values.get("package"),
            rework_count=values.get("rework_count", 0),
            skill_versions=values.get("skill_versions", ()),
            journal=tuple(values.get("journal", [])),
        )

    @staticmethod
    def _config(thread_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": thread_id}}

    # ---------------------------------------------------------------- graph

    def _build(self) -> StateGraph[WorkflowState, Any, WorkflowState, WorkflowState]:
        graph: StateGraph[WorkflowState, Any, WorkflowState, WorkflowState] = (
            StateGraph(WorkflowState)
        )
        graph.add_node("validate_input", self._validate_input)
        graph.add_node("retrieve_product_facts", self._retrieve_product_facts)
        graph.add_node("build_brief", self._build_brief)
        graph.add_node("generate_copy", self._generate_copy)
        graph.add_node("generate_media", self._generate_media)
        graph.add_node("compliance_check", self._compliance_check)
        graph.add_node("human_review", self._human_review)
        graph.add_node("package_approved", self._package_approved)

        graph.add_edge(START, "validate_input")
        graph.add_edge("validate_input", "retrieve_product_facts")
        graph.add_conditional_edges(
            "retrieve_product_facts",
            self._route_after_facts,
            {"build_brief": "build_brief", "blocked": END},
        )
        graph.add_edge("build_brief", "generate_copy")
        graph.add_conditional_edges(
            "generate_copy",
            self._route_after_copy,
            {
                "generate_media": "generate_media",
                "compliance_check": "compliance_check",
            },
        )
        graph.add_edge("generate_media", "compliance_check")
        graph.add_conditional_edges(
            "compliance_check",
            self._route_after_compliance,
            {"human_review": "human_review", "blocked": END},
        )
        graph.add_conditional_edges(
            "human_review",
            self._route_after_review,
            {
                "package_approved": "package_approved",
                "fact_issue": "retrieve_product_facts",
                "copy_issue": "generate_copy",
                "asset_issue": "generate_media",
                "rejected": END,
            },
        )
        graph.add_edge("package_approved", END)
        return graph

    # ---------------------------------------------------------------- nodes

    def _validate_input(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        request_hash = model_hash(request)
        return {
            "status": "RUNNING",
            "status_reason": "input_validated",
            "journal": _entry(
                "validate_input", request_hash, request_hash, "request accepted"
            ),
        }

    def _retrieve_product_facts(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        query = f"{request.objective} {' '.join(request.target_audience)}"
        facts: list[RetrievedFactV1] = []
        index_version = ""
        for product_id in request.product_ids:
            filters = RetrievalFilters(
                tenant=request.tenant,
                product_id=product_id,
                market=request.market,
                locale=request.locale,
                as_of=request.as_of,
            )
            for passage in self._retriever.retrieve(
                query, filters, k=self._retrieval_k
            ):
                index_version = passage.index_version
                facts.append(
                    RetrievedFactV1(
                        text=passage.text,
                        score=passage.score,
                        citation=passage.citation,
                    )
                )
        bundle = FactBundleV1(
            request_id=request.request_id,
            index_version=index_version,
            facts=tuple(facts),
        )
        update: WorkflowState = {
            "facts": bundle,
            "journal": _entry(
                "retrieve_product_facts",
                model_hash(request),
                model_hash(bundle),
                f"{len(facts)} facts, index {index_version or 'n/a'}",
            ),
        }
        if not facts:
            update["status"] = "BLOCKED"
            update["status_reason"] = "no_approved_facts"
        return update

    def _route_after_facts(self, state: WorkflowState) -> str:
        return "blocked" if state.get("status") == "BLOCKED" else "build_brief"

    def _build_brief(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        facts = state.get("facts")
        assert facts is not None
        skill_set = self._skills.load(
            agent="content",
            tenant=request.tenant,
            market=request.market,
            locale=request.locale,
            channel=request.channel,
            as_of=request.as_of,
        )
        brief = ContentBriefV1(
            request_id=request.request_id,
            tenant=request.tenant,
            market=request.market,
            locale=request.locale,
            channel=request.channel,
            objective=request.objective,
            target_audience=request.target_audience,
            tone=skill_set.brand.tone or "professional",
            facts=facts.facts,
            banned_phrases=skill_set.medical.banned_phrases
            + skill_set.market.banned_phrases,
            required_disclosures=skill_set.medical.required_disclosures
            + skill_set.market.required_disclosures,
            max_headline_chars=skill_set.channel.max_headline_chars or 150,
            skill_versions=tuple(sorted(skill_set.versions.items())),
        )
        return {
            "brief": brief,
            "skills_approved": skill_set.all_approved,
            "skill_versions": brief.skill_versions,
            "status_reason": "brief_built",
            "journal": _entry(
                "build_brief",
                model_hash(facts),
                model_hash(brief),
                f"skills {dict(brief.skill_versions)}",
            ),
        }

    def _generate_copy(self, state: WorkflowState) -> WorkflowState:
        brief = state.get("brief")
        assert brief is not None
        draft = self._model.generate_copy(brief)
        if not isinstance(draft, CopyDraftV1):  # pragma: no cover - defense
            raise InvalidNodeOutputError("model returned a non-CopyDraftV1 object")
        if draft.request_id != brief.request_id or draft.channel != brief.channel:
            raise InvalidNodeOutputError(
                "model output does not match the brief request/channel"
            )
        return {
            "copy_draft": draft,
            "status_reason": "copy_generated",
            "journal": _entry(
                "generate_copy",
                model_hash(brief),
                model_hash(draft),
                f"{len(draft.claims)} claims by {draft.model_id}",
            ),
        }

    def _route_after_copy(self, state: WorkflowState) -> str:
        # copy_issue 返工保留原有媒体资产，仅失效相关下游。
        return "compliance_check" if state.get("media") else "generate_media"

    def _generate_media(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        brief = state.get("brief")
        assert brief is not None
        attempt = state.get("rework_count", 0)
        assets = tuple(
            self._media.generate_media(brief, media_type, attempt=attempt)
            for media_type in request.requested_media_types
        )
        output_hash = text_hash("|".join(asset.sha256 for asset in assets))
        return {
            "media": assets,
            "status_reason": "media_generated",
            "journal": _entry(
                "generate_media",
                model_hash(brief),
                output_hash,
                f"{len(assets)} assets by {self._media.generator_id}",
            ),
        }

    def _compliance_check(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        brief = state.get("brief")
        draft = state.get("copy_draft")
        assert brief is not None and draft is not None
        media = state.get("media") or ()
        violations: list[ComplianceViolationV1] = []
        uncited: list[str] = []
        checked = (
            "claims_present",
            "claim_citation_required",
            "citation_grounded_in_facts",
            "banned_phrase",
            "disclosure_required",
            "headline_max_chars",
            "media_present",
        )
        grounded_citations = {
            self._citation_key(fact.citation) for fact in brief.facts
        }
        if not draft.claims:
            violations.append(
                ComplianceViolationV1(
                    rule="claims_present", detail="draft contains no claims"
                )
            )
        for claim in draft.claims:
            if claim.citation is None:
                uncited.append(claim.text)
                violations.append(
                    ComplianceViolationV1(
                        rule="claim_citation_required",
                        detail=f"uncited claim: {claim.text[:120]}",
                    )
                )
            elif self._citation_key(claim.citation) not in grounded_citations:
                violations.append(
                    ComplianceViolationV1(
                        rule="R-CITE-011",
                        detail=(
                            "claim citation is not grounded in retrieved facts: "
                            f"{claim.citation.source_id}@{claim.citation.source_version}"
                        ),
                    )
                )
        searchable = self._searchable_text(draft, media)
        for phrase in brief.banned_phrases:
            if phrase.lower() in searchable:
                violations.append(
                    ComplianceViolationV1(
                        rule="banned_phrase", detail=f"banned phrase: {phrase}"
                    )
                )
        for disclosure in brief.required_disclosures:
            if disclosure not in draft.disclosures and disclosure not in draft.body:
                violations.append(
                    ComplianceViolationV1(
                        rule="disclosure_required",
                        detail=f"missing disclosure: {disclosure}",
                    )
                )
        if len(draft.headline) > brief.max_headline_chars:
            violations.append(
                ComplianceViolationV1(
                    rule="headline_max_chars",
                    detail=(
                        f"headline {len(draft.headline)} chars exceeds "
                        f"{brief.max_headline_chars}"
                    ),
                )
            )
        produced_types = {asset.media_type for asset in media}
        for media_type in request.requested_media_types:
            if media_type not in produced_types:
                violations.append(
                    ComplianceViolationV1(
                        rule="media_present",
                        detail=f"missing media asset: {media_type}",
                    )
                )
        report = ComplianceReportV1(
            request_id=request.request_id,
            passed=not violations,
            violations=tuple(violations),
            uncited_claims=tuple(uncited),
            checked_rules=checked,
        )
        update: WorkflowState = {
            "compliance": report,
            "journal": _entry(
                "compliance_check",
                model_hash(draft),
                model_hash(report),
                f"passed={report.passed} violations={len(violations)}",
            ),
        }
        if report.passed:
            update["status_reason"] = "compliance_passed"
        else:
            update["status"] = "BLOCKED"
            update["status_reason"] = "compliance_failed"
        return update

    @staticmethod
    def _citation_key(citation: object) -> tuple[str, str, str, str]:
        return (
            str(getattr(citation, "source_id")),
            str(getattr(citation, "source_version")),
            str(getattr(citation, "source_content_hash")),
            str(getattr(citation, "chunk_hash")),
        )

    @staticmethod
    def _searchable_text(
        draft: CopyDraftV1, media: tuple[MediaAssetV1, ...]
    ) -> str:
        parts = [draft.headline, draft.body]
        parts.extend(draft.disclosures)
        parts.extend(claim.text for claim in draft.claims)
        parts.extend(asset.alt_text for asset in media)
        return "\n".join(parts).lower()

    def _route_after_compliance(self, state: WorkflowState) -> str:
        report = state.get("compliance")
        return "human_review" if report is not None and report.passed else "blocked"

    def _human_review(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        draft = state.get("copy_draft")
        report = state.get("compliance")
        assert draft is not None and report is not None
        payload = interrupt(
            {
                "request_id": request.request_id,
                "copy_hash": model_hash(draft),
                "compliance_hash": model_hash(report),
                "workflow_version": CONTENT_WORKFLOW_VERSION,
            }
        )
        try:
            decision = ReviewDecisionV1.model_validate(payload)
        except ValidationError as exc:
            raise InvalidNodeOutputError(
                f"review decision violates ReviewDecisionV1: {exc}"
            ) from exc
        if decision.request_id != request.request_id:
            raise InvalidNodeOutputError(
                "review decision request_id does not match this run"
            )
        update: WorkflowState = {
            "review": decision,
            "journal": _entry(
                "human_review",
                model_hash(draft),
                model_hash(decision),
                f"{decision.outcome} target={decision.rework_target}",
            ),
        }
        if decision.outcome == "approved":
            update["status"] = "RUNNING"
            update["status_reason"] = "review_approved"
            return update
        if decision.rework_target is None:
            update["status"] = "REJECTED"
            update["status_reason"] = "review_rejected"
            return update
        next_rework_count = state.get("rework_count", 0) + 1
        if next_rework_count > self._max_rework:
            update["status"] = "REJECTED"
            update["status_reason"] = "max_rework_exceeded"
            return update
        update["status"] = "REWORK"
        update["status_reason"] = f"rework_{decision.rework_target}"
        update["rework_count"] = next_rework_count
        update["compliance"] = None
        invalidated: dict[ReworkTarget, tuple[str, ...]] = {
            "fact_issue": ("facts", "brief", "copy_draft", "media"),
            "copy_issue": ("copy_draft",),
            "asset_issue": ("media",),
        }
        for key in invalidated[decision.rework_target]:
            update[key] = None  # type: ignore[literal-required]
        return update

    def _route_after_review(self, state: WorkflowState) -> str:
        review = state.get("review")
        assert review is not None
        if state.get("status") == "REJECTED":
            return "rejected"
        if review.outcome == "approved":
            return "package_approved"
        if review.rework_target is None:
            return "rejected"
        return review.rework_target

    def _package_approved(self, state: WorkflowState) -> WorkflowState:
        request = state["request"]
        draft = state.get("copy_draft")
        report = state.get("compliance")
        review = state.get("review")
        media = state.get("media") or ()
        assert draft is not None and report is not None and review is not None
        if not state.get("skills_approved", False):
            # Skill 未正式批准：允许产出草稿，禁止 Approved Package。
            return {
                "package": None,
                "status": "DRAFT",
                "status_reason": "skills_not_approved",
                "journal": _entry(
                    "package_approved",
                    model_hash(review),
                    text_hash("draft-only"),
                    "draft only: unapproved skill versions",
                ),
            }
        package = ApprovedPackageV1(
            request_id=request.request_id,
            tenant=request.tenant,
            market=request.market,
            locale=request.locale,
            channel=request.channel,
            copy_hash=model_hash(draft),
            media_hashes=tuple(asset.sha256 for asset in media),
            compliance_report_hash=model_hash(report),
            review_decision_hash=model_hash(review),
            skill_versions=state.get("skill_versions", ()),
            workflow_version=CONTENT_WORKFLOW_VERSION,
        )
        return {
            "package": package,
            "status": "APPROVED_PACKAGED",
            "status_reason": "package_assembled",
            "journal": _entry(
                "package_approved",
                model_hash(review),
                model_hash(package),
                "approved package assembled",
            ),
        }
