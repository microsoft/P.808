import ast
import asyncio
import configparser
import importlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from jinja2 import Template


@pytest.mark.parametrize(
    ("template", "required_device", "selected_devices", "expected"),
    [
        (template, "headset", ["in-ear", "ib-ls"], True)
        for template in [
            "ACR_template.html", "CCR_template.html", "DCR_template.html", "P808_multi.html",
            "P835_template.html", "P835_personalized_template3.html",
        ]
    ] + [
        ("CCR_template.html", "headset", ["over-ear", "ex-ls"], True),
        ("CCR_template.html", "headset", ["in-ear", "over-ear"], True),
        ("CCR_template.html", "headset", ["ib-ls", "ex-ls"], False),
        ("CCR_template.html", "headset", [], False),
        ("CCR_template.html", "loudspeaker", ["in-ear", "ex-ls"], True),
        ("CCR_template.html", "loudspeaker", ["over-ear"], False),
        ("CCR_template.html", "any", ["in-ear", "ex-ls"], True),
        ("CCR_template.html", "any", [], False),
    ],
)
def test_templates_accept_any_eligible_reported_device(template, required_device, selected_devices, expected):
    """
    Execute the listening-device availability check without confusing ownership with active playback.

    :param template: Template file containing the availability check.
    :param required_device: Configured playback-device class.
    :param selected_devices: Device types reported as available by the participant.
    :param expected: Whether the available devices meet the configured requirement.
    :return: None.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute template JavaScript.")
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / template
    html = path.read_text(encoding="utf-8")
    function = re.search(
        r"function selfReportedDeviceAvailable\(requiredDevice\) \{.*?\n\s*\}(?=\n)", html, re.DOTALL,
    ).group(0)
    script = (
        "const selected = " + json.dumps(selected_devices) + ";"
        "const $ = selector => ({toArray: () => selected.map(value => ({value}))});"
        + function
        + "\nconsole.log(JSON.stringify(selfReportedDeviceAvailable(" + json.dumps(required_device) + ")));"
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=10)
    assert json.loads(result.stdout) is expected
    assert "device_check = selfReportedDeviceAvailable(config.requiredPlaybackDevice);" in html


def test_ccr_clip_highlights_follow_media_playback_events():
    """
    Verify clip highlighting follows playback events and the counter never moves backward when pausing in the gap.

    :return: None.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute template JavaScript.")
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / "CCR_template.html"
    html = path.read_text(encoding="utf-8")
    start = html.index("function configureDoubleClipPlaybackUiForClip(clip){")
    end = html.index("function doubleClipIsended()", start)
    function = html[start:end].rstrip()
    clip_start = html.index("class DoubleClip {")
    clip_class = html[clip_start:html.index("\n}", clip_start) + 2]
    script = clip_class + function + """
String.prototype.toMMSS = function () { return String(parseInt(this, 10)); };
let frames = [];
const runFrame = () => frames.splice(0).forEach(callback => callback());
const media = duration => ({
    paused: true, currentTime: 0, duration, listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    play() { this.paused = false; },
    pause() { this.paused = true; },
    trigger(name) { if (this.listeners[name]) this.listeners[name](); }
});
const first = media(3.6);
const second = media(3.6);
const classes = new Set();
const title = {classList: {
    add(name) { classes.add(name); },
    remove(...names) { names.forEach(name => classes.delete(name)); }
}};
const counter = {textContent: ""};
global.document = {getElementById(id) { return id.startsWith("title_") ? title : counter; }};
global.requestAnimationFrame = callback => frames.push(callback);
const clip = new DoubleClip("q_1", first, second);
const expect = (actual, expected, label) => {
    if (String(actual) !== String(expected)) throw new Error(label + ": " + actual + " instead of " + expected);
};
configureDoubleClipPlaybackUiForClip(clip);
clip.play();
first.trigger("playing");
expect([...classes], "play_clip1", "first clip highlight");
first.currentTime = 2.5;
runFrame();
expect(counter.textContent, 2, "counter while the first clip plays");
first.currentTime = first.duration;
first.paused = true;
clip.in_between = true;
first.trigger("ended");
expect(classes.size, 0, "highlight during the gap");
runFrame();
expect(counter.textContent, 3, "counter during the gap");
clip.pause();
runFrame();
expect(counter.textContent, 3, "counter after pausing inside the gap");
expect(frames.length, 0, "frames scheduled while paused");
clip.play();
second.currentTime = 0.5;
second.trigger("playing");
expect([...classes], "play_clip2", "second clip highlight");
runFrame();
expect(counter.textContent, 5, "counter after resuming");
second.currentTime = second.duration;
second.paused = true;
second.trigger("ended");
runFrame();
expect(classes.size, 0, "highlight after playback");
expect(counter.textContent, 8, "final counter");
expect(frames.length, 0, "frames scheduled after playback");
"""
    subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=10)


def test_ccr_training_completion_without_dynamic_code_generation():
    """
    Remember practice only after every pair finishes, even when CSP forbids eval.

    :return: None.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute template JavaScript.")
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / "CCR_template.html"
    html = path.read_text(encoding="utf-8")
    start = html.index("function playedAudioTraining(id){")
    end = html.index("\n}", html.index("function getSum(", start)) + 2
    script = html[start:end] + """
