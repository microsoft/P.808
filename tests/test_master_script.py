import asyncio
import configparser
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest
from jinja2 import Template


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
                "allowed_max_hit_in_project": "2",
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
