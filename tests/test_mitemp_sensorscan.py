import pytest
import mitemp_scan


class TestFormatSensor(object):
    def test_correctly_formats_one_reading(self):
        assert len(mitemp_scan.format_sensor_readings(1, {"readings":{"a": 1}, "timestamp": '2'} )) == 1
        assert mitemp_scan.format_sensor_readings(1, {"readings":{"a": 1}, "timestamp": '2'}) == [{"sensor_id": 1, "timestamp": '2', 'measure_type': "a", "reading": 1}]

    def test_correctly_formats_several_readings(self):
        multiple_readings = {"readings":{"a": 1, "b": 2, "c": 3}, "timestamp": '5'}
        assert len(mitemp_scan.format_sensor_readings(17, multiple_readings)) == 3
        formatted_readings = mitemp_scan.format_sensor_readings(17, multiple_readings)
        assert {"sensor_id": 17, "timestamp": '5', 'measure_type': "a", "reading": 1} in formatted_readings
        assert {"timestamp": '5', "sensor_id": 17, 'measure_type': "b", "reading": 2} in formatted_readings
        assert {"sensor_id": 17, "timestamp": '5', 'measure_type': "c", "reading": 3} in formatted_readings
