---
name: data-search
description: 根据时间范围、IP地址、威胁等级、攻击结果等条件查询数据（日志、告警、安全事件），支持 SPL（搜索处理语言）语法。
---

# Data Search Skill

## Overview
本技能用于查询安全数据，包括日志、告警和安全事件。它将自然语言查询转换为 SPL 语法，并通过 `search_data` 工具执行。

## When to Use
- 用户要求查询日志、告警、安全事件
- 用户需要按时间范围、IP段、威胁等级等条件查询数据

## How to Use

### Step 1: Understand the Query
解析用户意图，识别以下内容：
- **数据类型**: 日志（event）、告警（attack）或安全事件（incident）
- **时间范围**: 今天、最近7天、自定义
- **过滤条件**: IP、严重等级、攻击结果等
- **分页参数**: 页码和每页条数

### Step 2: Translate to SPL
SPL查询语法：

| Requirement | SPL Pattern                                    |
|-------------|------------------------------------------------|
| 字段等于        | `field:value`                                  |
| 字段不等于       | `NOT field:value`                              |
| 范围查询        | `field:>=value` or `field:<=value`             |
| 多个值         | `field:(value1 OR value2)`                     |
| IP 范围       | `src_ip:>=172.17.6.1 AND src_ip:<172.17.6.254` |
| AND 组合      | `condition1 AND condition2`                    |
| OR 组合       | `condition1 OR condition2`                     |
| 支持括号        | `(condition1 OR condition2) AND condition3`    |
| 模糊/通配符      | `field:*value*`                                |

枚举值必须转换为数字:
  * 攻击结果(attack_res): 未知0,失败1,成功2,攻陷3
  * 威胁/严重等级(severity): 低危1,中危2,高危3,超危4
  * 攻击方向(attack_direction): 外到内0,内到外1,外到外2,内到内3

### Step 3: Call search_data Tool
使用 search_data 工具，并传入以下参数：

```json
{
  "indexName": "event|attack|incident",
  "query": "SPL query string",
  "timeType": 1|2|3|4|5,
  "timeLimit": "YYYY-MM-DD HH:MM:SS,YYYY-MM-DD HH:MM:SS",
  "pageNum": 1,
  "pageSize": 10,
  "sortField": "severity|event_time",
  "sortOrder": "desc|asc"
}
```

**timeType取值说明：**

- `1`: Today
- `2`: Last 7 days
- `3`: Last 14 days
- `4`: Last 30 days
- `5`: Custom (requires timeLimit)

### Step 4: Format Response
按以下要求返回结果

**重要约束：**
- 严禁在输出内容前后添加 ````json` 或 ```` ` 等 Markdown 代码块标记
- 直接输出纯文本 JSON 格式，第一个字符必须是 `{`，最后一个字符必须是 `}`
- 不要输出任何解释性文字或换行符（JSON内部换行除外）

示例输出：
{
  "spl": "translated SPL query",
  "result": {
    "total": 86,
    "hits": [...],
    "page": 1,
    "page_size": 10
  }
}