const assert = require("node:assert/strict");
String.prototype.f = function (value) { return this.replace("{0}", value); };
const finished = new Map();
const cookies = [];
const config = {cookieName: "practice", forceRetrainingInHours: 1, knownQuestionInTrainingUrl: "trap.wav"};
let trainingStimulusPlayed = [0, 0, 0];
const $ = selector => ({
    val: () => finished.get(selector) || 0,
    off: () => {},
    attr: () => "clip.wav",
});
const createCookie = (...args) => cookies.push(args);
playedAudioTraining("t_1");
assert.deepEqual(trainingStimulusPlayed, [0, 0, 0]);
assert.deepEqual(cookies, []);
finished.set("#audio_n_finish_t_1", 1);
playedAudioTraining("t_1");
playedAudioTraining("t_1");
assert.deepEqual(trainingStimulusPlayed, [1, 0, 0]);
assert.deepEqual(cookies, []);
finished.set("#audio_n_finish_t_3", 1);
playedAudioTraining("t_3");
assert.deepEqual(trainingStimulusPlayed, [1, 0, 1]);
assert.deepEqual(cookies, []);
finished.set("#audio_n_finish_t_2", 1);
playedAudioTraining("t_2");
assert.deepEqual(trainingStimulusPlayed, [1, 1, 1]);
assert.deepEqual(cookies, [["practice_training", "un_important", 60]]);
"""
    subprocess.run(
        [node, "--disallow-code-generation-from-strings", "-e", script],
        capture_output=True, text=True, check=True, timeout=10,
    )


def test_ccr_progress_bars_report_current_question_and_completed_ratings():
    """
    Provide accessible progress indicators for both practice and main comparisons.

    :return: None.
    """
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / "CCR_template.html"
    html = path.read_text(encoding="utf-8")
    for prefix in ("t", "q"):
        assert f'id="{prefix}-progress-label" role="status" aria-live="polite"' in html
        assert f'id="{prefix}-progress-bar" class="progress-bar" role="progressbar"' in html
        assert f'aria-labelledby="{prefix}-progress-label"' in html
    assert 'updateProgressForSection(this.closest("#training") ? "training" : "rating_section")' in html


def test_ccr_completion_guidance_requires_ratings_playback_and_active_task():
    """
    Update final-item navigation and the submit reminder without bypassing practice or task gates.

    :return: None.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute template JavaScript.")
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / "CCR_template.html"
    html = path.read_text(encoding="utf-8")
    function = re.search(r"function updateProgressForSection\(sectionId\)\{.*?\n\}", html, re.DOTALL).group(0)
    script = function + """
const assert = require("node:assert/strict");
const config = {trainingUrls: [{}, {}], questionUrls: [{}, {}]};
const answered = new Map();
const elements = new Map();
const ui = {trainingIndex: 0, ratingIndex: 0, trainingNext: "", ratingNext: true, thanks: false,
            disabled: false, visible: true};
const fieldsets = [1, 2].map(i => ({
    disabled: false, querySelector: () => answered.get("t" + i)
}));
for (const prefix of ["t", "q"]) {
    elements.set(prefix + "-progress-label", {textContent: ""});
    elements.set(prefix + "-progress-bar", {style: {}, setAttribute() {}});
    for (const i of [1, 2]) elements.set("audio_n_finish_" + prefix + "_" + i, {value: "0"});
}
const document = {
    getElementById: id => elements.get(id),
    querySelector: selector => answered.get(selector.match(/name="([tq]\\d+)"/)[1]),
    querySelectorAll: selector => {
        assert.equal(selector, ".trainingFieldset");
        return fieldsets;
    }
};
const $ = selector => {
    switch (selector) {
        case "#trainingTabs li.active": return {index: () => ui.trainingIndex};
        case "#nav-tab-ul li.active": return {index: () => ui.ratingIndex};
        case "#next-training a": return {html: value => {ui.trainingNext = value;}};
        case "#next-rating": return {toggle: value => {ui.ratingNext = value;}};
        case "#thanks": return {toggle: value => {ui.thanks = value;}};
        case "#rating_section": return {hasClass: () => ui.disabled, is: () => ui.visible};
        default: throw new Error("Unexpected selector: " + selector);
    }
};
const finish = (prefix, i) => {
    answered.set(prefix + i, {name: prefix + i});
    elements.get("audio_n_finish_" + prefix + "_" + i).value = "1";
};
updateProgressForSection("training");
assert.match(ui.trainingNext, /^Next /);
assert.equal(ui.ratingNext, true);
assert.equal(ui.thanks, false);
ui.trainingIndex = 1;
updateProgressForSection("training");
assert.equal(ui.trainingNext, "Go to comparisons");
ui.trainingIndex = 0;
updateProgressForSection("training");
assert.match(ui.trainingNext, /^Next /);
ui.ratingIndex = 1;
updateProgressForSection("rating_section");
assert.equal(ui.ratingNext, false);
finish("q", 1);
finish("q", 2);
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false, "unfinished practice blocks completion");
finish("t", 1);
answered.set("t2", {name: "t2"});
updateProgressForSection("training");
assert.equal(ui.thanks, false, "practice must be heard, not merely answered");
finish("t", 2);
updateProgressForSection("training");
assert.equal(ui.thanks, true, "last practice answer refreshes main completion too");
ui.disabled = true;
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false);
ui.disabled = false;
ui.visible = false;
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false, "screened-out tasks must not invite submission");
ui.visible = true;
for (const i of [1, 2]) {
    fieldsets[i - 1].disabled = true;
    answered.delete("t" + i);
    elements.get("audio_n_finish_t_" + i).value = "0";
}
updateProgressForSection("rating_section");
assert.equal(ui.thanks, true, "cached practice needs no new answers");
answered.delete("q2");
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false);
answered.set("q2", {name: "q2"});
elements.get("audio_n_finish_q_2").value = "0";
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false, "each main pair must have finished playing");
finish("q", 2);
ui.ratingIndex = 0;
updateProgressForSection("rating_section");
assert.equal(ui.ratingNext, true, "returning to an earlier tab restores Next");
assert.equal(ui.thanks, true);
config.questionUrls = [];
updateProgressForSection("rating_section");
assert.equal(ui.thanks, false, "an empty test must not report completion");
"""
    subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=10)
    assert 'id="thanks" style="display: none;" role="status" aria-live="polite"' in html
    assert "Your responses have not been submitted yet." in html


