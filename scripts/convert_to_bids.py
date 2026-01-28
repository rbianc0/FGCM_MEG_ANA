#!/usr/bin/env python
"""
Batch convert FGCM MEG data to BIDS format.

Usage:
    python scripts/convert_to_bids.py [--subject C01] [--task audio_base] [--dry-run]

Examples:
    # Convert all subjects and tasks
    python scripts/convert_to_bids.py

    # Convert single subject
    python scripts/convert_to_bids.py --subject C01

    # Dry run (show what would be converted)
    python scripts/convert_to_bids.py --dry-run
"""

import argparse
from pathlib import Path

from dfgt.bids import batch_convert, create_dataset_description, create_participants_tsv
from dfgt.config import BIDS_ROOT, FGCM_TASKS, SUBJECT_LIST_CSV
from dfgt.utils import get_valid_subjects


def main():
    parser = argparse.ArgumentParser(description="Convert FGCM MEG data to BIDS format")
    parser.add_argument(
        "--subject",
        type=str,
        help="Convert single subject (e.g., C01)",
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Convert single task (e.g., audio_base)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without doing it",
    )
    parser.add_argument(
        "--bids-root",
        type=Path,
        default=BIDS_ROOT,
        help="BIDS output directory",
    )

    args = parser.parse_args()

    # Get subject list
    if args.subject:
        subjects = [args.subject]
    else:
        subjects = get_valid_subjects(SUBJECT_LIST_CSV)

    # Get task list
    if args.task:
        tasks = [args.task]
    else:
        tasks = FGCM_TASKS

    print(f"Subjects to convert: {len(subjects)}")
    print(f"Tasks per subject: {len(tasks)}")
    print(f"Total conversions: {len(subjects) * len(tasks)}")
    print(f"Output: {args.bids_root}")

    if args.dry_run:
        print("\n[DRY RUN] Would convert:")
        for subj in subjects:
            for task in tasks:
                print(f"  - {subj} / {task}")
        return

    # Create output directory
    args.bids_root.mkdir(parents=True, exist_ok=True)

    # Run batch conversion
    results = batch_convert(subjects, tasks, bids_root=args.bids_root)

    # Create dataset files
    print("\nCreating dataset files...")
    create_dataset_description(bids_root=args.bids_root)
    create_participants_tsv(bids_root=args.bids_root)

    # Summary
    print("\n" + "=" * 50)
    print(f"Completed: {len(results['success'])}/{len(subjects) * len(tasks)}")
    print(f"Failed: {len(results['failed'])}")

    if results["failed"]:
        print("\nFailed conversions:")
        for subj, task, error in results["failed"]:
            print(f"  - {subj} / {task}: {error}")


if __name__ == "__main__":
    main()
