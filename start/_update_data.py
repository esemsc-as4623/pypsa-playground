import csv
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def fill_years_csv(start_year: int, end_year: int, data_repo: str = "sample_data") -> None:
    """
    Fill a CSV file with years from start_year to end_year (inclusive).
    
    Parameters
    ----------
    - start_year: The starting year
    - end_year: The ending year (inclusive)
    - data_repo: Directory where the CSV file is located (default: "sample_data")

    Raises
    ------
    - ValueError: If start_year is greater than end_year
    - IOError: If unable to write to the CSV file
    """
    logger.info(f"Starting to fill years CSV from {start_year} to {end_year}")

    # Validate input
    if start_year > end_year:
        logger.error(f"Invalid year range: start_year ({start_year}) > end_year ({end_year})")
        raise ValueError(f"start_year ({start_year}) must be <= end_year ({end_year})")
    
    csv_path = Path(data_repo) / "YEAR.csv"

    # Ensure directory exists
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    # Create years list
    years = list(range(start_year, end_year + 1))
    
    try:
        # Write to CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['VALUE'])  # Header
            for year in years:
                writer.writerow([year])
        
        logger.info(f"Successfully wrote {len(years)} years to {csv_path}")
        
    except IOError as e:
        logger.exception(f"Failed to write to {csv_path}")
        raise

    
