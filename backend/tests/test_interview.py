import asyncio

import anthropic

from app.interview import SYSTEM, idea_to_spec
from app.spec import MapSpec


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
    # The structured-output schema doesn't require the tag, so the prompt asks for it.
    for tag in ('"type": "max_density"', '"type": "min_distance"'):
        assert tag in SYSTEM
