"""Predict tactical-camera possession from the match's automatic tracking and tags."""

import argparse
import csv
from dataclasses import dataclass
from math import exp, hypot, isfinite
from pathlib import Path
from statistics import median
import xml.etree.ElementTree as ET

FPS = 25
FRAME_COUNT = 199_319
HALVES = ((11_185, 90_652), (110_808, 190_198))
LENGTH, WIDTH = 105.3, 68.0
PREFIX = "BAR-ATH_tactical"
ATTACK = {
    "ATTACKING TRANSITION", "BUILD UP", "PROGRESSION", "BALL IN THE BOX",
    "BALL IN FINAL THIRD", "CREATING CHANCES", "LONG BALL",
}
DEFEND = {
    "DEFENSIVE TRANSITION", "DEFENDING IN DEFENSIVE THIRD",
    "DEFENDING IN MIDDLE THIRD", "DEFENDING IN ATTACKING THIRD",
}


@dataclass(frozen=True)
class Observation:
    x: float
    y: float
    home: float
    away: float
    speed: float


@dataclass(frozen=True)
class Tag:
    start: int
    end: int
    code: str
    team: int
    kind: str


def point(fields):
    if not fields or not fields[0] or fields[0].casefold() == "nan":
        return None
    x, y = map(float, fields[:2])
    if isfinite(x) and isfinite(y):
        return x * LENGTH, y * WIDTH
    return None


def read_tracking(metadata, raw):
    root = ET.parse(metadata).getroot()
    team_ids = [team.attrib["id"] for team in root.iter("Team")]
    if len(team_ids) != 2 or len(set(team_ids)) != 2:
        raise ValueError("Expected exactly two distinct teams in tracking metadata")
    slots = [team_ids.index(player.attrib["teamId"]) for player in root.iter("Player")]
    if set(slots) != {0, 1}:
        raise ValueError("Both teams must have tracking slots")

    observations = [None] * FRAME_COUNT
    with raw.open(encoding="utf-8-sig") as handle:
        count = 0
        for count, line in enumerate(handle, 1):
            frame, players, ball = line.rstrip().split(":")
            if int(frame) != count or count > FRAME_COUNT:
                raise ValueError(f"Unexpected tracking frame {frame} on line {count}")
            ball_fields = ball.split(",")
            position = point(ball_fields)
            if position is None:
                continue
            groups = players.split(";")
            if len(groups) != len(slots):
                raise ValueError(f"Track slot count disagrees with metadata at frame {frame}")
            x, y = position
            nearest = [float("inf"), float("inf")]
            for team, group in zip(slots, groups):
                if group.startswith("NaN"):
                    continue
                player = point(group.split(","))
                if player is not None:
                    nearest[team] = min(nearest[team], hypot(player[0] - x, player[1] - y))
            speed = float(ball_fields[2]) if len(ball_fields) > 2 else float("nan")
            observations[count - 1] = Observation(x, y, *nearest, speed)
    if count != FRAME_COUNT:
        raise ValueError(f"Tracking contains {count} frames, expected {FRAME_COUNT}")
    if not any(observations):
        raise ValueError("Tracking contains no valid ball positions")
    return observations


def read_tags(path):
    def frame(node, field):
        return round(float(node.findtext(field)) * FPS)

    tags = []
    for item in ET.parse(path).iter("instance"):
        values = {
            label.findtext("group", "").strip().casefold(): label.findtext("text", "").strip()
            for label in item.findall("label")
        }
        club = values.get("team", "").casefold()
        team = 1 if "barcelona" in club else -1 if club in {
            "atletic club", "athletic club", "athletic bilbao",
        } else 0
        start, end = frame(item, "start"), frame(item, "end")
        tags.append(Tag(start, end, item.findtext("code", "").strip().upper(),
                        team, values.get("type", "").casefold()))
    if not tags:
        raise ValueError("No Smart Tagging instances found")
    return sorted(tags, key=lambda tag: tag.start)


def outside(observation, margin=0.6):
    return (observation.x < -margin or observation.x > LENGTH + margin
            or observation.y < -margin or observation.y > WIDTH + margin)


def tag_evidence(tags, start, stop):
    changes = [0.0] * (stop - start + 1)
    for tag in tags:
        direction = tag.team
        lo, hi = max(start, tag.start), min(stop, tag.end)
        if tag.code == "SET PIECES":
            hi = min(stop, tag.start + FPS)
            weight = 0.47
        elif tag.code in ATTACK:
            weight = 0.12
        elif tag.code in DEFEND:
            weight, direction = 0.10, -direction
        else:
            continue
        if lo < hi:
            changes[lo - start] += weight * direction
            changes[hi - start] -= weight * direction
    value = 0.0
    for i in range(stop - start):
        value += changes[i]
        changes[i] = max(-0.36, min(0.36, value))
    return changes


