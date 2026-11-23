import ast
import configparser
import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest

from src.convert_assignments import convert_assignments, main


def _inputs():
    """
    Provide shuffled assignments and a clip lookup with distinct canonical pairs.

    :return: Assignment and comparison records.
    """
    return (
        [
            {"bundle_id": "bundle-1", "position": "2", "item_id": "002", "order": "ab"},
            {"bundle_id": "bundle-2", "position": "1", "item_id": "002", "order": "ba"},
            {"bundle_id": "bundle-1", "position": "1", "item_id": "001", "order": "ba"},
            {"bundle_id": "bundle-2", "position": "2", "item_id": "001", "order": "ab"},
        ],
        [
            {"comparison_id": "001", "references": "a1.wav?x=1&y=2", "rating_clips": "b1.wav"},
            {
                "comparison_id": "002", "references": "a2.wav", "rating_clips": "b2.wav",
                "role": "contrast", "practice_exposure": "same_scene",
            },
        ],
    )


@pytest.mark.parametrize("method", ["ccr", "dcr"])
def test_conversion_preserves_canonical_pairs_and_positions(method):
    """
    Preserve positions, leading-zero IDs and URLs; never swap canonical URLs for a ba assignment.

    :param method: Output test method.
    :return: None.
    """
    assignments, clips = _inputs()
    sessions = convert_assignments(assignments, clips, id_column="comparison_id", method=method)
    assert [row["bundle_id"] for row in sessions] == ["bundle-1", "bundle-2"]
    lookup = {row["comparison_id"]: row for row in clips}
    for assignment in assignments:
        row = next(row for row in sessions if row["bundle_id"] == assignment["bundle_id"])
        prefix = f"Q{int(assignment['position']) - 1}_"
        clip = lookup[assignment["item_id"]]
        assert row[prefix + "R"] == clip["references"]
        assert row[prefix + "P"] == clip["rating_clips"]
        if method == "ccr":
            assert row[prefix + "ID"] == assignment["item_id"]
            assert row[prefix + "ORDER"] == assignment["order"]
            assert row[prefix + "ROLE"] == clip.get("role", "main")
            assert row[prefix + "EXPOSURE"] == clip.get("practice_exposure", "")
        else:
            assert set(row) == {"bundle_id", "Q0_R", "Q0_P", "Q1_R", "Q1_P"}


@pytest.mark.parametrize("case, message", [
    ("unknown_id", "Unknown comparison"),
    ("duplicate_id", "unique comparison IDs"),
    ("missing_url", "nonempty references"),
    ("bad_order", "playback order"),
    ("unsafe_id", "Invalid CCR comparison ID"),
    ("bad_role", "Invalid comparison role"),
    ("unsafe_exposure", "Invalid practice exposure"),
    ("duplicate_position", "Duplicate position"),
    ("repeated_item", "Repeated comparison"),
    ("bad_position", "positive integer positions"),
    ("position_gap", "contiguous positions"),
    ("unequal_sizes", "equal sizes"),
    ("empty_bundle_id", "nonempty bundle IDs"),
    ("empty_plan", "must not be empty"),
])
def test_conversion_rejects_malformed_inputs(case, message):
    """
    Reject ambiguous joins, invalid metadata and incomplete bundles instead of changing the plan.

    :param case: Input-integrity failure to exercise.
    :param message: Expected diagnostic fragment.
    :return: None.
    """
    assignments, clips = _inputs()
    if case == "unknown_id":
        assignments[0]["item_id"] = "missing"
    elif case == "duplicate_id":
        clips.append(dict(clips[0]))
    elif case == "missing_url":
        clips[0]["references"] = " "
    elif case == "bad_order":
        del assignments[0]["order"]
    elif case == "unsafe_id":
        clips[0]["comparison_id"] = "unsafe'id"
    elif case == "bad_role":
        clips[0]["role"] = "trap"
    elif case == "unsafe_exposure":
        clips[0]["practice_exposure"] = "same scene"
    elif case == "duplicate_position":
        assignments[0]["position"] = "1"
    elif case == "repeated_item":
        assignments[0]["item_id"] = "001"
    elif case == "bad_position":
        assignments[0]["position"] = "1.5"
    elif case == "position_gap":
        assignments[0]["position"] = "3"
    elif case == "unequal_sizes":
        assignments.pop()
    elif case == "empty_bundle_id":
        assignments[0]["bundle_id"] = ""
    elif case == "empty_plan":
        assignments.clear()
    with pytest.raises(ValueError, match=message):
        convert_assignments(assignments, clips, id_column="comparison_id")