@pytest.mark.parametrize(
    ("custom", "randomize_training", "expected_randomization"),
    [(False, None, "true"), (True, None, "true"), ("wording", None, "true"),
     (True, "false", "false"), (True, "true", "true")],
)
def test_ccr_presentation_and_metadata_are_opt_in(
    tmp_path, monkeypatch, custom, randomize_training, expected_randomization,
):
    """
    Preserve stock defaults while allowing reviewed content and preassigned directions.

    :param tmp_path: Temporary training/presentation/output directory.
    :param monkeypatch: Fixture for importing the CLI's existing module layout.
    :param custom: Whether the study opts into presentation and comparison metadata.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    training = tmp_path / "training.csv"
    pd.DataFrame({
        "training_references": ["a.wav", "c.wav", "e.wav"],
        "training_clips": ["b.wav", "d.wav", "f.wav"],
        "order": ["ab", "ba", "ab"],
        "pair_id": ["practice-1", "practice-2", "practice-3"],
        "practice_example": ["identical", "strong_worse", "moderate_better"],
    }).to_csv(training, index=False)
    cfg = {
        "allowed_max_hit_in_project": "7", "hit_base_payment": "0.5",
        "quantity_hits_more_than": "2", "quantity_bonus": "0.1",
        "quality_top_percentage": "20", "quality_bonus": "0.15",
    }
    if randomize_training is not None:
        cfg["randomize_training_questions"] = randomize_training
    if custom:
        presentation = tmp_path / "presentation.json"
        content = {
            "title": "Reviewed wording", "style": "body {font-size:20px;}",
            "instructions": '<section id="Survey">Approved welcome</section>',
            "script": "window.reviewedContent = true;",
        }
        if custom is True:
            content.update({
                "training": '<section id="training">Approved practice</section>',
                "rating": '<section id="rating_section">Approved comparisons</section>',
            })
        presentation.write_text(json.dumps(content), encoding="utf-8")
        cfg.update({
            "comparison_metadata": "true", "presentation_file": str(presentation), "append_training_trap": "false",
        })
    output = tmp_path / "ccr.html"
    template, _ = master.get_path("ccr", False)
    asyncio.run(master.create_hit_app_ccr_dcr(
        cfg, template, str(output), str(training),
        {"number_of_clips_per_session": "2", "number_of_trapping_per_session": "0" if custom else "1"},
        {},
    ))
    html = output.read_text(encoding="utf-8")
    training_urls = ast.literal_eval(re.search(r"trainingUrls:\s*(\[.*\]),", html).group(1))
    rating_urls = ast.literal_eval(re.search(r"questionUrls:\s*(\[.*\]),", html).group(1))
    assert len(training_urls) == (3 if custom else 4)
    assert len(rating_urls) == (2 if custom else 3)
    assert training_urls[1]["order"] == "ba"
    assert [item["pair_id"] for item in training_urls[:3]] == ["practice-1", "practice-2", "practice-3"]
    assert [item["practice_example"] for item in training_urls[:3]] == [
        "identical", "strong_worse", "moderate_better",
    ]
    assert 'name="T{0}_ID"' in html
    assert "urls[i].pair_id" in html
    assert ("Approved welcome" in html) == bool(custom)
    assert ("Welcome to this Data Labeling task!" in html) != bool(custom)
    assert ("window.reviewedContent = true;" in html) == bool(custom)
    assert f'randomizeTrainingQuestions:"{expected_randomization}"' in html
    assert ("pair_id" in rating_urls[0]) == bool(custom)
    assert ('id="trainingTabs"' in html) == (custom is not True)
    assert ('id="nav-tab-ul"' in html) == (custom is not True)
    assert 'id="qualification"' in html
    assert 'id="device_check_section"' in html
    assert 'id="setup"' in html
    assert "validateQualificationAnswer" in html
    assert "passDeviceCheck" in html


@pytest.mark.parametrize(
    ("strategy", "columns", "accepted"),
    [
        ("random", None, False),
        ("prepacked", "Q0_ID,Q0_ROLE,Q0_ORDER", False),
        ("prepacked", "Q0_ID,Q0_ROLE,Q0_ORDER,Q0_EXPOSURE", True),
    ],
)
def test_ccr_comparison_metadata_requires_prepacked_columns(tmp_path, monkeypatch, strategy, columns, accepted):
    """
    Reject CCR comparison metadata before setup unless prepacked sessions supply every metadata column.

    :param tmp_path: Temporary prepacked sessions directory.
    :param monkeypatch: Fixture for the CLI's module layout.
    :param strategy: Configured clip packing strategy.
    :param columns: Prepacked CSV header, or None when no CSV is configured.
    :param accepted: Whether validation should pass.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    create_input = {"number_of_clips_per_session": "1", "clip_packing_strategy": strategy}
    if columns:
        sessions = tmp_path / "sessions.csv"
        sessions.write_text(columns + "\n", encoding="utf-8")
        create_input["prepacked_sessions"] = str(sessions)
    cfg = {"create_input": create_input, "hit_app_html": {"comparison_metadata": "true"}}
    monkeypatch.setattr(master, "prepare_csv_for_create_input", AsyncMock(side_effect=RuntimeError("validated")))
    args = SimpleNamespace(general_assets=None, p831_fest=False, clips=None, gold_clips=None, trapping_clips=None)

    with pytest.raises(RuntimeError if accepted else SystemExit):
        asyncio.run(master.main(cfg, "ccr", args))


