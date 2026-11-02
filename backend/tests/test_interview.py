import asyncio
from typing import get_args

import anthropic
import pytest

from app.interview import (
    INTERVIEW_SYSTEM,
    MAX_MESSAGE,
    SYSTEM,
    ChatMessage,
    InterviewResult,
    Question,
    _Turn,
    idea_to_spec,
    interview,
)
from app.llm import LLMError, TextDelta
from app.spec import MapSpec, SpecDraft, SpecField


def test_idea_to_spec_returns_spec_from_llm(fake_llm, make_spec):
    spec = make_spec(
        theme="abandoned library",
        mood="creepy",
        objects=[{"kind": "player_spawn", "count": 1}, {"kind": "guard", "count": 2}],
        rules=[{"type": "min_distance", "a": "guard", "b": "player_spawn", "tiles": 5}],
    )
    fake_llm.reply(spec.model_dump_json())
    idea = "a creepy abandoned library where the player sneaks past guards"
    assert asyncio.run(idea_to_spec(idea)) == spec
    (request,) = fake_llm.requests
    assert request["messages"] == [{"role": "user", "content": idea}]
    assert request["output_config"]["format"]["schema"] == anthropic.transform_schema(MapSpec)


def test_prompt_names_the_rule_tags():
    # The schema requires the tag too; stating it saves a retry when Claude leaves it out.
    for tag in ('"type": "max_density"', '"type": "min_distance"'):
        assert tag in SYSTEM


IDEA = [ChatMessage(role="user", content="a creepy library where the player sneaks past guards")]
QUESTION = {
    "field": "width",
    "reason": "Room size sets how much space there is to sneak.",
    "suggestions": ["Small (12x10)", "Medium (20x14)", "Large (32x24)"],
}


EMPTY = SpecDraft().model_dump()


def run_interview(messages=IDEA, draft=None):
    async def collect():
        return [event async for event in interview(messages, draft or SpecDraft())]

    return asyncio.run(collect())


def test_interview_streams_question_then_result(fake_llm):
    draft = SpecDraft(theme="abandoned library", mood="creepy").model_dump()
    fake_llm.reply("How big should the room be?", submit={"draft": draft, "question": QUESTION})
    *text, result = run_interview()
    assert text == [TextDelta("How big should the room be?")]
    assert result == InterviewResult(
        message="How big should the room be?",
        question=Question.model_validate(QUESTION),
        draft=SpecDraft.model_validate(draft),
        spec=None,
    )


def test_interview_returns_spec_once_draft_is_complete(fake_llm, make_spec):
    spec = make_spec(objects=[{"kind": "player_spawn", "count": 1}])
    fake_llm.reply("The spec is ready.", submit={"draft": spec.model_dump(), "question": None})
    *_, result = run_interview()
    assert result.spec == spec
    assert result.question is None


def test_interview_sends_history_and_draft(fake_llm):
    draft = SpecDraft(theme="abandoned library")
    messages = [
        *IDEA,
        ChatMessage(role="assistant", content="What mood?"),
        ChatMessage(role="user", content="creepy"),
    ]
    fake_llm.reply("How big?", submit={"draft": draft.model_dump(), "question": QUESTION})
    run_interview(messages, draft)
    (request,) = fake_llm.requests
    assert request["messages"] == [m.model_dump() for m in messages]
    assert request["system"].startswith(INTERVIEW_SYSTEM)
    assert draft.model_dump_json() in request["system"]
    (tool,) = request["tools"]
    assert tool["input_schema"] == anthropic.transform_schema(_Turn)


def test_interview_retries_a_finish_with_missing_fields(fake_llm):
    draft = SpecDraft(theme="library").model_dump()
    fake_llm.reply("All done!", submit={"draft": draft, "question": None})
    fake_llm.reply("How big should the room be?", submit={"draft": draft, "question": QUESTION})
    *text, result = run_interview()
    assert text == [TextDelta("All done!")]
    # The retry's message replaces the streamed one, which no longer fits the question.
    assert result.message == "How big should the room be?"
    assert result.question == Question.model_validate(QUESTION)
    feedback = fake_llm.requests[1]["messages"][-1]["content"][0]["content"]
    assert "missing: mood, width, height, doors, objects, rules" in feedback


