"""
Core XYRS extraction and formatting logic for KiCad PCB files.

This module provides utilities to extract XYRS (X, Y, Rotation, Side) information
from KiCad footprints and format the data into tabular reports.

Functions include unit conversion, sorting reference designators, determining
coordinate origins, and formatting the final output for supported placement file types.
"""
import math
import csv
import re
import logging
from dataclasses import dataclass
from pathlib import Path
import pcbnew

_log = logging.getLogger("kicad_xyrs")


@dataclass
class Settings:
    """
    All the options that can be passed
    """
    origin: tuple[float, float] = (0, 0)


def convert_units(value, unit):
    mult = 1 # mm
    if unit == "mm":
        mult = 1
    elif unit in ["mil", "thou"]:
        mult = 1000/25.4
    elif unit == "inch":
        mult = 1/25.4
    else:
        raise ValueError(f"Unit {unit} unknown")
    return float(value)*mult

def refdes_key(ref):
    """Split refdes into (prefix, number) tuple for natural sorting."""
    match = re.match(r'([A-Za-z]+)(\d+)', ref)
    if match:
        prefix, number = match.groups()
        return (prefix, int(number))
    else:
        # fallback for unexpected formats
        return (ref, 0)


def translate_output(format_dict, df):
    name_map = format_dict["name_map"]
    unit = format_dict["units"]
    for field in ["x", "y", "x size", "y size"]:
        df[field] = [convert_units(pt, unit) for pt in df[field]]

    df.columns = [name_map.get(h, h) for h in df.columns]
    return df[name_map.values()]


def calc_position(center: tuple[float, float], origin: tuple[float, float]):
    """
    Calculate position as relative to the origin and in cartesian coordinates.
    The origin and center should be in native kicad pixel coordinates.
    """
    return (center[0] - origin[0]), -1 * (center[1] - origin[1])


def get_position(p: pcbnew.FOOTPRINT, settings: Settings) -> tuple[float, float]:
    origin = settings.origin
    center = [round(pt, 4) for pt in pcbnew.ToMM(p.GetCenter())]
    position = calc_position(origin=origin, center=center)
    return [round(pt, 4) for pt in position]


def get_origin_by_mode(board, mode: str):
    origin = (0,0)
    bbox = board.GetBoardEdgesBoundingBox()
    mode = mode.upper()
    if mode == "ORIGIN":
        origin = (0,0)
    elif mode == "DRILL":
        ds = board.GetDesignSettings()
        origin = ds.GetAuxOrigin()
    elif mode == "CENTER":
        origin = bbox.GetCenter()
    elif mode == "BOTTOMLEFT":
        origin = (bbox.GetLeft(), bbox.GetBottom())
    elif mode == "BOTTOMRIGHT":
        origin = (bbox.GetRight(), bbox.GetBottom())
    elif mode == "TOPLEFT":
        origin = (bbox.GetLeft(), bbox.GetTop())
    elif mode == "TOPRIGHT":
        origin = (bbox.GetRight(), bbox.GetTop())
    else:
        raise ValueError(f"Unknown mode {mode}")
    return [pcbnew.ToMM(pt) for pt in origin]


def get_field(fp: pcbnew.FOOTPRINT) -> str:
    '''
    Get a field or return empty string
    '''
    try:
        field = fp.GetFieldByName("MPN").GetText()
    except AttributeError:
        field = ""
    return field


# Table of fields and how to get them
_fields = {
    "ref des": (lambda fp, **kwargs: fp.GetReferenceAsString()),
    "side": (lambda fp, **kwargs: "BOTTOM" if fp.GetSide() else "TOP"),
    "x": (lambda fp, **kwargs: get_position(fp, **kwargs)[0]),
    "y": (lambda fp, **kwargs: get_position(fp, **kwargs)[1]),
    "rotation": (lambda fp, **kwargs: fp.GetOrientationDegrees()),
    "type": (lambda fp, **kwargs: "PTH" if fp.HasThroughHolePads() else "SMT"),
    "x size": (lambda fp, **kwargs: pcbnew.ToMM(fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetWidth())),
    "y size": (lambda fp, **kwargs: pcbnew.ToMM(fp.GetCourtyard(pcbnew.F_CrtYd).BBox().GetHeight())),
    "value": (lambda fp, **kwargs: fp.GetValueAsString()),
    "MPN": (lambda fp, **kwargs: get_field(fp)),
    "DNP": (lambda fp, **kwargs: fp.IsDNP()),
    "populate": (lambda fp, **kwargs: not fp.IsDNP()),
    "library": (lambda fp, **kwargs: fp.GetFieldByName("Footprint").GetText().split(":")[0]),
    "footprint": (lambda fp, **kwargs: fp.GetFieldByName("Footprint").GetText().split(":")[1])
}


def build_footprint_report(
    board: pcbnew.BOARD, settings: Settings, footprints: tuple[pcbnew.FOOTPRINT]
) -> list[dict]:
    if footprints:
        assert isinstance(footprints[0], pcbnew.FOOTPRINT)
    return [
        {key: value(p, settings=settings) for key, value in _fields.items()}
        for p in footprints
    ]


ORIGIN_MODES = {
    "ORIGIN",
    "DRILL",
    "CENTER",
    "BOTTOMLEFT",
    "BOTTOMRIGHT",
    "TOPLEFT",
    "TOPRIGHT"
}

macrofab_name_map = {
    "ref des": "Designator",
    "x": "X-Loc",
    "y": "Y-Loc",
    "rotation": "Rotation",
    "side": "Side",
    "type": "Type",
    "x size": "X-Size",
    "y size": "Y-Size",
    "value": "Value",
    "footprint": "Footprint",
    "populate": "Populate",
    "MPN": "MPN",
}

default_name_map = {
    'ref des': 'ref des',
    'side': 'side',
    'x': 'x',
    'y': 'y',
    'rotation': 'rotation',
    'type': 'type',
    'x size': 'x size',
    'y size': 'y size',
    'value': 'value',
    'footprint': 'footprint',
    'library': 'library',
    'DNP': 'DNP',
    'MPN': 'MPN',
}

output_formats = {
    "macrofab": {
        "origin_mode": "BOTTOMLEFT",
        "name_map": macrofab_name_map,
        "units": "thou"},
    "default": {
        "origin_mode": "DRILL",
        "name_map": default_name_map,
        "units": "mm"},
}

"""
Dictionary of supported output formats.

Each format defines:
- `origin_mode`: Coordinate origin ("DRILL", "BOARD", etc.)
- `name_map`: Dictionary of column mappings
- `units`: Units for output. 'mil', 'mm', 'inch' etc.
"""
