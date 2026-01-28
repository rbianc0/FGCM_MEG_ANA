# AGENTS.md - FGCM MEG to BIDS Conversion

## Project Structure

```
FGCM_MEG_ANA_PY/
├── AGENTS.md                 # Project specifications and guidelines (this file)
├── pyproject.toml            # Python project configuration
├── FGCM_Demographics.csv     # Subject list (local-only, git-ignored)
│
├── dfgt/                     # Main Python package (reusable modules)
│   ├── __init__.py           # Package initialization
│   ├── config.py             # Paths, channel maps, task definitions
│   ├── io.py                 # Data loading (CTF, BIDS, epochs)
│   ├── bids.py               # BIDS conversion functions
│   ├── preproc.py            # MEG preprocessing pipeline
│   └── utils.py              # Shared utilities (triggers, subject mapping)
│
├── scripts/                  # Executable scripts
│   └── convert_to_bids.py    # Batch BIDS conversion CLI
│
├── notebooks/                # Jupyter notebooks for visualization
│   └── 01_data_exploration.ipynb
│
└── figures/                  # Output figures directory
```

## Module Descriptions

### dfgt/config.py
Central configuration file containing:
- **Data paths**: MEG_RAW_ROOT, BIDS_ROOT, DERIVATIVES_ROOT, BEH_ROOT
- **FGCM channel map**: ECG, UPPT001/UPPT002 (stim), UADC005-007 (eyegaze/pupil via prefix match)
- **Task mapping**: A/B group randomization (runs 01-06)
- **Processing parameters**: ICA settings, power line frequency, anonymization

### dfgt/io.py
Data loading utilities:
- `load_raw_ctf()`: Load CTF MEG data (.ds directories)
- `load_raw_bids()`: Load from BIDS format
- `load_epochs()`: Load preprocessed epochs
- `get_raw_path()`: Construct path to raw data
- `get_bids_path()`: Construct BIDSPath object

### dfgt/bids.py
BIDS conversion functions:
- `convert_to_bids()`: Single subject/task conversion
- `batch_convert()`: Batch conversion with progress tracking
- `update_channel_types()`: Apply channel type mappings
- `check_trigger_consistency()`: Report trigger label counts per run
- `create_dataset_description()`: Generate dataset_description.json
- `create_participants_tsv()`: Generate participants.tsv

### dfgt/preproc.py
MEG preprocessing pipeline:
- `preprocess()`: Main preprocessing pipeline
- `apply_gradient_compensation()`: CTF compensation
- `filter_raw()`: Bandpass and notch filtering
- `run_ica()`: ICA artifact removal
- `create_epochs()`: Epoch creation
- `reject_artifacts_autoreject()`: Automatic artifact rejection

### dfgt/utils.py
Shared utilities:
- `source_id_to_bids_id()`: Convert C01 → 001
- `bids_id_to_source_id()`: Convert 001 → C01
- `get_subject_group()`: Determine A/B group
- `fix_inverted_triggers()`: Relabel Gen triggers for C03/C04 (Gen1↔Gen7, Gen2↔Gen6, Gen3↔Gen5)
- `load_subject_list()`: Load subject list file

### scripts/convert_to_bids.py
CLI script for batch conversion:
```bash
# Convert all subjects
python scripts/convert_to_bids.py

# Convert single subject
python scripts/convert_to_bids.py --subject C01

# Dry run
python scripts/convert_to_bids.py --dry-run
```

### notebooks/
Jupyter notebooks for interactive analysis and visualization.

---

## Project Specifications

| Item | Value |
|------|-------|
| **Study** | FGCM (FearGenCrossMod) |
| **Data Format** | CTF MEG (.ds directories) |
| **Source** | `/media/bianco/LaCie/DATA/DFGT/FGCM_MEG_RAW/` |
| **Output** | `/media/bianco/LaCie/DATA/DFGT/FGCM_BIDS/` |
| **Subjects** | From FGCM_Demographics.csv (local-only, git-ignored) |
| **Tasks** | audio_base, audio_cond, audio_test, visual_base, visual_cond, visual_test |
| **Stack** | Python >=3.13, mne >=1.10.2, mne-bids >=0.17.0, uv |

## Data Structure

```
FGCM_MEG_RAW/
└── C01/
    └── C01-1/
        └── A3122_FearGenTinn_20230425_01.ds  (runs 01-06)
```

Raw .ds filenames may still include FearGenTinn; keep those as-is.

## Task Mapping (A/B Randomization)

| Task | A-group run | B-group run |
|------|-------------|-------------|
| audio_base | 01 | 04 |
| audio_cond | 02 | 05 |
| audio_test | 03 | 06 |
| visual_base | 04 | 01 |
| visual_cond | 05 | 02 |
| visual_test | 06 | 03 |

## Channel Configuration (FGCM-specific)

