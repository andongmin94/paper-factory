import pytest
from pydantic import ValidationError

from paper_factory.models import (
    Paper,
    PaperState,
    Project,
    Study,
    StudyState,
    Submission,
    transition_paper,
    transition_study,
)


STUDY_TRANSITIONS = {
    (StudyState.STUDY_PLANNED, StudyState.NOVELTY_CHECKED),
    (StudyState.STUDY_PLANNED, StudyState.EXPERIMENTS_RUNNING),
    (StudyState.NOVELTY_CHECKED, StudyState.EXPERIMENTS_RUNNING),
    (StudyState.EXPERIMENTS_RUNNING, StudyState.EVIDENCE_READY),
    (StudyState.EVIDENCE_READY, StudyState.EXPERIMENTS_RUNNING),
}

PAPER_TRANSITIONS = {
    (PaperState.MANUSCRIPT_DRAFTED, PaperState.INTEGRITY_CHECKED),
    (PaperState.INTEGRITY_CHECKED, PaperState.AUTHOR_APPROVED),
    (PaperState.INTEGRITY_CHECKED, PaperState.MANUSCRIPT_DRAFTED),
}


@pytest.mark.parametrize("initial", list(StudyState))
@pytest.mark.parametrize("target", list(StudyState))
def test_study_transition_guards(initial, target):
    study = Study(project_id="project-1", title="Study", research_question="Question?", state=initial)
    if (initial, target) in STUDY_TRANSITIONS:
        transition_study(study, target)
        assert study.state is target
    else:
        with pytest.raises(ValueError, match="Invalid study transition"):
            transition_study(study, target)
        assert study.state is initial


@pytest.mark.parametrize("initial", list(PaperState))
@pytest.mark.parametrize("target", list(PaperState))
def test_paper_transition_guards(initial, target):
    paper = Paper(study_id="study-1", title="Paper", state=initial, claim_ids=[], citation_ids=[], manuscript_sha256="abc", document_sha256="def")
    if (initial, target) in PAPER_TRANSITIONS:
        transition_paper(paper, target)
        assert paper.state is target
    else:
        with pytest.raises(ValueError, match="Invalid paper transition"):
            transition_paper(paper, target)
        assert paper.state is initial


def test_project_study_paper_and_submission_have_distinct_identity_boundaries():
    project = Project(name="Project", source="/source", snapshot_digest="snapshot", assets=[])
    study = Study(project_id=project.id, title="Study", research_question="Question?")
    paper = Paper(study_id=study.id, title="Paper", claim_ids=[], citation_ids=[], manuscript_sha256="abc", document_sha256="def")
    submission = Submission(paper_id=paper.id, venue_id="venue-1", policy_id="policy-1", candidate_digest="frozen")
    assert len({project.id, study.id, paper.id, submission.id}) == 4
    assert study.project_id == project.id
    assert paper.study_id == study.id
    assert submission.paper_id == paper.id


def test_unknown_and_invalid_state_values_are_rejected():
    with pytest.raises(ValidationError):
        Study(project_id="p", title="Study", research_question="Question?", state="PUBLISHED")
    with pytest.raises(ValidationError):
        Study(project_id="p", title="Study", research_question="Question?", extra_field=True)
    study = Study(project_id="p", title="Study", research_question="Question?")
    with pytest.raises(ValidationError):
        study.state = "SUBMITTED"
    assert study.state is StudyState.STUDY_PLANNED
