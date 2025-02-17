
"""
db_sqlite_rafting.py

Functions:
- init_db(): Initialize the SQLite database and create the 'rafting_feedback' and 'log_events' tables if they don't exist.
- insert_feedback(feedback: dict, db_path: pathlib.Path): Insert a single feedback record into the SQLite database.
- log_event(event_type: str, message: str, db_path: pathlib.Path): Log an event in the 'log_events' table.
- generate_guide_performance_report(db_path: pathlib.Path): Generate a guide performance report and save it as a CSV file.
- plot_guide_performance(db_path: pathlib.Path): Visualize guide performance using matplotlib.
"""

#####################################
# Import Modules
#####################################

import os
import pathlib
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict
from utils.utils_logger import logger
# from utils.utils_config import get_sqlite_path

#####################################
# Database Initialization
#####################################

def init_db(db_path: pathlib.Path) -> None:
    """
    Initialize the SQLite database. Create the 'rafting_feedback' and 'log_events' tables if they don't exist.
    """
    logger.info(f"Initializing SQLite database at {db_path}.")
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rafting_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    guide TEXT,
                    trip_type TEXT,
                    comment TEXT,
                    is_negative TEXT CHECK(is_negative IN ('yes', 'no')),
                    temperature REAL,
                    weather TEXT,
                    wind_speed REAL,
                    rainfall REAL,
                    river_flow REAL,
                    water_level REAL,
                    water_temperature REAL,
                    timestamp TEXT NOT NULL
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS log_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT
                );
            """)
            conn.commit()
        logger.info("SUCCESS: Database initialized and tables are ready.")
    except Exception as e:
        logger.error(f"ERROR: Failed to initialize SQLite database: {e}")

#####################################
# Insert Feedback into Database
#####################################

def insert_feedback(feedback: Dict, db_path: pathlib.Path) -> None:
    """
    Insert a single feedback record into the SQLite database.
    """
    logger.info("Inserting feedback into SQLite database.")
    try:
        init_db(db_path)  # Ensure table exists before inserting
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rafting_feedback (
                    date, guide, trip_type, comment, is_negative, 
                    temperature, weather, wind_speed, rainfall, 
                    river_flow, water_level, water_temperature, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                feedback.get("date"),
                feedback.get("guide"),
                feedback.get("trip_type"),
                feedback.get("comment"),
                feedback.get("is_negative"),
                feedback.get("temperature"),
                feedback.get("weather"),
                feedback.get("wind_speed"),
                feedback.get("rainfall"),
                feedback.get("river_flow"),
                feedback.get("water_level"),
                feedback.get("water_temperature"),
                feedback.get("timestamp")
            ))
            conn.commit()
        log_event("INFO", f"Inserted feedback for guide: {feedback.get('guide')}", db_path)
        logger.info("SUCCESS: Feedback inserted into the database.")
    except Exception as e:
        logger.error(f"ERROR: Failed to insert feedback: {e}")
        log_event("ERROR", f"Failed to insert feedback: {e}", db_path)

#####################################
# Log Event to Database
#####################################

def log_event(event_type: str, message: str, db_path: pathlib.Path) -> None:
    """
    Log an event to the 'log_events' table.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                INSERT INTO log_events (timestamp, event_type, message)
                VALUES (datetime('now'), ?, ?);
            """, (event_type, message))
            conn.commit()
    except Exception as e:
        logger.error(f"ERROR: Failed to log event: {e}")

#####################################
# Generate Guide Performance Report
#####################################

def generate_guide_performance_report(db_path: pathlib.Path) -> None:
    """
    Generate a performance report for each rafting guide and save it as a CSV file.
    """
    logger.info("Generating guide performance report...")
    try:
        with sqlite3.connect(db_path) as conn:
            query = """
                SELECT guide,
                       COUNT(CASE WHEN is_negative = 'no' THEN 1 END) AS positive_feedback,
                       COUNT(CASE WHEN is_negative = 'yes' THEN 1 END) AS negative_feedback
                FROM rafting_feedback
                GROUP BY guide
                ORDER BY guide;
            """
            df = pd.read_sql_query(query, conn)
            df.to_csv("guide_performance_report.csv", index=False)
            logger.info("Guide performance report saved as 'guide_performance_report.csv'.")
    except Exception as e:
        logger.error(f"ERROR: Failed to generate guide performance report: {e}")

#####################################
# Visualize Guide Performance
#####################################

def plot_guide_performance(db_path: pathlib.Path) -> None:
    """
    Visualize guide performance (positive vs. negative feedback).
    """
    logger.info("Generating guide performance visualization...")
    try:
        with sqlite3.connect(db_path) as conn:
            query = """
                SELECT guide,
                       COUNT(CASE WHEN is_negative = 'no' THEN 1 END) AS positive_feedback,
                       COUNT(CASE WHEN is_negative = 'yes' THEN 1 END) AS negative_feedback
                FROM rafting_feedback
                GROUP BY guide;
            """
            df = pd.read_sql_query(query, conn)
        df.plot(kind='bar', x='guide', stacked=True)
        plt.title("Guide Performance (Positive vs. Negative Feedback)")
        plt.xlabel("Guide")
        plt.ylabel("Feedback Count")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except Exception as e:
        logger.error(f"ERROR: Failed to generate visualization: {e}")
