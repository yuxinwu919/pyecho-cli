#!/usr/bin/env python3
"""Run MATLAB reference post-processing for ECHO2D examples N2-N14, N16.

For each example:
  1. Builds an isolated staging dir under matlab_outputs/_work/<N>/
     mirroring the layout the original PostProcessor* scripts expect
     (PostProcessor2D/{Round,Flat}/, ECHO2D/{round,magn,elec}/).
  2. Copies the *original* MATLAB post-processing scripts from
     tests/Examples/<N>/PostProcessor*/ (falling back to the canonical
     ECHO2D_v3_5/PostProcessor2D/Wakes/ copies when the example ships no
     matching script) and copies the ECHO2D raw output from the integration
     run dir.
  3. Writes a small wrapper script that cd's into the post-process dir,
     hides figures, runs the original scripts, and prints the key values
     (loss / kick / peak / spread) with VAL_<key>=<value> markers.
  4. Runs MATLAB in -batch mode, captures stdout+stderr, parses the VAL
     markers, and stores the raw log in matlab_outputs/.

MATLAB: /Applications/MATLAB_R2025b.app/bin/matlab
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/Users/yuxinwu/my_projects/ECHO2D_CLI")
EXAMPLES_DIR = ROOT / "tests/Examples"
RUNS_DIR = ROOT / "tests/integration/test_project/runs"
OUT_DIR = ROOT / "tests/integration/results/matlab_outputs"
WORK = OUT_DIR / "_work"
MATLIB = ROOT / "ECHO2D_v3_5/MatLib4ECHO"
UPSTREAM = ROOT / "ECHO2D_v3_5/PostProcessor2D/Wakes"
MATLAB_BIN = "/Applications/MATLAB_R2025b.app/bin/matlab"

# Symlink so the original scripts' path('../../../../MatLib4ECHO',path)
# resolves from _work/<N>/PostProcessor2D/{Round,Flat}/.
ML_SYMLINK = OUT_DIR / "MatLib4ECHO"

UPPER = {"round": "Round", "flat": "Flat"}


def example_postproc(n: str) -> Path | None:
    d = _example_dir(n)
    if d is None:
        return None
    for c in (d / "PostProcessor2D", d / "PostProzessor2D"):
        if c.is_dir():
            return c
    return None


def _example_dir(n: str) -> Path | None:
    """tests/Examples/N4_* -> the example directory for example id N4."""
    for d in EXAMPLES_DIR.iterdir():
        if d.is_dir() and d.name.startswith(n + "_"):
            return d
    return None


def src_script(n: str, name: str, geo: str) -> Path:
    """Locate the original script: example dir first, then upstream."""
    ex = example_postproc(n)
    if ex is not None:
        for sub in ("Round", "Flat", "round", "flat", "Wakes/Flat", "Fields/Flat"):
            p = ex / sub / name
            if p.is_file():
                return p
    up = UPSTREAM / (UPPER[geo] if geo == "flat" else "Round") / name
    if up.is_file():
        return up
    if geo == "flat":
        up = UPSTREAM / "Flat" / name
        if up.is_file():
            return up
    raise FileNotFoundError(f"script {name} not found for {n}")


def copy_data(src_dir: Path, dst_dir: Path, patterns: list[str]) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for pat in patterns:
        for p in src_dir.glob(pat):
            if p.is_file():
                shutil.copy2(p, dst_dir / p.name)


PRINT_BODY = {
    "monopole": """
fprintf('VAL_{tag}_loss=%.10g\\n', loss);
fprintf('VAL_{tag}_spread=%.10g\\n', spread);
[~,~,pk] = LossShape([s B],[s W]);
fprintf('VAL_{tag}_peak=%.10g\\n', pk);
""",
    "dipole": """
fprintf('VAL_{tag}_loss=%.10g\\n', loss);
fprintf('VAL_{tag}_spread=%.10g\\n', spread);
fprintf('VAL_{tag}_kick=%.10g\\n', kick);
fprintf('VAL_{tag}_rms_kick=%.10g\\n', rms_kick);
[~,~,pk] = LossShape([s B],[s W]);
fprintf('VAL_{tag}_peak=%.10g\\n', pk);
""",
    "wakeLQ": """
fprintf('VAL_{tag}_lossL=%.10g\\n', lossL);
fprintf('VAL_{tag}_spreadL=%.10g\\n', spreadL);
fprintf('VAL_{tag}_lossQ=%.10g\\n', lossQ);
fprintf('VAL_{tag}_spreadQ=%.10g\\n', spreadQ);
""",
    "wakeLQD": """
