# SPL Query Syntax Reference

## Basic Syntax

| Operation | Syntax | Example |
|-----------|--------|---------|
| Equals | `field:value` | `severity:3` |
| Not equals | `NOT field:value` | `NOT attack_res:0` |
| Greater than | `field:>value` | `log_count:>10` |
| Greater than or equal | `field:>=value` | `severity:>=3` |
| Less than | `field:<value` | `severity:<2` |
| Less than or equal | `field:<=value` | `severity:<=2` |
| Wildcard | `field:*value*` | `ioc_resource:*0pendns*` |
| Exists | `_exists_:field` | `_exists_:file_hash_md5` |
| Range | `field:[min TO max]` | `log_count:[1 TO 10]` |

## Logical Operators

| Operator | Syntax | Example |
|----------|--------|---------|
| AND | `condition1 AND condition2` | `severity>=3 AND attack_res:2` |
| OR | `condition1 OR condition2` | `src_ip:172.19.1.1 OR dst_ip:172.19.1.1` |
| NOT | `NOT condition` | `NOT attack_res:0` |
| Grouping | `(condition1 AND condition2) OR condition3` | `(src_ip:172.19.1.1 OR dst_ip:172.19.1.1) AND severity>=3` |

## Field-specific Syntax

### IP Fields (src_ip, dst_ip)
IP fields support CIDR notation and range queries:
- `src_ip:172.19.1.1` - exact match
- `src_ip:172.19.1.0/24` - CIDR range
- `src_ip:>=172.19.1.1 AND src_ip:<172.19.1.254` - IP range

### Numeric Fields (severity, attack_res, log_count)
- `severity:>=3` - threshold
- `log_count:[1 TO 10]` - inclusive range

### String Fields (rule_id, attacker_addr, victim_addr)
- `rule_id:"103035661"` - exact match with quotes
- `attacker_addr:*202.101*` - wildcard search
- `ioc_resource:"v.beahh.com"` - exact match

## Common Query Patterns

### IP Range with Conditions
- (src_ip:>=172.19.1.1 AND src_ip:<172.19.1.25) AND (dst_ip:>=172.19.1.1 AND dst_ip:<=172.19.1.200) AND (attack_res:2 OR severity>=3)

### Threat Intelligence Lookup
- ioc_resource:"v.beahh.com" OR file_hash_md5:"d41d8cd98f00b204e9800998ecf8427e"

### Time Range Query (handled automatically by tool)
Time ranges are applied via the `timeType` parameter, not in SPL.

## Special Character Escaping
The following characters must be escaped with backslash when used in values: `+ - = && || > < ! ( ) { } [ ] ^ " ~ * ? : \ /`

Example: `ioc_resource:"xxx.abc\\!.com"`
