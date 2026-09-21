"""imagespec.validate: spec-driven payload validation with the renderer's tolerance
(template strings, nulls), agreeing with the JSON Schema on what it rejects."""

from __future__ import annotations

import pytest

from imagespec import Issue, RenderContext, RenderError, render, validate
from test_schema_export import ACCEPTS, REJECTS, _previews

# ── real payloads validate ─────────────────────────────────────────────────


@pytest.mark.parametrize("name", sorted(_previews().SAMPLES))
def test_every_preview_payload_validates(name):
    sample = _previews().SAMPLES[name]
    payload = sample if isinstance(sample, list) else [sample]
    assert validate(payload) == []


def test_golden_scene_payloads_validate():
    from test_golden import SCENES

    for name, scene in SCENES.items():
        assert validate(scene["payload"]) == [], name


# ── what is reported, and where ────────────────────────────────────────────


def _paths(payload):
    return [i.path for i in validate(payload)]


def test_unknown_key_typo():
    issues = validate([{"type": "circle", "x": 1, "y": 1, "radius": 3, "fil": "red"}])
    assert issues == [Issue("[0].fil", "unknown key for 'circle'")]
    assert str(issues[0]) == "[0].fil: unknown key for 'circle'"


def test_missing_required_top_level_and_in_group():
    # text's y is optional (flow cursor), so only x is reported
    assert _paths([{"type": "text", "value": "a"}]) == ["[0].x"]
    assert _paths([{"type": "group", "elements": [{"type": "text", "value": "a"}]}]) == ["[0].elements[0].x"]
    assert _paths([{"type": "circle", "radius": 3}]) == ["[0].x", "[0].y"]


def test_stack_children_do_not_need_xy():
    assert validate([{"type": "row", "elements": [{"type": "text", "value": "a"}]}]) == []
    assert validate([{"type": "text", "value": "a"}], positioned=False) == []


def test_unknown_type_and_missing_type():
    assert _paths([{"type": "sprite", "x": 0, "y": 0}]) == ["[0].type"]
    assert _paths([{"x": 0, "y": 0}]) == ["[0].type"]
    assert "sprite" in validate([{"type": "sprite"}])[0].message


def test_wrong_kinds_with_paths():
    payload = [
        {"type": "circle", "x": "left", "y": 1, "radius": 3, "fill": 7, "dither": "foo"},
        {"type": "dlimg", "x": 0, "y": 0, "url": "u", "xsize": 1, "ysize": 1, "mode": "zoom"},
        {"type": "line", "x_start": 0, "x_end": 1, "dash": [4, "x"]},
        {"type": "plot", "data": [{"entity": "s.a", "width": "thick"}], "ylegend": {"nope": 1}},
    ]
    assert _paths(payload) == [
        "[0].x",
        "[0].fill",
        "[0].dither",
        "[1].mode",
        "[2].dash[1]",
        "[3].data[0].width",
        "[3].ylegend.nope",
    ]


def test_template_strings_and_nulls_are_tolerated():
    payload = [
        {"type": "circle", "x": "10", "y": " 3.5 ", "radius": "2", "fill": None, "visible": "False", "dither": "0"},
        {"type": "plot", "data": [{"entity": "s.a"}], "ylegend": None},
        {"type": "legend", "x": 0, "y": 0, "items": "a,red;b,blue"},
        {"type": "circle", "x": 1, "y": 1, "radius": 3, "dither": 1},
    ]
    assert validate(payload) == []


def test_null_for_required_key_is_missing():
    assert _paths([{"type": "circle", "x": None, "y": 1, "radius": 3}]) == ["[0].x"]


def test_non_list_payloads():
    assert validate({"type": "circle"})[0].message.startswith("payload must be a list")
    assert _paths(["circle"]) == ["[0]"]


# ── agrees with the JSON Schema on the must-reject / must-accept sets ──────


@pytest.mark.parametrize("label, payload", REJECTS)
def test_rejects_what_the_schema_rejects(label, payload):
    assert validate(payload), label


@pytest.mark.parametrize("label, payload", ACCEPTS)
def test_accepts_what_the_schema_accepts(label, payload):
    assert validate(payload) == [], label


@pytest.mark.parametrize("label, payload", [c for c in ACCEPTS if "plot" not in c[0]])
def test_accepted_payloads_render(ctx, label, payload):
    # What validate() passes must not die in a handler.
    assert render(payload, 40, 40, strict=True, context=ctx).size == (40, 40), label


# ── null on any optional key never reaches a handler as None ───────────────


# Conditionally required: `null` = omitted, and omitted is a documented RenderError
# when the matching `fit_*` is on. validate() cannot express that yet.
_CONDITIONALLY_REQUIRED = {("new_multiline", "width"), ("new_multiline", "height")}


def _optional_null_cases():
    from imagespec.registry import get_spec
    from imagespec.spec import COMMON_FIELDS

    for name, sample in sorted(_previews().SAMPLES.items()):
        payload = sample if isinstance(sample, list) else [sample]
        for i, el in enumerate(payload):
            spec = get_spec(el["type"])
            for f in (*spec.fields, *COMMON_FIELDS):
                if f.required or f.name == "type" or (el["type"], f.name) in _CONDITIONALLY_REQUIRED:
                    continue
                mutated = [dict(e) for e in payload]
                mutated[i][f.name] = None
                yield pytest.param(mutated, id=f"{name}.{f.name}")


@pytest.mark.parametrize("payload", list(_optional_null_cases()))
def test_every_optional_key_accepts_null(history_ctx, payload):
    # The schema and validate() accept `null` for every optional key, so the
    # renderer must too: it is dropped (= omitted) unless the field declares
    # a meaning for it (colours, dither, nullable=True).
    assert validate(payload) == []
    img = render(payload, 296, 128, strict=True, context=history_ctx)
    assert img.size == (296, 128)


# ── render(strict=True) ────────────────────────────────────────────────────


def test_render_strict_raises_with_every_issue(ctx):
    payload = [{"type": "circle", "x": 1, "y": 1, "radius": 3, "fil": "red", "radiu": 2}]
    render(payload, 10, 10, context=ctx)  # lenient: unknown keys ignored
    with pytest.raises(RenderError, match=r"invalid payload: \[0\]\.fil: .*; \[0\]\.radiu: "):
        render(payload, 10, 10, strict=True, context=ctx)


def test_render_strict_passes_valid_payload(ctx):
    img = render([{"type": "circle", "x": "5", "y": 5, "radius": 3, "fill": "red"}], 10, 10, strict=True, context=ctx)
    assert img.size == (10, 10)


def test_dither_null_inherits_render_wide_setting():
    # `dither: null` is "no override": with global dithering on, the element is
    # dithered like everything else (it used to be flat-quantized in isolation).
    ctx = RenderContext(palette="bw")
    el = {"type": "rectangle", "x_start": 0, "y_start": 0, "x_end": 39, "y_end": 39, "fill": "#808080"}
    dithered = render([el], 40, 40, background="white", dither=True, context=ctx)
    with_null = render([dict(el, dither=None)], 40, 40, background="white", dither=True, context=ctx)
    with_false = render([dict(el, dither=False)], 40, 40, background="white", dither=True, context=ctx)
    assert with_null.tobytes() == dithered.tobytes()
    assert with_false.tobytes() != dithered.tobytes()
