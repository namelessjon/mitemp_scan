"""Poll a number of Xaomi MiTemp sensors"""

__version__ = "0.1"

from mitemp_bt.mitemp_bt_poller import MiTempBtPoller
from btlewrap.bluepy import BluepyBackend
import time
import logging
import psycopg2
import os
import yaml
import sys

logger = logging.getLogger('mitemp_scan')


def format_sensor_readings(sensor_id, readings):
    reading_id = {
                    'sensor_id': sensor_id,
                    'timestamp': readings['timestamp'],
                }
    reading_array = [dict(measure_type=k, reading=v, **reading_id) for k, v in readings['readings'].items()]
    return reading_array


def _write_many_sensor_readings(cursor, sensor_id, readings):
    sql = """
    INSERT INTO sensor_readings(time, sensor_id, measure_type, reading)
    VALUES %s
    """
    template = "(%(timestamp)s, %(sensor_id)s, %(measure_type)s, %(reading)s)"
    form_readings = format_sensor_readings(sensor_id, readings)
    psycopg2.extras.execute_values(
            cursor=cursor,
            sql=sql,
            argslist=form_readings,
            template=template,
            )


def _find_sensor(cursor, sensor_name):
    id = cursor.execute("SELECT id FROM sensors WHERE sensor = %s",
            (sensor_name,))
    id = cursor.fetchone()
    return id


def write_readings(connection_string, readings):
    conn = None
    sensor_name = readings['name']
    try:
        conn = psycopg2.connect(connection_string)
        with conn, conn.cursor() as cur:
            sensor = _find_sensor(cur, sensor_name)
            _write_many_sensor_readings(cur, sensor, readings)
    finally:
        if conn:
            conn.close()


def read_config_file(config_file):
    with open(config_file, "r") as f:
        return yaml.load(f)


class XaomiSensor(object):
    def __init__(self, name, poller, measurements):
        self.name = name
        self._poller = poller
        self._measurements = measurements
        if self._measurements is None:
            self._measurements = ['temperature', 'humidity', 'battery']

    def read(self):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            readings = {
                        'name': self.name,
                        'timestamp': timestamp,
                    }
            measures = {m: self._poller.parameter_value(m) for m in self._measurements}
            readings['readings'] = measures
            return readings
        except Exception as e:
            logger.error("Failed to connect to sensor (%s)", str(e))
            return None


def create_xaomi_poller(sensor, default_interval=300):
    if 'mac' in sensor:
        timeout = max(sensor.get('interval', default_interval) - 60, 60)
        poller = MiTempBtPoller(sensor['mac'],
                                BluepyBackend,
                                cache_timeout=timeout)
        return XaomiSensor(sensor['name'],
                           poller,
                           sensor.get('measures'))
    else:
        raise RuntimeError(f"No mac for sensor '{sensor['name']}'")


def main(config_file):

    # read in the config
    config = read_config_file(config_file)
    default_interval = config.get('default_interval', 300)

    sensors = {}
    error = False
    for sensor in config['sensors']:
        name = sensor['name']
        st = sensor['type']
        if st == 'xaomi_mitemp':
            sensors[name] = create_xaomi_poller(sensor, default_interval)
        else:
            error = True
            logger.error("Unknown sensor type for %s. "
                         "(valid values are: xaomi_mitemp)", sensor['name'])

    if error:
        logger.error("Problem intialising sensors")
        sys.exit(1)

    while True:
        start = time.monotonic()

        for (name, sensor) in sensors:
            readings = sensor.read()
            if readings:
                print(json.dumps(readings))
                for attempt in range(1, 6):
                    try:
                        write_readings(os.environ['DATABASE_DSN'],
                                       readings)
                    except Exception:
                        logger.exception("Failed to write to DB")
                        sleep_time = random.uniform(1, 2**attempt)
                        time.sleep(sleep_time)

        end = time.monotonic()
        duration = end - start

        time.sleep(default_interval - min(duration, 60))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', help="The YAML config file")
    args = parser.parse_args()
    main(args.config_file)
