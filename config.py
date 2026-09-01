# -*- coding: utf-8 -*-
"""
全局配置文件
============
任务 1（温湿度模拟器）和任务 2（Modbus 采集器）两个独立脚本共用这一套配置。
所有参数也可通过环境变量覆盖。
"""
import os


def _env_int(name, default):
    return int(os.getenv(name, str(default)))


def _env_float(name, default):
    return float(os.getenv(name, str(default)))


def _env_str(name, default):
    return os.getenv(name, default)


# ============ 小组身份 ============
GROUP_ID = _env_int("GROUP_ID", 8)   # 第 8 组

# ============ MQTT 服务器（两个任务共用） ============
MQTT_BROKER = _env_str("MQTT_BROKER", "172.16.4.211")
MQTT_PORT = _env_int("MQTT_PORT", 9783)
MQTT_USERNAME = _env_str("MQTT_USERNAME", "test")
MQTT_PASSWORD = _env_str("MQTT_PASSWORD", "123456")
MQTT_KEEPALIVE = _env_int("MQTT_KEEPALIVE", 60)
MQTT_QOS = _env_int("MQTT_QOS", 1)

# ============ 任务 1：温湿度模拟器 ============
SENSOR_DEVICE_ID = _env_str("SENSOR_DEVICE_ID", "sensor-01")
SENSOR_JSON_FILE = _env_str("SENSOR_JSON_FILE", "sensor.json")   # 监视的 JSON 文件
SENSOR_INTERVAL = _env_float("SENSOR_INTERVAL", 2.0)   # 检测周期（秒）

# ============ 任务 2：Modbus TCP 从站 ============
MODBUS_HOST = _env_str("MODBUS_HOST", "192.168.20.59")
MODBUS_PORT = _env_int("MODBUS_PORT", 5502)
MODBUS_UNIT = _env_int("MODBUS_UNIT", 1)             # Modbus 单元标识符（Unit ID）
MODBUS_TIMEOUT = _env_float("MODBUS_TIMEOUT", 3.0)   # 通信超时（秒）
MODBUS_POLL_INTERVAL = _env_float("MODBUS_POLL_INTERVAL", 5.0)  # 采集周期（秒）
MODBUS_DEVICE_ID = _env_str("MODBUS_DEVICE_ID", "modbus-01")

# ============ 寄存器分配（任务 2） ============
# 从站保持寄存器范围：0x0000 ~ 0x0009（共 10 个）
# 每组占用 1 个寄存器，第 N 组对应 0x(N-1)：
#   第 1 组 -> 0x0000
#   第 2 组 -> 0x0001
#   ...
#   第 8 组 -> 0x0007
#   0x0008 ~ 0x0009 备用
# 若不同地址，改 REGISTERS_PER_GROUP 或直接改 group_register_range 即可。
REGISTER_START = _env_int("REGISTER_START", 0x0000)
REGISTER_TOTAL = 10
REGISTERS_PER_GROUP = 1


def group_register_range(group_id=None):
    """返回指定小组占用的寄存器区间 (起始地址, 结束地址)，闭区间。

    例如 group_id=1 -> (0, 0)，group_id=8 -> (7, 7)。
    """
    gid = group_id if group_id is not None else GROUP_ID
    start = REGISTER_START + (gid - 1) * REGISTERS_PER_GROUP
    end = start + REGISTERS_PER_GROUP - 1
    if start < REGISTER_START or end >= REGISTER_START + REGISTER_TOTAL:
        raise ValueError(
            f"GROUP_ID={gid} 超出寄存器范围：最多 {REGISTER_TOTAL // REGISTERS_PER_GROUP} 组"
        )
    return start, end


# ============ MQTT 主题 ============
def _topic(kind, device_id, suffix):
    return f"iot/group{GROUP_ID}/{kind}/{device_id}/{suffix}"


def sensor_data_topic(device_id=None):
    return _topic("sensor", device_id or SENSOR_DEVICE_ID, "data")


def sensor_status_topic(device_id=None):
    return _topic("sensor", device_id or SENSOR_DEVICE_ID, "status")


def modbus_data_topic(device_id=None):
    return _topic("modbus", device_id or MODBUS_DEVICE_ID, "data")


def modbus_status_topic(device_id=None):
    return _topic("modbus", device_id or MODBUS_DEVICE_ID, "status")
