"""Tests for bluelock.config."""
import pytest
from bluelock.config import Config, _to_toml


class TestConfigDefaults:
    def test_default_values(self):
        c = Config()
        assert c.device_mac == ""
        assert c.device_name == ""
        assert c.lock_rssi_threshold == -15
        assert c.lock_duration == 6
        assert c.unlock_rssi_threshold == -10
        assert c.unlock_duration == 1
        assert c.lock_command == ""
        assert c.unlock_command == ""
        assert c.buffer_size == 16
        assert c.scan_interval == 1.0

    def test_lock_threshold_lower_than_unlock(self):
        c = Config()
        assert c.lock_rssi_threshold < c.unlock_rssi_threshold


class TestConfigLoadSave:
    def test_round_trip(self, tmp_config_path):
        c = Config(
            device_mac="AA:BB:CC:DD:EE:FF",
            device_name="My Phone",
            lock_rssi_threshold=-20,
            lock_duration=5,
            unlock_rssi_threshold=-12,
            unlock_duration=2,
            lock_command="loginctl lock-session",
            unlock_command="",
            buffer_size=8,
            scan_interval=2.0,
        )
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)

        assert loaded.device_mac == c.device_mac
        assert loaded.device_name == c.device_name
        assert loaded.lock_rssi_threshold == c.lock_rssi_threshold
        assert loaded.lock_duration == c.lock_duration
        assert loaded.unlock_rssi_threshold == c.unlock_rssi_threshold
        assert loaded.unlock_duration == c.unlock_duration
        assert loaded.lock_command == c.lock_command
        assert loaded.unlock_command == c.unlock_command
        assert loaded.buffer_size == c.buffer_size
        assert loaded.scan_interval == c.scan_interval

    def test_missing_file_returns_defaults(self, tmp_config_path):
        loaded = Config.load(tmp_config_path)
        assert loaded == Config()

    def test_corrupt_file_returns_defaults(self, tmp_config_path):
        tmp_config_path.write_text("this is not valid toml }{")
        loaded = Config.load(tmp_config_path)
        assert loaded == Config()

    def test_partial_config(self, tmp_config_path):
        tmp_config_path.write_text('[device]\nmac = "12:34:56:78:9A:BC"\n')
        loaded = Config.load(tmp_config_path)
        assert loaded.device_mac == "12:34:56:78:9A:BC"
        assert loaded.device_name == ""         # default
        assert loaded.lock_duration == 6        # default

    def test_save_creates_parent_directory(self, tmp_path):
        path = tmp_path / "subdir" / "config.toml"
        Config().save(path)
        assert path.exists()

    def test_empty_string_commands(self, tmp_config_path):
        c = Config(lock_command="", unlock_command="")
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)
        assert loaded.lock_command == ""
        assert loaded.unlock_command == ""

    def test_command_with_special_chars(self, tmp_config_path):
        cmd = 'dbus-send --session --dest=org.gnome.ScreenSaver "/path" bool:true'
        c = Config(lock_command=cmd)
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)
        assert loaded.lock_command == cmd


class TestToToml:
    def test_string_values(self):
        result = _to_toml({"section": {"key": "value"}})
        assert '[section]' in result
        assert 'key = "value"' in result

    def test_int_values(self):
        result = _to_toml({"s": {"n": 42}})
        assert "n = 42" in result

    def test_float_values(self):
        result = _to_toml({"s": {"f": 1.5}})
        assert "f = 1.5" in result

    def test_bool_true(self):
        result = _to_toml({"s": {"b": True}})
        assert "b = true" in result

    def test_bool_false(self):
        result = _to_toml({"s": {"b": False}})
        assert "b = false" in result

    def test_string_with_quotes_escaped(self):
        result = _to_toml({"s": {"k": 'say "hello"'}})
        assert r'say \"hello\"' in result

    def test_sections_separated_by_blank_line(self):
        result = _to_toml({"a": {"x": 1}, "b": {"y": 2}})
        lines = result.splitlines()
        # Find the blank line between sections
        assert "" in lines