fprintf('VAL_{tag}_lossL=%.10g\\n', lossL);
fprintf('VAL_{tag}_spreadL=%.10g\\n', spreadL);
fprintf('VAL_{tag}_lossD=%.10g\\n', lossD);
fprintf('VAL_{tag}_spreadD=%.10g\\n', spreadD);
fprintf('VAL_{tag}_lossQ=%.10g\\n', lossQ);
fprintf('VAL_{tag}_spreadQ=%.10g\\n', spreadQ);
""",
}

# ---------------------------------------------------------------------------
# Example definitions
# ---------------------------------------------------------------------------
# Each step: dict(file=script name, action="run"|"analyze",
#                 print=key into PRINT_BODY, tag=value label,
#                 patch=None or (old,new))
EXAMPLES: list[dict] = [
    # --------------------------- round ---------------------------
    dict(
        name="N2", run="002_roundcollimatordipole", geo="round",
        data=[("round", "round", ["wakeL_01.txt", "Iz0.txt"])],
        steps=[dict(file="PP_Wake_Dipole.m", action="analyze",
                    print="dipole", tag="dipole")],
    ),
    dict(
        name="N3", run="003_roundcollimatordipoleconductive", geo="round",
        data=[("round", "round", ["wakeL_00.txt", "wakeL_01.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wake_Monopole.m", action="analyze",
                 print="monopole", tag="mono"),
            dict(file="PP_Wake_Dipole.m", action="analyze",
                 print="dipole", tag="dipole"),
        ],
    ),
    dict(
        name="N9", run="009_resistivepillbox", geo="round",
        data=[("round", "round", ["wakeL_00.txt", "wakeL_01.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wake_Monopole.m", action="analyze",
                 print="monopole", tag="mono"),
            dict(file="PP_Wake_Dipole.m", action="analyze",
                 print="dipole", tag="dipole"),
        ],
    ),
    dict(
        name="N10", run="010_teslacavitylong", geo="round",
        data=[("round", "round", ["wakeL_00.txt", "wakeL_01.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wake_Monopole.m", action="analyze",
                 print="monopole", tag="mono"),
            dict(file="PP_Wake_Dipole.m", action="analyze",
                 print="dipole", tag="dipole"),
        ],
    ),
    dict(
        name="N11", run="011_round_dielectric", geo="round",
        data=[("round", "round_1m", ["wakeL_00.txt", "wakeL_01.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wake_Monopole.m", action="analyze",
                 print="monopole", tag="mono"),
            dict(file="PP_Wake_Dipole.m", action="analyze",
                 print="dipole", tag="dipole"),
        ],
    ),
    dict(
        name="N13", run="013_restart", geo="round",
        data=[("round", "round_2", ["wakeL_00.txt", "wakeL_01.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wake_Monopole.m", action="analyze",
                 print="monopole", tag="mono"),
            dict(file="PP_Wake_Dipole.m", action="analyze",
                 print="dipole", tag="dipole"),
        ],
    ),
    dict(
        name="N14", run="014_wakemonitor_arbitrarybunchshape", geo="round",
        data=[("round", "round", ["wakeL_00.txt", "Iz0.txt"])],
        steps=[dict(file="PP_Wake_Monopole.m", action="analyze",
                    print="monopole", tag="mono")],
    ),
    # --------------------------- flat ---------------------------
    dict(
        name="N4", run="004_flatabsorberlongquad", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wcc.m", action="run"),
            dict(file="PP_WakeLQ.m", action="analyze",
                 print="wakeLQ", tag="wake"),
        ],
    ),
    dict(
        name="N5", run="005_flatabsorberdipole", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"]),
              ("elec", "elec", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wcc.m", action="run"),
            dict(file="PP_Wss.m", action="run"),
            dict(file="PP_WakeLQD.m", action="analyze",
                 print="wakeLQD", tag="wake"),
        ],
    ),
    dict(
        name="N6", run="006_pohangdechirper", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wcc.m", action="run"),
            dict(file="PP_WakeLQ.m", action="analyze",
                 print="wakeLQ", tag="wake"),
        ],
    ),
    dict(
        name="N7", run="007_taperedresistivecollimator", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wcc.m", action="run"),
            dict(file="PP_WakeLQ.m", action="analyze",
                 print="wakeLQ", tag="wake"),
        ],
    ),
    dict(
        name="N8", run="008_flattaperwithfieldmonitor", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            # N8 scripts sit at PostProcessor2D/Wakes/Flat (one level deeper)
            # and PP_Wcc references '../../../ECHO2D/magn/'; PP_WakeLQ already
            # uses '../../ECHO2D/magn/'. Patch PP_Wcc so both run from Flat/.
            dict(file="PP_Wcc.m", action="run",
                 patch=("'../../../ECHO2D/magn/'", "'../../ECHO2D/magn/'")),
            dict(file="PP_WakeLQ.m", action="analyze",
                 print="wakeLQ", tag="wake"),
        ],
    ),
    dict(
        name="N12", run="012_flat_dielectric", geo="flat",
        data=[("magn", "magn", ["wakeL_*.txt", "Iz0.txt"]),
              ("elec", "elec", ["wakeL_*.txt", "Iz0.txt"])],
        steps=[
            dict(file="PP_Wcc.m", action="run", patch=("Nm=15;", "Nm=3;")),
            dict(file="PP_Wss.m", action="run", patch=("Nm=15;", "Nm=3;")),
            dict(file="PP_WakeLQD.m", action="analyze",
                 print="wakeLQD", tag="wake"),
        ],
    ),
]


def generate_wrapper(example: dict, stage: Path, matlib: Path) -> str:
    geo = example["geo"]
    cd_dir = stage / "PostProcessor2D" / UPPER[geo]
    lines = []
    lines.append("function run_wrapper()")
    lines.append(f"    cd('{cd_dir}');")
    lines.append("    set(0,'DefaultFigureVisible','off');")
    lines.append(f"    addpath('{matlib}');")
    lines.append("    addpath(pwd);")
    for step in example["steps"]:
        lines.append(f"    run('{step['file']}');")
        if step["action"] == "analyze":
            snippet = PRINT_BODY[step["print"]].format(tag=step["tag"])
            for ln in snippet.splitlines():
                lines.append("    " + ln)
    lines.append(f"    fprintf('{example['name']}_COMPLETE\\n');")
    lines.append("end")
    return "\n".join(lines)


def main() -> None:
    only = set(sys.argv[1:])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not ML_SYMLINK.exists():
        ML_SYMLINK.symlink_to(MATLIB, target_is_directory=True)
    WORK.mkdir(parents=True, exist_ok=True)

    summary: dict[str, dict] = {}

    for example in EXAMPLES:
        n = example["name"]
        if only and n not in only:
            continue
        run_dir = RUNS_DIR / example["run"]
        stage = WORK / n
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True)

        ppdir = stage / "PostProcessor2D" / UPPER[example["geo"]]
        ppdir.mkdir(parents=True, exist_ok=True)

        script_srcs: dict[str, str] = {}
        for step in example["steps"]:
            src = src_script(n, step["file"], example["geo"])
            dst = ppdir / step["file"]
            text = src.read_text(encoding="utf-8", errors="replace")
            if step.get("patch"):
                old, new = step["patch"]
                if old in text:
                    text = text.replace(old, new)
                else:
                    print(f"  WARN {n}: patch pattern {old!r} not found in {step['file']}")
            dst.write_text(text, encoding="utf-8")
            script_srcs[step["file"]] = str(src)

        for src_sub, dst_sub, patterns in example["data"]:
            copy_data(run_dir / src_sub, stage / "ECHO2D" / dst_sub, patterns)

        wrapper = stage / f"run_{n}.m"
        wrapper.write_text(generate_wrapper(example, stage, MATLIB), encoding="utf-8")

        log = stage / f"{n}.log"
        cmd = [MATLAB_BIN, "-batch", f"run('{wrapper}')"]
        try:
            proc = subprocess.run(
                cmd, cwd=str(stage), capture_output=True, text=True, timeout=600
            )
            raw = proc.stdout + proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            raw = (exc.stdout or "") + (exc.stderr or "")
            exit_code = -1
        except Exception as exc:  # noqa: BLE001
            raw = f"launch error: {exc}"
            exit_code = -2
        log.write_text(raw, encoding="utf-8", errors="replace")

        values: dict[str, float] = {}
        for m in re.finditer(r"VAL_(\w+)=([0-9.eE+-]+)", raw):
            values[m.group(1)] = float(m.group(2))

        complete = f"{n}_COMPLETE" in raw
        errored = any(k in raw for k in ("错误", "Error", "Undefined", "无法识别"))

        summary[n] = {
            "example": n,
            "run_dir": example["run"],
            "geometry": example["geo"],
            "matlab_exit_code": exit_code,
            "completed": complete,
            "errored": errored,
            "scripts": script_srcs,
            "values": values,
        }
        shutil.copy2(log, OUT_DIR / f"{n}.log")
        print(f"{n}: exit={exit_code} complete={complete} errored={errored} "
              f"values={ {k: round(v, 6) for k, v in values.items()} }")

    (OUT_DIR / "matlab_summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )
    print("Summary written to", OUT_DIR / "matlab_summary.json")


if __name__ == "__main__":
    sys.exit(main())
