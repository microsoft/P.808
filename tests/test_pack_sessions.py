import csv
import hashlib
import json
from collections import Counter, defaultdict
from itertools import combinations

import pytest

from src.pack_sessions import main, pack_sessions


def _items():
    """
    Create comparison pairs sharing source scenes and balanced strata.

    :return: Synthetic comparison records.
    """
    return [
        {"item_id": f"item-{scene:02d}-{stratum}", "scene": str(scene), "stratum": stratum}
        for scene in range(20) for stratum in ("first", "second")
    ]


def _pack(rows, **kwargs):
    """
    Pack the synthetic comparisons using the test's balanced protocol.

    :param rows: Synthetic comparison records.
    :param kwargs: Overrides for the packing parameters.
    :return: Assignments and audit.
    """
    options = {
        "repeats": 6, "session_size": 4, "group_column": "scene", "stratum_column": "stratum",
        "quotas": {"first": 2, "second": 2}, "seed": 17, "iterations": 10000,
    }
    options.update(kwargs)
    return pack_sessions(rows, **options)


def test_joint_coverage_sources_orders_and_context():
    """
    Verify exact coverage and balance against independently reconstructed context.

    :return: None.
    """
    items = _items()
    assignments, audit = _pack(items)
    by_id = {row["item_id"]: row for row in items}
    bundles = defaultdict(list)
    orders = defaultdict(Counter)
    for row in assignments:
        bundles[row["bundle_id"]].append(row)
        orders[row["item_id"]][row["order"]] += 1
    assert len(bundles) == 60
    assert set(orders) == set(by_id)
    assert all(counts == {"ab": 3, "ba": 3} for counts in orders.values())
    signatures = []
    companions = Counter()
    for bundle in bundles.values():
        identifiers = [row["item_id"] for row in bundle]
        assert [row["position"] for row in bundle] == [1, 2, 3, 4]
        assert len({by_id[item]["scene"] for item in identifiers}) == 4
        assert Counter(by_id[item]["stratum"] for item in identifiers) == {"first": 2, "second": 2}
        signatures.append(frozenset(identifiers))
        companions.update(combinations(sorted(identifiers), 2))
    assert len(set(signatures)) == len(bundles)
    cost = sum(count * (count - 1) // 2 for count in companions.values())
    assert audit["context_after"]["collision_cost"] == cost
    assert cost < audit["context_before"]["collision_cost"]
    assert audit["context_after"]["distinct_companions_min"] > 3


def test_seed_is_reproducible_and_input_order_does_not_matter():
    """
    Verify stable assignments and audit without depending on input row order.

    :return: None.
    """
    original = _pack(_items())
    assert _pack(list(reversed(_items()))) == original
    assert _pack(_items(), seed=18)[0] != original[0]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"repeats": 3}, "positive even"),
        ({"session_size": 0}, "positive integer"),
        ({"iterations": -1}, "nonnegative"),
        ({"quotas": {"first": 1, "second": 3}}, "incompatible"),
        ({"quotas": {"first": 4}}, "match the input strata"),
    ],
)
def test_invalid_protocol_fails_instead_of_padding(overrides, message):
    """
    Reject settings that cannot preserve the requested protocol.

    :param overrides: Invalid protocol parameters.
    :param message: Expected diagnostic fragment.
    :return: None.
    """
    with pytest.raises(ValueError, match=message):
        _pack(_items(), **overrides)


def test_infeasible_sources_and_duplicate_ids_are_rejected():
    """
    Reject impossible source exposure and ambiguous comparison identities.

    :return: None.
    """
    with pytest.raises(ValueError, match="source group"):
        _pack([{**row, "scene": "same"} for row in _items()])
    with pytest.raises(ValueError, match="unique item IDs"):
        _pack(_items() + [_items()[0]])
    with pytest.raises(ValueError, match="distinct bundle memberships"):
        pack_sessions([{"item_id": "a"}, {"item_id": "b"}], repeats=2, session_size=1)


def test_cli_outputs_audited_assignments_and_preserves_existing_files(tmp_path):
    """
    Exercise CSV serialization, provenance, and non-overwriting behavior.

    :param tmp_path: Temporary directory supplied by pytest.
    :return: None.
    """
    source = tmp_path / "input.csv"
    with source.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["item_id", "scene", "stratum"])
        writer.writeheader()
        writer.writerows(_items())
    output = tmp_path / "assignments.csv"
    audit_path = tmp_path / "audit.json"
    arguments = [
        "--input", str(source), "--output", str(output), "--audit", str(audit_path),
        "--repeats", "6", "--session-size", "4", "--group-column", "scene",
        "--stratum-column", "stratum", "--quota", "first=2", "--quota", "second=2",
        "--seed", "17", "--iterations", "100",
    ]
    main(arguments)
    with output.open(newline="", encoding="utf-8") as stream:
        assignments = list(csv.DictReader(stream))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert len(assignments) == 240
    assert audit["input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert audit["assignment_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    previous = output.read_bytes(), audit_path.read_bytes()
    with pytest.raises(SystemExit):
        main(arguments)
    assert (output.read_bytes(), audit_path.read_bytes()) == previous
