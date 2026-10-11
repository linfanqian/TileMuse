from app import explainer
from app.explainer import FALLBACK_TEMPLATE, explain
from app.models import Violation


def test_uses_template_for_code(monkeypatch):
    monkeypatch.setitem(explainer.TEMPLATES, "blocked", "Cell ({x}, {y}) blocks {what}.")
    [out] = explain([Violation(code="blocked", x=1, y=2, details={"what": "the door"})])
    assert out.code == "blocked"
    assert out.text == "Cell (1, 2) blocks the door."


def test_unknown_code_uses_fallback_without_dropping_it():
    [out] = explain([Violation(code="no_template_yet")])
    assert out.text == FALLBACK_TEMPLATE.format(code="no_template_yet")
