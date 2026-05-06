"""Unit tests for NSLogger CLI core modules (no external deps, synthetic data)."""
import io
import json
import struct
import tempfile
import os
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cli_anything.nslogger.core.message import (
    LogMessage, MSG_TYPE_LOG, MSG_TYPE_CLIENT_INFO, MSG_TYPE_BLOCK_START, MSG_TYPE_BLOCK_END,
    LEVEL_NAMES,
)
from cli_anything.nslogger.core.filter import filter_messages
from cli_anything.nslogger.core.stats import compute_stats
from cli_anything.nslogger.core.exporter import export_text, export_json, export_csv, export_messages
from cli_anything.nslogger.core.blocks import iter_block_tree, extract_clients, merge_files
from cli_anything.nslogger.core.listener import (
    NSLoggerListener, _bonjour_service_types, _dns_sd_txt_args, _looks_like_tls_client_hello,
    _classify_connection, _swift_helper_env,
)
from cli_anything.nslogger.nslogger_cli import (
    _format_live_output_message,
    _listen_waiting_message,
    _open_live_output_file,
)
from cli_anything.nslogger.utils.generate import encode_message, generate_sample_file
from cli_anything.nslogger.core.parser import _parse_message, parse_raw_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_msg(**kwargs) -> LogMessage:
    defaults = dict(
        sequence=0,
        timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        timestamp_ms=500,
        level=2,
        tag="Test",
        thread_id="main",
        text="hello world",
        message_type=MSG_TYPE_LOG,
    )
    defaults.update(kwargs)
    return LogMessage(**defaults)


# ---------------------------------------------------------------------------
# LogMessage model
# ---------------------------------------------------------------------------

class TestLogMessage:
    def test_level_name_known(self):
        msg = make_msg(level=0)
        assert msg.level_name == "ERROR"

    def test_level_name_unknown(self):
        msg = make_msg(level=99)
        assert "99" in msg.level_name

    def test_type_name_text(self):
        msg = make_msg(text="hello")
        assert msg.type_name == "text"

    def test_type_name_image(self):
        msg = make_msg(image_data=b"\xff\xd8\xff", image_width=100, image_height=200)
        assert msg.type_name == "image"

    def test_type_name_data(self):
        msg = make_msg(binary_data=b"\x00\x01")
        assert msg.type_name == "data"

    def test_type_name_client_info(self):
        msg = make_msg(message_type=MSG_TYPE_CLIENT_INFO)
        assert msg.type_name == "client_info"

    def test_to_dict_keys(self):
        msg = make_msg()
        d = msg.to_dict()
        assert "sequence" in d
        assert "timestamp" in d
        assert "level_name" in d
        assert "type" in d
        assert "text" in d

    def test_to_dict_timestamp_isoformat(self):
        msg = make_msg()
        d = msg.to_dict()
        assert "2024-01-01" in d["timestamp"]

    def test_to_text_line_contains_text(self):
        msg = make_msg(text="SAMPLE_TEXT")
        line = msg.to_text_line()
        assert "SAMPLE_TEXT" in line

    def test_to_text_line_contains_level(self):
        msg = make_msg(level=0)
        line = msg.to_text_line()
        assert "ERROR" in line

    def test_to_text_line_contains_tag(self):
        msg = make_msg(tag="NetworkOps")
        line = msg.to_text_line()
        assert "NetworkOps" in line

    def test_to_text_line_no_timestamp(self):
        msg = make_msg(timestamp=None)
        line = msg.to_text_line()
        assert "??" in line

    def test_to_text_line_image(self):
        msg = make_msg(image_data=b"x", image_width=320, image_height=240)
        line = msg.to_text_line()
        assert "image" in line
        assert "320" in line

    def test_to_text_line_binary(self):
        msg = make_msg(binary_data=b"\x00" * 10)
        line = msg.to_text_line()
        assert "10" in line


