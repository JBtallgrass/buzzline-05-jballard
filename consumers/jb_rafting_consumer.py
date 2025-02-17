"""
jb_rafting_consumer.py

Consumes JSON messages from a Kafka topic (`rafting_feedback`) 
and processes them for real-time visualization and database storage.

This script:
- Logs ALL customer feedback.
- Flags negative comments with a red 🛑.
- Tracks weekly guide performance trends.
- Stores feedback in an SQLite database via `db_sqlite_rafting.py`.
- Generates real-time visualizations of sentiment trends.

"""

import os
import json
import time
import threading
from collections import defaultdict
from datetime import datetime
from kafka import KafkaConsumer
from dotenv import load_dotenv
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib
import pathlib

matplotlib.use("TkAgg")

from utils.utils_logger import logger
from db_sqlite_rafting import insert_feedback
from utils.utils_config import get_sqlite_path

#####################################
# Load Environment Variables
#####################################

load_dotenv()

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = os.getenv("RAFTING_TOPIC", "rafting_feedback")

if not KAFKA_BROKER or not KAFKA_TOPIC:
    logger.critical("❌ Missing required environment variables.")
    raise EnvironmentError("Missing required environment variables.")

#####################################
# Get SQLite Database Path
#####################################

DB_PATH = pathlib.Path(get_sqlite_path())

#####################################
# Create folder for saving plots
#####################################

SAVE_FOLDER = "visualizations"
os.makedirs(SAVE_FOLDER, exist_ok=True)

# Global counter for messages processed
message_count = 0

#####################################
# Initialize Tracking Data
#####################################

data_buffer = []
guide_feedback = defaultdict(lambda: {"positive": 0, "negative": 0})
weekly_feedback = defaultdict(lambda: {"positive": 0, "negative": 0})
negative_feedback_log = []

#####################################
# Kafka Consumer with Auto-Reconnect
#####################################

