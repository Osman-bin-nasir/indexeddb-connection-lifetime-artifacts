# Reproduce the six grayscale scientific figures

`rebuild_figures.py` reads the registered-table recomputation and A3/A4 results from this evidence release. It starts no VM, acquires no new observations, uses no network tools, and does not modify source evidence. All numerical series and selected denominators are saved in `FIGURE_DATA.json`, alongside the six PNGs and a rendering receipt.

Python 3.11 or newer plus Matplotlib and NumPy are needed only for this figure command. Registered-table and A1–A4 record analyses otherwise use the Python standard library. In an analysis environment lacking the optional plotting dependencies, install them explicitly before running the figure builder:

```bash
python3 -m pip install matplotlib numpy
```

No package installation is performed by the script. The successful reference rebuild used Matplotlib 3.11.2, NumPy 2.5.3, the Agg renderer and DejaVu Serif fonts. Different renderer, font or dependency versions can alter PNG bytes even when the numerical series remain identical.

From the release root, first recompute the existing raw records into a separate folder, then render:

```bash
python3 analysis/recompute.py --release-root . --out /tmp/idbv2-figure-inputs
python3 analysis/grid_strict_reanalysis.py --root . --out /tmp/idbv2-figure-inputs/a3_a4
python3 analysis/rebuild_figures.py \
  --release-root . \
  --recomputed /tmp/idbv2-figure-inputs/RECOMPUTED_RESULTS.json \
  --a3-a4 /tmp/idbv2-figure-inputs/a3_a4/A3_A4_RESULTS.json \
  --out /tmp/idbv2-rebuilt-figures
```

If you have already verified the supplied derived data, the shorter command uses the release's current recomputed outputs:

```bash
python3 analysis/rebuild_figures.py --release-root . --out /tmp/idbv2-rebuilt-figures
```

The output must be outside the release evidence folder. To compare with an existing reference PNG set without changing it, add `--compare-dir /path/to/reference-figures`. The reference folder must differ from the output folder. The optional comparison reports SHA-256 equality, image dimensions, differing pixels and maximum channel differences. Running the command may replace only derived figure files in the selected output folder.

## Outputs and scientific semantics

| PNG | Content |
| --- | --- |
| `01_grid.png` | Two panels: eighteen separate assigned-gap cell estimates with exact pointwise 95% intervals; twenty assigned-2.0-s outcomes at achieved estimates, with recorded mapping half-RTT. |
| `02_held.png` | Five held cells and the two registered immediate-close controls, with exact pointwise intervals. |
| `03_fault.png` | QMP, SysRq and SIGKILL plotted separately within each of the four keys. Held-15-s SIGKILL uses 9/9 eligible outcomes, with an asterisk for its unknown endpoint. |
| `04_block.png` | Linear, dm-log-writes and dm-flakey cells kept separate by key. Original cell counts are plotted; dependent log-prefix reads are excluded. |
| `05_environment.png` | Four registered environment profiles kept separate by key. |
| `06_workload.png` | Four registered workloads kept separate by key. |

All six use the current manuscript's grayscale colors, labels, marker styles, plotting limits and exact numerical data. Small horizontal display offsets separate markers and do not change assigned timing. Intervals are pointwise rather than simultaneous. Figure 1's mapping half-RTT is a diagnostic, not a calibrated total-error interval. No interpolated threshold, fitted safe waiting time, pooled recovery rate or extra scientific denominator is introduced.

`FIGURE_DATA.json` contains eighty-one original cell estimates and the twenty dependent display points in Figure 1's second panel, with input hashes. `FIGURE_REBUILD_REPORT.json` records library versions, output hashes and optional reference comparisons. The release includes the successful reference rebuild receipts under `derived/`; the actual generated PNGs were written outside the release.

The reference rebuild matched all six current manuscript PNGs byte-for-byte and pixel-for-pixel, with zero differing pixels. The data continue to represent 930 consumed assignments, 925 eligible endpoints, 340 recovered and 585 lost. Rebuilding figures adds zero scientific units and leaves all unknown or premeasurement dispositions unchanged.
