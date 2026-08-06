"""Data export commands for the ECHO2D CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from pyecho.cli import export_app

@export_app.command("hdf5")
def export_hdf5(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output HDF5 file"),
    ] = None,
    compress: Annotated[
        int,
        typer.Option("--compress", "-c", help="Compression level (0-9)"),
    ] = 4,
) -> None:
    """Export results to HDF5 format."""
    import h5py
    from pyecho.parser import OutputLoader

    loader = OutputLoader(output_dir)
    out_path = Path(output or f"{Path(output_dir).name}_results.h5")

    with h5py.File(out_path, "w") as f:
        # Export wakes
        wakes = loader.load_all_wakes()
        if wakes:
            wake_grp = f.create_group("wakes")
            for mode, (s, W, hr, offset, D, sigma) in wakes.items():
                g = wake_grp.create_group(f"mode_{mode:02d}")
                g.create_dataset("s", data=s, compression="gzip", compression_opts=compress)
                g.create_dataset("W_raw", data=W, compression="gzip", compression_opts=compress)
                g.attrs["hr"] = hr
                g.attrs["offset"] = offset
                g.attrs["D"] = D
                g.attrs["sigma"] = sigma

        # Export currents
        currents = loader.load_currents()
        if currents is not None:
            f.create_dataset("currents_z", data=currents[1], compression="gzip", compression_opts=compress)
            f.create_dataset("s_current", data=currents[0], compression="gzip", compression_opts=compress)

        # Export field monitors
        monitors = loader.list_monitors()
        for mode, mon_id in monitors:
            mon = loader.load_monitor(mode=mode, monitor_id=mon_id)
            if mon is not None:
                g = f.create_group(f"monitors/m{mode:02d}_N{mon_id:02d}")
                g.create_dataset("T", data=mon.T, compression="gzip", compression_opts=compress)
                g.create_dataset("Z", data=mon.Z, compression="gzip", compression_opts=compress)
                g.create_dataset("R", data=mon.R, compression="gzip", compression_opts=compress)
                g.create_dataset("F", data=mon.F, compression="gzip", compression_opts=compress)
                g.attrs["component"] = mon.field_component
                g.attrs["time_type"] = mon.time_type
                g.attrs["D"] = mon.D

    console.print(f"[bold green]✓[/bold green] Exported to [cyan]{out_path}[/cyan]")


@export_app.command("csv")
def export_csv(
    output_dir: Annotated[str, typer.Argument(help="Output directory")],
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output directory for CSV files"),
    ] = None,
) -> None:
    """Export results to CSV format."""
    import numpy as np
    from pyecho.parser import OutputLoader

    loader = OutputLoader(output_dir)
    out_dir = Path(output or f"{Path(output_dir).name}_csv")
    out_dir.mkdir(parents=True, exist_ok=True)

    wakes = loader.load_all_wakes()
    for mode, (s, W, hr, offset, D, sigma) in wakes.items():
        data = np.column_stack([s, W])
        header = f"s[m],W_raw[m*V/nC]"
        np.savetxt(
            out_dir / f"wake_mode_{mode:02d}.csv",
            data,
            delimiter=",",
            header=header,
            comments="",
        )

    console.print(f"[bold green]✓[/bold green] CSV files exported to [cyan]{out_dir}[/cyan]")


# ===================================================================
# compare commands
# ===================================================================
