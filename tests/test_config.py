"""Tests for bluelock.config."""

from bluelock.config import Config, DeviceConfig, _to_toml


class TestConfigDefaults:
    def test_default_values(self):
        c = Config()
        assert c.device is None
        assert c.device_mac == ""
        assert c.device_name == ""
        assert c.lock_rssi_threshold == -15
        assert c.lock_duration == 4
        assert c.unlock_rssi_threshold == -10
        assert c.unlock_duration == 4
        assert c.lock_command == ""
        assert c.unlock_command == ""
        assert c.buffer_size == 16
        assert c.scan_interval == 1.0


class TestConfigLoadSave:
    def test_round_trip(self, tmp_config_path):
        c = Config(
            device=DeviceConfig(
                mac="AA:BB:CC:DD:EE:FF",
                name="My Phone",
                lock_rssi_threshold=-20,
                lock_duration=5,
                unlock_rssi_threshold=-12,
                unlock_duration=2,
                lock_command="loginctl lock-session",
                unlock_command="",
            ),
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
        assert loaded.device_name == ""  # default
        assert loaded.lock_duration == 4  # default

    def test_save_creates_parent_directory(self, tmp_path):
        path = tmp_path / "subdir" / "config.toml"
        Config().save(path)
        assert path.exists()

    def test_empty_string_commands(self, tmp_config_path):
        c = Config(device=DeviceConfig(mac="AA:BB:CC:DD:EE:FF", lock_command="", unlock_command=""))
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)
        assert loaded.lock_command == ""
        assert loaded.unlock_command == ""

    def test_command_with_special_chars(self, tmp_config_path):
        cmd = 'dbus-send --session --dest=org.gnome.ScreenSaver "/path" bool:true'
        c = Config(device=DeviceConfig(mac="AA:BB:CC:DD:EE:FF", lock_command=cmd))
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)
        assert loaded.lock_command == cmd

    def test_adapter_addresses_round_trip(self, tmp_config_path):
        c = Config(device=DeviceConfig(
            mac="AA:BB:CC:DD:EE:FF",
            adapter_addresses=["11:22:33:44:55:66", "AA:BB:CC:DD:EE:01"],
        ))
        c.save(tmp_config_path)
        loaded = Config.load(tmp_config_path)
        assert loaded.adapter_addresses == ["11:22:33:44:55:66", "AA:BB:CC:DD:EE:01"]
        assert loaded.device.adapter_addresses == ["11:22:33:44:55:66", "AA:BB:CC:DD:EE:01"]

    def test_adapter_addresses_empty_omitted_from_toml(self, tmp_config_path):
        c = Config(device=DeviceConfig(mac="AA:BB:CC:DD:EE:FF"))
        c.save(tmp_config_path)
        text = tmp_config_path.read_text()
        assert "adapter_addresses" not in text

    def test_adapter_addresses_missing_in_legacy_config(self, tmp_config_path):
        # An existing (pre-multi-adapter) config: no adapter_addresses key.
        tmp_config_path.write_text(
            '[device]\n'
            'mac = "AA:BB:CC:DD:EE:FF"\n'
            'lock_rssi = -20\n'
            'lock_duration = 4\n'
            'unlock_rssi = -10\n'
            'unlock_duration = 4\n'
        )
        loaded = Config.load(tmp_config_path)
        assert loaded.adapter_addresses == []

    def test_adapter_addresses_non_list_falls_back_to_empty(self, tmp_config_path):
        # Defensive: malformed config should not raise.
        tmp_config_path.write_text(
            '[device]\n'
            'mac = "AA:BB:CC:DD:EE:FF"\n'
            'lock_rssi = -20\n'
            'adapter_addresses = "not-a-list"\n'
        )
        loaded = Config.load(tmp_config_path)
        assert loaded.adapter_addresses == []


class TestToToml:
    def test_string_values(self):
        c = Config(device=DeviceConfig(mac="00:11:22", name="N"))
        result = _to_toml(c)
        assert 'mac = "00:11:22"' in result
        assert 'name = "N"' in result

    def test_int_values(self):
        c = Config(device=DeviceConfig(mac="00:11:22", lock_rssi_threshold=-42))
        result = _to_toml(c)
        assert "lock_rssi = -42" in result

    def test_float_values(self):
        c = Config(scan_interval=1.5)
        result = _to_toml(c)
        assert "scan_interval = 1.5" in result

    def test_bools_not_present_in_config(self):
        c = Config(device=DeviceConfig(mac="00:11:22"))
        result = _to_toml(c)
        for line in result.splitlines():
            if line and not line.startswith("#"):
                assert not line.strip().lower().startswith(("true", "false")), f"Unexpected boolean: {line}"

    def test_string_with_quotes_escaped(self):
        c = Config(device=DeviceConfig(mac="00:11:22", name='say "hello"'))
        result = _to_toml(c)
        assert r"say \"hello\"" in result

    def test_sections_separated_by_blank_line(self):
        c = Config(device=DeviceConfig(mac="00:11:22"))
        result = _to_toml(c)
        lines = result.splitlines()
        # Find the blank line between sections
        assert "" in lines