def test_ccr_pair_aggregation_requires_comparison_metadata(monkeypatch):
    """
    Reject pair aggregation when the HIT app would not record the comparison identities it needs.

    :param monkeypatch: Fixture for the CLI's module layout.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    cfg = {"create_input": {"aggregate_by_pair_id": "true"}, "hit_app_html": {}}
    monkeypatch.setattr(master, "prepare_csv_for_create_input", AsyncMock(side_effect=RuntimeError("validated")))
    args = SimpleNamespace(general_assets=None, p831_fest=False, clips=None, gold_clips=None, trapping_clips=None)

    with pytest.raises(SystemExit):
        asyncio.run(master.main(cfg, "ccr", args))


@pytest.mark.parametrize(
    ("test_method", "comparison_metadata", "error"),
    [
        ("ccr", "false", "Prepacked Qn_ORDER requires comparison_metadata = true"),
        ("dcr", "false", "Prepacked Qn_ORDER is not supported for DCR"),
        ("dcr", "true", "Prepacked Qn_ORDER is not supported for DCR"),
    ],
)
def test_prepacked_order_validation_is_method_specific(
    tmp_path, monkeypatch, test_method, comparison_metadata, error
):
    """
    Reject prepacked orders that the selected method cannot honor.

    :param tmp_path: Temporary prepacked sessions directory.
    :param monkeypatch: Fixture for the CLI's module layout.
    :param test_method: Listening-test method.
    :param comparison_metadata: Whether comparison metadata is enabled.
    :param error: Expected validation error.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    sessions = tmp_path / "sessions.csv"
    sessions.write_text("Q0_R,Q0_P,Q0_ORDER\na.wav,b.wav,ab\n", encoding="utf-8")
    cfg = {
        "create_input": {
            "number_of_clips_per_session": "1",
            "clip_packing_strategy": "prepacked",
            "prepacked_sessions": str(sessions),
        },
        "hit_app_html": {"comparison_metadata": comparison_metadata},
    }
    monkeypatch.setattr(master, "prepare_csv_for_create_input", AsyncMock(side_effect=RuntimeError("validated")))
    args = SimpleNamespace(general_assets=None, p831_fest=False, clips=None, gold_clips=None, trapping_clips=None)

    with pytest.raises(SystemExit, match=error):
        asyncio.run(master.main(cfg, test_method, args))


def test_dcr_rejects_comparison_metadata_without_order(tmp_path, monkeypatch):
    """
    Reject comparison metadata for DCR even when the prepacked file has no order column.

    :param tmp_path: Temporary prepacked sessions directory.
    :param monkeypatch: Fixture for the CLI's module layout.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    sessions = tmp_path / "sessions.csv"
    sessions.write_text("Q0_R,Q0_P\na.wav,b.wav\n", encoding="utf-8")
    cfg = {
        "create_input": {
            "number_of_clips_per_session": "1",
            "clip_packing_strategy": "prepacked",
            "prepacked_sessions": str(sessions),
        },
        "hit_app_html": {"comparison_metadata": "true"},
    }
    monkeypatch.setattr(master, "prepare_csv_for_create_input", AsyncMock(side_effect=RuntimeError("validated")))
    args = SimpleNamespace(general_assets=None, p831_fest=False, clips=None, gold_clips=None, trapping_clips=None)

    with pytest.raises(SystemExit, match="DCR comparison_metadata is not supported"):
        asyncio.run(master.main(cfg, "dcr", args))


@pytest.mark.parametrize("test_method", ["ccr", "dcr"])
@pytest.mark.parametrize("bw_max", ["NB-WB", "SWB"])
def test_ccr_dcr_reject_bandwidth_max_below_fullband(monkeypatch, test_method, bw_max):
    """
    Reject bandwidth settings that conflict with the all-answers-correct HIT check.

    :param monkeypatch: Fixture for the CLI's module layout.
    :param test_method: Listening-test method.
    :param bw_max: Configured maximum bandwidth.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")

    with pytest.raises(SystemExit, match="requires bw_max = FB"):
        master.extend_general_cfg_bw({}, {"bw_min": "NB-WB", "bw_max": bw_max}, test_method)


@pytest.mark.parametrize("test_method", ["ccr", "dcr"])
def test_ccr_dcr_allow_fullband_bandwidth_max(monkeypatch, test_method):
    """
    Keep the compatible fullband maximum available for CCR and DCR studies.

    :param monkeypatch: Fixture for the CLI's module layout.
    :param test_method: Listening-test method.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")

    assert master.extend_general_cfg_bw(
        {}, {"bw_min": "NB-WB", "bw_max": "FB"}, test_method
    ) == {"bw_min": "NB-WB", "bw_max": "FB"}


@pytest.mark.parametrize("test_method", ["ccr", "dcr"])
def test_ccr_dcr_allow_narrower_bandwidth_max_without_online_qualification(monkeypatch, test_method):
    """
    Allow narrower bandwidth limits when the HIT does not run online qualification.

    :param monkeypatch: Fixture for the CLI's module layout.
    :param test_method: Listening-test method.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")

    assert master.extend_general_cfg_bw(
        {},
        {"bw_min": "NB-WB", "bw_max": "SWB", "run_online_eval_qualification": "false"},
        test_method,
    ) == {"bw_min": "NB-WB", "bw_max": "SWB"}