| Channel | BIDS Type | Status |
|---------|-----------|--------|
| ECG | ecg | Available |
| UADC005/006 | eyegaze | Available |
| UADC007 | pupil | Available |
| UPPT001/UPPT002 | stim | Available |
| EOGvert/EOGhor | - | NOT PRESENT |
| UADC001 (Respiration) | - | NOT PRESENT |

## Trigger Labels (CTF markers)

Labels are taken from CTF markers (MarkerFile.mrk) and written to BIDS `events.tsv`.

Full label union across tasks:
`startACQ`, `CSminus`, `CSplusUnpaired`, `CSplusPaired`, `Gen1`, `Gen2`, `Gen3`,
`Gen4`, `Gen5`, `Gen6`, `Gen7`, `USface`, `WarningTrial`, `acTrgBeep`, `acTrgScream`.

Task-specific label sets (from a full C01 conversion):

| Task | Labels |
|------|--------|
| audio_base | startACQ, CSminus, CSplusUnpaired, Gen1-Gen7, USface, WarningTrial, acTrgBeep, acTrgScream |
| audio_cond | startACQ, CSminus, CSplusUnpaired, CSplusPaired, USface, acTrgBeep, acTrgScream |
| audio_test | startACQ, CSminus, CSplusUnpaired, CSplusPaired, Gen1-Gen7, USface, acTrgBeep, acTrgScream |
| visual_base | startACQ, CSminus, CSplusUnpaired, Gen1-Gen7, USface, WarningTrial, acTrgScream |
| visual_cond | startACQ, CSminus, CSplusUnpaired, CSplusPaired, USface, acTrgScream |
| visual_test | startACQ, CSminus, CSplusUnpaired, CSplusPaired, Gen1-Gen7, USface, acTrgScream |

## Critical Requirements

1. **MEGGRADAXIAL Support**: Use mne-bids >=0.17.0 (includes MEGGRADAXIAL mapping)
2. **Modular Design**: Functions must be reusable for future DFGT conversion
3. **No MRI**: Skip anatomical data processing
4. **Trigger Fix**: Relabel Gen triggers for C03/C04 during conversion
5. **BIDS IDs**: Use standard format sub-001, sub-002... (not sub-C01)

## Subject Handling Rules

- Convert ONLY subjects present in `FGCM_Demographics.csv` (local-only list)
- Use `megid` as the source ID (ignore `subid`)
- Ignore #MERGE comments - convert recordings as-is
- Fix inverted triggers for C03, C04 during conversion
- Map C01->sub-001, C02->sub-002, etc.

## Known Issues (Documented)

| Subject | Issue | Action |
|---------|-------|--------|
| C03, C04 | Gen triggers mis-assigned | Relabel Gen1↔Gen7, Gen2↔Gen6, Gen3↔Gen5 |
|          |                      |                       |

## Output Structure

```
FGCM_BIDS/
├── dataset_description.json
├── participants.tsv
├── sub-001/
│   └── meg/
│       ├── sub-001_task-audiobase_meg.ds/
│       ├── sub-001_task-audiobase_channels.tsv
│       ├── sub-001_task-audiobase_meg.json
│       └── ...
└── sub-002/
    └── ...
```

## Dependencies

```toml
[project]
requires-python = ">=3.13"
dependencies = [
    "mne>=1.10.2",
    "mne-bids>=0.17.0",
    "pandas",
]
```

## Git & GitHub Workflow

### Branch Naming Convention
All development work must be done on feature branches following this pattern:
```
agent/<feature-name>
```

Examples:
- `agent/refactor-folder-structure`
- `agent/add-preprocessing-pipeline`
- `agent/fix-trigger-inversion`

### Commit Guidelines
- **Commit frequently** with meaningful, atomic commits
- Use descriptive commit messages following conventional format:
  - `feat:` New feature
  - `fix:` Bug fix
  - `refactor:` Code refactoring
  - `docs:` Documentation updates
  - `chore:` Maintenance tasks

Example messages:
```bash
git commit -m "feat: add modular dfgt package with io, bids, preproc modules"
git commit -m "refactor: reorganize project structure for reusability"
git commit -m "docs: update AGENTS.md with git workflow requirements"
```

### GitHub CLI Workflow
Use `gh` CLI for all GitHub operations:

```bash
# Create feature branch
git checkout -b agent/feature-name

# Stage and commit changes
git add .
git commit -m "feat: description of changes"

# Push to remote
git push -u origin agent/feature-name

# Create pull request for review
gh pr create --title "Feature: Description" --body "Summary of changes"
```

### Pull Request Requirements
1. All changes must go through PR review before merging to `main`
2. PR title should be descriptive
3. PR body should include:
   - Summary of changes
   - Any breaking changes
   - Testing notes if applicable

### Protected Branches
- `main` - Production-ready code, requires PR review