def test_interview_retries_a_complete_draft_that_does_not_fit(fake_llm, make_spec):
    spec = make_spec(width=4, height=4)
    crowded = {**spec.model_dump(), "objects": [{"kind": "chest", "count": 5}]}
    fake_llm.reply("Ready.", submit={"draft": crowded, "question": None})
    fake_llm.reply(submit={"draft": spec.model_dump(), "question": None})
    *_, result = run_interview()
    assert result.spec == spec
    feedback = fake_llm.requests[1]["messages"][-1]["content"][0]["content"]
    assert "don't fit together" in feedback


def test_interview_rejects_a_question_without_enough_suggestions(fake_llm):
    one = {**QUESTION, "suggestions": ["Small"]}
    fake_llm.reply("How big?", submit={"draft": EMPTY, "question": one})
    fake_llm.reply(submit={"draft": EMPTY, "question": QUESTION})
    *_, result = run_interview()
    assert len(result.question.suggestions) == 3


@pytest.mark.parametrize(
    ("question", "message"), [(QUESTION, "What should the width be?"), (None, "The spec is ready.")]
)
def test_interview_falls_back_when_claude_writes_no_message(fake_llm, make_spec, question, message):
    draft = make_spec().model_dump() if question is None else EMPTY
    fake_llm.reply(submit={"draft": draft, "question": question})
    (result,) = run_interview()
    assert result.message == message
    # The message must be valid history for the next turn.
    ChatMessage(role="assistant", content=result.message)


def test_interview_falls_back_when_a_retry_drops_the_stale_message(fake_llm):
    # "All done!" doesn't fit the question the retry adds, and the retry wrote no new message.
    fake_llm.reply("All done!", submit={"draft": EMPTY, "question": None})
    fake_llm.reply(submit={"draft": EMPTY, "question": QUESTION})
    *_, result = run_interview()
    assert result.message == "What should the width be?"


def test_interview_fails_on_a_message_too_long_for_the_next_turn(fake_llm, caplog):
    fake_llm.reply("x" * (MAX_MESSAGE + 1), submit={"draft": EMPTY, "question": QUESTION})
    with pytest.raises(LLMError, match="characters"):
        run_interview()
    assert "over 2000" in caplog.text


def test_interview_retries_a_draft_that_drops_a_field(fake_llm):
    # Claude must restate every field, so one it didn't touch can't silently reset to null.
    draft = SpecDraft(theme="abandoned library", mood="creepy")
    dropped = {"theme": "abandoned library", **dict.fromkeys(["width", "height"], None)}
    fake_llm.reply("How big?", submit={"draft": dropped, "question": QUESTION})
    fake_llm.reply(submit={"draft": draft.model_dump(), "question": QUESTION})
    *_, result = run_interview(draft=draft)
    assert result.draft == draft
    feedback = fake_llm.requests[1]["messages"][-1]["content"][0]["content"]
    assert "mood" in feedback


def test_submitted_draft_schema_requires_every_field(fake_llm):
    fake_llm.reply("How big?", submit={"draft": EMPTY, "question": QUESTION})
    run_interview()
    (tool,) = fake_llm.requests[0]["tools"]
    schema = tool["input_schema"]
    (draft_def,) = [d for name, d in schema["$defs"].items() if "Draft" in name]
    assert draft_def["required"] == list(get_args(SpecField))


def test_interview_strips_the_message(fake_llm):
    fake_llm.reply(" " * MAX_MESSAGE + "How big?\n", submit={"draft": EMPTY, "question": QUESTION})
    *_, result = run_interview()
    assert result.message == "How big?"


def test_interview_keeps_asking_while_the_draft_does_not_fit(fake_llm, make_spec):
    # The user shrank the room; Claude asks how to resolve it instead of failing the turn.
    crowded = {
        **make_spec(width=4, height=4).model_dump(),
        "objects": [{"kind": "chest", "count": 5}],
    }
    question = {**QUESTION, "field": "objects"}
    fake_llm.reply(
        "Five chests don't fit now. Which should go?",
        submit={"draft": crowded, "question": question},
    )
    *_, result = run_interview()
    assert len(fake_llm.requests) == 1
    assert result.spec is None
    assert result.draft.missing() == []
