# Data

The complete benchmark is downloaded from the pinned upstream source and is not committed here.

```bash
python scripts/download_data.py
```

The command downloads and verifies:

- `train_data.csv`
- `test_data.csv`
- `one_shot_data.csv`

from MedCalc-Bench Verified v1.0.7.

The two committed processed artifacts are:

- `processed/few_shot_selected_train_rows_k3.csv`: the selected training-row manifest.
- `processed/case_library_template_v1_8.json`: calculator schemas and three
  same-calculator demonstration records, with every patient-note field blank.

`scripts/download_data.py` reconstructs the ignored
`processed/case_library_merged_v1_8.json` from the pinned training CSV and the
committed row-number metadata. This keeps complete patient-note text out of Git
while preserving a deterministic preparation path. To rebuild it separately:

```bash
python scripts/prepare_case_library.py
```

The template and manifest are adaptations of MedCalc-Bench Verified and remain
under CC BY-SA 4.0. See [NOTICE.md](../NOTICE.md). Although the benchmark is
public and contains synthetic, template-generated, or published-note-derived
text, do not treat it as de-identified clinical data for unrelated deployment.
