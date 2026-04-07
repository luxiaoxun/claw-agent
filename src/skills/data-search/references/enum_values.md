# Enum Values Reference (枚举值参考)

## attack_res (攻击结果)

| Value | Chinese | English |
|-------|---------|---------|
| 0 | 未知 | Unknown |
| 1 | 失败 | Failed |
| 2 | 成功 | Successful |
| 3 | 攻陷 | Compromised |

## severity (威胁等级)

| Value | Chinese | English |
|-------|---------|---------|
| 1 | 低危 | Low |
| 2 | 中危 | Medium |
| 3 | 高危 | High |
| 4 | 超危 | Critical |

## attack_direction (攻击方向)

| Value | Chinese | English |
|-------|---------|---------|
| 0 | 外到内 | External to Internal |
| 1 | 内到外 | Internal to External |
| 2 | 外到外 | External to External |
| 3 | 内到内 | Internal to Internal |

## attack_scene (攻击场景)

| Value | Chinese | English |
|-------|---------|---------|
| 0x01 | 外网攻击 | External Attack |
| 0x02 | 内网渗透 | Internal Penetration |
| 0x03 | 失陷破坏 | Compromise & Damage |

## threat_class / threat_class_list (告警类型)

| Value | Chinese | English |
|-------|---------|---------|
| 0x1 | Web攻击 | Web Attack |
| 0x2 | 恶意软件 | Malware |
| 0x3 | 内网攻击 | Internal Attack |
| 0x4 | 漏洞利用 | Exploit |
| 0x5 | 网络攻击 | Network Attack |
| 0x6 | 扫描爆破 | Scan/Brute Force |
| 0x7 | 挖矿行为 | Cryptomining |
| 0x8 | Web Shell | Web Shell |
| 0x9 | 口令安全 | Credential Security |
| 0xa | 勒索软件 | Ransomware |
| 0x10 | 可疑威胁 | Suspicious Threat |

## threat_tag (威胁标签)

