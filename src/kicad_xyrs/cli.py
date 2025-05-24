"""Console script for kicad_xyrs.

This module defines the command-line interface for the KiCad XYRS (XY Placement + Rotation + Side) exporter.
It integrates with KiCad's pcbnew to extract footprint data from a PCB file.
Supported formats are defined in `output_formats`, with configurable origins and unit conversions.
"""

import logging
import sys
from pathlib import Path
import re

import click
import pandas as pd
import pcbnew

from . import file_io
from . import kicad_xyrs
from .kicad_xyrs import output_formats, convert_units, refdes_key, get_origin_by_mode, translate_output, ORIGIN_MODES

_log = logging.getLogger("kicad_xyrs")


@click.command(
    help="Generate XYRS"
)
@click.version_option()
@click.option("--pcb", type=str, required=True, help="Source PCB file")
@click.option("--out", type=str, required=True, help="Output file")
@click.option("--format", "-f", "output_format", default="Default", type=click.Choice(output_formats.keys(), case_sensitive=False), help="Output format.")
@click.option("--debug", is_flag=True, help="")

def main_cli(pcb, out, output_format, debug):
    """
    CLI entry point for generating XYRS position files from a KiCad PCB.

    Args:
        pcb (str): Path to the input KiCad PCB file.
        out (str): Path to the output spreadsheet.
        no_drill_center (bool): If True, do not use drill origin as the coordinate origin.
        output_format (str): Output format name (must match a key in `output_formats`).
        debug (bool): Enable debug logging.

    Returns:
        int: Exit code (0 on success).
    """
    logging.basicConfig()
    _log.setLevel(logging.INFO)
    if debug:
        _log.setLevel(logging.DEBUG)

    board_path = Path(pcb).absolute()
    assert board_path.exists()
    print(board_path)
    board = pcbnew.LoadBoard(board_path.as_posix())
    unsorted_footprints = [fp for fp in board.GetFootprints() if (lambda fp: not fp.IsExcludedFromBOM()\
                        and not fp.IsBoardOnly() \
                        and not fp.IsExcludedFromPosFiles())(fp)]

    footprints = sorted(unsorted_footprints, key=lambda fp: refdes_key(fp.GetReference()))

    assert len(footprints) > 0

    format_dict = output_formats[output_format.lower()]
    origin_mode = format_dict.get("origin_mode", "DRILL")

    settings = kicad_xyrs.Settings()
    settings.origin = get_origin_by_mode(board, origin_mode)

    report = kicad_xyrs.build_footprint_report(settings, footprints)
    report_df = pd.DataFrame(report)

    df = translate_output(format_dict, report_df)

    file_io.write(df, out)
    return sys.exit(0)

def main():
    main_cli()


if __name__ == "__main__":
    logging.basicConfig()
    _log.setLevel(logging.INFO)
    main()  # pragma: no cover