def create_kafka_consumer():
    """Creates a Kafka consumer with automatic retry on failure."""
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                auto_offset_reset="earliest",
                group_id="jb_rafting_group",
                value_deserializer=lambda x: json.loads(x.decode("utf-8"))
            )
            logger.info("✅ Connected to Kafka.")
            return consumer
        except Exception as e:
            logger.error(f"❌ Kafka connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

#####################################
# Message Processing and Database Insertion
#####################################

def process_message(message):
    """Process a single feedback message and store it in SQLite."""
    global message_count

    try:
        guide = message.get("guide", "unknown")
        comment = message.get("comment", "No comment provided")
        is_negative = "yes" if message.get("is_negative", False) else "no"
        trip_date = message.get("date", "unknown")

        # Convert trip date to week number
        week_number = datetime.strptime(trip_date, "%Y-%m-%d").isocalendar()[1]
        feedback_type = "negative" if is_negative == "yes" else "positive"

        # Update tracking structures
        guide_feedback[guide][feedback_type] += 1
        weekly_feedback[(guide, week_number)][feedback_type] += 1

        if is_negative == "yes":
            negative_feedback_log.append(message)

        # Store in SQLite database using `insert_feedback` from `db_sqlite_rafting.py`
        feedback_data = {
            "date": trip_date,
            "guide": guide,
            "trip_type": message.get("trip_type", "unknown"),
            "comment": comment,
            "is_negative": is_negative,
            "temperature": message.get("temperature", "N/A"),
            "weather": message.get("weather", "N/A"),
            "wind_speed": message.get("wind_speed", "N/A"),
            "rainfall": message.get("rainfall", "N/A"),
            "river_flow": message.get("river_flow", "N/A"),
            "water_level": message.get("water_level", "N/A"),
            "water_temperature": message.get("water_temperature", "N/A"),
            "timestamp": message.get("timestamp", datetime.utcnow().isoformat())
        }
        insert_feedback(feedback_data, DB_PATH)

        logger.info(f"📝 Feedback ({trip_date}) | Guide: {guide} | Comment: {comment}")

        message_count += 1  # Increment the message counter
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")

#####################################
# Real-Time Visualization
#####################################

def plot_guide_performance(df):
    """Plot the performance of guides based on feedback."""
    guide_performance = df.groupby("guide")["is_negative"].value_counts().unstack().fillna(0)
    guide_performance.plot(kind="bar", stacked=True, color=["green", "red"])
    plt.title("Guide Performance")
    plt.xlabel("Guide")
    plt.ylabel("Count")
    plt.xticks(rotation=45)

def plot_sentiment_distribution(df):
    """Plot the distribution of sentiment in the feedback."""
    sentiment_counts = df["is_negative"].value_counts()
    sentiment_counts.plot(kind="bar", color=["green", "red"])
    plt.title("Sentiment Distribution")
    plt.xlabel("Sentiment")
    plt.ylabel("Count")
    plt.xticks(ticks=[0, 1], labels=["Positive", "Negative"], rotation=0)

def plot_weekly_trend(df):
    """Plot the weekly trend of feedback."""
    weekly_counts = df.groupby("week")["is_negative"].value_counts().unstack().fillna(0)
    weekly_counts.plot(kind="bar", stacked=True, color=["green", "red"])
    plt.title("Weekly Feedback Trend")
    plt.xlabel("Week")
    plt.ylabel("Count")
    plt.xticks(rotation=45)

def plot_negative_feedback_trend(df):
    """Plot the trend of negative feedback over time."""
    negative_feedback = df[df["is_negative"] == "yes"]
    negative_feedback["date"] = pd.to_datetime(negative_feedback["date"], errors="coerce")
    negative_feedback.set_index("date", inplace=True)
    negative_feedback.resample("W").size().plot(kind="line", color="red")
    plt.title("Negative Feedback Trend")
    plt.xlabel("Date")
    plt.ylabel("Count")

def update_chart(frame):
    global message_count

    if not data_buffer:
        return

    df = pd.DataFrame(data_buffer)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["week"] = df["date"].dt.isocalendar().week

    plt.clf()
    plt.figure(figsize=(14, 10))
    plt.subplots_adjust(hspace=0.4, wspace=0.3)

    plt.subplot(2, 2, 1)
    plot_sentiment_distribution(df)

    plt.subplot(2, 2, 2)
    plot_weekly_trend(df)

    plt.subplot(2, 2, 3)
    plot_guide_performance(df)

    plt.subplot(2, 2, 4)
    plot_negative_feedback_trend(df)

    plt.tight_layout()
    plt.draw()
    plt.pause(0.1)

    #####################################
    # Save visualization at defined intervals
    #####################################
    if message_count == 1 or message_count % 5 == 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = os.path.join(SAVE_FOLDER, f"feedback_plot_{timestamp}.png")
        plt.savefig(save_path)
        print(f"📊 Saved visualization: {save_path}")

#####################################
# Kafka Consumer Loop in a Separate Thread
#####################################

def kafka_consumer_loop():
    """Runs the Kafka consumer in a separate thread."""
    try:
        for message in consumer:
            process_message(message.value)
            data_buffer.append(message.value)

            if len(data_buffer) > 1000:
                data_buffer.pop(0)

            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.warning("⚠️ Consumer interrupted by user.")
    except Exception as e:
        logger.error(f"❌ Error in Kafka consumer: {e}")
    finally:
        consumer.close()

#####################################
# Main Function
#####################################

def main():
    logger.info("🚀 Starting jb_rafting_consumer.")
    global consumer
    consumer = create_kafka_consumer()

    fig = plt.figure(figsize=(12, 10))
    global ani
    ani = FuncAnimation(fig, update_chart, interval=2000, cache_frame_data=False)

    plt.ion()
    plt.show(block=False)

    kafka_thread = threading.Thread(target=kafka_consumer_loop, daemon=True)
    kafka_thread.start()

    while True:
        plt.pause(0.1)

#####################################
# Conditional Execution
#####################################

if __name__ == "__main__":
    main()
