from mitemp_bt.mitemp_bt_poller import MiTempBtPoller
from btlewrap.bluepy import BluepyBackend
import time
import logging
import psycopg2
import os

logger = logging.getLogger('mitemp_scan')

bt_mac = "xx:xx:xx:xx:xx"
sensor_id = f'xaomi-{bt_mac}'

def _write_one_sensor_reading(cursor, sensor, reading_type, reading):
    cursor.execute("INSERT INTO sensor_readings(time, sensor_id, measure_type, reading) VALUES (NOW(), %s, %s, %s)", (sensor, reading_type, reading))


def _write_many_sensor_readings(cursor, sensor, readings):
    for (t, reading) in readings.items():
        _write_one_sensor_reading(cursor, sensor, t, reading)

def _find_sensor(cursor, sensor_name):
    id = cursor.execute("SELECT id FROM sensors WHERE sensor = %s",
            (sensor_name,))
    id = cursor.fetchone()
    return id

def write_readings(connection_string, sensor_name, readings):
    conn = None
    try:
        conn = psycopg2.connect(connection_string)
        with conn, conn.cursor() as cur:
            sensor = _find_sensor(cur, sensor_name)
            _write_many_sensor_readings(cur, sensor, readings)
    finally:
        if conn:
            conn.close()


def main():

    poller = MiTempBtPoller(bt_mac, BluepyBackend, cache_timeout=240)

    with open("mitemp.log", "a", buffering=1) as fout:
        while True:
            start = time.monotonic()
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            try:
                temp = poller.parameter_value('temperature')
                humid = poller.parameter_value('humidity')
                battery = poller.parameter_value('battery')
            except Exception as e:
                logger.error("Failed to connect to sensor (%s)", str(e))
                time.sleep(60)
                continue

            tsv = f"{timestamp}\t{temp}\t{humid}\t{battery}"
            print(tsv)
            fout.write(f"{tsv}\n")
            try:
                write_readings(os.environ['DATABASE_DSN'],
                    sensor_id,
                    {'temperature': temp, 'humidity': humid, 'battery': battery})
            except:
                logger.exception("Failed to write to DB")
            end = time.monotonic()
            duration = end - start

            time.sleep(60*5 - min(duration, 60))


if __name__ == '__main__':
    main()
