# https://sauran.ac.za/api/DataDownload/SUN/Minute/2023-12-31/2023-12-31
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

start_date = datetime(2010, 5, 1)
end_date = datetime(2024, 12, 31)

current_date = start_date
while current_date <= end_date:
    month_start = current_date.replace(day=1)
    month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)

    if month_end > end_date:
        month_end = end_date

    start_str = month_start.strftime('%Y-%m-%d')
    end_str = month_end.strftime('%Y-%m-%d')

    url = f"https://sauran.ac.za/api/DataDownload/SUN/Minute/{start_str}/{end_str}"

    response = requests.get(url)

    if response.status_code == 200:
        filename = f"sauran_{start_str}_{end_str}.csv"
        with open(filename, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
    else:
        print(f"Failed to download data for {start_str} to {end_str}")

    current_date = month_start + relativedelta(months=1)
