#!/usr/bin/env python
"""
Fetch Mark Six lottery results from lottery.hk website.
Scrapes the latest results and updates history.csv.
"""

import requests
from bs4 import BeautifulSoup
import csv
from pathlib import Path
from datetime import datetime
import re

def fetch_mark_six_results(year=2026):
    """
    Fetch Mark Six results for a given year from lottery.hk.
    
    Args:
        year: Year to fetch results for (default: 2026)
    
    Returns:
        List of dictionaries containing draw data
    """
    url = f"https://lottery.hk/en/mark-six/results/{year}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all draw result rows
        results = []
        
        # The structure shows draw numbers like 26/028, 26/027, etc.
        # We need to parse the table structure
        table_rows = soup.find_all('tr')
        
        for row in table_rows:
            cells = row.find_all('td')
            if len(cells) >= 3:
                # Extract draw number (e.g., "26/028")
                draw_cell = cells[0].get_text(strip=True)
                
                # Extract date
                date_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                
                # Extract numbers (should be in the third cell)
                numbers_cell = cells[2] if len(cells) > 2 else None
                
                if numbers_cell:
                    # Find all number elements
                    number_divs = numbers_cell.find_all('div', class_='ball')
                    if not number_divs:
                        # Try alternative structure
                        number_divs = numbers_cell.find_all(string=True)
                    
                    numbers = []
                    for num_div in number_divs:
                        num_text = num_div.get_text(strip=True) if hasattr(num_div, 'get_text') else str(num_div).strip()
                        if num_text.isdigit():
                            numbers.append(int(num_text))
                    
                    if len(numbers) >= 7 and draw_cell and date_cell:
                        # Parse date (format might be like "13 Mar 2026" or "2026-03-13")
                        parsed_date = parse_date(date_cell)
                        
                        if parsed_date:
                            results.append({
                                'draw_number': draw_cell,
                                'date': parsed_date,
                                'n1': numbers[0],
                                'n2': numbers[1],
                                'n3': numbers[2],
                                'n4': numbers[3],
                                'n5': numbers[4],
                                'n6': numbers[5],
                                'special_number': numbers[6]
                            })
        
        return results
        
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []


def parse_date(date_str):
    """
    Parse various date formats to YYYY-MM-DD.
    
    Args:
        date_str: Date string in various formats
    
    Returns:
        Date string in YYYY-MM-DD format or None
    """
    # Try different date formats
    formats = [
        "%d %b %Y",      # 13 Mar 2026
        "%d %B %Y",      # 13 March 2026
        "%Y-%m-%d",      # 2026-03-13
        "%d/%m/%Y",      # 13/03/2026
        "%m/%d/%Y",      # 03/13/2026
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    return None


def update_history_csv(new_results, csv_path):
    """
    Update history.csv with new results, avoiding duplicates.
    
    Args:
        new_results: List of new result dictionaries
        csv_path: Path to history.csv file
    """
    # Read existing data
    existing_dates = set()
    existing_data = []
    
    if csv_path.exists():
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_dates.add(row['date'])
                existing_data.append(row)
    
    # Add new results (avoiding duplicates)
    added_count = 0
    for result in new_results:
        if result['date'] not in existing_dates:
            existing_data.append({
                'date': result['date'],
                'n1': result['n1'],
                'n2': result['n2'],
                'n3': result['n3'],
                'n4': result['n4'],
                'n5': result['n5'],
                'n6': result['n6'],
                'special_number': result['special_number']
            })
            existing_dates.add(result['date'])
            added_count += 1
    
    # Sort by date (newest first)
    existing_data.sort(key=lambda x: x['date'], reverse=True)
    
    # Write back to CSV
    with open(csv_path, 'w', newline='') as f:
        fieldnames = ['date', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'special_number']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_data)
    
    print(f"Updated history.csv: {added_count} new entries added, {len(existing_data)} total entries")
    return added_count


def main():
    """Main function to fetch and update Mark Six data."""
    print("Fetching Mark Six results...")
    
    script_dir = Path(__file__).parent
    csv_path = script_dir / "history.csv"
    
    # Fetch results for 2026 and 2025
    results_2026 = fetch_mark_six_results(2026)
    results_2025 = fetch_mark_six_results(2025)
    
    all_results = results_2026 + results_2025
    
    if all_results:
        print(f"Fetched {len(all_results)} results")
        added = update_history_csv(all_results, csv_path)
        
        if added > 0:
            print(f"✓ Successfully added {added} new entries")
        else:
            print("✓ No new entries (data is up to date)")
    else:
        print("✗ Failed to fetch results")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
