"""
csv_feedback_consumer.py

Consumes structured feedback messages from Kafka (`rafting_csv_feedback`)
and writes them into an SQLite database (`rafting_feedback` table).
"""

#####################################
# Import Modules
#####################################

import os
import json
from kafka import KafkaConsumer
from dotenv import load_dotenv
from pathlib import Path
from utils.utils_logger import logger
from db_sqlite_rafting import init_db, insert_feedback
from utils.utils_config import get_sqlite_path

#####################################
# Load Environment Variables
#####################################

load_dotenv()
KAFKA_BROKER = os.getenv("KAFKA_BROKER_ADDRESS", "172.30.179.152:9092")
KAFKA_TOPIC = os.getenv("RAFTING_CSV_TOPIC", "rafting_csv_feedback")
DB_PATH = Path(get_sqlite_path())

#####################################
# Initialize Database
#####################################

init_db(DB_PATH)

#####################################
# Create Kafka Consumer
#####################################

consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset="earliest",
    group_id="rafting_csv_analysis_group",
    value_deserializer=lambda x: json.loads(x.decode("utf-8"))
)

#####################################
# Function to Process and Insert Feedback
#####################################

def process_and_insert_feedback(feedback):
    """
    Process a single feedback message and insert it into the SQLite database.

    Args:
        feedback (dict): The feedback message to process.
    """
    try:
        logger.info(f"📥 Received feedback: {json.dumps(feedback, indent=2)}")
        insert_feedback(feedback, DB_PATH)
    except Exception as e:
        logger.error(f"❌ Failed to process and insert feedback: {e}")

#####################################
# Main Function
#####################################

def main():
    logger.info("🚀 START: Kafka Consumer for Rafting CSV Feedback")
    
    try:
        for message in consumer:
            feedback = message.value
            process_and_insert_feedback(feedback)
    except KeyboardInterrupt:
        logger.warning("⚠️ Consumer interrupted by user.")
    except Exception as e:
        logger.error(f"❌ Error while consuming messages: {e}")
    finally:
        consumer.close()
        logger.info("✅ Kafka consumer closed.")

#####################################
# Conditional Execution
#####################################

if __name__ == "__main__":
    main()