| Value | Chinese | English                                            |
|-------|---------|----------------------------------------------------|
| 0x1 | SQL注入 | SQL Injection                                      |
| 0x2 | 暴力猜解 | Brute Force                                        |
| 0x3 | WebShell | WebShell                                           |
| 0x4 | 菜刀 | China Chopper                                      |
| 0x5 | 冰蝎 | Behinder                                           |
| 0x6 | 蚁剑 | AntSword                                           |
| 0x7 | 哥斯拉 | Godzilla                                           |
| 0x8 | 一句话木马 | One-liner Trojan                                   |
| 0xa | 文件上传 | File Upload                                        |
| 0xb | 命令执行 | Command Execution                                  |
| 0xc | 内网隧道 | Intranet Tunnel                                    |
| 0xd | 反弹Shell | Reverse Shell                                      |
| 0xe | 反序列化 | Deserialization                                    |
| 0xf | 代码执行 | Code Execution                                     |
| 0x10 | XXE攻击 | XXE Attack                                         |
| 0x11 | 挖矿木马 | Cryptojacking Trojan                               |
| 0x13 | CobaltStrike | CobaltStrike                                       |
| 0x14 | Metasploit | Metasploit                                         |
| 0x15 | 扫描行为 | Scanning Behavior                                  |
| 0x16 | 开山斧 | Kaishanfu                                          |
| 0x17 | weevely | Weevely                                            |
| 0x18 | Cknife | Cknife                                             |
| 0x19 | XSS | XSS                                                |
| 0x1a | 矿池协议:Getwork | Mining Pool Protocol: Getwork                      |
| 0x1b | 矿池协议:Getblocktemplate | Mining Pool Protocol: Getblocktemplate             |
| 0x1d | 币种:Ethereum | Currency: Ethereum                                 |
| 0x4b | 币种:Monero | Currency: Monero                                   |
| 0x4c | 币种:Bitcoin | Currency: Bitcoin                                  |
| 0x4d | 币种:Pascalcoin | Currency: Pascalcoin                               |
| 0x4e | 下载器 | Downloader                                         |
| 0x50 | 矿池协议 | Mining Pool Protocol                               |
| 0x51 | 配置不当 | Misconfiguration                                   |
| 0x52 | 信息泄露 | Information Disclosure                             |
| 0x53 | CVE | CVE                                                |
| 0x54 | 溢出攻击 | Overflow Attack                                    |
| 0x55 | JSON注入 | JSON Injection                                     |
| 0x56 | 文件写入 | File Write                                         |
| 0x57 | 暗网 | Dark Web                                           |
| 0x58 | XPath注入 | XPath Injection                                    |
| 0x59 | 跨站请求伪造 | CSRF                                               |
| 0x5a | 代理工具 | Proxy Tool                                         |
| 0x5b | CRLF注入 | CRLF Injection                                     |
| 0x5c | 测试病毒 | Test Virus                                         |
| 0x5d | 非授权访问 | Unauthorized Access                                |
| 0x5e | 渗透工具 | Penetration Tool                                   |
| 0x5f | 目录穿越 | Directory Traversal                                |
| 0x60 | 明文口令 | Plaintext Password                                 |
| 0x61 | 逻辑攻击 | Logic Attack                                       |
| 0x62 | URL跳转 | URL Redirect                                       |
| 0x63 | 文件包含 | File Inclusion                                     |
| 0x64 | URL过长 | URL Overlength                                     |
| 0x65 | CNC | CNC                                                |
| 0x66 | 病毒工具 | Virus Tool                                         |
| 0x67 | 灰色软件 | Grayware                                           |
| 0x68 | XML注入 | XML Injection                                      |
| 0x69 | CNNVD | CNNVD                                              |
| 0x6a | 端口转发 | Port Forwarding                                    |
| 0x6b | 网络蠕虫 | Network Worm                                       |
| 0x6c | 隐秘隧道 | Covert Tunnel                                      |
| 0x6d | APT | APT                                                |
| 0x6e | SSRF | SSRF                                               |
| 0x6f | 弱口令 | Weak Password                                      |
| 0x70 | 窃密木马 | Information Stealer                                |
| 0x71 | LDAP注入 | LDAP Injection                                     |
| 0x72 | 后门程序 | Backdoor                                           |
| 0x73 | HTTP响应截断 | HTTP Response Splitting                            |
| 0x74 | 空口令 | Empty Password                                     |
| 0x75 | 网络钓鱼 | Phishing                                           |
| 0x76 | 间谍软件 | Spyware                                            |
| 0x77 | XQuery注入 | XQuery Injection                                   |
| 0x78 | 编码绕过 | Encoding Bypass                                    |
| 0x79 | 拒绝服务 | Denial of Service                                  |
| 0x7a | 僵尸网络 | Botnet                                             |
| 0x7b | 文件读取 | File Read                                          |
| 0x7c | 爬虫 | Crawler                                            |
| 0x7d | 机器学习 | Machine Learning                                   |
| 0x7e | 勒索 | Ransomware                                         |
| 0x7f | 提权 | Privilege Escalation                               |
| 0x80 | SQLMAP | SQLMAP                                             |
| 0x81 | AWVS | AWVS                                               |
| 0x82 | Nessus | Nessus                                             |
| 0x83 | Nmap | Nmap                                               |
| 0x84 | Hydra | Hydra                                              |
| 0x85 | BurpSuite | BurpSuite                                          |
| 0x86 | Masscan | Masscan                                            |
| 0x87 | 绿盟扫描器 | NSFOCUS Scanner                                    |
| 0x88 | Empire | Empire                                             |
| 0x89 | Dnscat | Dnscat                                             |
| 0x8a | Dirbuster | Dirbuster                                          |
| 0x8b | 御剑 | Yujian                                             |
| 0x8c | WebCruiser | WebCruiser                                         |
| 0x8d | Nikto | Nikto                                              |
| 0x8e | 矿池域名 | Mining Pool Domain                                 |
| 0x90 | Shellcode | Shellcode                                          |
| 0x91 | 可疑工具 | Suspicious Tool                                    |
| 0x92 | SMB | SMB                                                |
| 0x93 | 挖矿内核登录 | Mining Kernel Login                                |
| 0x94 | 挖矿内核抽水 | Mining Kernel Drain                                |
| 0x95 | 文件下载 | File Download                                      |
| 0x96 | 内存损坏 | Memory Corruption                                  |
| 0x97 | 内存泄漏 | Memory Leak                                        |
| 0x98 | EL注入 | EL Injection                                       |
| 0x99 | 内网命令执行 | Intranet Command Execution                         |
| 0x9a | 内网凭据窃取 | Intranet Credential Theft                          |
| 0x9b | 内网信息探测 | Intranet Information Detection                     |
| 0x9c | 0day漏洞 | 0-day Vulnerability                                |
| 0x9d | 恶意域名访问 | Malicious Domain Access                            |
| 0x9e | 可疑请求 | Suspicious Request                                 |
| 0x9f | 重保 | Major Security Protection                          |
| 0xa0 | SSTI注入 | SSTI Injection                                     |
| 0xa1 | DGA域名 | DGA Domain                                         |
| 0xa2 | ARP欺骗 | ARP Spoofing                                       |
| 0xa3 | DNS劫持 | DNS Hijacking                                      |
| 0xa4 | 漏洞扫描 | Vulnerability Scan                                 |
| 0xa5 | 银狐RAT | Silver Fox RAT                                     |
| 0xa6 | 0day/Nday | 0-day/N-day                                        |
| 0xa7 | basic认证 | Basic Authentication                               |
| 0xa8 | 工控 | Industrial Control                                 |
| 0xa9 | 中间件 | Middleware                                         |
| 0xaa | 信创漏洞 | Xinchuang Vulnerability                            |
| 0xab | 两高一弱 | High Risk Ports or Vulnerabilities, Weak Passwords |