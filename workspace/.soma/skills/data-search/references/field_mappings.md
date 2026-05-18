# Field Mappings Reference (字段映射参考)

## Common Fields (All Data Types)

| Display Name | Field Name | Type | Description |
|--------------|------------|------|-------------|
| 源IP | src_ip | IP | Source IP address |
| 目的IP | dst_ip | IP | Destination IP address |
| 源端口 | src_port | integer | Source port number |
| 目的端口 | dst_port | integer | Destination port number |
| 严重等级 | severity | integer | Threat severity level |
| 攻击结果 | attack_res | integer | Attack result (see enum) |
| 攻击方向 | attack_direction | integer | Attack direction (see enum) |
| 规则ID | rule_id | string | Detection rule identifier |
| 时间戳 | timestamp | datetime | Event timestamp |
| 事件时间 | event_time | datetime | Event occurrence time |

## Logs Only (xdr_tdp_event)

| Display Name | Field Name | Type |
|--------------|------------|------|
| 日志类型 | log_type | string |
| 原始日志 | raw_log | string |
| 攻击者 | attacker_addr | string |
| 受害者 | victim_addr | string |
| 攻击场景 | attack_scene | string |
| 威胁类型 | threat_type | string |
| 威胁标签 | threat_tag | array |
| 攻击技术 | attack_tec | string |
| 置信度 | confidence | integer |
| 攻击分数 | attack_score | integer |

## Alerts Only (xdr_tdp_attack)

| Display Name | Field Name | Type |
|--------------|------------|------|
| 攻击者 | attacker_addr | string |
| 受害者 | victim_addr | string |
| 攻击场景 | attack_scene | string |
| 威胁类型 | threat_type | string |
| 威胁标签 | threat_tag | array |
| 攻击技术 | attack_tec | string |
| 置信度 | confidence | integer |
| 攻击分数 | attack_score | integer |

## Security Incidents Only (xdr_tdp_incident)

| Display Name | Field Name | Type |
|--------------|------------|------|
| 事件名称 | incident_name | string |
| 事件等级 | incident_severity | integer |
| 事件状态 | incident_status | integer |
| 关联告警 | related_alerts | array |
| 处理建议 | suggestion | string |