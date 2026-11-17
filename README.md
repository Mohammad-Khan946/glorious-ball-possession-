# Glorious — Ball Possession Prediction

Team Glorious’s solution for Phase 1 of More Than a Hack 2027.

The Python pipeline predicts ball possession for every frame of the provided Barcelona vs Athletic Club match using automatic tactical tracking and event tags.

## Output

The program generates a CSV containing 199,319 predictions at 25 frames per second.

| Label | Meaning |
|------|---------|
| H | Home team in possession |
| A | Away team in possession |
| D | Dead ball |
| X | No prediction, including pre-match, halftime and post-match footage |

The output format is:

```csv
frame,label
0,X
1,X
2,X
```

## Requirements

- Python 3.10 or newer
- Python standard library only

The organisers’ evaluation tools separately require the packages listed in their `requirements.txt`.

## Input files

Obtain these files from the organisers and place them in `data/tactical/`.

```text
data/
└── tactical/
    ├── BAR-ATH_tactical_atd.txt
    ├── BAR-ATH_tactical_atd.xml
    └── BAR-ATH_tactical_smart_tagging.xml
```

The pipeline uses player and ball positions, team assignments and automatic tactical event tags. Videos and homography files are optional assets that this implementation does not use.

Match data is licensed separately by the organisers. Keep the input files out of the public repository.

## Run the predictor

From the folder containing `predict.py`, run:

```powershell
python predict.py --data data --output glorious.csv
```

You can also specify a folder that directly contains the three input files:

```powershell
python predict.py --data "C:\path\to\files" --output glorious.csv
```

Repeated runs with the same inputs and source code produce the same CSV.

## Approach

1. Read tracking metadata to identify each track slot’s team.
2. Convert normalised positions into pitch coordinates in metres.
3. Measure the distance from the ball to the closest tracked player on each team.
4. Combine distance-based evidence with automatic tactical event tags.
5. Identify potential stoppages using sustained out-of-bounds observations and evidence around tagged restarts.
6. Use a temporal decoder that penalises possession changes to reduce switches caused by isolated observations.
7. Export one label per video frame.

Missing ball observations contribute no geometric possession evidence. The decoder can carry possession through gaps using surrounding observations and event evidence.

No human-labelled training data was used. Parameters were chosen heuristically.

## Official validation

Download and extract the organisers’ repository:

https://github.com/metrica-sports/more-than-a-hack-2027

From its root folder, install the evaluation dependencies:

```powershell
python -m pip install -r requirements.txt
```

Copy `glorious.csv` into its `evaluation/results/` folder, then run:

```powershell
python evaluation/validate_submission.py evaluation/results/glorious.csv
```

Run the public evaluation:

```powershell
python evaluation/run_evaluation.py
```

## Results

The generated submission passed the official format validator with 199,319 rows and sequential frames from 0 to 199318.

Results on the organisers’ five-minute public reference window:

| Metric | Result |
|--------|--------|
| spellF1 | 0.3524 |
| macroF1 | 0.6505 |
| Frame accuracy | 73.0% |
| Predicted possessions | 25 |
| Reference possessions | 17 |

The public reference window is for checking the pipeline. It was not used for training or parameter tuning. Final competition rankings use private full-match reference labels.

## Limitations

- Missing or inaccurate ball tracking can affect turnover timing.
- Automatic tactical tags can contain errors.
- The predictor can split a possession into multiple shorter stretches.
- Stoppage detection is heuristic and can miss or incorrectly identify dead-ball intervals.
- Performance across the full match remains unverified against the private reference labels.

## Project files

| File | Purpose |
|------|---------|
| predict.py | Generates possession predictions |
| README.md | Setup, execution and evaluation instructions |
| Technical-Method.md | Technical explanation and limitations |
| .gitignore | Excludes match inputs and generated files |

## Submission

Team name: `glorious`

The competition submission consists of:

- `glorious.csv`
- A public URL for this code repository
- `glorious.md`, the technical document

## Official challenge

https://github.com/metrica-sports/more-than-a-hack-2027
