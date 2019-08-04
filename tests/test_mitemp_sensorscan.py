import pytest
import mitemp_scan


class TestFormatSensor(object):
    def test_correctly_formats_one_reading(self):
        reading = mitemp_scan.XaomiReadings(name='a', location='x', timestamp='2', temperature=1, humidity=2, battery=3)
        assert mitemp_scan.format_sensor_readings(
            1, reading) == {"sensor_id": 1, "timestamp": '2', "location": "x", "temperature": 1, "humidity":2, "battery":3}