def test_other_methods_allow_narrower_bandwidth_max(monkeypatch):
    """
    Keep the CCR/DCR-specific guard from changing other study methods.

    :param monkeypatch: Fixture for the CLI's module layout.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")

    assert master.extend_general_cfg_bw(
        {}, {"bw_min": "NB-WB", "bw_max": "SWB"}, "acr"
    ) == {"bw_min": "NB-WB", "bw_max": "SWB"}


@pytest.mark.parametrize("order", ["ba", "AB", "rp"])
def test_ccr_training_order_is_validated_and_clip_urls_are_preserved(tmp_path, monkeypatch, order):
    """
    Preserve training clip URLs and reject unsupported prescribed orders.

    :param tmp_path: Temporary training/output directory.
    :param monkeypatch: Fixture for the CLI's module layout.
    :param order: Training order of the second row; only "ab", "ba" or empty are valid.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    training = tmp_path / "training.csv"
    training.write_text(
        "training_references,training_clips,order,pair_id\n"
        f"a.wav,b.wav,,001\nc.wav,d.wav,{order},practice-2\n",
        encoding="utf-8",
    )
    output = tmp_path / "ccr.html"
    template, _ = master.get_path("ccr", False)
    create = master.create_hit_app_ccr_dcr(
        {
            "allowed_max_hit_in_project": "7", "hit_base_payment": "0.5",
            "quantity_hits_more_than": "2", "quantity_bonus": "0.1",
            "quality_top_percentage": "20", "quality_bonus": "0.15", "append_training_trap": "false",
        },
        template, str(output), str(training),
        {"number_of_clips_per_session": "1", "number_of_trapping_per_session": "0"}, {},
    )
    if order != "ba":
        with pytest.raises(ValueError):
            asyncio.run(create)
        return
    asyncio.run(create)
    html = output.read_text(encoding="utf-8")
    training_urls = ast.literal_eval(re.search(r"trainingUrls:\s*(\[.*\]),", html).group(1))
    assert [item["ref"] for item in training_urls] == ["a.wav", "c.wav"]
    assert "order" not in training_urls[0]
    assert training_urls[1]["order"] == "ba"
    assert [item["pair_id"] for item in training_urls] == ["001", "practice-2"]


def test_ccr_training_pair_id_rejects_unsafe_values(tmp_path, monkeypatch):
    """
    Reject training IDs that cannot safely be embedded in the HIT app.

    :param tmp_path: Temporary training/output directory.
    :param monkeypatch: Fixture for importing the CLI's existing module layout.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    training = tmp_path / "training.csv"
    training.write_text(
        "training_references,training_clips,pair_id\n"
        "a.wav,b.wav,unsafe'pair\n",
        encoding="utf-8",
    )
    template, _ = master.get_path("ccr", False)
    create = master.create_hit_app_ccr_dcr(
        {
            "allowed_max_hit_in_project": "7", "hit_base_payment": "0.5",
            "quantity_hits_more_than": "2", "quantity_bonus": "0.1",
            "quality_top_percentage": "20", "quality_bonus": "0.15", "append_training_trap": "false",
        },
        template, str(tmp_path / "ccr.html"), str(training),
        {"number_of_clips_per_session": "1", "number_of_trapping_per_session": "0"}, {},
    )

    with pytest.raises(ValueError, match="Invalid training pair ID"):
        asyncio.run(create)


@pytest.mark.parametrize(("counter", "limit", "blocked"), [
    (None, 0, True), (None, 20, False), ("19", 20, False), ("20", 20, True),
])
def test_ccr_zero_limit_blocks_fresh_browsers(counter, limit, blocked):
    """
    Apply the native participation limit even before a counter has been stored.

    :param counter: Stored completion count, or no prior browser record.
    :param limit: Configured maximum number of tasks.
    :param blocked: Whether the native task must be disabled.
    :return: None.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required to execute template JavaScript.")
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / "CCR_template.html"
    html = path.read_text(encoding="utf-8")
    body = html.split("\t\thit_num = readCookie(", 1)[1].split("\t\tif ((qual_passed", 1)[0]
    script = (
        f"const config={{cookieName:'fixture',allowedMaxHITsInProject:{limit}}};"
        f"const readCookie=()=>{json.dumps(counter)};"
        "const Hide_HIT_REASON={MAX_ACHIVED:'maximum'};let disabled=false;"
        "const disableTheHIT=()=>{disabled=true;};"
        "hit_num = readCookie(" + body + "\nconsole.log(JSON.stringify(disabled));"
    )
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=10)
    assert json.loads(result.stdout) is blocked


