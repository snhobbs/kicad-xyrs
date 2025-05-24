"""
kicad_xyrs
Command line tool which exports the position of footprints from a PCB to create a test point document
"""
import math
import csv
import re
import logging
from dataclasses import dataclass
from pathlib import Path
import pcbnew

_log = logging.getLogger("kicad_xyrs")

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
    "DNP": "Populate",
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
    "macrofab": {"origin_mode": "BOTTOMLEFT", "name_map": macrofab_name_map, "units": "thou", "ext": ".xyrs"},
    "default": {"name_map": default_name_map, "units": "mm", "ext": ".csv"},
}


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


@dataclass
class Settings:
    """
    All the options that can be passed
    """
    origin: tuple[float, float] = (0, 0)


def calc_position(center: tuple[float, float], origin: tuple[float, float]):
    """
    Calculate position as relative to the origin and in cartesian coordinates.
    The origin and center should be in native kicad pixel coordinates.
    """
    return (center[0] - origin[0]), -1 * (center[1] - origin[1])


def get_position(p: pcbnew.FOOTPRINT, settings: Settings) -> tuple[float, float]:
    """
    Get the center of the pad, the origin setting, and the quadrant setting,
    calculate the transformed position.

    The position internal to kicad never changes. The position is always the distance from
    the top left with x increasing to the right and y increasing down.

    Take the origin location and calculate the distance. Then multiple the axis so it is
    increasing in the desired direction. To match the gerbers this should be increasing right and up.
    """
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
