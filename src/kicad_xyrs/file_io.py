"""
file_io.py: All the file read and write functions
"""

import csv
from pathlib import Path

import numpy as np
import pandas as pd


def read_csv_to_df(fname: str, **kwargs) -> pd.DataFrame:
    """
    Expects sep or delimiter in kwargs. If not included then we
    fallback on the pandas interpretation
    Use automatic dialect detection by setting sep to None and engine to python
    """
    if "delimiter" in kwargs and "sep" not in kwargs:
        kwargs["sep"] = kwargs["delimiter"]

    kwargs["delimiter"] = None
    if "sep" in kwargs:
        return pd.read_csv(fname, **kwargs)

    # Use automatic dialect detection by setting sep to None and engine to python
    kwargs["sep"] = None
    return pd.read_csv(fname, engine="python", **kwargs)


def read_ods_format_to_df(fname: str, **kwargs) -> pd.DataFrame:
    """
    Read ODS format to dataframe
    """
    import pyexcel_ods3

    data = pyexcel_ods3.get_data(fname, **kwargs)
    ave_line_length = np.mean([len(line) for line in data])
    data_lines = [
        line for line in data if len(line) >= ave_line_length
    ]  # assume this is the data
    header = data_lines[0]
    data_lines = data_lines[1:]
    df_dict = {column: [] for column in header}
    for line in data_lines:
        for column, pt in zip(df_dict.keys(), line, strict=False):
            df_dict[column].append(pt)
    return pd.DataFrame(df_dict)


def get_supported_file_types_df():
    """
    Installed readers
    """
    return [
        {
            "title": "text",
            "kwargs": {
                "header": 0,
                #"skipinitialspace": True,
                "index": False,
                #"comment": "#",
                "quotechar": '"',
                "quoting": csv.QUOTE_MINIMAL,
                "engine": "python",
                "skip_blank_lines": True,
                "sep": "\t",
                "float_format": "%.2f"
            },
            "write_kwargs": {
                "sep": "\t",
                "index": False,
                "header": True,
                "float_format": "%.2f",
                "quotechar": '"',
                "quoting": csv.QUOTE_ALL
            },

            "extensions": ("xyrs",),
            "writedf": pd.DataFrame.to_csv,
            "readf": read_csv_to_df,
        },
        {
            "title": "text",
            "kwargs": {
                "header": 0,
                "skipinitialspace": True,
                "index_col": None,
                "comment": "#",
                "quotechar": '"',
                "quoting": csv.QUOTE_MINIMAL,
                "engine": "python",
                "skip_blank_lines": True,
            },
            "write_kwargs": {
                "index": False,
                "header": True,
                "quotechar": '"',
                "quoting": csv.QUOTE_MINIMAL
            },
            "extensions": ("csv", "txt"),
            "writedf": pd.DataFrame.to_csv,
            "readf": read_csv_to_df,
        },
        {
            "title": "excel",
            "kwargs": {"sheet_name": 0, "header": 0, "skiprows": 0},
            "extensions": ("xls", "xlsx", "xlsm", "xlsb"),
            "writedf": pd.DataFrame.to_excel,
            "readf": pd.read_excel,
        },
        {
            "title": "ods",
            "kwargs": {"sheet_name": 0, "header": 0, "skiprows": 0},
            "extensions": ("ods", "odt", "odf"),
            "writedf": None,
            "readf": read_ods_format_to_df,
        },
    ]


def get_supported_file_formats() -> tuple[str]:
    """
    returns collection of all the supported extensions
    """
    extensions = []
    for entry in get_supported_file_types_df():
        extensions.extend(entry["extensions"])
    return tuple(extensions)


def read_file_to_df(fname: str, **kwargs) -> pd.DataFrame:
    """
    Cycle through extensions, use the reader object to call
    """
    ext = Path(fname).suffix.strip(".").lower()
    df = None
    found = False
    for reader in get_supported_file_types_df():
        if ext in reader["extensions"]:
            found = True
            if kwargs is None:
                kwargs = reader["kwargs"]
            df = reader["readf"](fname, **kwargs)
            break
    if not found:
        msg = f"Extension {ext} unsupported"
        raise UserWarning(msg)
    return pd.DataFrame(df)


def write(df: pd.DataFrame, fname: str, **kwargs) -> None:
    """
    Search for the correct exporter and write the dataframe
    using that writer.
    """
    ext = Path(fname).suffix.strip(".").lower()
    types = get_supported_file_types_df()
    writer = None
    for value in types:
        if ext in value["extensions"]:
            writer = value["writedf"]
            kwargs = kwargs if kwargs else dict()
            defaults = value.get("write_kwargs", value["kwargs"])

            kwargs.update(defaults)
            break

    assert writer
    writer(df, fname, **kwargs)
