# Game Information Processing Script

## Overview

This Python script processes video game information from a CSV file, makes API calls to a specified endpoint, and
generates an HTML file with the results. It categorizes games as high or low confidence matches based on the comparison
of game IDs from the CSV file and the API response.

## Requirements

- Python 3.x.
- `requests` library for handling API requests (Install using `pip install requests`).
- `tqdm` library for progress bar visualization (Install using `pip install tqdm`).
- A GGN API key, obtainable by following instructions on the GGN wiki.
- A CSV file with `game` and `id` columns, representing a game's Steam name and Steam ID. This file can be generated
  using tools like [Steam Lab](https://www.lorenzostanco.com/lab/steam/).

## Usage

Run the script with an API key and the CSV file path as command-line arguments. You can optionally enable verbose output
or suppress all output using the provided flags. The script outputs an `output.html` file containing the processed
results.

### Example Command

```bash
python steam2ggn.py "your_api_key" "path_to_your_csv_file.csv"