# ---------------------------------------------------------------------------
# filter_messages
# ---------------------------------------------------------------------------

class TestFilterMessages:
    def _msgs(self):
        return [
            make_msg(sequence=1, level=0, tag="Auth", thread_id="main", text="error occurred"),
            make_msg(sequence=2, level=2, tag="Network", thread_id="bg", text="request sent"),
            make_msg(sequence=3, level=3, tag="Auth", thread_id="main", text="token refreshed"),
            make_msg(sequence=4, level=4, tag="UI", thread_id="main", text="view loaded"),
        ]

    def test_no_filter_passes_all(self):
        result = list(filter_messages(iter(self._msgs())))
        assert len(result) == 4

    def test_max_level(self):
        result = list(filter_messages(iter(self._msgs()), max_level=1))
        assert all(m.level <= 1 for m in result)
        assert len(result) == 1

    def test_min_level(self):
        result = list(filter_messages(iter(self._msgs()), min_level=3))
        assert all(m.level >= 3 for m in result)
        assert len(result) == 2

    def test_tag_filter(self):
        result = list(filter_messages(iter(self._msgs()), tags=["auth"]))
        assert all(m.tag == "Auth" for m in result)
        assert len(result) == 2

    def test_tag_case_insensitive(self):
        result = list(filter_messages(iter(self._msgs()), tags=["AUTH"]))
        assert len(result) == 2

    def test_thread_filter(self):
        result = list(filter_messages(iter(self._msgs()), thread_id="bg"))
        assert len(result) == 1
        assert result[0].sequence == 2

    def test_text_search(self):
        result = list(filter_messages(iter(self._msgs()), text_search="token"))
        assert len(result) == 1
        assert "token" in result[0].text.lower()

    def test_text_search_case_insensitive(self):
        result = list(filter_messages(iter(self._msgs()), text_search="ERROR"))
        assert len(result) == 1

    def test_regex_filter(self):
        result = list(filter_messages(iter(self._msgs()), text_regex=r"re(quest|freshed)"))
        assert len(result) == 2

    def test_limit(self):
        result = list(filter_messages(iter(self._msgs()), limit=2))
        assert len(result) == 2

    def test_combined_filters(self):
        result = list(filter_messages(iter(self._msgs()), max_level=2, tags=["auth"]))
        assert len(result) == 1
        assert result[0].level == 0

    def test_empty_input(self):
        result = list(filter_messages(iter([])))
        assert result == []


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------

class TestComputeStats:
    def _msgs(self):
        return [
            make_msg(level=0, tag="Auth", thread_id="main",
                     timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)),
            make_msg(level=2, tag="Network", thread_id="bg",
                     timestamp=datetime(2024, 1, 1, 10, 1, tzinfo=timezone.utc)),
            make_msg(level=2, tag="Auth", thread_id="main",
                     timestamp=datetime(2024, 1, 1, 10, 2, tzinfo=timezone.utc)),
        ]

    def test_total(self):
        s = compute_stats(iter(self._msgs()))
        assert s["total"] == 3

    def test_by_level(self):
        s = compute_stats(iter(self._msgs()))
        assert s["by_level"]["ERROR"] == 1
        assert s["by_level"]["INFO"] == 2

    def test_by_tag(self):
        s = compute_stats(iter(self._msgs()))
        assert s["by_tag"]["Auth"] == 2
        assert s["by_tag"]["Network"] == 1

    def test_by_thread(self):
        s = compute_stats(iter(self._msgs()))
        assert s["by_thread"]["main"] == 2

    def test_duration(self):
        s = compute_stats(iter(self._msgs()))
        assert s["duration_seconds"] == 120.0

    def test_timestamps(self):
        s = compute_stats(iter(self._msgs()))
        assert "2024-01-01T10:00:00" in s["first_timestamp"]
        assert "2024-01-01T10:02:00" in s["last_timestamp"]

    def test_empty(self):
        s = compute_stats(iter([]))
        assert s["total"] == 0

    def test_by_type(self):
        s = compute_stats(iter(self._msgs()))
        assert "text" in s["by_type"]


