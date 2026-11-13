"""Pack repeated comparisons into distinct, counterbalanced listening sessions."""

import argparse
import csv
import hashlib
import io
import json
import math
import random
from collections import Counter
from itertools import combinations
from pathlib import Path


def _column(rows, name):
    """
    Read a required nonempty string column without changing its identifiers.

    :param rows: Input comparison records.
    :param name: Required column name.
    :return: Column values.
    """
    values = [row.get(name) for row in rows]
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"Column {name!r} must contain nonempty strings in every row.")
    return values


def _edge(first, second):
    """
    Identify an unordered pair of companion comparisons.

    :param first: First comparison index.
    :param second: Second comparison index.
    :return: Canonical index pair.
    """
    return (first, second) if first < second else (second, first)


def _swap(bundles, group_counts, groups, first, second):
    """
    Exchange two slots and update their source-group counts.

    :param bundles: Mutable bundle membership.
    :param group_counts: Source-group counts per bundle.
    :param groups: Source group per comparison.
    :param first: First bundle index and slot.
    :param second: Second bundle index and slot.
    :return: None.
    """
    left, left_slot = first
    right, right_slot = second
    a, b = bundles[left][left_slot], bundles[right][right_slot]
    group_counts[left][groups[a]] -= 1
    group_counts[left][groups[b]] += 1
    group_counts[right][groups[b]] -= 1
    group_counts[right][groups[a]] += 1
    bundles[left][left_slot], bundles[right][right_slot] = b, a


def _repair_groups(bundles, slots, groups, strata, rng):
    """
    Remove within-bundle source repeats using quota-preserving exchanges.

    :param bundles: Mutable bundle membership.
    :param slots: All slots indexed by stratum.
    :param groups: Source group per comparison.
    :param strata: Stratum per comparison.
    :param rng: Local seeded random generator.
    :return: Group counts if repaired, or None if exchanges become stuck.
    """
    counts = [Counter(groups[item] for item in bundle) for bundle in bundles]
    while True:
        conflicts = [
            (index, slot)
            for index, bundle in enumerate(bundles)
            for slot, item in enumerate(bundle)
            if counts[index][groups[item]] > 1
        ]
        if not conflicts:
            return counts
        rng.shuffle(conflicts)
        repaired = False
        for left, left_slot in conflicts:
            a = bundles[left][left_slot]
            candidates = slots[strata[a]].copy()
            rng.shuffle(candidates)
            for right, right_slot in candidates:
                b = bundles[right][right_slot]
                if left != right and counts[right][groups[a]] == 0 and counts[left][groups[b]] == 0:
                    _swap(bundles, counts, groups, (left, left_slot), (right, right_slot))
                    repaired = True
                    break
            if repaired:
                break
        if not repaired:
            return None


def _companions(bundles):
    """
    Count how often each unordered pair of comparisons shares a bundle.

    :param bundles: Bundle membership.
    :return: Companion co-occurrence counts.
    """
    return Counter(_edge(a, b) for bundle in bundles for a, b in combinations(bundle, 2))


