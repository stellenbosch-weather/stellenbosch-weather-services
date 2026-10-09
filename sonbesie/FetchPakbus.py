import datetime
from dateutil.relativedelta import relativedelta
from pycampbellcr1000 import CR1000, device


def get_oldest_timestamp(host):
    # Initialize connection to the logger
    logger = CR1000.from_url(host)
    
    # List available tables
    tables = logger.list_tables()
    print("Available tables:", tables)

    start_date = datetime.datetime(2010, 1, 1, 0, 0, 0)
    # end_date = start_date + relativedelta(months=1)
    end_date = datetime.datetime(2025, 12, 1, 0, 0, 0)
    data = logger.get_data('TMin', start_date, end_date)
    print(data[0]["Datetime"])


if __name__ == "__main__":
    # Example usage for localhost:5001
    # Replace 'Public' with your actual table name (e.g., 'Daily', 'Hourly')
    get_oldest_timestamp('tcp:146.232.144.63:5001')