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
    Verify clip highlighting changes on actual playback events and clears at completion.

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
    script = function + """
String.prototype.toMMSS = function () { return this.toString(); };
let nextFrame = 0;
const media = () => ({
    paused: true, currentTime: 0, duration: 3, listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    trigger(name) {
        this.paused = name !== "playing";
        this.listeners[name]();
    }
});
const first = media();
const second = media();
const classes = new Set();
const clip = {
    id: "q_1", ae1: first, ae2: second, pause_time_sec: 1, in_between: false,
    get paused() { return first.paused && second.paused && !this.in_between; }
};
const title = {classList: {
    add(name) { classes.add(name); },
    remove(...names) { names.forEach(name => classes.delete(name)); }
}};
const counter = {textContent: ""};
global.document = {getElementById(id) { return id.startsWith("title_") ? title : counter; }};
global.performance = {now: () => 1000};
global.requestAnimationFrame = () => ++nextFrame;
global.cancelAnimationFrame = () => {};
""" + function + """
configureDoubleClipPlaybackUiForClip(clip);
first.trigger("playing");
if (!classes.has("play_clip1")) throw new Error("first clip highlight missing");
first.trigger("ended");
if (classes.size) throw new Error("highlight remained during the gap");
second.currentTime = second.duration;
second.trigger("playing");
if (!classes.has("play_clip2")) throw new Error("second clip highlight missing");
second.trigger("ended");
if (classes.size) throw new Error("highlight remained after playback");
if (counter.textContent !== "7") throw new Error("final counter is " + counter.textContent);
"""
    subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=10)


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
            "aggregate_by_pair_id": "true", "expected_votes_per_file": "10",
        },
        "hit_app_html": {
            "allowed_max_hit_in_project": "0", "quantity_hits_more_than": "0", "quantity_bonus": "0",
            "quality_top_percentage": "0", "quality_bonus": "0",
        },
    }
    output = tmp_path / "parser.cfg"
    _, template = master.get_path("ccr", False)
    master.create_analyzer_cfg_dcr_ccr(cfg, template, str(output), {"bw_min": "SWB", "bw_max": "FB"}, 400)
    parsed = configparser.ConfigParser()
    parsed.read(output)
    assert parsed.getint("acceptance_criteria", "allowedMaxHITsInProject") == 0
    assert parsed.getint("acceptance_criteria", "correct_tps_bigger_equal") == expected_threshold
    assert parsed.getboolean("general", "aggregate_by_pair_id")
    assert parsed.getint("general", "expected_votes_per_file") == 10
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
