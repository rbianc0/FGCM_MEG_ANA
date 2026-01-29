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

    # Add Polhemus headshape files only (after conversion already exists)
    python scripts/convert_to_bids.py --only-headshape
"""

import argparse
from pathlib import Path

from dfgt.bids import (
    add_headshape_files,
    batch_convert,
    create_dataset_description,
    create_participants_tsv,
)
from dfgt.config import BIDS_ROOT, FGCM_TASKS, POS_ROOT, SUBJECT_LIST_CSV
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
    parser.add_argument(
        "--pos-root",
        type=Path,
        default=POS_ROOT,
        help="Directory with Polhemus .pos files",
    )
    parser.add_argument(
        "--add-headshape",
        action="store_true",
        help="Add Polhemus headshape files after conversion",
    )
    parser.add_argument(
        "--only-headshape",
        action="store_true",
        help="Only add headshape files; skip MEG conversion",
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

    run_conversion = not args.only_headshape
    run_headshape = args.add_headshape or args.only_headshape

    if run_conversion:
        print(f"Subjects to convert: {len(subjects)}")
        print(f"Tasks per subject: {len(tasks)}")
        print(f"Total conversions: {len(subjects) * len(tasks)}")
        print(f"Output: {args.bids_root}")
    else:
        print("Skipping conversion; only adding headshape files.")
        print(f"Subjects to update: {len(subjects)}")
        print(f"Output: {args.bids_root}")

    if args.dry_run:
        if run_conversion:
            print("\n[DRY RUN] Would convert:")
            for subj in subjects:
                for task in tasks:
                    print(f"  - {subj} / {task}")
        if run_headshape:
            print("\n[DRY RUN] Would add headshape files:")
            for subj in subjects:
                print(f"  - {subj}")
        return

    if run_conversion:
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

    if run_headshape:
        headshape_results = add_headshape_files(
            subjects,
            bids_root=args.bids_root,
            pos_root=args.pos_root,
            dry_run=args.dry_run,
        )
        print("\n" + "=" * 50)
        print(f"Headshape updated: {len(headshape_results['success'])}")
        print(f"Headshape skipped: {len(headshape_results['skipped'])}")
        print(f"Headshape failed: {len(headshape_results['failed'])}")

        if headshape_results["failed"]:
            print("\nFailed headshape updates:")
            for subj, error in headshape_results["failed"]:
                print(f"  - {subj}: {error}")


if __name__ == "__main__":
    main()