def _context_summary(counts, item_count):
    """
    Summarize repeated context and distinct companions per comparison.

    :param counts: Companion co-occurrence counts.
    :param item_count: Number of unique comparisons.
    :return: Context-diversity statistics.
    """
    diversity = [0] * item_count
    for (a, b), count in counts.items():
        if count:
            diversity[a] += 1
            diversity[b] += 1
    return {
        "collision_cost": sum(count * (count - 1) // 2 for count in counts.values()),
        "cooccurrence_histogram": dict(sorted(Counter(count for count in counts.values() if count).items())),
        "distinct_companions_min": min(diversity),
        "distinct_companions_mean": sum(diversity) / item_count,
        "distinct_companions_max": max(diversity),
    }


def _mix_context(bundles, slots, groups, strata, group_counts, rng, iterations):
    """
    Reduce repeated companions without changing coverage or hard constraints.

    The cost counts pairs of occurrences of the same companion relationship.
    Only non-increasing-cost swaps are accepted; this is not a global optimizer.

    :param bundles: Mutable, initially feasible and distinct bundles.
    :param slots: All slots indexed by stratum.
    :param groups: Source group per comparison.
    :param strata: Stratum per comparison.
    :param group_counts: Source-group counts per bundle.
    :param rng: Local seeded random generator.
    :param iterations: Maximum number of proposed swaps.
    :return: Initial and final context statistics and accepted swap count.
    """
    counts = _companions(bundles)
    before = _context_summary(counts, len(groups))
    cost = before["collision_cost"]
    signatures = [frozenset(bundle) for bundle in bundles]
    seen = set(signatures)
    accepted = 0
    for _ in range(iterations):
        if cost == 0:
            break
        left = rng.randrange(len(bundles))
        left_slot = rng.randrange(len(bundles[left]))
        a = bundles[left][left_slot]
        right, right_slot = rng.choice(slots[strata[a]])
        b = bundles[right][right_slot]
        if left == right or group_counts[left][groups[b]] or group_counts[right][groups[a]]:
            continue
        old_left, old_right = signatures[left], signatures[right]
        new_left = (old_left - {a}) | {b}
        new_right = (old_right - {b}) | {a}
        if new_left == new_right or any(
            signature in seen and signature not in (old_left, old_right) for signature in (new_left, new_right)
        ):
            continue
        left_only = (old_left - {a}) - (old_right - {b})
        right_only = (old_right - {b}) - (old_left - {a})
        transfers = [(_edge(a, item), _edge(b, item)) for item in sorted(left_only)]
        transfers.extend((_edge(b, item), _edge(a, item)) for item in sorted(right_only))
        change = sum(counts[new] - counts[old] + 1 for old, new in transfers)
        if change > 0:
            continue
        for old, new in transfers:
            counts[old] -= 1
            counts[new] += 1
        _swap(bundles, group_counts, groups, (left, left_slot), (right, right_slot))
        seen.difference_update((old_left, old_right))
        seen.update((new_left, new_right))
        signatures[left], signatures[right] = new_left, new_right
        cost += change
        accepted += 1
    after = _context_summary(counts, len(groups))
    return before, after, accepted


def pack_sessions(
    rows, *, repeats, session_size, id_column="item_id", group_column=None,
    stratum_column=None, quotas=None, seed=0, iterations=100000,
):
    """
    Jointly pack repeated comparisons, without fixed bundles or partitions.

    Every item receives equal coverage and exact A-first/B-first balance.
    Source groups cannot repeat within a bundle. Input order is immaterial.

    :param rows: Input records with unique IDs and optional source/stratum columns.
    :param repeats: Positive even number of appearances per comparison.
    :param session_size: Main comparisons per bundle, excluding training/controls.
    :param id_column: Column identifying a canonical A/B comparison.
    :param group_column: Optional column identifying mutually exclusive source scenes.
    :param stratum_column: Optional column whose values have per-bundle quotas.
    :param quotas: Required per-bundle counts when stratum_column is supplied.
    :param seed: Local random seed for reproducibility.
    :param iterations: Nonnegative context-optimization proposal budget.
    :return: Long-format assignments and an audit dictionary.
    """
    if not isinstance(repeats, int) or repeats <= 0 or repeats % 2:
        raise ValueError("repeats must be a positive even integer for exact playback-order balance.")
    if not isinstance(session_size, int) or session_size <= 0:
        raise ValueError("session_size must be a positive integer.")
    if not isinstance(iterations, int) or iterations < 0:
        raise ValueError("iterations must be a nonnegative integer.")
    rows = list(rows)
    identifiers = _column(rows, id_column)
    if not rows or len(set(identifiers)) != len(rows):
        raise ValueError("Input must contain at least one comparison and unique item IDs.")
    rows = sorted(rows, key=lambda row: row[id_column])
    identifiers = _column(rows, id_column)
    groups = _column(rows, group_column) if group_column else identifiers
    strata = _column(rows, stratum_column) if stratum_column else ["all"] * len(rows)
    if stratum_column is None and quotas is not None:
        raise ValueError("quotas requires stratum_column.")
    quotas = dict(quotas) if quotas is not None else {"all": session_size}
    if set(quotas) != set(strata) or any(
        not isinstance(value, int) or value <= 0 for value in quotas.values()
    ) or sum(quotas.values()) != session_size:
        raise ValueError("Positive quotas must match the input strata and sum to session_size.")
    total = len(rows) * repeats
    if total % session_size:
        raise ValueError("Total appearances must be divisible by session_size; padding is not allowed.")
    bundle_count = total // session_size
    stratum_counts = Counter(strata)
    if any(stratum_counts[key] * repeats != bundle_count * quota for key, quota in quotas.items()):
        raise ValueError("Stratum coverage is incompatible with equal repeats and per-bundle quotas.")
    if any(count * repeats > bundle_count for count in Counter(groups).values()):
        raise ValueError("A source group needs more appearances than there are bundles.")
    possible = math.prod(math.comb(stratum_counts[key], quota) for key, quota in quotas.items())
    if possible < bundle_count:
        raise ValueError("Not enough distinct bundle memberships for these settings.")
    rng = random.Random(seed)
    for _ in range(32):
        bundles = [[] for _ in range(bundle_count)]
        slots = {}
        for stratum, quota in sorted(quotas.items()):
            pool = [index for index, value in enumerate(strata) if value == stratum] * repeats
            rng.shuffle(pool)
            offset = len(bundles[0])
            slots[stratum] = [
                (index, position) for index in range(bundle_count) for position in range(offset, offset + quota)
            ]
            for index, bundle in enumerate(bundles):
                bundle.extend(pool[index * quota:(index + 1) * quota])
        group_counts = _repair_groups(bundles, slots, groups, strata, rng)
        if group_counts is not None and len({frozenset(bundle) for bundle in bundles}) == bundle_count:
            break
    else:
        raise RuntimeError(
            "Could not construct distinct, source-disjoint bundles; review constraints or try another seed.")
    before, after, accepted = _mix_context(bundles, slots, groups, strata, group_counts, rng, iterations)
    rng.shuffle(bundles)
    occurrences = [[] for _ in rows]
    assignments = []
    for index, bundle in enumerate(bundles, 1):
        rng.shuffle(bundle)
        for position, item in enumerate(bundle, 1):
            record = {"bundle_id": f"bundle-{index:04d}", "position": position, "item_id": identifiers[item]}
            assignments.append(record)
            occurrences[item].append(record)
    for records in occurrences:
        rng.shuffle(records)
        for index, record in enumerate(records):
            record["order"] = "ab" if index < repeats // 2 else "ba"
    audit = {
        "items": len(rows), "bundles": bundle_count, "session_size": session_size, "repeats": repeats,
        "appearances": total, "seed": seed, "iterations": iterations, "accepted_context_swaps": accepted,
        "id_column": id_column, "group_column": group_column, "stratum_column": stratum_column,
        "quotas": quotas, "orders_per_item": {"ab": repeats // 2, "ba": repeats // 2},
        "unique_bundle_memberships": len({frozenset(bundle) for bundle in bundles}),
        "context_before": before, "context_after": after,
        "optimization": "Seeded non-increasing-cost local search; no claim of global optimality.",
        "allocation": (
            "One completion per bundle. Distinct URLs do not prevent repeated items across a participant's sessions."
        ),
        "scope": "Main comparisons only; training, controls, hosting and participant routing are not generated.",
    }
    return assignments, audit


def main(argv=None):
    """
    Generate a long-format assignment CSV and its reproducibility audit.

    :param argv: Optional command-line argument list.
    :return: None.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--repeats", type=int, required=True)
    parser.add_argument("--session-size", type=int, required=True)
    parser.add_argument("--id-column", default="item_id")
    parser.add_argument("--group-column")
    parser.add_argument("--stratum-column")
    parser.add_argument("--quota", action="append", default=[], metavar="STRATUM=COUNT")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=100000)
    args = parser.parse_args(argv)
    paths = [path.resolve() for path in (args.input, args.output, args.audit)]
    if len(set(paths)) != 3:
        parser.error("Input, output and audit paths must be different.")
    if args.output.exists() or args.audit.exists():
        parser.error("Output files already exist; choose new paths to preserve earlier assignments.")
    try:
        quotas = {}
        for entry in args.quota:
            key, value = entry.rsplit("=", 1)
            if key in quotas:
                raise ValueError(f"Duplicate quota for {key!r}.")
            quotas[key] = int(value)
        source = args.input.read_bytes()
        rows = list(csv.DictReader(io.StringIO(source.decode("utf-8-sig"), newline="")))
        assignments, audit = pack_sessions(
            rows, repeats=args.repeats, session_size=args.session_size, id_column=args.id_column,
            group_column=args.group_column, stratum_column=args.stratum_column, quotas=quotas or None,
            seed=args.seed, iterations=args.iterations,
        )
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    audit["input_sha256"] = hashlib.sha256(source).hexdigest()
    for path in (args.output, args.audit):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["bundle_id", "position", "item_id", "order"])
        writer.writeheader()
        writer.writerows(assignments)
    audit["assignment_sha256"] = hashlib.sha256(args.output.read_bytes()).hexdigest()
    with args.audit.open("x", encoding="utf-8", newline="") as output:
        output.write(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: audit[key] for key in ("items", "bundles", "appearances", "context_after")}))


if __name__ == "__main__":
    main()
