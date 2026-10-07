from typing import Protocol, Sequence


class QuestionLike(Protocol):
    id: str
    correct_index: int


def grade_quiz(
    questions: Sequence[QuestionLike],
    submitted_answers: dict[str, int],
) -> tuple[int, int, int]:
    """
    Grades a quiz submission against the stored questions.

    Args:
        questions: The stored list of questions with their IDs and correct_index.
        submitted_answers: Map of question_id -> selected_option_index.

    Returns:
        tuple of (score, total, percent), where percent is rounded to the nearest whole number.

    Raises:
        ValueError: If any question is missing from submitted_answers.
    """
    total = len(questions)
    if total == 0:
        return 0, 0, 0

    score = 0
    missing_questions = []

    for q in questions:
        if q.id not in submitted_answers:
            missing_questions.append(q.id)
            continue
        selected_index = submitted_answers[q.id]
        if selected_index == q.correct_index:
            score += 1

    if missing_questions:
        raise ValueError(
            f"Missing answers for {len(missing_questions)} question(s). All questions must be answered."
        )

    percent = round((score / total) * 100)
    return score, total, percent
