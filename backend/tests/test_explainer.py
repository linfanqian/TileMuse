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


def test_details_with_x_or_y_keys_do_not_crash(monkeypatch):
    monkeypatch.setitem(explainer.TEMPLATES, "at", "At ({x}, {y}).")
    [out] = explain([Violation(code="at", x=3, y=4, details={"x": 9, "y": 9})])
    assert out.text == "At (3, 4)."
