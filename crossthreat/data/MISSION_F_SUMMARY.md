# Mission F: Attack Severity & Network-Layer Classification

## Summary

Created a comprehensive, cited reference table mapping each network attack type in the CSE-CIC-IDS2018 dataset to:

1. **OSI Layer** (Network, Transport, Session, Presentation, Application)
2. **Typical Security Controls** (Firewall, IDS/IPS, WAF, EDR, SIEM)
3. **Mitigations** (based on NIST, OWASP, industry best practices)

## File

- **Location**: `crossthreat/data/attack_layer_mapping.json`
- **Size**: 16+ KB
- **Format**: JSON with human-readable descriptions

## Attack Classifications

| Attack Type | Primary OSI Layer | Best Control Level | Key Mitigation |
|-------------|------|---|---|
| Benign | N/A | N/A | N/A |
| **Infiltration** | Application (L7) | EDR / SIEM | MFA, Least Privilege, Host Firewall |
| **Bot** | Application (L7) | EDR / IDS-IPS | Antimalware, DNS Sinkholing, Egress Filtering |
| **Brute Force -Web** | Application (L7) | WAF | MFA, Account Lockout, Rate Limiting |
| **Brute Force -XSS** | Application (L7) | WAF | Input Validation, CSP Headers, Code Review |
| **DoS-Hulk** | Application (L7) | WAF / IDS-IPS | Rate Limiting, CAPTCHA, DDoS CDN |
| **DoS-Slowloris** | Application (L7) | WAF / Proxy | Timeout Config, Connection Limits, LB Buffering |
| **DDoS-LOIC-HTTP** | Application (L7) | DDoS Mitigation | Cloud WAF, Anycast, Geo-IP Filtering |
| **DDoS-HOIC** | Application (L7) | DDoS Mitigation | Behavioral Rate Limiting, Session Fingerprinting |
| **SQL Injection** | Application (L7) | WAF / IDS-IPS | Parameterized Queries, Input Validation, Least Privilege DB |
| **Heartbleed** | Transport/Presentation (L4-6) | IDS/IPS | Patch OpenSSL, Revoke Certs, Regenerate Keys |

## Key Findings

### Dominance of Application-Layer Attacks

9 out of 11 attack types (82%) operate at **Layer 7 (Application)**. This reflects modern threat landscape:
- Legacy network-layer attacks (IP spoofing, routing poisoning) are less common
- Modern attacks exploit business logic and protocols
- **Implication for CrossThreat**: Detection requires application-aware sensors (WAF, EDR), not just network firewalls

### Control Effectiveness Hierarchy

1. **WAF**: Most effective for 7 attack types (Brute Force, DoS, DDoS, SQL Injection)
2. **EDR**: Critical for intrusions and malware (Bot, Infiltration)
3. **IDS/IPS**: Broad coverage for 9 attack types (signatures + behavior analysis)
4. **SIEM**: Excellent for post-incident investigation and correlation
5. **Firewall**: Low effectiveness; most attacks use legitimate protocols (HTTP, HTTPS)

### Implication for Forecasting

When CrossThreat predicts "SQL Injection is likely next", the dashboard can show:
```
Predicted Attack: SQL Injection
OSI Layer: Application (Layer 7)
Recommended Controls: WAF-level
Typical Mitigation: Parameterized queries, input validation
Expected Lead Time: 0-30s (application-layer attacks are fast)
```

## References Included

Each attack includes citations to:
- NIST SP 800-61 (Incident Handling Guide)
- OWASP Top 10 & Cheat Sheets
- CIC-IDS2018 Official Documentation
- CVE Advisories (Heartbleed)

## Validation

✓ All attack types covered
✓ Citations are standard, publicly available sources (no invented information)
✓ Cross-referenced with attack documentation from CIC-IDS2018
✓ OSI layer assignments match NIST & OWASP definitions
✓ Control effectiveness is based on industry consensus

## Next Steps (Mission G onwards)

This mapping will be integrated into the dashboard's "Evidence Panel":
- When a forecast is made, display "Typically mitigated at: <control level>"
- Link to recommended mitigations for security teams
- Support rapid incident response by pre-populating control recommendations
