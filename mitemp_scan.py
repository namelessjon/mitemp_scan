"""Poll a number of Xaomi MiTemp sensors"""

__version__ = "0.5.1"

from mitemp_bt.mitemp_bt_poller import MiTempBtPoller
from btlewrap.bluepy import BluepyBackend
import logging
import psycopg2
import psycopg2.extras
import os
import yaml
import json
import sys
import time
import random
import datetime
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

logger = logging.getLogger('mitemp_scan')


@dataclass(frozen=True)
class XaomiReadings:
    __slots__ = ['name', 'location', 'timestamp', 'temperature', 'humidity', 'battery']

    name: str
    location: str
    timestamp: str
    temperature: float
    humidity: float
    battery: float

    reading_types = ('temperature', 'humidity', 'battery')

    def format(self, sensor_id: int) -> Dict[str, Any]:
        d = asdict(self)
        del d['name']
        d['sensor_id'] = sensor_id
        return d

    @property
    def asjson(self):
        """
        Returns dictionary suitable for json serializing

        Preserves the history formatting
        """
        return {
            'name': self.name,
            'location': self.location,
            'timestamp': self.timestamp,
            'readings': { r: getattr(self, r) for r in self.reading_types },
        }


def format_sensor_readings(sensor_id: int, readings: XaomiReadings):
    return readings.format(sensor_id)


def format_multiple_readings(cursor, readings: List[XaomiReadings]):
    name_map = {}

    # format readings into list of lists
    formatted_readings = [format_one_reading(cursor, name_map, r) for r in readings]

    return formatted_readings


def format_one_reading(cursor, name_map, reading):
    sensor_name = reading['name']
    sensor_id = _lookup_sensor(cursor, name_map, sensor_name)

    return format_sensor_readings(sensor_id, reading)


def _lookup_sensor(cursor, name_map: Dict[str, int], sensor_name: str) -> int:
    if sensor_name in name_map:
        sensor_id = name_map[sensor_name]
    else:
        sensor_id = _find_sensor(cursor, sensor_name)
        name_map[sensor_name] = sensor_id
    return sensor_id



def _write_many_sensor_readings(cursor, readings: List[Dict[str, Any]]):

    stmt = """
    INSERT INTO sensor_measurements(time, sensor_id, location, temperature, humidity, battery)
    VALUES %s
    """

    template = "(%(timestamp)s, %(sensor_id)s, %(location)s, %(temperature)s, %(humidity)s, %(battery)s)"
    psycopg2.extras.execute_values(
            cur=cursor,
            sql=stmt,
            argslist=readings,
            template=template,
            )


def _find_sensor(cursor, sensor_name: str) -> int:
    id = cursor.execute("SELECT id FROM sensors WHERE sensor = %s",
            (sensor_name,))
    id = cursor.fetchone()[0]
    return id


def write_readings(connection_string: str, readings: XaomiReadings):
    write_many_readings(connection_string, [readings])


def write_many_readings(connection_string: str, readings: List[XaomiReadings]):
    conn = None

    try:
        conn = psycopg2.connect(connection_string)
        with conn, conn.cursor() as cur:
            r = format_multiple_readings(cur, readings)
            _write_many_sensor_readings(cur, r)
    finally:
        if conn:
            conn.close()


def read_config_file(config_file: str) -> Dict[str, Any]:
    with open(config_file, "r") as f:
        return yaml.safe_load(f)


class XaomiSensor(object):
    def __init__(self, name: str, location: str, poller, measurements):
        self.name = name
        self.location = location
        self._poller = poller
        self._measurements = measurements
        if self._measurements is None:
            self._measurements = ['temperature', 'humidity', 'battery']

    def read(self):
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            measures = {m: self._poller.parameter_value(m) for m in self._measurements}
            readings = XaomiReadings(
                name=self.name,
                timestamp=timestamp,
                location=self.location,
                **measures
            )
            return readings
        except Exception as e:
            logger.error("Failed to connect to sensor %s: %s",
                         self.name, str(e))
            return None


def create_xaomi_poller(sensor, default_interval=300):
    if 'mac' in sensor:
        timeout = max(sensor.get('interval', default_interval) - 60, 60)
        poller = MiTempBtPoller(sensor['mac'],
                                BluepyBackend,
                                cache_timeout=timeout)
        return XaomiSensor(sensor['name'],
                           sensor['location'],
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

        for (name, sensor) in sensors.items():
            readings = sensor.read()
            if readings:
                print(json.dumps(readings.asjson), flush=True)
                for attempt in range(1, 6):
                    try:
                        write_readings(os.environ['DATABASE_DSN'],
                                       readings)
                        break
                    except Exception:
                        logger.exception("Failed to write to DB")
                        sleep_time = random.uniform(1, 2**attempt)
                        time.sleep(sleep_time)

        end = time.monotonic()
        duration = end - start

        time.sleep(default_interval - min(duration, 60))


def cli():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', help="The YAML config file")
    args = parser.parse_args()
    main(args.config_file)


if __name__ == '__main__':
    cli()
