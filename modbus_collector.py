# -*- coding: utf-8 -*-
"""
Modbus TCP 数据采集器（功能 2）
===============================
功能：
  1. 作为 Modbus 主站，通过 Modbus TCP 读取从站的保持寄存器；
  2. 只读写本小组分配的寄存器区间，避免与其他小组冲突；
  3. 采集到的数据通过 MQTT 上报。

从站：192.168.20.59:5502，寄存器区间 0x0000~0x0009。

用法：
  python modbus_collector.py                        # 周期采集并上报（默认）
  python modbus_collector.py --read                 # 读取一次并上报后退出
  python modbus_collector.py --write 0x0000 100     # 向本小组寄存器写入数值
  python modbus_collector.py --report-all           # 每次采集都上报（默认仅在值变化时上报）

上报主题：iot/group{GROUP_ID}/modbus/{device_id}/data
上报 Payload 示例：
  {
    "type": "modbus",
    "device_id": "modbus-01",
    "group": 1,
    "slave": {"host": "192.168.20.59", "port": 5502, "unit": 1},
    "registers": {"0x0000": 123, "0x0001": 456},
    "seq": 3,
    "ts": 1725157680.123,
    "datetime": "2026-09-01T10:28:00+08:00"
  }
"""
import argparse
import logging
import signal
import threading
import time
from datetime import datetime

from pymodbus.client import ModbusTcpClient

import config
import mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("modbus")


class ModbusCollector:
    """Modbus TCP 主站采集器，只操作本小组的寄存器区间。"""

    def __init__(self, device_id=None, group=None):
        self.device_id = device_id or config.MODBUS_DEVICE_ID
        self.group = group if group is not None else config.GROUP_ID
        self.start, self.end = config.group_register_range(self.group)
        self.count = self.end - self.start + 1
        self.seq = 0
        self._last = None
        self.client = ModbusTcpClient(
            config.MODBUS_HOST, port=config.MODBUS_PORT, timeout=config.MODBUS_TIMEOUT
        )

    # ---------- 连接 ----------
    def connect(self):
        if not self.client.connect():
            raise ConnectionError(
                f"Modbus 从站连接失败 {config.MODBUS_HOST}:{config.MODBUS_PORT}"
            )
        log.info("已连接 Modbus 从站 %s:%s (unit=%s)",
                 config.MODBUS_HOST, config.MODBUS_PORT, config.MODBUS_UNIT)

    def close(self):
        self.client.close()

    # ---------- 读 / 写 ----------
    def read_group(self):
        """读取本小组寄存器区间，返回 {地址字符串: 数值}。"""
        rr = self.client.read_holding_registers(
            self.start, count=self.count, device_id=config.MODBUS_UNIT
        )
        if rr.isError():
            raise IOError(f"读取寄存器失败：{rr}")
        return {f"0x{a:04X}": int(v) for a, v in zip(range(self.start, self.end + 1), rr.registers)}

    def write_register(self, address, value):
        """向单个寄存器写入数值，仅允许本小组区间。"""
        self._check_address(address)
        wr = self.client.write_register(address, int(value), device_id=config.MODBUS_UNIT)
        if wr.isError():
            raise IOError(f"写入寄存器失败：{wr}")
        log.info("已写入 0x%04X = %s", address, value)

    def write_registers(self, address, values):
        """向连续寄存器写入一组数值，仅允许本小组区间。"""
        for i in range(len(values)):
            self._check_address(address + i)
        wr = self.client.write_registers(address, [int(v) for v in values], device_id=config.MODBUS_UNIT)
        if wr.isError():
            raise IOError(f"写入寄存器失败：{wr}")
        log.info("已写入 0x%04X ~ 0x%04X", address, address + len(values) - 1)

    def _check_address(self, address):
        if not (self.start <= address <= self.end):
            raise ValueError(
                f"地址 0x{address:04X} 不在本小组区间 [0x{self.start:04X}-0x{self.end:04X}] 内，"
                f"请修改 GROUP_ID 或使用本小组的寄存器"
            )

    # ---------- 上报 ----------
    def build_payload(self, registers):
        self.seq += 1
        ts = time.time()
        return {
            "type": "modbus",
            "device_id": self.device_id,
            "group": self.group,
            "slave": {"host": config.MODBUS_HOST, "port": config.MODBUS_PORT, "unit": config.MODBUS_UNIT},
            "registers": registers,
            "seq": self.seq,
            "ts": round(ts, 3),
            "datetime": datetime.now().astimezone().isoformat(timespec="seconds"),
        }


def run_poll(report_all=False):
    """周期采集并上报。"""
    collector = ModbusCollector()
    data_topic = config.modbus_data_topic(collector.device_id)
    status_topic = config.modbus_status_topic(collector.device_id)

    client = mqtt.create_client(f"modbus-col-g{collector.group}", will_topic=status_topic)
    mqtt.connect(client, config.MQTT_BROKER, config.MQTT_PORT,
                 config.MQTT_KEEPALIVE, config.MQTT_USERNAME, config.MQTT_PASSWORD)
    mqtt.publish_status(client, status_topic, "online")

    stop_event = threading.Event()

    def _handle(signum, frame):
        log.info("收到退出信号，正在下线...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    log.info("Modbus 采集器启动 device=%s group=%s 区间=[0x%04X-0x%04X]",
             collector.device_id, collector.group, collector.start, collector.end)
    log.info("上报主题：%s", data_topic)

    try:
        collector.connect()
        while not stop_event.is_set():
            try:
                registers = collector.read_group()
                if report_all or registers != collector._last:
                    mqtt.publish_json(client, data_topic, collector.build_payload(registers), qos=config.MQTT_QOS)
                    log.info("已上报寄存器：%s", registers)
                    collector._last = registers
            except Exception as e:
                log.warning("采集失败：%s", e)
            stop_event.wait(config.MODBUS_POLL_INTERVAL)
    finally:
        mqtt.publish_status(client, status_topic, "offline")
        client.loop_stop()
        client.disconnect()
        collector.close()
        log.info("已下线，退出")


def main():
    parser = argparse.ArgumentParser(description="Modbus TCP 数据采集器")
    parser.add_argument("--read", action="store_true", help="只读取一次并上报后退出")
    parser.add_argument("--write", nargs=2, metavar=("ADDR", "VALUE"),
                        help="向本小组寄存器写入，例如 --write 0x0000 100")
    parser.add_argument("--report-all", action="store_true",
                        help="每次采集都上报（默认仅在值变化时上报）")
    args = parser.parse_args()

    if args.write:
        addr = int(args.write[0], 16)
        value = int(args.write[1])
        collector = ModbusCollector()
        try:
            collector.connect()
            collector.write_register(addr, value)
        finally:
            collector.close()
        return

    if args.read:
        collector = ModbusCollector()
        data_topic = config.modbus_data_topic(collector.device_id)
        client = mqtt.create_client(f"modbus-col-g{collector.group}")
        mqtt.connect(client, config.MQTT_BROKER, config.MQTT_PORT,
                     config.MQTT_KEEPALIVE, config.MQTT_USERNAME, config.MQTT_PASSWORD)
        try:
            collector.connect()
            registers = collector.read_group()
            mqtt.publish_json(client, data_topic, collector.build_payload(registers), qos=config.MQTT_QOS)
            log.info("已上报寄存器：%s", registers)
        finally:
            client.loop_stop()
            client.disconnect()
            collector.close()
        return

    run_poll(args.report_all)


if __name__ == "__main__":
    main()
