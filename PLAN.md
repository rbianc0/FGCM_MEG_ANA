# PLAN.md - CTF MEG to BIDS Conversion Pipeline

## Overview

Convert FGT (FearGenTinn) CTF MEG data to BIDS format using mne-python and mne-bids.
Design modular functions for future DFGT dataset reuse.

**Scope**: 41 subjects, 6 tasks each = 246 MEG recordings

---

## Project Structure

```
DFGT_MEG_ANA_PY/
├── AGENTS.md                 # Project specifications and guidelines
├── PLAN.md                   # Conversion pipeline plan (this file)
├── pyproject.toml            # Python project configuration
├── FGT_MEG_subject_list.csv  # Subject list (41 subjects)
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

---

## Phase 1: Environment Setup

### Step 1.1: Sync uv environment
```bash
cd /home/bianco/Documents/DFGT/DFGT_MEG_ANA_PY
uv sync
```

### Step 1.2: Install bids-validator
```bash
# Option A: npm (recommended)
npm install -g bids-validator

# Option B: pip
uv add bids-validator
```

### Step 1.3: Apply MEGGRADAXIAL patch
**Location**: `.venv/lib/python3.13/site-packages/mne_bids/utils.py`

**Change at line ~82** (in `_get_ch_type_mapping` or similar):
```python
# Add MEGGRADAXIAL to the magnetometer mapping
mag="MEGGRADAXIAL"
```

### Step 1.4: Verify paths
```bash
# Check source data accessible
ls /media/bianco/LaCie/DATA/DFGT/FGT_MEG_RAW/C01/

# Check output directory exists
mkdir -p /media/bianco/LaCie/DATA/DFGT/DFGT_BIDS
```

---

## Phase 2: Single Subject Test

### Step 2.1: Test conversion (C01 -> sub-001)

```python
from dfgt.bids import convert_to_bids

# Convert one task
convert_to_bids("C01", "audio_base")
```

### Step 2.2: Validate output structure

```bash
# Check files created
ls -la /media/bianco/LaCie/DATA/DFGT/DFGT_BIDS/sub-001/meg/

# Expected files:
# sub-001_task-audiobase_meg.ds/
# sub-001_task-audiobase_channels.tsv
# sub-001_task-audiobase_meg.json
```

### Step 2.3: Verify channels.tsv

```bash
cat /media/bianco/LaCie/DATA/DFGT/DFGT_BIDS/sub-001/meg/sub-001_task-audiobase_channels.tsv
```

Confirm:
- ECG marked as `ecg`
- UADC005/006/007 marked as `eyetrack`
- UPPT01 marked as `stim`
- NO EOG or RESP entries

### Step 2.4: Run bids-validator

```bash
bids-validator /media/bianco/LaCie/DATA/DFGT/DFGT_BIDS --verbose
```

---

## Phase 3: Batch Conversion

### Step 3.1: Run batch conversion

```bash
# Dry run first
python scripts/convert_to_bids.py --dry-run

# Full conversion
python scripts/convert_to_bids.py
```

### Step 3.2: Generate dataset files

The script automatically creates:
- `dataset_description.json`
- `participants.tsv`

---

## Phase 4: Validation & Documentation

### Step 4.1: Final BIDS validation

```bash
bids-validator /media/bianco/LaCie/DATA/DFGT/DFGT_BIDS
```

Expected output: No errors (warnings acceptable for MEG-specific fields)

### Step 4.2: Generate conversion report

```python
# conversion_report.txt
"""
FGT -> BIDS Conversion Report
=============================
Date: YYYY-MM-DD
Subjects attempted: 41
Subjects converted: XX
Failed: XX

Failed subjects:
- C03: [reason]
- ...

Notes:
- Trigger inversion applied to: C03, C04
- #MERGE subjects converted as single recordings
"""
```

### Step 4.3: Update project README

Document:
- MEGGRADAXIAL patch requirement
- Conversion command
- Known issues and handling

---

## Checklist

### Environment
- [ ] uv sync completed
- [ ] bids-validator installed
- [ ] MEGGRADAXIAL patch applied
- [ ] External drive mounted

### Testing
- [ ] Single subject test passed
- [ ] channels.tsv verified (correct types)
- [ ] bids-validator passes

### Batch Conversion
- [ ] All 41 subjects converted
- [ ] All 6 tasks per subject
- [ ] dataset_description.json created
- [ ] participants.tsv created

### Final
- [ ] bids-validator passes on full dataset
- [ ] Conversion report generated
- [ ] README updated

---

## File Structure After Completion

```
DFGT_MEG_ANA_PY/
├── AGENTS.md
├── PLAN.md
├── pyproject.toml
├── FGT_MEG_subject_list.csv
├── dfgt/
│   ├── __init__.py
│   ├── config.py
│   ├── io.py
│   ├── bids.py
│   ├── preproc.py
│   └── utils.py
├── scripts/
│   └── convert_to_bids.py
├── notebooks/
│   └── 01_data_exploration.ipynb
└── figures/

DFGT_BIDS/
├── dataset_description.json
├── participants.tsv
├── README                       # Optional
├── sub-001/
│   └── meg/
│       ├── sub-001_task-audiobase_meg.ds/
│       ├── sub-001_task-audiobase_channels.tsv
│       ├── sub-001_task-audiobase_meg.json
│       ├── sub-001_task-audiocond_meg.ds/
│       └── ... (6 tasks)
├── sub-002/
└── ... (41 subjects)
```
