# Ball possession from tactical tracking

## Method

The pipeline uses a deterministic temporal decoder. It converts the tracked positions to metres and measures the shortest distance between the ball and any tracked player on each team. The difference between distance-decayed contact scores indicates which team is more likely to have control. Fast ball movement reduces the strength of a close pass or incidental touch as turnover evidence. An absent ball contributes zero geometric evidence.

Automatic attacking and defending phases provide bounded team evidence. Tags without a recognised team contribute no team evidence. Set-piece tags add a short prior for the restarting team when one is provided. A separate stoppage detector marks sustained out-of-bounds observations and looks backward from tagged restarts for a plausible dead-ball interval, using out-of-bounds observations, low motion or a detection gap. These are heuristics for stoppages that cannot be observed directly from tracking.

Within each live interval, dynamic programming chooses the home or away sequence with the strongest total evidence after charging a fixed penalty per turnover. The penalty favours maintaining possession through isolated touches and gaps. A dead-ball interval ends the current possession. The next live interval is decoded independently. Frames outside the documented halves and live intervals with zero team evidence are labelled X.

## Inputs and reproducibility

The input files are the tactical ATD text and metadata XML and the tactical Smart Tagging XML. The ATD IDs are converted to zero-based video indices and the tag times are converted from seconds at 25 fps. The code uses the published half boundaries. It does not require video, calibration matrices or broadcast data. There were no training labels, manual corrections or full-match reference labels. The constants are heuristic choices.

Run `python predict.py --data /path/to/dataset --output TEAM_NAME.csv` with Python 3.10 or newer. The source has no third-party dependencies. Repeated runs on the same input produce byte-identical UTF-8 CSV output.

## Limitations

Long ball tracking gaps can blur turnover timing. Team assignments and tags can contain errors. The stoppage detector can miss untagged fouls, confuse a stationary live ball with a stoppage near a false restart tag, or split a spell at an erroneous tracking position. There is no result from the official scorer until the program has been run on the actual match assets.

[Official data documentation](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/DATA.md)