@pytest.mark.parametrize(("trap_count", "expected_threshold"), [(0, 0), (1, 1)])
def test_ccr_analyzer_keeps_html_limit_and_pair_identity_settings(
    tmp_path, monkeypatch, trap_count, expected_threshold,
):
    """
    Synchronize deferred participation limits and retain metadata-enabled CCR aggregation.

    :param tmp_path: Temporary generated analyzer configuration directory.
    :param monkeypatch: Fixture for the CLI's module layout.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master = importlib.import_module("master_script")
    cfg = {
        "create_input": {
            "number_of_clips_per_session": "22", "number_of_trapping_per_session": str(trap_count),
            "aggregate_by_pair_id": "true",
        },
        "hit_app_html": {
            "allowed_max_hit_in_project": "0", "quantity_hits_more_than": "0", "quantity_bonus": "0",
            "quality_top_percentage": "0", "quality_bonus": "0",
        },
    }
    output = tmp_path / "parser.cfg"
    _, template = master.get_path("ccr", False)
    master.create_analyzer_cfg_dcr_ccr(
        cfg, template, str(output), {"bw_min": "SWB", "bw_max": "FB", "cmp_pass_threshold": 2}, 400)
    parsed = configparser.ConfigParser()
    parsed.read(output)
    assert parsed.getint("acceptance_criteria", "allowedMaxHITsInProject") == 0
    assert parsed.getint("acceptance_criteria", "correct_tps_bigger_equal") == expected_threshold
    assert parsed.getboolean("general", "aggregate_by_pair_id")
    assert parsed.getint("general", "expected_votes_per_file") == 5
    assert parsed.get("acceptance_criteria", "bw_min") == "SWB"
    assert parsed.get("acceptance_criteria", "bw_max") == "FB"


class _FakeAzureClipStorage:
    def __init__(self, config, alg):
        """
        Configure deterministic Azure clip data for URL-matching tests.

        :param config: Unused storage configuration.
        :param alg: Store identifier used to select clips and signatures.
        """
        self._alg = alg
        self._clips = {
            "store1": [
                "processed/speech;one.wav",
                "processed/speech;two.wav",
            ],
            "noisy": [
                "references/speech;one.wav",
                "references/speech;two.wav",
            ],
        }[alg]

    @property
    async def clip_names(self):
        """
        Return deterministic raw blob names.

        :return: Blob names for the configured fake store.
        """
        return self._clips

    def make_clip_url(self, clip):
        """
        Return a deterministic signed URL for a raw blob name.

        :param clip: Raw blob name.
        :return: URL with a store-specific query signature.
        """
        return f"https://example.blob.core.windows.net/clips/{clip}?sig={self._alg}"


def test_prepare_csv_matches_azure_references_without_sas_queries(tmp_path, monkeypatch):
    """
    Verify that DCR/CCR matching compares URL paths while retaining signed URLs.

    :param tmp_path: Temporary directory for input CSV files.
    :param monkeypatch: Fixture for replacing Azure storage access.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    monkeypatch.setattr(master_script, "AzureClipStorage", _FakeAzureClipStorage)
    general_path = tmp_path / "general.csv"
    pd.DataFrame({"math": ["https://example.test/math.wav"]}).to_csv(general_path, index=False)
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "RatingClips": {"RatingClipsConfigurations": "store1"},
            "store1": {},
            "noisy": {},
        }
    )

    result = asyncio.run(
        master_script.prepare_csv_for_create_input(
            cfg,
            "ccr",
            str(tmp_path / "missing-clips.csv"),
            None,
            None,
            str(general_path),
        )
    )

    assert result["rating_clips"].tolist() == [
        "https://example.blob.core.windows.net/clips/processed/speech;one.wav?sig=store1",
        "https://example.blob.core.windows.net/clips/processed/speech;two.wav?sig=store1",
    ]
    assert result["references"].tolist() == [
        "https://example.blob.core.windows.net/clips/references/speech;one.wav?sig=noisy",
        "https://example.blob.core.windows.net/clips/references/speech;two.wav?sig=noisy",
    ]
    assert result["trapping_clips"].tolist() == result["references"].tolist()


