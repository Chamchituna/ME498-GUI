from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import csv
import numpy as np
from matplotlib.ticker import AutoMinorLocator, MultipleLocator


def _read_csv(csv_path: str) -> Tuple[List[str], List[List[str]]]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    with open(path, newline="") as f:
        rows = [row for row in csv.reader(f) if any(cell.strip() for cell in row)]

    if not rows:
        raise ValueError(f"CSV appears empty: {csv_path}")

    header = rows[0]
    data = rows[1:] if len(rows) > 1 else []
    if not data:
        raise ValueError("CSV contains header but no data rows.")

    return header, data


def _column_by_hint(header: List[str], hints: List[str]) -> int:
    for hint in hints:
        for idx, name in enumerate(header):
            if hint in name.lower():
                return idx
    return -1


def _to_float(values: List[str]) -> np.ndarray:
    out: List[float] = []
    for val in values:
        try:
            out.append(float(val))
        except Exception:
            out.append(float("nan"))
    return np.asarray(out, dtype=float)

def plot_csv(ax, csv_path: str) -> None:

   header, data = _read_csv(csv_path)

   order_idx = _column_by_hint(header, ["order", "m", "index"])
   if order_idx < 0:
        order_idx = 0
   x_vals = _to_float([row[order_idx] if order_idx < len(row) else "" for row in data])
    
   candidate_hints = ["diff", "eff", "rs", "rp", "s11", "intensity", "power"]
   y_indices: List[int] = []
   for hint in candidate_hints:
        idx = _column_by_hint(header, [hint])
        if idx >= 0 and idx != order_idx and idx not in y_indices:
            y_indices.append(idx)
   if not y_indices:
        for idx in range(len(header)):
            if idx != order_idx:
                y_indices.append(idx)

   if not y_indices:
        raise ValueError("No value columns detected for plotting.")
   ax.cla()
   plotted = 0
   for idx in y_indices:
        series = _to_float([row[idx] if idx < len(row) else "" for row in data])
        mask = np.isfinite(x_vals) & np.isfinite(series)
        if not np.any(mask):
            continue
        label = header[idx].strip() or f"col{idx+1}"
        ax.plot(x_vals[mask], series[mask], marker="o", label=label)
        plotted += 1

   if plotted == 0:
        raise ValueError("Parsed CSV but found no plottable numeric data.")

   xlabel = header[order_idx].strip() or "Diffraction Order"
   ax.set_xlabel(xlabel)
   ax.set_ylabel("Value")
   ax.xaxis.set_major_locator(MultipleLocator(1))
   ax.xaxis.set_minor_locator(AutoMinorLocator(2))
   ax.grid(True, which="major", linewidth=0.8, alpha=0.6)
   ax.grid(True, which="minor", linewidth=0.4, alpha=0.35)
   if plotted > 1:
        ax.legend(loc="best")

   ax.figure.tight_layout()