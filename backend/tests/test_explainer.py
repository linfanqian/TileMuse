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


def test_template_with_missing_placeholder_uses_fallback(monkeypatch):
    monkeypatch.setitem(explainer.TEMPLATES, "needs_what", "Missing {what}.")
    [out] = explain([Violation(code="needs_what")])
    assert out.code == "needs_what"
    assert out.text == FALLBACK_TEMPLATE.format(code="needs_what")


def test_template_that_cannot_format_its_values_uses_fallback(monkeypatch):
    monkeypatch.setitem(explainer.TEMPLATES, "typed", "At {x:d}.")
    [out] = explain([Violation(code="typed")])  # x is None, so {x:d} raises TypeError
    assert out.text == FALLBACK_TEMPLATE.format(code="typed")


def test_fallback_for_broken_template_logs_a_warning(monkeypatch, caplog):
    monkeypatch.setitem(explainer.TEMPLATES, "typo", "Missing {wat}.")
    explain([Violation(code="typo")])
    assert "typo" in caplog.text