@pytest.mark.parametrize(
    ("setting", "show_alert"),
    [(None, False), ("false", False), ("true", True), (" TRUE ", True)],
)
def test_p804_loudness_alert_is_opt_in(tmp_path, monkeypatch, setting, show_alert):
    """
    Verify that P.804 generation places the optional warning before rating audio.

    :param tmp_path: Temporary directory for local input and generated HTML files.
    :param monkeypatch: Fixture for configuring the master script without network access.
    :param setting: Optional loudness-alert configuration value.
    :param show_alert: Whether the generated rating section should contain the warning.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    monkeypatch.setattr(master_script, "args", SimpleNamespace(training_gold_clips=None), raising=False)
    training_path = tmp_path / "training.csv"
    trap_path = tmp_path / "trapping.csv"
    output_path = tmp_path / "p804.html"
    pd.DataFrame({"training_clips": ["https://example.test/training.wav"]}).to_csv(training_path, index=False)
    pd.DataFrame(
        {"trapping_clips": ["https://example.test/trapping.wav"], "trapping_ans": [1]}
    ).to_csv(trap_path, index=False)
    cfg = {
        "hit_base_payment": "0.5",
        "quantity_hits_more_than": "2",
        "quantity_bonus": "0.1",
        "quality_top_percentage": "20",
        "quality_bonus": "0.15",
    }
    if setting is not None:
        cfg["show_loudness_alert"] = setting
    template_path, _ = master_script.get_path("p804", False)
    asyncio.run(
        master_script.create_hit_app_pp835_p804(
            cfg,
            template_path,
            str(output_path),
            str(training_path),
            str(trap_path),
            {
                "number_of_clips_per_session": "10",
                "number_of_trapping_per_session": "1",
                "number_of_gold_clips_per_session": "2",
            },
            None,
            {"allow_cannot_rate": "false"},
            2,
        )
    )
    html = output_path.read_text(encoding="utf-8")
    rating_section = html.split('id="rating_section">', 1)[1].split("</section>", 1)[0]
    assert ('id="loudness_alert"' in html) == show_alert
    assert "Lower the volume before starting playback." not in rating_section
    if show_alert:
        assert rating_section.index('id="loudness_alert"') < rating_section.index('id="volume4"')
        assert 'role="alert" id="loudness_alert"' in rating_section
        assert "hearing damage" in rating_section
        assert "we recommend using loudspeaker playback" in rating_section
        assert "volume level of your loudspeakers" in rating_section
    else:
        assert "volume level of your headset" in rating_section


@pytest.mark.parametrize(
    ("method", "show_alert", "device", "warn"),
    [
        ("p804", "true", None, True),
        ("p804", "true", " HEADSET ", True),
        ("p804", "true", "any", False),
        ("p804", "true", "loudspeaker", False),
        ("p804", "false", "headset", False),
        ("p804", None, "headset", False),
        ("pp835", "true", "headset", False),
    ],
)
def test_loudness_alert_warns_about_conflicting_device(
    tmp_path, monkeypatch, capsys, method, show_alert, device, warn
):
    """
    Verify that the master script warns only about an enabled P.804 headset conflict.

    :param tmp_path: Temporary directory for generated project paths.
    :param monkeypatch: Fixture for isolating generation from clip and storage processing.
    :param capsys: Fixture for capturing researcher-facing generation messages.
    :param method: Test method being generated.
    :param show_alert: Optional loudness-alert configuration value.
    :param device: Optional required-playback-device configuration value.
    :param warn: Whether generation should print a configuration-conflict hint.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(master_script, "prepare_csv_for_create_input", AsyncMock(return_value=pd.DataFrame()))
    monkeypatch.setattr(master_script.ca, "validate_inputs", Mock())
    monkeypatch.setattr(master_script.ca, "create_input_for_mturk", Mock(return_value=2))
    monkeypatch.setattr(master_script, "prepare_basic_cfg", Mock(return_value={}))
    monkeypatch.setattr(master_script, "extend_general_cfg_bw", Mock(return_value={}))
    renderer = AsyncMock()
    monkeypatch.setattr(master_script, "create_hit_app_pp835_p804", renderer)
    monkeypatch.setattr(master_script, "create_analyzer_cfg_general", Mock())
    cfg = configparser.ConfigParser()
    cfg.read_dict(
        {
            "create_input": {"clip_packing_strategy": "random"},
            "hit_app_html": {
                "quantity_hits_more_than": "1",
                "screenout_code": "test-only",
            },
        }
    )
    if show_alert is not None:
        cfg["hit_app_html"]["show_loudness_alert"] = show_alert
    if device is not None:
        cfg["hit_app_html"]["required_playback_device"] = device
    args = SimpleNamespace(
        general_assets=None,
        p831_fest=False,
        clips=None,
        gold_clips=None,
        trapping_clips=None,
        project="test-project",
        training_clips=None,
    )
    asyncio.run(master_script.main(cfg, method, args))
    output = capsys.readouterr().out
    assert ("may conflict" in output) == warn
    if warn:
        assert "required_playback_device: any" in output
        assert "qualification and setup" in output
    renderer.assert_awaited_once()
    assert renderer.await_args.args[7]["required_playback_device"] == (device or "headset").strip().lower()


@pytest.mark.parametrize(
    ("number_of_hits", "allowed_hits", "quantity_threshold", "expected_messages"),
    [
        (60, 60, 30, []),
        (60, 60, 20, ["outside the recommended range"]),
        (60, 70, 30, ["greater than the total number of HITs"]),
        (60, 20, 30, ["workers cannot reach the quantity bonus"]),
        (
            60,
            60,
            61,
            [
                "outside the recommended range",
                "greater than the total number of HITs (60), so workers cannot reach",
            ],
        ),
    ],
)
def test_bonus_setting_warnings(
    number_of_hits,
    allowed_hits,
    quantity_threshold,
    expected_messages,
    monkeypatch,
):
    """
    Verify warnings for unusual and unreachable bonus configurations.

    :param number_of_hits: Total number of generated HITs.
    :param allowed_hits: Maximum HITs one worker may complete.
    :param quantity_threshold: Accepted HIT count required for a quantity bonus.
    :param expected_messages: Warning fragments expected for the configuration.
    :param monkeypatch: Fixture for importing the repository source module.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    warnings = master_script.get_bonus_setting_warnings(
        {
            "allowed_max_hit_in_project": str(allowed_hits),
            "quantity_hits_more_than": str(quantity_threshold),
        },
        number_of_hits,
    )

    assert len(warnings) == len(expected_messages)
    for expected_message in expected_messages:
        assert any(expected_message in warning for warning in warnings)


def test_bonus_setting_warnings_use_optional_worker_limit_default(monkeypatch):
    """
    Verify that omitted worker HIT limits use the method-specific effective default.

    :param monkeypatch: Fixture for importing the repository source module.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")

    warnings = master_script.get_bonus_setting_warnings(
        {"quantity_hits_more_than": "30"},
        60,
        default_allowed_hits=50,
    )

    assert warnings == []


@pytest.mark.parametrize(
    ("configured_value", "expected_threshold"),
    [
        (None, 2),
        ("3", 3),
        (" 4 ", 4),
    ],
)
def test_comparison_pass_threshold_configuration(
    configured_value,
    expected_threshold,
    monkeypatch,
):
    """
    Verify the configurable comparison threshold and its default.

    :param configured_value: Optional raw threshold from the HIT app configuration.
    :param expected_threshold: Parsed comparison threshold.
    :param monkeypatch: Fixture for importing the repository source module.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    hitapp = {}
    if configured_value is not None:
        hitapp["cmp_pass_threshold"] = configured_value

    assert master_script._get_cmp_pass_threshold(hitapp) == expected_threshold


@pytest.mark.parametrize("configured_value", ["invalid", "0", "5"])
def test_comparison_pass_threshold_rejects_invalid_values(
    configured_value,
    monkeypatch,
):
    """
    Verify that unsupported comparison thresholds stop study generation.

    :param configured_value: Invalid raw threshold from the HIT app configuration.
    :param monkeypatch: Fixture for importing the repository source module.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")

    with pytest.raises(ValueError, match="cmp_pass_threshold"):
        master_script._get_cmp_pass_threshold(
            {"cmp_pass_threshold": configured_value}
        )


