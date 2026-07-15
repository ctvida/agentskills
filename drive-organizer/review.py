#!/usr/bin/env python3
"""Grouped review tool for governed_actions.csv.

Reviewing thousands of proposed moves row-by-row is impractical. This tool
groups proposals by destination folder so whole groups can be approved or
rejected in one command.

Usage:
    python3 review.py                     # print grouped summary, write review_summary.md
    python3 review.py --reject '/Archive/*'    # set approved=FALSE where proposed_path matches
    python3 review.py --approve '/Finance/*'   # set approved=TRUE where proposed_path matches
    python3 review.py --selfcheck         # run built-in sanity test

Patterns are shell globs matched against proposed_path (exact match also counts).
--approve/--reject may be repeated; they are applied in command-line order, then
the CSV is rewritten in place and the summary regenerated.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from fnmatch import fnmatch

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SKILL_DIR, 'governed_actions.csv')
SUMMARY_PATH = os.path.join(SKILL_DIR, 'review_summary.md')
SAMPLE_NAMES = 5


def load_rows(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def save_rows(path, rows):
    if not rows:
        return
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def matches(dest, pattern):
    return dest == pattern or fnmatch(dest, pattern)


def set_approval(rows, pattern, value):
    """Set approved=value on rows whose proposed_path matches pattern. Returns count."""
    n = 0
    for r in rows:
        if matches(r.get('proposed_path', ''), pattern):
            r['approved'] = value
            n += 1
    return n


def group(rows):
    groups = defaultdict(lambda: {'files': [], 'sources': defaultdict(int), 'approved': 0})
    for r in rows:
        g = groups[r.get('proposed_path', '')]
        g['files'].append(r.get('file_name', ''))
        g['sources'][r.get('current_path', '')] += 1
        if r.get('approved', '').strip().upper() == 'TRUE':
            g['approved'] += 1
    return groups


def render_summary(rows):
    groups = group(rows)
    total = len(rows)
    approved = sum(g['approved'] for g in groups.values())
    lines = [
        '# Review Summary — governed_actions.csv',
        '',
        f'**{total} proposed moves into {len(groups)} destination folders. '
        f'{approved} currently approved.**',
        '',
        'Bulk actions: `python3 review.py --reject \'/Some/Dest/*\'` or `--approve <glob>`.',
        'Fine-grained edits: change the `approved` column in governed_actions.csv directly.',
        '',
        '| Destination | Files | Approved | Top sources | Sample files |',
        '|---|---|---|---|---|',
    ]
    for dest, g in sorted(groups.items(), key=lambda kv: -len(kv[1]['files'])):
        top_sources = ', '.join(
            f'{s} ({n})' for s, n in sorted(g['sources'].items(), key=lambda kv: -kv[1])[:3]
        )
        samples = ', '.join(g['files'][:SAMPLE_NAMES])
        if len(g['files']) > SAMPLE_NAMES:
            samples += f', … +{len(g["files"]) - SAMPLE_NAMES} more'
        lines.append(
            f'| `{dest}` | {len(g["files"])} | {g["approved"]}/{len(g["files"])} '
            f'| {top_sources} | {samples} |'
        )
    return '\n'.join(lines) + '\n'


def selfcheck():
    rows = [
        {'file_name': 'a.pdf', 'current_path': '/Misc/', 'file_id': '1',
         'proposed_path': '/Finance/Taxes', 'approved': 'TRUE'},
        {'file_name': 'b.jpg', 'current_path': '/Misc/', 'file_id': '2',
         'proposed_path': '/Media/Photos', 'approved': 'TRUE'},
        {'file_name': 'c.jpg', 'current_path': '/Old/', 'file_id': '3',
         'proposed_path': '/Media/Photos', 'approved': 'TRUE'},
    ]
    assert set_approval(rows, '/Media/*', 'FALSE') == 2
    assert [r['approved'] for r in rows] == ['TRUE', 'FALSE', 'FALSE']
    assert set_approval(rows, '/Finance/Taxes', 'FALSE') == 1  # exact match, no glob chars
    groups = group(rows)
    assert len(groups) == 2 and len(groups['/Media/Photos']['files']) == 2
    assert groups['/Media/Photos']['approved'] == 0
    assert '| `/Media/Photos` | 2 |' in render_summary(rows)
    print('selfcheck OK')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--approve', action='append', default=[], metavar='GLOB')
    parser.add_argument('--reject', action='append', default=[], metavar='GLOB')
    parser.add_argument('--csv', default=CSV_PATH, help='path to governed_actions.csv')
    parser.add_argument('--selfcheck', action='store_true')
    args = parser.parse_args()

    if args.selfcheck:
        selfcheck()
        return

    if not os.path.exists(args.csv):
        sys.exit(f'Error: {args.csv} not found. Run scanner.py then proposer.py first.')

    rows = load_rows(args.csv)
    changed = False
    for pattern in args.approve:
        print(f'approve {pattern!r}: {set_approval(rows, pattern, "TRUE")} rows')
        changed = True
    for pattern in args.reject:
        print(f'reject  {pattern!r}: {set_approval(rows, pattern, "FALSE")} rows')
        changed = True
    if changed:
        save_rows(args.csv, rows)

    summary = render_summary(rows)
    with open(SUMMARY_PATH, 'w') as f:
        f.write(summary)
    print(summary)
    print(f'Written to {SUMMARY_PATH}')


if __name__ == '__main__':
    main()