# ---------------------------------------------------------------------------
# exporter
# ---------------------------------------------------------------------------

class TestExporter:
    def _msgs(self):
        return [
            make_msg(sequence=1, level=0, tag="A", text="first message"),
            make_msg(sequence=2, level=2, tag="B", text="second message"),
        ]

    def test_export_text(self):
        out = export_text(self._msgs())
        assert "first message" in out
        assert "second message" in out

    def test_export_json_valid(self):
        out = export_json(self._msgs())
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["sequence"] == 1

    def test_export_json_has_all_fields(self):
        out = export_json(self._msgs())
        data = json.loads(out)
        for key in ("sequence", "timestamp", "level", "level_name", "tag", "text", "type"):
            assert key in data[0]

    def test_export_csv_has_header(self):
        out = export_csv(self._msgs())
        assert "sequence" in out.splitlines()[0]

    def test_export_csv_has_data(self):
        out = export_csv(self._msgs())
        lines = out.strip().splitlines()
        assert len(lines) == 3  # header + 2 rows

    def test_export_messages_text(self):
        out = export_messages(iter(self._msgs()), fmt="text")
        assert "first message" in out

    def test_export_messages_json(self):
        out = export_messages(iter(self._msgs()), fmt="json")
        json.loads(out)  # must be valid JSON

    def test_export_messages_csv(self):
        out = export_messages(iter(self._msgs()), fmt="csv")
        assert "," in out


# ---------------------------------------------------------------------------
# wire protocol encoder / parser
# ---------------------------------------------------------------------------

class TestWireProtocol:
    def _encode_and_parse(self, **kwargs):
        raw_file_bytes = encode_message(sequence=1, **kwargs)
        # raw_file_bytes = [4-byte length][body]
        body = raw_file_bytes[4:]
        return _parse_message(body)

    def test_round_trip_text(self):
        msg = self._encode_and_parse(text="hello", level=2, tag="TAG", thread_id="main")
        assert msg.text == "hello"
        assert msg.level == 2
        assert msg.tag == "TAG"
        assert msg.thread_id == "main"
        assert msg.sequence == 1

    def test_round_trip_timestamp(self):
        ts = 1700000000.5
        msg = self._encode_and_parse(timestamp=ts, text="x")
        assert msg.timestamp is not None
        assert abs(msg.timestamp.timestamp() - int(ts)) < 1

    def test_round_trip_client_info(self):
        msg = self._encode_and_parse(
            msg_type=3,
            client_name="TestApp",
            client_version="2.0",
            os_name="iOS",
            os_version="17.0",
            machine="iPhone15,2",
        )
        assert msg.client_name == "TestApp"
        assert msg.os_name == "iOS"

    def test_encode_message_has_length_prefix(self):
        raw = encode_message(sequence=0, text="x")
        declared_len = struct.unpack(">I", raw[:4])[0]
        assert declared_len == len(raw) - 4

    def test_official_integer_parts_do_not_have_length_fields(self):
        body = encode_message(sequence=7, text="official", level=1)[4:]
        msg = _parse_message(body)
        assert msg.sequence == 7
        assert msg.level == 1
        assert msg.text == "official"

    def test_legacy_lengthful_integer_parts_still_parse(self):
        parts = b""
        parts += bytes([0, 3]) + struct.pack(">I", 4) + struct.pack(">I", 0)
        parts += bytes([10, 3]) + struct.pack(">I", 4) + struct.pack(">I", 8)
        text = b"legacy"
        parts += bytes([7, 0]) + struct.pack(">I", len(text)) + text
        body = struct.pack(">H", 3) + parts
        msg = _parse_message(body)
        assert msg.sequence == 8
        assert msg.text == "legacy"


# ---------------------------------------------------------------------------
# generate_sample_file
# ---------------------------------------------------------------------------

