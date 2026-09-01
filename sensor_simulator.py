# -*- coding: utf-8 -*-
"""
任务 1：温湿度模拟器（JSON 文件 + MQTT 上报）
==============================================
职责：
  1. 监视 sensor.json 文件中的温度 / 湿度数值；
  2. 当数值发生变化时，立即通过 MQTT 上报到服务器。

测试方式（配合 MQTTX）：
  1. 运行 python sensor_simulator.py
  2. 手动修改项目根目录下的 sensor.json（改 temperature / humidity 并保存）
  3. 脚本检测到变化后自动上报，MQTTX 即可收到消息

上报主题：iot/group8/sensor/sensor-01/data
上报 Payload 示例：
  {
    "type": "sensor",
    "device_id": "sensor-01",
    "group": 8,
    "temperature": 25.6,
    "humidity": 48.2,
    "unit": {"temperature": "celsius", "humidity": "percentRH"},
    "seq": 3,
    "ts": 1725157680.123,
    "datetime": "2026-09-01T11:04:17+08:00"
  }
"""
import json
import logging
import os
import signal
import threading
import time
from datetime import datetime

import config
import mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("sensor")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, config.SENSOR_JSON_FILE)

DEFAULT_STATE = {"temperature": 25.0, "humidity": 50.0}


def _ensure_json_exists():
    """若 sensor.json 不存在，写入默认初始值，方便测试。"""
    if os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_STATE, f, ensure_ascii=False, indent=2)
    log.info("已生成默认 JSON 文件：%s（可手动修改其中数值进行测试）", DATA_FILE)


def _read_json():
    """读取 sensor.json 中的 (temperature, humidity)，失败返回 None。"""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return float(data["temperature"]), float(data["humidity"])
    except (OSError, KeyError, ValueError, TypeError) as e:
        log.warning("读取 %s 失败：%s", DATA_FILE, e)
        return None


def build_payload(temperature, humidity, seq):
    """构造上报 payload。"""
    ts = time.time()
    return {
        "type": "sensor",
        "device_id": config.SENSOR_DEVICE_ID,
        "group": config.GROUP_ID,
        "temperature": temperature,
        "humidity": humidity,
        "unit": {"temperature": "celsius", "humidity": "percentRH"},
        "seq": seq,
        "ts": round(ts, 3),
        "datetime": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def run():
    """监视 sensor.json 变化并上报。"""
    _ensure_json_exists()

    data_topic = config.sensor_data_topic()
    status_topic = config.sensor_status_topic()

    client = mqtt.create_client(f"sensor-sim-g{config.GROUP_ID}", will_topic=status_topic)
    mqtt.connect(client, config.MQTT_BROKER, config.MQTT_PORT,
                 config.MQTT_KEEPALIVE, config.MQTT_USERNAME, config.MQTT_PASSWORD)
    mqtt.publish_status(client, status_topic, "online")

    stop_event = threading.Event()

    def _handle(signum, frame):
        log.info("收到退出信号，正在下线...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    log.info("温湿度模拟器启动 device=%s group=%s", config.SENSOR_DEVICE_ID, config.GROUP_ID)
    log.info("监视文件：%s", DATA_FILE)
    log.info("上报主题：%s", data_topic)

    last = None
    seq = 0
    try:
        while not stop_event.is_set():
            current = _read_json()
            if current is not None and current != last:
                seq += 1
                temperature, humidity = current
                mqtt.publish_json(client, data_topic, build_payload(temperature, humidity, seq),
                                  qos=config.MQTT_QOS)
                log.info("检测到数值变化，已上报：温度=%.1f℃ 湿度=%.1f%%", temperature, humidity)
                last = current
            stop_event.wait(config.SENSOR_INTERVAL)
    finally:
        mqtt.publish_status(client, status_topic, "offline")
        client.loop_stop()
        client.disconnect()
        log.info("已下线，退出")


def main():
    run()


if __name__ == "__main__":
    main()
