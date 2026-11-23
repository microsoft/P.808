"""Convert a saved session assignment plan and comparison URLs into prepacked CCR/DCR input."""

import argparse
import csv
import re
from pathlib import Path


def convert_assignments(assignments, clips, *, id_column="item_id", method="ccr"):
    """
    Join a long-format plan to canonical audio pairs without changing playback order.

    :param assignments: Records containing bundle_id, one-based position, item_id and CCR order.
    :param clips: Records with unique IDs, references (A), rating_clips (B), and optional role/practice_exposure.
    :param id_column: Comparison-ID column in clips; assignment IDs always use item_id.
    :param method: CCR retains presentation-order metadata; DCR uses fixed reference/processed order.
    :return: One wide-format record per bundle, ready for prepacked_sessions.
    """
    if method not in ("ccr", "dcr"):
        raise ValueError("method must be ccr or dcr.")
    pairs = {}
    for clip in clips:
        item_id = clip.get(id_column)
        if not isinstance(item_id, str) or not item_id.strip() or item_id in pairs:
            raise ValueError("Clips must have nonempty, unique comparison IDs.")
        pair = {"R": clip.get("references"), "P": clip.get("rating_clips")}
        if any(not isinstance(url, str) or not url.strip() for url in pair.values()):
            raise ValueError(f"Comparison {item_id!r} requires nonempty references and rating_clips URLs.")
        if method == "ccr":
            role = clip.get("role", "main")
            exposure = clip.get("practice_exposure", "")
            if not re.fullmatch(r"[A-Za-z0-9_.:-]+", item_id):
                raise ValueError(f"Invalid CCR comparison ID: {item_id!r}.")
            if role not in ("main", "identical", "contrast"):
                raise ValueError(f"Invalid comparison role for {item_id!r}: {role!r}.")
            if not isinstance(exposure, str) or (exposure and not re.fullmatch(r"[A-Za-z0-9_.:-]+", exposure)):
                raise ValueError(f"Invalid practice exposure for {item_id!r}: {exposure!r}.")
            pair.update(ID=item_id, ROLE=role, EXPOSURE=exposure)
        pairs[item_id] = pair
    bundles = {}
    for assignment in assignments:
        bundle_id = assignment.get("bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id.strip():
            raise ValueError("Assignments must have nonempty bundle IDs.")
        position = str(assignment.get("position", ""))
        if not re.fullmatch(r"[1-9][0-9]*", position):
            raise ValueError(f"Bundle {bundle_id!r} requires positive integer positions.")
        position = int(position)
        item_id = assignment.get("item_id")
        if item_id not in pairs:
            raise ValueError(f"Unknown comparison ID in assignments: {item_id!r}.")
        bundle = bundles.setdefault(bundle_id, {})
        if position in bundle:
            raise ValueError(f"Duplicate position {position} in bundle {bundle_id!r}.")
        if any(item["item_id"] == item_id for item in bundle.values()):
            raise ValueError(f"Repeated comparison {item_id!r} in bundle {bundle_id!r}.")
        if method == "ccr" and assignment.get("order") not in ("ab", "ba"):
            raise ValueError(f"Invalid CCR playback order for {item_id!r}; expected ab or ba.")
        bundle[position] = assignment
    if not bundles:
        raise ValueError("Assignments must not be empty.")
    session_size = len(next(iter(bundles.values())))
    sessions = []
    for bundle_id, bundle in sorted(bundles.items()):
        if set(bundle) != set(range(1, session_size + 1)):
            raise ValueError("Bundles must have equal sizes and contiguous positions starting at 1.")
        session = {"bundle_id": bundle_id}
        for position, assignment in sorted(bundle.items()):
            pair = dict(pairs[assignment["item_id"]])
            if method == "ccr":
                pair["ORDER"] = assignment["order"]
            session.update({f"Q{position - 1}_{field}": value for field, value in pair.items()})
        sessions.append(session)
    return sessions


def main(argv=None):
    """
    Convert existing assignment and clip CSVs without overwriting any input or output.

    :param argv: Optional command-line argument list.
    :return: None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assignments", type=Path, required=True, help="Saved pack_sessions.py assignment CSV.")
    parser.add_argument("--clips", type=Path, required=True,
                        help="CSV with unique comparison IDs, references (A) and rating_clips (B).")
    parser.add_argument("--output", type=Path, required=True, help="New prepacked_sessions CSV.")
    parser.add_argument("--id-column", default="item_id", help="Comparison-ID column in --clips.")
    parser.add_argument("--method", choices=("ccr", "dcr"), default="ccr",
                        help="CCR preserves ab/ba orders; DCR always uses fixed reference/processed order.")
    args = parser.parse_args(argv)
    if args.output.resolve() in (args.assignments.resolve(), args.clips.resolve()):
        parser.error("Output must be different from both inputs.")
    if args.output.exists():
        parser.error("Output already exists; choose a new path to preserve earlier sessions.")
    try:
        with args.assignments.open(encoding="utf-8-sig", newline="") as source:
            assignments = list(csv.DictReader(source))
        with args.clips.open(encoding="utf-8-sig", newline="") as source:
            clips = list(csv.DictReader(source))
        sessions = convert_assignments(assignments, clips, id_column=args.id_column, method=args.method)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(sessions[0]))
            writer.writeheader()
            writer.writerows(sessions)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    print(f"Created {len(sessions)} prepacked {args.method.upper()} sessions in {args.output}")


if __name__ == "__main__":
    main()