class TestGenerateSampleFile:
    def test_creates_file(self, tmp_path):
        path = str(tmp_path / "sample.rawnsloggerdata")
        generate_sample_file(path, count=5)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0

    def test_parseable(self, tmp_path):
        path = str(tmp_path / "sample.rawnsloggerdata")
        generate_sample_file(path, count=10)
        msgs = list(parse_raw_file(path))
        assert len(msgs) >= 10  # 10 log + 1 client_info

    def test_varied_levels(self, tmp_path):
        path = str(tmp_path / "sample.rawnsloggerdata")
        generate_sample_file(path, count=50)
        msgs = list(parse_raw_file(path))
        levels = {m.level for m in msgs}
        assert len(levels) > 1


# ---------------------------------------------------------------------------
# parse_raw_file (file I/O)
# ---------------------------------------------------------------------------

class TestParseRawFile:
    def _write_file(self, tmp_path, *messages_kwargs):
        path = str(tmp_path / "test.rawnsloggerdata")
        with open(path, "wb") as f:
            for i, kw in enumerate(messages_kwargs):
                f.write(encode_message(sequence=i, **kw))
        return path

    def test_single_message(self, tmp_path):
        path = self._write_file(tmp_path, {"text": "only one"})
        msgs = list(parse_raw_file(path))
        assert len(msgs) == 1
        assert msgs[0].text == "only one"

    def test_multiple_messages(self, tmp_path):
        path = self._write_file(
            tmp_path,
            {"text": "first", "level": 0},
            {"text": "second", "level": 2},
            {"text": "third", "level": 4},
        )
        msgs = list(parse_raw_file(path))
        assert len(msgs) == 3
        assert msgs[0].text == "first"
        assert msgs[2].text == "third"

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "empty.rawnsloggerdata")
        open(path, "wb").close()
        msgs = list(parse_raw_file(path))
        assert msgs == []


# ---------------------------------------------------------------------------
# filter_messages — new time-range and sequence-range options
# ---------------------------------------------------------------------------

class TestFilterMessagesExtended:
    def _msgs_with_timestamps(self):
        t = lambda h, m: datetime(2024, 1, 1, h, m, 0, tzinfo=timezone.utc)
        return [
            make_msg(sequence=10, timestamp=t(10, 0), level=0, text="early error"),
            make_msg(sequence=20, timestamp=t(10, 30), level=2, text="mid info"),
            make_msg(sequence=30, timestamp=t(11, 0), level=3, text="late debug"),
        ]

    def test_after_filter(self):
        after = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
        result = list(filter_messages(iter(self._msgs_with_timestamps()), after=after))
        assert len(result) == 2
        assert result[0].sequence == 20

    def test_before_filter(self):
        before = datetime(2024, 1, 1, 10, 45, tzinfo=timezone.utc)
        result = list(filter_messages(iter(self._msgs_with_timestamps()), before=before))
        assert len(result) == 2
        assert result[-1].sequence == 20

    def test_after_and_before_window(self):
        after = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
        before = datetime(2024, 1, 1, 10, 45, tzinfo=timezone.utc)
        result = list(filter_messages(iter(self._msgs_with_timestamps()), after=after, before=before))
        assert len(result) == 1
        assert result[0].sequence == 20

    def test_from_seq(self):
        result = list(filter_messages(iter(self._msgs_with_timestamps()), from_seq=20))
        assert len(result) == 2
        assert result[0].sequence == 20

    def test_to_seq(self):
        result = list(filter_messages(iter(self._msgs_with_timestamps()), to_seq=20))
        assert len(result) == 2
        assert result[-1].sequence == 20

    def test_seq_range(self):
        result = list(filter_messages(iter(self._msgs_with_timestamps()), from_seq=20, to_seq=20))
        assert len(result) == 1
        assert result[0].sequence == 20

    def test_no_timestamp_excluded_by_after(self):
        msgs = [make_msg(sequence=1, timestamp=None, text="no ts")]
        after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = list(filter_messages(iter(msgs), after=after))
        assert result == []