@pytest.mark.parametrize(
    "template_name",
    [
        "acr_result_parser_template.cfg",
        "p804_result_parser_template.cfg",
        "pp835_result_parser_template.cfg",
    ],
)
def test_general_analyzer_cfg_uses_environment_comparison_threshold(
    tmp_path,
    monkeypatch,
    template_name,
):
    """
    Verify that general analyzer templates use the HIT app's comparison threshold.

    :param tmp_path: Temporary directory for the rendered analyzer configuration.
    :param monkeypatch: Fixture for importing the repository source module.
    :param template_name: Analyzer template rendered by the general generator.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    source_dir = Path(__file__).resolve().parents[1] / "src"
    template_path = source_dir / "assets_master_script" / template_name
    output_path = tmp_path / "result_parser.cfg"
    cfg = {
        "create_input": {
            "number_of_clips_per_session": "10",
            "number_of_trapping_per_session": "1",
            "number_of_gold_clips_per_session": "1",
        }
    }
    cfg_section = {
        "quantity_hits_more_than": "10",
        "quantity_bonus": "0.1",
        "quality_top_percentage": "20",
        "quality_bonus": "0.15",
    }

    master_script.create_analyzer_cfg_general(
        cfg,
        cfg_section,
        template_path,
        output_path,
        {"bw_min": "NB-WB", "bw_max": "FB", "cmp_pass_threshold": 3},
        20,
    )

    output = output_path.read_text(encoding="utf-8")
    assert "correct_cmp_bigger_equal: 3" in output


def test_comparison_analyzer_cfg_uses_environment_comparison_threshold(
    tmp_path,
    monkeypatch,
):
    """
    Verify that DCR/CCR analyzer output uses the HIT app's comparison threshold.

    :param tmp_path: Temporary directory for the rendered analyzer configuration.
    :param monkeypatch: Fixture for importing the repository source module.
    :return: None.
    """
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "src"))
    master_script = importlib.import_module("master_script")
    source_dir = Path(__file__).resolve().parents[1] / "src"
    template_path = source_dir / "assets_master_script" / "dcr_ccr_result_parser_template.cfg"
    output_path = tmp_path / "result_parser.cfg"
    cfg = {
        "create_input": {
            "number_of_clips_per_session": "10",
            "number_of_trapping_per_session": "1",
        },
        "hit_app_html": {
            "quantity_hits_more_than": "10",
            "quantity_bonus": "0.1",
            "quality_top_percentage": "20",
            "quality_bonus": "0.15",
        },
    }

    master_script.create_analyzer_cfg_dcr_ccr(
        cfg,
        template_path,
        output_path,
        {"bw_min": "NB-WB", "bw_max": "FB", "cmp_pass_threshold": 3},
        20,
    )

    output = output_path.read_text(encoding="utf-8")
    assert "correct_cmp_bigger_equal: 3" in output


@pytest.mark.parametrize(
    "template_name",
    [
        "ACR_template.html",
        "CCR_template.html",
        "DCR_template.html",
        "P808_multi.html",
        "P835_template.html",
        "P835_personalized_template3.html",
        "echo_impairment_test_template.html",
        "echo_impairment_test_fest_template.html",
        "P831_ACR_template.html",
        "P831_DCR_template.html",
    ],
)
def test_cmp_setup_templates_use_per_question_correct_hashes(template_name):
    """
    Verify CMP checks compare each answer with its own question's hash.

    :param template_name: Worker-facing template containing CMP setup questions.
    :return: None.
    """
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / template_name
    template = Template(path.read_text(encoding="utf-8"))
    html = template.render(cfg={"run_online_eval_setup": "true"})
    assert re.search(r'cmp_correct_hashes:\s*\["\$\{cmp_correct_hash1\}", "\$\{cmp_correct_hash2\}",', html)
    assert all(f'"${{cmp_correct_hash{index}}}"' in html for index in range(3, 5))
    assert 'config["cmp_correct_hashes"][i]' in html
    assert "selectedHash === expectedHash.toLowerCase()" in html
    assert 'config["cmp_correct_answers"]' not in html

    disabled_html = template.render(cfg={"run_online_eval_setup": "false"})
    assert re.search(r"cmp_correct_hashes:\s*\[\s*\]", disabled_html)


@pytest.mark.parametrize(
    "template_name",
    [
        "ACR_template.html",
        "CCR_template.html",
        "DCR_template.html",
        "P808_multi.html",
        "P835_template.html",
        "P835_personalized_template3.html",
    ],
)
@pytest.mark.parametrize("section_id", ["qualification_rejected", "setup_rejected"])
def test_screenout_alert_prohibits_further_project_submissions(template_name, section_id):
    """
    Verify that both screen-out paths warn workers not to submit additional project HITs.

    :param template_name: Worker-facing HTML template to render.
    :param section_id: Qualification or setup screen-out section.
    :return: None.
    """
    path = Path(__file__).resolve().parents[1] / "src" / "P808Template" / template_name
    html = Template(path.read_text(encoding="utf-8")).render(cfg={})
    section = html.split(f'id="{section_id}" hidden>', 1)[1].split("</section>", 1)[0]
    alert = section.rsplit('<div class="alert alert-danger" role="alert">', 1)[1]
    assert "You are not allowed to submit any more HITs from this project." in alert
    assert "Any additional screen-out submissions from this project will be rejected." in alert
    assert "hidden" not in alert
