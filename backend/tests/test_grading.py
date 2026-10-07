from dataclasses import dataclass
import pytest
from backend.app.grading import grade_quiz


@dataclass
class DummyQuestion:
    id: str
    correct_index: int


def test_grade_quiz_all_correct():
    questions = [
        DummyQuestion(id="q1", correct_index=0),
        DummyQuestion(id="q2", correct_index=2),
        DummyQuestion(id="q3", correct_index=1),
    ]
    answers = {"q1": 0, "q2": 2, "q3": 1}
    score, total, percent = grade_quiz(questions, answers)
    assert score == 3
    assert total == 3
    assert percent == 100


def test_grade_quiz_partial():
    questions = [
        DummyQuestion(id="q1", correct_index=0),
        DummyQuestion(id="q2", correct_index=1),
        DummyQuestion(id="q3", correct_index=2),
    ]
    # 2 out of 3 = 66.666% -> rounded to 67%
    answers = {"q1": 0, "q2": 1, "q3": 0}
    score, total, percent = grade_quiz(questions, answers)
    assert score == 2
    assert total == 3
    assert percent == 67

    # 1 out of 3 = 33.333% -> rounded to 33%
    answers2 = {"q1": 0, "q2": 0, "q3": 0}
    score2, total2, percent2 = grade_quiz(questions, answers2)
    assert score2 == 1
    assert total2 == 3
    assert percent2 == 33


def test_grade_quiz_zero_score():
    questions = [
        DummyQuestion(id="q1", correct_index=1),
        DummyQuestion(id="q2", correct_index=1),
    ]
    answers = {"q1": 0, "q2": 0}
    score, total, percent = grade_quiz(questions, answers)
    assert score == 0
    assert total == 2
    assert percent == 0


def test_grade_quiz_missing_answers_raises_error():
    questions = [
        DummyQuestion(id="q1", correct_index=1),
        DummyQuestion(id="q2", correct_index=2),
    ]
    answers = {"q1": 1}  # Missing q2
    with pytest.raises(ValueError, match="Missing answers"):
        grade_quiz(questions, answers)


def test_grade_quiz_empty_questions():
    score, total, percent = grade_quiz([], {})
    assert (score, total, percent) == (0, 0, 0)
