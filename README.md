# Modbus + MQTT IoT Simulation Prototype
> 项目定位：ESP32网关项目前期纯软件仿真原型，用于验证Modbus寄存器采集、JSON报文封装、MQTT消息上报链路，无硬件依赖，在PC端完成通信逻辑验证，后续移植至ESP32硬件网关。

## 运行指令
```bash
python modbus_collector.py --write 0x0007 100    # 向指定寄存器写入数值
运行逻辑：基于 pymodbus 库读取 Modbus 从站保持寄存器，读取结果组装为标准化 JSON 报文，通过 MQTT 协议上报。
完整链路：pymodbus 读取寄存器 → 组装JSON载荷 → MQTT发布 → MQTTX订阅接收查看报文
寄存器分配
从站保持寄存器地址范围：0x0000 ~ 0x0009，共 10 个寄存器。
本程序仅操作0x0007寄存器，程序做地址校验，尝试读写其他寄存器会直接拒绝。
如需修改操作寄存器地址，可在 config.py 调整 REGISTERS_PER_GROUP 或 group_register_range 参数。
表格
寄存器地址	用途
0x0000 ~ 0x0006	预留
0x0007	本程序操作寄存器
0x0008、0x0009	备用寄存器
MQTT 主题与报文 Payload
MQTT 主题定义：
text
iot/group8/sensor/sensor-01/data     # 传感器模拟：数据上报
iot/group8/sensor/sensor-01/status   # 传感器模拟：在线状态（online/offline）
iot/group8/modbus/modbus-01/data     # Modbus采集：寄存器数据上报
iot/group8/modbus/modbus-01/status   # Modbus采集：在线状态（online/offline）
任务 1 温湿度传感器模拟上报 Payload 示例
json
{"type":"sensor","device_id":"sensor-01","group":8,"temperature":25.6,"humidity":48.2, 
"unit":{"temperature":"celsius","humidity":"percentRH"},"seq":3,"ts":1725157680.123,"datetime":"2026-09-01T11:04:17+08:00"}
任务 2 Modbus 寄存器采集上报 Payload 示例
json
{"type":"modbus","device_id":"modbus-01","group":8, 
"slave":{"host":"192.168.20.59","port":5502,"unit":1}, 
"registers":{"0x0007":8000},"seq":3,"ts":1725157680.123,"datetime":"2026-09-01T11:04:17+08:00"}
使用 MQTTX 进行通信测试
MQTTX 新建连接：服务地址 172.16.4.211，端口 9783，匿名连接。
订阅主题：iot/group8/#，#为通配符，接收 group8 下全部 MQTT 消息。
传感器仿真测试：运行 python sensor_simulator.py，修改sensor.json内数值，在 MQTTX 查看实时上报数据。
Modbus 采集测试：运行 python modbus_collector.py，观察寄存器数据上报；使用--write参数修改寄存器值，验证数据变更上报。
本地离线测试（无需外部 Modbus 硬件设备）
新开两个终端窗口，本地启动 Modbus 从站模拟器进行闭环测试
powershell
# 终端1：启动本地Modbus从站模拟器
python modbus_slave_sim.py
# 终端2：采集程序连接本地模拟器
$env:MODBUS_HOST="127.0.0.1"
python modbus_collector.py
Experiment Result
MQTTX client subscribes to MQTT topics and receives formatted JSON payload:
mqttx_payload.png（MQTTX报文截图）

MQTT broker message log:
mqtt_broker_log.png（MQTT broker日志截图）

Project Description
This is a pre-development software simulation prototype. The Modbus acquisition and MQTT message forwarding logic verified in this project was later migrated to the ESP32 4-channel relay Modbus IoT gateway project.
本项目为预开发软件仿真原型，本项目验证的 Modbus 采集、MQTT 消息转发逻辑，后续移植到 ESP32 四通道继电器 Modbus 物联网网关项目。