def test_cli_preserves_inputs_and_existing_output(tmp_path):
    """
    Exercise CSV conversion with a BOM and protect both inputs and an earlier conversion.

    :param tmp_path: Temporary CSV directory.
    :return: None.
    """
    assignments, clips = _inputs()
    for clip in clips:
        clip.setdefault("role", "main")
        clip.setdefault("practice_exposure", "")
    assignment_path = tmp_path / "assignments.csv"
    clips_path = tmp_path / "clips.csv"
    for path, rows in ((assignment_path, assignments), (clips_path, clips)):
        with path.open("w", encoding="utf-8-sig", newline="") as source:
            writer = csv.DictWriter(source, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    output = tmp_path / "sessions.csv"
    arguments = [
        "--assignments", str(assignment_path), "--clips", str(clips_path), "--id-column", "comparison_id",
    ]
    main(arguments + ["--output", str(output)])
    with output.open(encoding="utf-8", newline="") as source:
        assert list(csv.DictReader(source)) == convert_assignments(assignments, clips, id_column="comparison_id")
    for protected in (assignment_path, clips_path, output):
        before = protected.read_bytes()
        with pytest.raises(SystemExit):
            main(arguments + ["--output", str(protected)])
        assert protected.read_bytes() == before
    assignment_path.write_text("bundle_id,position,item_id,order\nb,1,missing,ab\n", encoding="utf-8")
    invalid_output = tmp_path / "invalid.csv"
    with pytest.raises(SystemExit):
        main(arguments + ["--output", str(invalid_output)])
    assert not invalid_output.exists()


@pytest.mark.parametrize("method", ["ccr", "dcr"])
def test_cli_pipeline_generates_stock_hit(tmp_path, method):
    """
    Run the packer, converter and master CLI without a wrapper or presentation overrides.

    :param tmp_path: Temporary study inputs and generated artifacts.
    :param method: Test method exercised through all three commands.
    :return: None.
    """
    src = Path(__file__).resolve().parents[1] / "src"
    clips = [
        {
            "comparison_id": f"{index:03d}", "scene": str(index // 2),
            "references": f"https://example.org/a{index}.wav",
            "rating_clips": f"https://example.org/b{index}.wav",
        }
        for index in range(8)
    ]
    with (tmp_path / "clips.csv").open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(clips[0]))
        writer.writeheader()
        writer.writerows(clips)
    cfg = configparser.ConfigParser()
    cfg.read(src / "configurations" / "master.cfg", encoding="utf-8")
    cfg["create_input"].update({
        "clip_packing_strategy": "prepacked", "prepacked_sessions": "sessions.csv",
        "number_of_clips_per_session": "2", "number_of_trapping_per_session": "0",
        "aggregate_by_pair_id": str(method == "ccr").lower(),
    })
    cfg["hit_app_html"].update({
        "comparison_metadata": str(method == "ccr").lower(), "bw_min": "NB-WB", "bw_max": "FB",
        "cmp_pass_threshold": "3",
    })
    with (tmp_path / "master.cfg").open("w", encoding="utf-8") as output:
        cfg.write(output)
    commands = [
        [
            "pack_sessions.py", "--input", "clips.csv", "--output", "assignments.csv", "--audit", "audit.json",
            "--id-column", "comparison_id", "--group-column", "scene", "--repeats", "2",
            "--session-size", "2", "--seed", "17", "--iterations", "100",
        ],
        [
            "convert_assignments.py", "--assignments", "assignments.csv", "--clips", "clips.csv",
            "--id-column", "comparison_id", "--method", method, "--output", "sessions.csv",
        ],
        [
            "master_script.py", "--project", "study", "--method", method, "--cfg", "master.cfg",
            "--clips", "clips.csv", "--training_clips", str(src / "test_inputs" / "training_clips_ccr.csv"),
        ],
    ]
    for script, *arguments in commands:
        result = subprocess.run(
            [sys.executable, str(src / script), *arguments], cwd=tmp_path,
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    with (tmp_path / "sessions.csv").open(encoding="utf-8", newline="") as source:
        sessions = list(csv.DictReader(source))
    with (tmp_path / "study" / "study_publish_batch.csv").open(encoding="utf-8", newline="") as source:
        published = list(csv.DictReader(source))
    assert len(published) == len(sessions) == 8
    for expected, actual in zip(sessions, published):
        assert {field: actual[field] for field in expected} == expected
    html = (tmp_path / "study" / f"study_{method}.html").read_text(encoding="utf-8")
    assert "Welcome to this Data Labeling task!" in html
    assert "max-width: 65ch" not in html
    assert re.search(r"cmp_pass_threshold:\s*3,", html)
    questions = ast.literal_eval(re.search(r"questionUrls:\s*(\[.*\]),", html).group(1))
    assert len(questions) == 2
    if method == "ccr":
        assert questions[0]["pair_id"] == "${Q0_ID}"
        assert questions[0]["order"] == "${Q0_ORDER}"
    parser_cfg = configparser.ConfigParser()
    parser_cfg.read(tmp_path / "study" / f"study_{method}_result_parser.cfg", encoding="utf-8")
    assert parser_cfg["general"].getboolean("aggregate_by_pair_id", fallback=False) == (method == "ccr")
    assert parser_cfg["accept_and_use"].getint("correct_cmp_bigger_equal") == 3
