---
name: report-generate
description: 用于按IP、用户名、告警统计数量生成报告
---

# Report Generate Skill

## Overview
本技能用于根据用户要求生成包含IP地址、用户名和告警统计的报告。数据通过 `script_execute` 工具执行本Skill `scripts/` 目录下的 `report.py` 脚本来获取，不要使用其他工具来获取数据。

## When to Use
- 用户要求生成报告、周报、数据统计
- 用户需要测试数据（IP、用户名）
- 用户询问告警趋势分析

## How to Use

### Step 1: 理解用户需求
确认用户需要哪些数据：IP数量、用户数量、告警天数

### Step 2: 调用脚本获取数据

脚本路径：`report-generate/scripts/report.py`

**获取IP**（示例：获取5个IP）
```bash
python report-generate/scripts/report.py --ip 5
```

**获取用户名**（示例：获取10个用户名）
```bash
python report-generate/scripts/report.py --user 10
```

**获取告警统计**（示例：获取最近7天）
```bash
python report-generate/scripts/report.py --alert 7
```

**组合获取**
```bash
python report-generate/scripts/report.py --ip 5 --user 10
```

### Step 3: 生成报告
按以下Markdown格式输出报告：
# {报告标题}

**生成时间**：{当前日期时间}

---

## 1. IP地址清单

共生成 **{数量}** 个IP地址：

| 序号 | IP地址 |
|------|--------|
| 1 | {ip} |
| 2 | {ip} |
| ... | ... |

---

## 2. 用户账号列表

共生成 **{数量}** 个用户名：

| 序号 | 用户名 |
|------|--------|
| 1 | {username} |
| 2 | {username} |
| ... | ... |

---

## 3. 告警统计分析

统计周期：最近 **{天数}** 天

### 每日告警详情

| 日期 | 告警数量 | 趋势 |
|------|----------|------|
| {date} | {count} | {↑/↓/→} |

### 统计汇总

- 总告警数：{total}
- 日均告警数：{average}
- 最高告警数：{max}
- 最低告警数：{min}

### 趋势结论

{根据数据给出简要分析结论}