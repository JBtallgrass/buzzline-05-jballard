"""
jb_rafting_consumer.py

Consumes JSON messages from a Kafka topic (`rafting_feedback`) 
and processes them for real-time visualization and database storage.

This script:
- Logs ALL customer feedback.
- Flags negative comments with a red 🛑.
- Tracks weekly guide performance trends.
- Stores feedback in an SQLite database for analysis.
- Generates real-time visualizations of sentiment trends.

"""

import os
import json
import time
import sqlite3
from collections import defaultdict
from datetime import datetime
from kafka import KafkaConsumer
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib

matplotlib.use("TkAgg")


from utils.utils_logger import logger

#####################################
# Load Environment Variables
#####################################

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "172.30.179.152:9092")
KAFKA_TOPIC = os.getenv("RAFTING_TOPIC", "rafting_feedback")

if not KAFKA_BROKER or not KAFKA_TOPIC:
    logger.critical("❌ Missing required environment variables.")
    raise EnvironmentError("Missing required environment variables.")

#####################################
# Initialize SQLite Database
#####################################

DB_FILE = "rafting_feedback.db"

def init_db():
    """Initialize SQLite database and create tables if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guide TEXT,
            comment TEXT,
            is_negative BOOLEAN,
            trip_date TEXT,
            week INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()
    logger.info("✅ SQLite database initialized.")

init_db()  # Initialize database on startup

#####################################
# Initialize Tracking Data
#####################################

data_buffer = []
guide_feedback = defaultdict(lambda: {"positive": 0, "negative": 0})
weekly_feedback = defaultdict(lambda: {"positive": 0, "negative": 0})
negative_feedback_log = []

#####################################
# Message Processing and Database Insertion
#####################################

def process_message(message):
    """Process a single feedback message and store it in SQLite."""
    try:
        guide = message.get("guide", "unknown")
        comment = message.get("comment", "No comment provided")
        is_negative = bool(message.get("is_negative", False))
        trip_date = message.get("date", "unknown")

        # Convert trip date to week number
        week_number = datetime.strptime(trip_date, "%Y-%m-%d").isocalendar()[1]
        feedback_type = "negative" if is_negative else "positive"

        # Update tracking structures
        guide_feedback[guide][feedback_type] += 1
        weekly_feedback[(guide, week_number)][feedback_type] += 1

        if is_negative:
            negative_feedback_log.append(message)

        # Store in SQLite database
        save_to_database(guide, comment, is_negative, trip_date, week_number)

        logger.info(f"📝 Feedback ({trip_date}) | Guide: {guide} | Comment: {comment}")
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")

def save_to_database(guide, comment, is_negative, trip_date, week_number):
    """Save processed feedback data to SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (guide, comment, is_negative, trip_date, week)
            VALUES (?, ?, ?, ?, ?)
            """,
            (guide, comment, is_negative, trip_date, week_number),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"❌ Error saving to database: {e}")

#####################################
# Real-Time Visualization
#####################################

def update_chart(frame):
    if not data_buffer:
        return

    df = pd.DataFrame(data_buffer)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["week"] = df["date"].dt.isocalendar().week

    plt.clf()
    plt.subplot(2, 2, 1)
    plot_sentiment_distribution(df)
    
    plt.subplot(2, 2, 2)
    plot_weekly_trend(df)
    
    plt.subplot(2, 2, 3)
    plot_guide_performance(df)
    
    plt.subplot(2, 2, 4)
    plot_negative_feedback_trend(df)
    
    plt.tight_layout()

#####################################
# Visualization Functions
#####################################

def plot_weekly_trend(df):
    weekly_counts = df.groupby('week')['is_negative'].value_counts().unstack().fillna(0)
    weekly_counts.columns = ['Positive', 'Negative']
    weekly_counts.plot(kind='line', ax=plt.gca())
    plt.title("Weekly Feedback Trend")
    plt.xlabel("Week Number")
    plt.ylabel("Feedback Count")

def plot_guide_performance(df):
    guide_counts = df.groupby('guide')['is_negative'].value_counts().unstack().fillna(0)
    guide_counts.columns = ['Positive', 'Negative']
    guide_counts.plot(kind='bar', stacked=True, ax=plt.gca())
    plt.title("Guide Performance (Positive vs Negative)")
    plt.xlabel("Guide")
    plt.ylabel("Feedback Count")
    plt.xticks(rotation=45)

def plot_negative_feedback_trend(df):
    negative_feedback = df[df['is_negative'] == True]
    negative_feedback.groupby('date').size().plot(kind='line', ax=plt.gca())
    plt.title("Daily Negative Feedback Trend")
    plt.xlabel("Date")
    plt.ylabel("Count of Negative Feedback")

def plot_sentiment_distribution(df):
    feedback_counts = df['is_negative'].value_counts()
    feedback_counts.index = ['Positive', 'Negative'] if len(feedback_counts) == 2 else ['Positive']
    feedback_counts.plot(kind='pie', autopct='%1.1f%%', ax=plt.gca())
    plt.title("Sentiment Distribution")
    plt.ylabel("")

#####################################
# Main Kafka Consumer Loop
#####################################

def main():
    """Main function to start the Kafka consumer and process messages."""
    logger.info("🚀 Starting jb_rafting_consumer.")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset="earliest",
        group_id="jb_rafting_group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8"))
    )

    fig = plt.figure(figsize=(12, 10))
    ani = FuncAnimation(fig, update_chart, interval=2000)

    try:
        for message in consumer:
            message_dict = message.value
            process_message(message_dict)
            data_buffer.append(message_dict)

            # Keep buffer size manageable
            if len(data_buffer) > 1000:
                data_buffer.pop(0)

            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.warning("⚠️ Consumer interrupted by user.")
    except Exception as e:
        logger.error(f"❌ Error in Kafka consumer: {e}")
    finally:
        plt.show()
        consumer.close()

#####################################
# Conditional Execution
#####################################

if __name__ == "__main__":
    main()