# ---------------------------------------------------------------------------
# blocks module
# ---------------------------------------------------------------------------

class TestIterBlockTree:
    def _block_msgs(self):
        return [
            make_msg(sequence=1, message_type=MSG_TYPE_LOG, text="before block"),
            make_msg(sequence=2, message_type=MSG_TYPE_BLOCK_START, text="enter"),
            make_msg(sequence=3, message_type=MSG_TYPE_LOG, text="inside"),
            make_msg(sequence=4, message_type=MSG_TYPE_BLOCK_END, text="exit"),
            make_msg(sequence=5, message_type=MSG_TYPE_LOG, text="after block"),
        ]

    def test_top_level_messages_have_depth_zero(self):
        pairs = list(iter_block_tree(iter(self._block_msgs())))
        assert pairs[0][0] == 0   # before block
        assert pairs[4][0] == 0   # after block

    def test_block_start_at_zero_before_increment(self):
        pairs = list(iter_block_tree(iter(self._block_msgs())))
        # block_start emitted at depth 0, then depth increments
        assert pairs[1][0] == 0
        assert pairs[1][1].message_type == MSG_TYPE_BLOCK_START

    def test_inside_block_has_depth_one(self):
        pairs = list(iter_block_tree(iter(self._block_msgs())))
        assert pairs[2][0] == 1

    def test_block_end_has_depth_zero_after_decrement(self):
        pairs = list(iter_block_tree(iter(self._block_msgs())))
        # block_end decrements first, so emitted at depth 0
        assert pairs[3][0] == 0

    def test_empty_input(self):
        assert list(iter_block_tree(iter([]))) == []


class TestExtractClients:
    def _msgs_with_client(self):
        client = LogMessage(
            sequence=0,
            message_type=MSG_TYPE_CLIENT_INFO,
            client_name="MyApp",
            client_version="3.1",
            os_name="iOS",
            os_version="17.0",
            machine="iPhone16,1",
        )
        log = make_msg(sequence=1, text="regular log")
        return [client, log]

    def test_returns_only_client_info(self):
        result = extract_clients(iter(self._msgs_with_client()))
        assert len(result) == 1

    def test_client_fields(self):
        result = extract_clients(iter(self._msgs_with_client()))
        c = result[0]
        assert c["client_name"] == "MyApp"
        assert c["client_version"] == "3.1"
        assert c["os_name"] == "iOS"
        assert c["machine"] == "iPhone16,1"

    def test_no_clients_returns_empty(self):
        result = extract_clients(iter([make_msg(text="log")]))
        assert result == []


class TestMergeFiles:
    def _write(self, tmp_path, name, *messages_kwargs):
        path = str(tmp_path / name)
        with open(path, "wb") as f:
            for i, kw in enumerate(messages_kwargs):
                f.write(encode_message(sequence=i, **kw))
        return path

    def test_merge_two_files_sorted(self, tmp_path):
        ts_early = 1700000000.0
        ts_late = 1700000100.0
        path_a = self._write(tmp_path, "a.rawnsloggerdata",
                             {"text": "late msg", "timestamp": ts_late})
        path_b = self._write(tmp_path, "b.rawnsloggerdata",
                             {"text": "early msg", "timestamp": ts_early})
        result = merge_files([path_a, path_b])
        assert len(result) == 2
        assert result[0].text == "early msg"
        assert result[1].text == "late msg"

    def test_merge_single_file(self, tmp_path):
        path = self._write(tmp_path, "c.rawnsloggerdata",
                           {"text": "only msg"})
        result = merge_files([path])
        assert len(result) == 1

    def test_merge_preserves_all_messages(self, tmp_path):
        path_a = self._write(tmp_path, "d.rawnsloggerdata",
                             {"text": "a1"}, {"text": "a2"})
        path_b = self._write(tmp_path, "e.rawnsloggerdata",
                             {"text": "b1"}, {"text": "b2"})
        result = merge_files([path_a, path_b])
        assert len(result) == 4


