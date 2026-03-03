"""Tests for the answer_judge node — parse_judge_response and edge cases."""

import pytest

from agent.nodes.answer_judge import parse_judge_response


# ---------------------------------------------------------------------------
# parse_judge_response tests
# ---------------------------------------------------------------------------


class TestParseJudgeResponse:
    """Tests for extracting score/reasoning from LLM output."""

    def test_valid_json(self):
        raw = '{"score": 0.85, "reasoning": "Covers all parts of the question."}'
        score, reasoning = parse_judge_response(raw)
        assert score == 0.85
        assert "all parts" in reasoning

    def test_json_with_surrounding_text(self):
        raw = 'Here is my assessment:\n{"score": 0.7, "reasoning": "Mostly good."}\nDone.'
        score, reasoning = parse_judge_response(raw)
        assert score == 0.7
        assert reasoning == "Mostly good."

    def test_score_clamped_above_one(self):
        raw = '{"score": 1.5, "reasoning": "Perfect."}'
        score, _ = parse_judge_response(raw)
        assert score == 1.0

    def test_score_clamped_below_zero(self):
        raw = '{"score": -0.3, "reasoning": "Terrible."}'
        score, _ = parse_judge_response(raw)
        assert score == 0.0

    def test_integer_score(self):
        raw = '{"score": 1, "reasoning": "Full marks."}'
        score, _ = parse_judge_response(raw)
        assert score == 1.0

    def test_score_zero(self):
        raw = '{"score": 0.0, "reasoning": "Completely irrelevant."}'
        score, _ = parse_judge_response(raw)
        assert score == 0.0

    def test_missing_reasoning_key(self):
        raw = '{"score": 0.6}'
        score, reasoning = parse_judge_response(raw)
        assert score == 0.6
        assert reasoning == ""

    def test_bare_number_fallback(self):
        raw = "I would rate this 0.75 out of 1."
        score, reasoning = parse_judge_response(raw)
        assert score == 0.75
        assert "unstructured" in reasoning

    def test_completely_unparseable(self):
        raw = "This answer is great!"
        score, reasoning = parse_judge_response(raw)
        assert score == 0.5
        assert "defaulting" in reasoning

    def test_empty_string(self):
        score, reasoning = parse_judge_response("")
        assert score == 0.5
        assert "defaulting" in reasoning

    def test_json_with_extra_whitespace(self):
        raw = '  \n  {"score": 0.9, "reasoning": "Good answer."}\n  '
        score, reasoning = parse_judge_response(raw)
        assert score == 0.9

    def test_malformed_json_with_valid_number(self):
        raw = '{"score": 0.8, reasoning: broken}'
        score, reasoning = parse_judge_response(raw)
        assert score == 0.8
        assert "unstructured" in reasoning

    def test_score_boundary_zero_point_zero(self):
        raw = '{"score": 0, "reasoning": "No relevance."}'
        score, _ = parse_judge_response(raw)
        assert score == 0.0

    def test_json_in_code_block(self):
        raw = '```json\n{"score": 0.92, "reasoning": "Excellent coverage."}\n```'
        score, reasoning = parse_judge_response(raw)
        assert score == 0.92
        assert "Excellent" in reasoning
