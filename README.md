# kicad_xyrs

Command-line tool to export XYRS (position and rotation) data from KiCad PCB files.
Compatible with Macrofab.

## Features

* Extracts footprint positions, rotations, types, and sizes from `.kicad_pcb` files
* Supports configurable origin modes (`center`, `drill`, `topleft`, etc.)
* Outputs in:

  * **Macrofab format** (`.xyrs`) – ready to upload with Gerbers
  * **Default CSV** – for a better centroid file
* Skips excluded footprints (e.g., virtual or DNP)

## Installation

```bash
pip install .
```

## Usage

```bash
kicad_xyrs --pcb my_board.kicad_pcb --out my_board.xyrs --format macrofab
```

### Options

* `--pcb`: Path to the `.kicad_pcb` file
* `--out`: Output file path (`.csv` or `.xyrs`)
* `--format`: Output format (`default`, `macrofab`)
* `--no-drill-center`: Use (0,0) instead of KiCad drill origin
* `--debug`: Enable debug logging

## Example: Macrofab Export

To export files compatible with Macrofab:

1. Export Gerbers and drill files in KiCad

2. Run:

   ```bash
   kicad_xyrs --pcb my_board.kicad_pcb --out my_board.xyrs --format macrofab
   ```

3. Upload both the `.zip` Gerber archive and `.xyrs` file to [Macrofab](https://macrofab.com/)

## License

MIT License
