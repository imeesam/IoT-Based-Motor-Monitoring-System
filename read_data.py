from flask import Flask, render_template, jsonify
import threading
from datetime import datetime
import gc
import serial
import requests
import time
import psycopg2  # PostgreSQL
import csv
import os

app = Flask(__name__)

# ------------------- Configuration -------------------
data_history = {
    'labels': [],
    'x': [],
    'y': [],
    'z': [],
    'total': [],
    'temperature': []
}

url = "http://localhost:3000/api/update-iot-data"
ser = serial.Serial('COM4', 115200)  # Adjust COM port and baudrate

# PostgreSQL connection config
DB_HOST = "localhost"
DB_NAME = "iot_db"
DB_USER = "postgres"
DB_PASSWORD = "12345678"

# CSV file path for SD card logging
SD_CARD_PATH = "sd_card_log.csv"

# ------------------- Setup PostgreSQL -------------------
def init_db():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP,
            x FLOAT,
            y FLOAT,
            z FLOAT,
            total FLOAT,
            temperature FLOAT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

# Initialize CSV file for SD card logging
def init_csv():
    if not os.path.exists(SD_CARD_PATH):
        with open(SD_CARD_PATH, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "x", "y", "z", "total", "temperature"])

# ------------------- Serial Reading -------------------
def read_serial_data():
    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                values = line.split(',')
                if len(values) == 6:
                    incoming_timestamp = float(values[0])  # UNIX timestamp from Arduino
                    x = float(values[1])
                    y = float(values[2])
                    z = float(values[3])
                    total = float(values[4])
                    temperature = float(values[5])
                    
                    dt_object = datetime.utcfromtimestamp(incoming_timestamp)
                    formatted_timestamp = dt_object.strftime('%Y-%m-%d %H:%M:%S')

                    # Append to history
                    data_history['labels'].append(formatted_timestamp)
                    data_history['x'].append(x)
                    data_history['y'].append(y)
                    data_history['z'].append(z)
                    data_history['total'].append(total)
                    data_history['temperature'].append(temperature)

                    # Send to remote server (optional)
                    data = {
                        'timestamp': formatted_timestamp,
                        'x': x, 'y': y, 'z': z,
                        'total': total, 'temperature': temperature
                    }
                    try:
                        response = requests.post(url, json=data)
                        print(f"Data sent: {data}, Response: {response.status_code}")
                    except:
                        print("Failed to send data to server.")

                    # ------------------- Log to PostgreSQL -------------------
                    try:
                        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO sensor_data (timestamp, x, y, z, total, temperature)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (formatted_timestamp, x, y, z, total, temperature))
                        conn.commit()
                        cursor.close()
                        conn.close()
                    except Exception as e:
                        print(f"PostgreSQL Error: {e}")

                    # ------------------- Log to SD card CSV -------------------
                    try:
                        with open(SD_CARD_PATH, mode='a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([formatted_timestamp, x, y, z, total, temperature])
                    except Exception as e:
                        print(f"CSV Logging Error: {e}")

            time.sleep(1)
        except serial.SerialException as e:
            print(f"Serial Error: {e}")
            time.sleep(5)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

# ------------------- Flask Routes -------------------
@app.route('/')
def index():
    gc.collect()
    return render_template('graph1.html')

@app.route('/api/get-graph-data', methods=['GET'])
def get_graph_data():
    return jsonify(data_history)

# ------------------- Main -------------------
if __name__ == "__main__":
    init_db()
    init_csv()
    threading.Thread(target=read_serial_data, daemon=True).start()
    app.run(port=3000, debug=True)