def stoppages(observations, tags, start, stop):
    """Use sustained out-of-bounds evidence and corroborated tagged restarts."""
    dead = bytearray(stop - start)
    run_start = None
    for frame in range(start, stop + 1):
        sighting = observations[frame] if frame < stop else None
        if sighting is not None and outside(sighting):
            if run_start is None:
                run_start = frame
        elif run_start is not None:
            if frame - run_start >= 10:
                dead[run_start - start:frame - start] = b"\x01" * (frame - run_start)
            run_start = None

    for tag in tags:
        restart = tag.start
        if tag.code != "SET PIECES" or not start < restart < stop:
            continue
        if tag.kind == "kick off (start)":
            continue
        lookback = max(start, restart - 480)
        last_motion = None
        last_outside = None
        for frame in range(lookback, restart):
            sighting = observations[frame]
            if sighting is None:
                continue
            if outside(sighting):
                last_outside = frame
            elif sighting.speed >= 2.5:
                last_motion = frame
        if last_outside is not None and (last_motion is None or last_outside > last_motion):
            onset = last_outside
            while onset > lookback:
                previous = observations[onset - 1]
                if previous is not None and not outside(previous):
                    break
                onset -= 1
        else:
            # Require either a quiet ball before the restart or a long detection gap.
            recent = [p for p in observations[max(start, restart - 45):restart] if p]
            speeds = [p.speed for p in recent if isfinite(p.speed)]
            if len(recent) > 5 and (not speeds or median(speeds) > 2.0):
                continue
            onset = max(start, restart - 125, (last_motion + 1) if last_motion else start)
        if restart - onset >= 18:
            dead[onset - start:restart - start] = b"\x01" * (restart - onset)
    return dead


def contact(observation):
    if observation is None or outside(observation):
        return 0.0
    home = exp(-observation.home / 2.1)
    away = exp(-observation.away / 2.1)
    speed = observation.speed
    reliability = 1.0 if not isfinite(speed) else max(0.22, 1.0 - max(0, speed - 3) / 14)
    return (home - away) * reliability


def decode(evidence, switch_cost=4.0):
    """Find the highest-scoring sequence with a cost for each turnover."""
    if not evidence:
        return ""
    home, away = 0.0, 0.0
    back_home, back_away = bytearray(len(evidence)), bytearray(len(evidence))
    for index, score in enumerate(evidence):
        change_to_home = away - switch_cost > home
        change_to_away = home - switch_cost > away
        back_home[index] = change_to_home
        back_away[index] = change_to_away
        home, away = (max(home, away - switch_cost) + score,
                      max(away, home - switch_cost) - score)

    # If a whole live interval offered no team evidence, abstain.
    if not any(evidence):
        return "X" * len(evidence)
    is_away = away > home
    labels = [""] * len(evidence)
    for index in range(len(evidence) - 1, -1, -1):
        labels[index] = "A" if is_away else "H"
        if (back_away if is_away else back_home)[index]:
            is_away = not is_away
    return "".join(labels)


def predict(observations, tags, halves=HALVES):
    labels = ["X"] * len(observations)
    for start, stop in halves:
        dead = stoppages(observations, tags, start, stop)
        phases = tag_evidence(tags, start, stop)
        run = []
        for offset, frame in enumerate(range(start, stop)):
            if dead[offset]:
                labels[frame - len(run):frame] = decode(run)
                labels[frame] = "D"
                run.clear()
            else:
                run.append(contact(observations[frame]) + phases[offset])
        labels[stop - len(run):stop] = decode(run)
    return labels


def write_submission(path, labels):
    if len(labels) != FRAME_COUNT or set(labels) - set("HADX"):
        raise ValueError("Prediction has invalid labels or the wrong frame count")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("frame", "label"))
        writer.writerows(enumerate(labels))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"),
                        help="dataset root or folder containing the three tactical files")
    parser.add_argument("--output", type=Path, default=Path("submission.csv"))
    args = parser.parse_args()
    folder = args.data / "tactical" if (args.data / "tactical").is_dir() else args.data
    paths = [folder / (PREFIX + suffix)
             for suffix in ("_atd.xml", "_atd.txt", "_smart_tagging.xml")]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        parser.error("Missing local input files: " + ", ".join(missing))
    observations = read_tracking(*paths[:2])
    tags = read_tags(paths[2])
    labels = predict(observations, tags)
    write_submission(args.output, labels)
    print(f"Wrote {len(labels):,} frames to {args.output}")
    print(" ".join(f"{label}={labels.count(label):,}" for label in "HADX"))


if __name__ == "__main__":
    main()