# ---------------------------------------------------------------------------
# listener
# ---------------------------------------------------------------------------

class TestNSLoggerListener:
    def test_swift_helper_env_uses_temp_module_caches(self):
        env = _swift_helper_env()

        assert env["SWIFT_MODULE_CACHE_PATH"].startswith(tempfile.gettempdir())
        assert env["CLANG_MODULE_CACHE_PATH"].startswith(tempfile.gettempdir())

    def test_named_bonjour_service_uses_filter_txt_record(self):
        assert _dns_sd_txt_args("bazinga", filter_clients=True) == ["filterClients=1"]

    def test_named_bonjour_service_does_not_filter_by_default(self):
        assert _dns_sd_txt_args("bazinga") == []

    def test_empty_bonjour_service_has_no_filter_txt_record(self):
        assert _dns_sd_txt_args("") == []

    def test_ssl_bonjour_advertises_only_ssl_service(self):
        assert _bonjour_service_types(True) == ("_nslogger-ssl._tcp",)

    def test_auto_bonjour_advertises_raw_and_ssl_services(self):
        assert _bonjour_service_types(True, allow_plaintext=True) == ("_nslogger._tcp", "_nslogger-ssl._tcp")

    def test_non_ssl_bonjour_advertises_only_legacy_service(self):
        assert _bonjour_service_types(False) == ("_nslogger._tcp",)

    def test_macos_bonjour_prefers_native_netservice(self):
        listener = NSLoggerListener(bonjour=True, bonjour_name="bazinga")

        class DummyNativePublisher:
            def __init__(self, service_name, service_types, port, filter_clients, on_debug):
                self.service_name = service_name
                self.service_types = service_types
                self.port = port
                self.filter_clients = filter_clients
                self.on_debug = on_debug

        with patch("cli_anything.nslogger.core.listener.sys.platform", "darwin"), \
                patch("cli_anything.nslogger.core.listener._NativeBonjourPublisher", DummyNativePublisher), \
                patch("cli_anything.nslogger.core.listener._DnsSdBonjourPublisher") as dns_sd_publisher, \
                patch("cli_anything.nslogger.core.listener._ZeroconfBonjourPublisher") as zeroconf_publisher:
            publisher = listener._start_bonjour("192.168.10.1")

        assert isinstance(publisher, DummyNativePublisher)
        assert publisher.service_name == "bazinga"
        assert publisher.service_types == ("_nslogger-ssl._tcp",)
        assert publisher.filter_clients is True
        assert dns_sd_publisher.call_count == 0
        assert zeroconf_publisher.call_count == 0

    def test_bonjour_auto_mode_can_publish_raw_and_ssl_services(self):
        listener = NSLoggerListener(
            bonjour=True,
            bonjour_name="bazinga",
            allow_plaintext=True,
        )

        class DummyNativePublisher:
            def __init__(self, service_name, service_types, port, filter_clients, on_debug):
                self.service_types = service_types

        with patch("cli_anything.nslogger.core.listener.sys.platform", "darwin"), \
                patch("cli_anything.nslogger.core.listener._NativeBonjourPublisher", DummyNativePublisher):
            publisher = listener._start_bonjour("192.168.10.1")

        assert publisher.service_types == ("_nslogger._tcp", "_nslogger-ssl._tcp")

    def test_dns_sd_publisher_can_be_forced_on_macos(self):
        listener = NSLoggerListener(
            bonjour=True,
            bonjour_name="bazinga",
            bonjour_publisher="dns-sd",
        )

        class DummyDnsSdPublisher:
            def __init__(self, service_name, service_types, port, filter_clients, on_debug):
                self.service_name = service_name
                self.service_types = service_types
                self.port = port
                self.filter_clients = filter_clients

        with patch("cli_anything.nslogger.core.listener.sys.platform", "darwin"), \
                patch("cli_anything.nslogger.core.listener._NativeBonjourPublisher") as native_publisher, \
                patch("cli_anything.nslogger.core.listener._DnsSdBonjourPublisher", DummyDnsSdPublisher):
            publisher = listener._start_bonjour("192.168.10.1")

        assert isinstance(publisher, DummyDnsSdPublisher)
        assert native_publisher.call_count == 0

    def test_zeroconf_publisher_can_be_forced_on_macos(self):
        listener = NSLoggerListener(
            bonjour=True,
            bonjour_name="bazinga",
            bonjour_publisher="zeroconf",
        )

        class DummyZeroconfPublisher:
            def __init__(self, service_name, service_types, port, local_ip, filter_clients):
                self.service_name = service_name
                self.service_types = service_types
                self.port = port
                self.local_ip = local_ip
                self.filter_clients = filter_clients

        with patch("cli_anything.nslogger.core.listener.sys.platform", "darwin"), \
                patch("cli_anything.nslogger.core.listener._ZeroconfBonjourPublisher", DummyZeroconfPublisher), \
                patch("cli_anything.nslogger.core.listener._DnsSdBonjourPublisher") as dns_sd_publisher:
            publisher = listener._start_bonjour("192.168.10.5")

        assert isinstance(publisher, DummyZeroconfPublisher)
        assert publisher.local_ip == "192.168.10.5"
        assert dns_sd_publisher.call_count == 0

    def test_ssl_handshake_failure_is_silent(self):
        class DummySSLContext:
            def wrap_socket(self, conn, server_side=True):
                raise OSError(22, "Invalid argument")

        class DummyConn:
            def __init__(self):
                self.closed = False
                self.peeked = False

            def recv(self, n, flags=0):
                if flags:
                    self.peeked = True
                    return b"\x16\x03\x01\x00\x2a"
                return b""

            def settimeout(self, timeout):
                pass

            def close(self):
                self.closed = True

        connect_calls = []
        disconnect_calls = []

        listener = NSLoggerListener(
            on_connect=lambda host, port: connect_calls.append((host, port)),
            on_disconnect=lambda host, port: disconnect_calls.append((host, port)),
        )
        listener._ssl_ctx = DummySSLContext()
        conn = DummyConn()

        listener._handle_client(conn, ("127.0.0.1", 50000))

        assert conn.closed is True
        assert connect_calls == []
        assert disconnect_calls == []

    def test_raw_connection_without_ssl_context_is_not_wrapped(self):
        class DummyConn:
            def __init__(self, payload: bytes):
                self.payload = payload
                self.closed = False

            def recv(self, n, flags=0):
                if flags == getattr(__import__("socket"), "MSG_PEEK", 0):
                    return self.payload[:n]
                return b""

            def settimeout(self, timeout):
                pass

            def close(self):
                self.closed = True

        listener = NSLoggerListener(use_ssl=False)
        conn = DummyConn(b"\x00\x00\x00\x10\x00")

        assert _looks_like_tls_client_hello(conn) is False
        listener._handle_client(conn, ("127.0.0.1", 50000))
        assert conn.closed is True

    def test_tls_client_hello_is_detected(self):
        class DummyConn:
            def recv(self, n, flags=0):
                if flags == getattr(__import__("socket"), "MSG_PEEK", 0):
                    return b"\x16\x03\x01\x00\x2a"
                return b""

        assert _looks_like_tls_client_hello(DummyConn()) is True

    def test_connection_classifier_distinguishes_tls_raw_and_empty(self):
        class DummyConn:
            def __init__(self, payload: bytes):
                self.payload = payload

            def recv(self, n, flags=0):
                return self.payload[:n]

        assert _classify_connection(DummyConn(b"\x16\x03\x01\x00\x2a"))[0] == "tls"
        assert _classify_connection(DummyConn(b"\x00\x00\x00\x10\x00"))[0] == "raw"
        assert _classify_connection(DummyConn(b""))[0] == "empty"

    def test_connection_classifier_distinguishes_timeout_from_empty_probe(self):
        class DummyConn:
            def recv(self, n, flags=0):
                raise __import__("socket").timeout()

        assert _classify_connection(DummyConn())[0] == "timeout"

    def test_auto_ssl_context_accepts_plaintext_live_packet(self):
        class DummySSLContext:
            def wrap_socket(self, conn, server_side=True):
                raise AssertionError("raw packet should not be TLS-wrapped")

        server, client = __import__("socket").socketpair()
        messages = []
        listener = NSLoggerListener(
            on_message=messages.append,
            use_ssl=True,
            allow_plaintext=True,
        )
        listener._ssl_ctx = DummySSLContext()
        thread = __import__("threading").Thread(
            target=listener._handle_client,
            args=(server, ("127.0.0.1", 50000)),
            daemon=True,
        )

        thread.start()
        client.sendall(encode_message(sequence=43, text="auto raw packet", tag="Network", level=1))
        client.close()
        thread.join(timeout=2.0)

        assert len(messages) == 1
        assert messages[0].sequence == 43
        assert messages[0].text == "auto raw packet"

    def test_handle_client_parses_official_live_packet(self):
        server, client = __import__("socket").socketpair()
        messages = []
        listener = NSLoggerListener(on_message=messages.append)
        thread = __import__("threading").Thread(
            target=listener._handle_client,
            args=(server, ("127.0.0.1", 50000)),
            daemon=True,
        )

        thread.start()
        client.sendall(encode_message(sequence=42, text="live packet", tag="Network", level=1))
        client.close()
        thread.join(timeout=2.0)

        assert len(messages) == 1
        assert messages[0].sequence == 42
        assert messages[0].text == "live packet"
        assert messages[0].tag == "Network"

    def test_handle_client_reports_parse_errors(self):
        server, client = __import__("socket").socketpair()
        errors = []
        listener = NSLoggerListener(on_parse_error=lambda host, port, raw, exc: errors.append((raw, exc)))
        thread = __import__("threading").Thread(
            target=listener._handle_client,
            args=(server, ("127.0.0.1", 50000)),
            daemon=True,
        )

        thread.start()
        client.sendall(struct.pack(">I", 2) + b"\x00\x01")
        client.close()
        thread.join(timeout=2.0)

        assert len(errors) == 1
        assert errors[0][0] == b"\x00\x01"


