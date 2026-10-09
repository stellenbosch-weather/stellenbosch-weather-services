#!/usr/bin/env python3
import os
import sys
import csv
import mysql.connector
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from settings_loader import load_database_settings

if len(sys.argv) < 2:
    print(f"Usage: python3 {sys.argv[0]} <file1.csv> [file2.csv ...]")
    sys.exit(1)

table_name = "SB_TMin"
data_files = sys.argv[1:]
db_config = load_database_settings()

def main():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        for data_file in data_files:
            print(f"--- Processing file: {data_file} ---")
            try:
                with open(data_file, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)

                    # Skip line 1 (Site info)
                    _ = next(reader)
                    # Line 2: The actual field names
                    fields = next(reader)
                    # Line 3 & 4: Units and Processing info (skip)
                    next(reader)
                    next(reader)

                    # Map field names to DB names
                    db_columns = []
                    for x in fields:
                        x = x.strip()
                        if x == "TmStamp": x = "TimeStamp"
                        elif x == "RecNum": x = "Record"
                        db_columns.append(x)

                    # Prepend Date and Time as they exist in DB schema
                    full_db_columns = ["Date", "Time"] + db_columns

                    countlines = 4
                    for row in reader:
                        countlines += 1
                        if not row or not row[0]:
                            continue

                        # Convert CSV format (01/06/2023 00:00:00) to DB formats
                        csv_timestamp = row[0]
                        try:
                            dt_obj = datetime.strptime(csv_timestamp, '%d/%m/%Y %H:%M:%S')
                            db_timestamp = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
                            db_date = dt_obj.strftime('%Y-%m-%d')
                            db_time = dt_obj.strftime('%H:%M:%S')
                        except ValueError:
                            print(f"Line {countlines}: Invalid timestamp format '{csv_timestamp}'")
                            continue

                        # Prepare data, handling 'NA' and 'NAN' as None (NULL)
                        processed_values = []
                        for val in row[1:]:
                            val = val.strip()
                            if val in ["NA", "NAN"]:
                                processed_values.append(None)
                            else:
                                processed_values.append(val)

                        # Data order: Date, Time, TimeStamp, ...rest of the row
                        data_to_insert = [db_date, db_time, db_timestamp] + processed_values

                        cols_str = ", ".join([f"`{c}`" for c in full_db_columns])
                        placeholders = ", ".join(["%s"] * len(full_db_columns))
                        # Update all columns except the primary key (TimeStamp) and index keys (Date, Time)
                        update_str = ", ".join([f"`{c}`=VALUES(`{c}`)" for c in full_db_columns if c not in ["TimeStamp", "Date", "Time"]])

                        sql = f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_str}"

                        cursor.execute(sql, data_to_insert)
                        if cursor.rowcount == 1:
                            print(f"{data_file} @ {countlines}: Inserted new record for {db_timestamp}")
                        elif cursor.rowcount == 2:
                            print(f"{data_file} @ {countlines}: Updated record for {db_timestamp}")

                conn.commit()
            except FileNotFoundError:
                print(f"Error: File '{data_file}' not found.")
            except Exception as e:
                print(f"Error processing '{data_file}': {e}")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
