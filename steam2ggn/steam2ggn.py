#!/usr/bin/env python3

import argparse
import csv
import html
import os
import sys
import requests
import time
from collections import deque
from datetime import datetime, timedelta
from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
from tqdm import tqdm

# Global Constants
RATE_LIMIT_COUNT = 5  # Number of API calls allowed in the rate limit window
RATE_LIMIT_WINDOW = 10  # Time window for rate limit in seconds


def strip_special_chars(text):
    return text.replace('®', '').replace('™', '')


def alternate_characters(text):
    """ Alternate between different apostrophes and quotation marks since they seem to be inconsistent on both Steam
    and GGN"""
    alt_text = text.replace("'", "’").replace('’', "'").replace('"', '“').replace('“', '”').replace('”', '"')
    return alt_text if alt_text != text else None


def html_escape(text):
    """ Ensure proper HTML escaping for output. """
    return html.escape(text)


def write_html_row(outputfile, game_name, status, url):
    """ Write a row to the HTML output file. """
    url_html = f'<a href="{html_escape(url)}" target="_blank">{html_escape(url)}</a>' if url else ''
    outputfile.write(f'<tr><td>{html_escape(game_name)}</td><td>{html_escape(status)}</td><td>{url_html}</td></tr>')
    outputfile.flush()  # Flush output to write data to HTML file in real-time


def process_file(api_key, file_path, output_file='output.html', silent=False, verbose=False):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise FileNotFoundError(f"The file {file_path} does not exist or is empty.")

    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile, open(output_file, 'w', newline='',
                                                                             encoding='utf-8') as outputfile:
        reader = csv.DictReader(csvfile)
        total_lines = sum(1 for _ in reader)
        csvfile.seek(0)  # Reset CSV file pointer to the start after counting lines
        reader = csv.DictReader(csvfile)  # Reinitialize reader

        outputfile.write('<html><body><table border="1"><tr><th>Name</th><th>Status</th><th>URL</th></tr>')

        progress_bar = tqdm(enumerate(reader), total=total_lines, disable=silent)

        if verbose:
            print("CSV Headers:", reader.fieldnames)
            print(f"Starting processing. Total lines: {total_lines}")

        api_call_times = deque(maxlen=RATE_LIMIT_COUNT)

        for i, row in progress_bar:
            if not row.get('game') or not row.get('id'):
                if verbose:
                    print(f"Skipping empty or malformed row {i}: {row}")
                continue

            current_time = datetime.now()
            if len(api_call_times) == RATE_LIMIT_COUNT and (
                    current_time - api_call_times[0]).total_seconds() < RATE_LIMIT_WINDOW:
                sleep_time = RATE_LIMIT_WINDOW - (current_time - api_call_times[0]).total_seconds()
                if verbose:
                    progress_bar.write(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)

            game_name = strip_special_chars(row['game'])
            game_id = row['id']
            try:
                response = make_api_call(api_key, game_name)
                status, url = parse_response(response, game_id)
                write_html_row(outputfile, game_name, status, url)
            except (RequestException, HTTPError, ConnectionError, Timeout) as e:
                progress_bar.write(f"Request failed: {e}")
                continue

            if verbose:
                progress_bar.write(f"API Response for {game_name}: {response}")

            if not silent:
                progress_bar.write(f"{game_name}, {status}, {url}")

            api_call_times.append(datetime.now())  # Add the timestamp of this API call to the queue

        outputfile.write('</table></body></html>')

        if verbose:
            print("Processing completed.")


def make_api_call(api_key, game_name):
    headers = {'X-API-Key': api_key}
    url = f"https://gazellegames.net/api.php?request=torrentgroup&name={game_name}"
    response = requests.get(url, headers=headers).json()

    if response.get('status', '') == 'failure':
        # Try with alternate characters if the name contains specific characters
        alt_game_name = alternate_characters(game_name)
        if alt_game_name:
            url = f"https://gazellegames.net/api.php?request=torrentgroup&name={alt_game_name}"
            response = requests.get(url, headers=headers).json()

    return response


def parse_response(response, game_id):
    if response.get('status', '') == 'failure':
        error_message = response.get('error', 'Unknown error')
        return f'❌ ({error_message})', ''

    high_confidence_match = None
    preferred_match = None
    preferred_order = ["Windows", "Mac", "Linux"]

    for group_id, group_info in response.get('response', {}).get('groups', {}).items():
        weblinks = group_info.get('weblinks', [])
        steam_url = ''

        if isinstance(weblinks, dict):
            steam_url = weblinks.get('Steam', '')
        elif isinstance(weblinks, list):
            for link in weblinks:
                if 'Steam' in link:
                    steam_url = link
                    break

        steam_id = steam_url.split('/app/')[-1].split('/')[0] if '/app/' in steam_url else ''

        if steam_id == game_id:
            high_confidence_match = ('✅', f'https://gazellegames.net/torrents.php?id={group_id}')
            break
        elif steam_url == '':
            platform = group_info.get('platform', '')
            if platform in preferred_order:
                if not preferred_match or preferred_order.index(platform) < preferred_order.index(preferred_match[2]):
                    preferred_match = ('☑️', f'https://gazellegames.net/torrents.php?id={group_id}', platform)

    if high_confidence_match:
        return high_confidence_match
    elif preferred_match:
        return preferred_match[0], preferred_match[1]

    return '❌ (none in preferred platforms)', ''


def main():
    parser = argparse.ArgumentParser(description='Process a CSV file of games and query an API for additional data.')
    parser.add_argument('api_key', help='API key for making requests', type=str)
    parser.add_argument('file_path', help='Path to the CSV file to be processed', type=str)
    parser.add_argument('-o', '--output', help='Output HTML file name', default='output.html', type=str)
    parser.add_argument('-v', '--verbose', action='store_true', help='Print verbose output, including API responses')
    parser.add_argument('-s', '--silent', action='store_true', help='Suppress all output except errors')
    args = parser.parse_args()

    if args.silent:
        level = os.environ.get('LOGLEVEL', 'ERROR').upper()
    else:
        level = os.environ.get('LOGLEVEL', 'INFO').upper()

    try:
        process_file(args.api_key, args.file_path, output_file=args.output, silent=args.silent, verbose=args.verbose)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
