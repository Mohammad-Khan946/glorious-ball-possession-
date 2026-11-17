# Tactical ball possession

This program generates the Phase 1 possession CSV from the tactical camera's automatic tracking and Smart Tagging files. It uses the Python standard library. Python 3.10 or newer is sufficient.

## Reproduce the output

1. Put the following files from the competition Drive in a local folder. Keep their original names.
   - `BAR-ATH_tactical_atd.txt`
   - `BAR-ATH_tactical_atd.xml`
   - `BAR-ATH_tactical_smart_tagging.xml`
2. From this project folder, run the command below. Use the registered team name in place of TEAM_NAME. The data argument accepts either the directory containing the files or its parent if the directory is named tactical.

```powershell
python predict.py --data "$env:USERPROFILE\Downloads" --output "TEAM_NAME.csv"
```

The output has 199,319 ordered rows after the header. Frames are zero-indexed. Use the competition repository's official validator on the resulting file. From the root of the official repository, run:

```powershell
python -m pip install -r requirements.txt
python evaluation/validate_submission.py "C:\path\to\TEAM_NAME.csv"
```

For a public-window pipeline check, place a copy in the official repository's `evaluation/results/` and run `python evaluation/run_evaluation.py`. Keep the team-named prediction and technical document for the submission form. The code repository should contain source and documentation. Keep licensed match inputs local.

[Official repository](https://github.com/metrica-sports/more-than-a-hack-2027)