class TestListenWaitingMessage:
    def test_non_bonjour_message(self):
        assert _listen_waiting_message(50000, False) == "Waiting for a client connection on port 50000…"

    def test_bonjour_message(self):
        assert _listen_waiting_message(50000, True) == "[Bonjour] Waiting for an iOS client to connect on port 50000…"


class TestListenOutputFile:
    def test_format_live_output_text(self):
        assert _format_live_output_message(make_msg(text="live text"), "text").endswith("live text")

    def test_format_live_output_jsonl(self):
        line = _format_live_output_message(make_msg(text="live json"), "jsonl")
        data = json.loads(line)

        assert data["text"] == "live json"

    def test_open_live_output_file_creates_parent_and_replaces(self, tmp_path):
        path = tmp_path / "nested" / "live.log"

        with _open_live_output_file(str(path), append=False) as f:
            f.write("new\n")

        assert path.read_text(encoding="utf-8") == "new\n"

    def test_open_live_output_file_appends(self, tmp_path):
        path = tmp_path / "nested" / "live.log"

        with _open_live_output_file(str(path), append=False) as f:
            f.write("one\n")
        with _open_live_output_file(str(path), append=True) as f:
            f.write("two\n")

        assert path.read_text(encoding="utf-8") == "one\ntwo\n"
