# NF-UNSW-NB15-v3 Audit Report

## 1. Executive Summary
- File: NF-UNSW-NB15-v3.csv
- Path: C:\CyberShield\crossthreat\data\external\NF-UNSW-NB15-v3.csv
- Size: 577360958 bytes
- Rows: 2,365,424
- Columns: 55
- Label column: Label
- Attack column: Attack
- Benign records: 2,237,731
- Attack records: 127,693
- Attack classes: 10
- Missing values: 63,425
- Duplicate rows: 14,815

## 2. Dataset Statistics

| Metric | Value |
|---|---:|
| Rows | 2,365,424 |
| Columns | 55 |
| Duplicate rows | 14,815 |
| Missing values | 63,425 |
| Benign | 2,237,731 |
| Attack | 127,693 |
| Attack classes | 10 |

## 3. Full Schema

1. `FLOW_START_MILLISECONDS` ? int64
2. `FLOW_END_MILLISECONDS` ? int64
3. `IPV4_SRC_ADDR` ? str
4. `L4_SRC_PORT` ? int64
5. `IPV4_DST_ADDR` ? str
6. `L4_DST_PORT` ? int64
7. `PROTOCOL` ? int64
8. `L7_PROTO` ? float64
9. `IN_BYTES` ? int64
10. `IN_PKTS` ? int64
11. `OUT_BYTES` ? int64
12. `OUT_PKTS` ? int64
13. `TCP_FLAGS` ? int64
14. `CLIENT_TCP_FLAGS` ? int64
15. `SERVER_TCP_FLAGS` ? int64
16. `FLOW_DURATION_MILLISECONDS` ? int64
17. `DURATION_IN` ? int64
18. `DURATION_OUT` ? int64
19. `MIN_TTL` ? int64
20. `MAX_TTL` ? int64
21. `LONGEST_FLOW_PKT` ? int64
22. `SHORTEST_FLOW_PKT` ? int64
23. `MIN_IP_PKT_LEN` ? int64
24. `MAX_IP_PKT_LEN` ? int64
25. `SRC_TO_DST_SECOND_BYTES` ? float64
26. `DST_TO_SRC_SECOND_BYTES` ? float64
27. `RETRANSMITTED_IN_BYTES` ? int64
28. `RETRANSMITTED_IN_PKTS` ? int64
29. `RETRANSMITTED_OUT_BYTES` ? int64
30. `RETRANSMITTED_OUT_PKTS` ? int64
31. `SRC_TO_DST_AVG_THROUGHPUT` ? int64
32. `DST_TO_SRC_AVG_THROUGHPUT` ? int64
33. `NUM_PKTS_UP_TO_128_BYTES` ? int64
34. `NUM_PKTS_128_TO_256_BYTES` ? int64
35. `NUM_PKTS_256_TO_512_BYTES` ? int64
36. `NUM_PKTS_512_TO_1024_BYTES` ? int64
37. `NUM_PKTS_1024_TO_1514_BYTES` ? int64
38. `TCP_WIN_MAX_IN` ? int64
39. `TCP_WIN_MAX_OUT` ? int64
40. `ICMP_TYPE` ? int64
41. `ICMP_IPV4_TYPE` ? int64
42. `DNS_QUERY_ID` ? int64
43. `DNS_QUERY_TYPE` ? int64
44. `DNS_TTL_ANSWER` ? int64
45. `FTP_COMMAND_RET_CODE` ? int64
46. `SRC_TO_DST_IAT_MIN` ? int64
47. `SRC_TO_DST_IAT_MAX` ? int64
48. `SRC_TO_DST_IAT_AVG` ? int64
49. `SRC_TO_DST_IAT_STDDEV` ? int64
50. `DST_TO_SRC_IAT_MIN` ? int64
51. `DST_TO_SRC_IAT_MAX` ? int64
52. `DST_TO_SRC_IAT_AVG` ? int64
53. `DST_TO_SRC_IAT_STDDEV` ? int64
54. `Label` ? int64
55. `Attack` ? str

## 4. Missing Values

- `SRC_TO_DST_SECOND_BYTES`: 63425 missing

## 5. Label Distribution

| Label | Count | Percentage |
|---|---:|---:|
| 0 | 2,237,731 | 94.602% |
| 1 | 127,693 | 5.398% |

| Attack class | Count |
|---|---:|
| Benign | 2,237,731 |
| Exploits | 42,748 |
| Fuzzers | 33,816 |
| Generic | 19,651 |
| Reconnaissance | 17,074 |
| DoS | 5,980 |
| Backdoor | 4,659 |
| Shellcode | 2,381 |
| Analysis | 1,226 |
| Worms | 158 |

## 6. Temporal Analysis

- `FLOW_START_MILLISECONDS`: min=2015-01-22T11:49:36.907000+00:00 | max=2015-02-18T12:29:24.927000+00:00 | unique=1893404 | duplicates=472020 | monotonic=False
- `FLOW_END_MILLISECONDS`: min=2015-01-22T11:50:14.036000+00:00 | max=2015-02-18T12:29:25.011000+00:00 | unique=2299732 | duplicates=65692 | monotonic=False
- `FLOW_DURATION_MILLISECONDS`: min=1970-01-01T00:00:00+00:00 | max=1970-01-01T00:02:00.948000+00:00 | unique=19809 | duplicates=2345615 | monotonic=False

The dataset contains valid millisecond flow timestamps and supports sequence construction using temporal ordering. However, it is flow-level telemetry rather than a clean per-device or per-session time series, so next-state forecasting still requires careful grouping and domain-aware labels; the mere presence of timestamps is not sufficient to guarantee a valid forecasting objective.

## 7. CIC-IDS2017 Compatibility

| NF feature | CIC feature | Match type | Usable? | Reason |
|---|---|---|---|---|
| FLOW_START_MILLISECONDS | Timestamp | APPROXIMATE | Yes | Both encode flow start time; NF uses epoch milliseconds and CIC uses a human-readable timestamp. |
| IPV4_SRC_ADDR | Src IP | EXACT | No | Same network identifier concept, but kept as an identifier and not a model feature. |
| IPV4_DST_ADDR | Dst IP | EXACT | No | Same network identifier concept; not a valid predictive feature for generalization. |
| L4_SRC_PORT | Src Port | EXACT | No | Port values are often protocol- and host-dependent and can leak endpoint identity. |
| L4_DST_PORT | Dst Port | EXACT | No | Destination port is semantically comparable, but can leak service identity and is unstable across datasets. |
| PROTOCOL | Protocol | EXACT | Yes | Same protocol code used to describe L3/L4 transport. |
| FLOW_DURATION_MILLISECONDS | Flow Duration | EXACT | Yes | Equivalent duration metric in millisecond units. |
| IN_BYTES | TotLen Fwd Pkts | APPROXIMATE | Yes | NF provides inbound byte count; CIC uses forward-total-length proxy, not exact same feature. |
| OUT_BYTES | TotLen Bwd Pkts | APPROXIMATE | Yes | NF provides outbound byte count; CIC uses reverse-direction total length, with direction semantics similar but not identical. |
| TCP_FLAGS | SYN Flag Cnt / ACK Flag Cnt / PSH Flag Cnt / RST Flag Cnt | APPROXIMATE | Yes | NF has aggregate TCP flags while CIC stores separate counts; this is a comparable signal but not a direct one-to-one match. |
| Label | Label | APPROXIMATE | Yes | Binary label in NF versus multi-class attack taxonomy in CIC; label mapping requires explicit recoding. |

## 8. CIC-IDS2018 Compatibility

| NF feature | CIC feature | Match type | Usable? | Reason |
|---|---|---|---|---|
| FLOW_START_MILLISECONDS | Timestamp | APPROXIMATE | Yes | Same concept in both collections but different timestamp formatting and granularity. |
| IPV4_SRC_ADDR | Src IP | EXACT | No | Identifier field, not a valid generalization feature. |
| IPV4_DST_ADDR | Dst IP | EXACT | No | Identifier field and likely source-specific leakage. |
| L4_SRC_PORT | Src Port | EXACT | No | Endpoint-derived port information is not stable across datasets or networks. |
| L4_DST_PORT | Dst Port | EXACT | No | Service identity can leak task-specific patterns and should be excluded from generalization models. |
| PROTOCOL | Protocol | EXACT | Yes | Protocol IDs are consistently represented. |
| FLOW_DURATION_MILLISECONDS | Flow Duration | EXACT | Yes | Equivalent concept. |
| IN_BYTES | Total Length of Fwd Packet | APPROXIMATE | Yes | Direction-specific byte totals approximate each other. |
| OUT_BYTES | Total Length of Bwd Packet | APPROXIMATE | Yes | Aggregate directional volumes are comparable. |
| TCP_FLAGS | SYN/ACK/PSH/RST flags | APPROXIMATE | Yes | Similar handshake/abnormal traffic indicators, but not exact field-level alignment. |
| Attack | Label | APPROXIMATE | Yes | Both are attack taxonomy labels, but the attack vocabulary differs across datasets and must be mapped explicitly. |

## 9. Label Mapping

| Original label | Dataset | Proposed canonical label | Mapping type | Reason |
|---|---|---|---|---|
| Benign | NF-UNSW-NB15-v3 | Benign | EXACT | Clearly normal traffic without malicious behavior. |
| Fuzzers | NF-UNSW-NB15-v3 | Fuzzers | EXACT | Specific malicious probing category recorded by the dataset. |
| Exploits | NF-UNSW-NB15-v3 | Exploits | EXACT | Direct exploit-attempt class. |
| DoS | NF-UNSW-NB15-v3 | DoS | EXACT | Direct denial-of-service class. |
| Reconnaissance | NF-UNSW-NB15-v3 | Reconnaissance | EXACT | Reconnaissance/scan traffic remains distinct. |
| Backdoor | NF-UNSW-NB15-v3 | Backdoor | EXACT | Mission-specific backdoor pattern. |
| Shellcode | NF-UNSW-NB15-v3 | Shellcode | APPROXIMATE | Equivalent exploit payload concept, but not identical to CIC naming. |
| Analysis | NF-UNSW-NB15-v3 | Analysis | APPROXIMATE | May align with some web-attack or reconnaissance behavior. |
| Worms | NF-UNSW-NB15-v3 | Worms | EXACT | Direct worm category. |
| Benign | CIC-IDS2017 | Benign | EXACT | Standard benign traffic label. |
| Infiltration | CIC-IDS2017 | Infiltration | EXACT | Direct infiltration class. |
| Web Attack / Brute Force | CIC-IDS2018 | WebAttack_BruteForce | APPROXIMATE | Web-attack family; a broader label than generic brute-force class and not identical to NF labels. |
| Web Attack / XSS | CIC-IDS2018 | WebAttack_XSS | APPROXIMATE | Security-specific web attack type that is not equivalent to the NF taxonomy. |
| Web Attack / SQL Injection | CIC-IDS2018 | WebAttack_SQLi | APPROXIMATE | Application-layer web attack with no direct NF equivalent. |
| Bot | CIC-IDS2018 | Bot | EXACT | Botnet class. |
| DDOS | CIC-IDS2018 | DoS | APPROXIMATE | Often grouped under DoS/DDoS family, but the taxonomies differ and should not be forced into exact equivalence. |
| Brute Force | CIC-IDS2018 | BruteForce | APPROXIMATE | Attack family with overlap, but not a direct NF dataset label. |

## 10. Common Feature Recommendation

- Recommended common feature count: 12
- Common family: protocol, directionally aggregated byte/packet counts, durations, TTL, throughput, and flags.
- Exclude identifiers and leakage-prone fields such as source/destination IPs, ports, DNS IDs and query metadata.
- Keep dataset identity explicit; do not merge raw records without a clear canonical schema and a label mapping table.

## 11. Leakage Risks

- Source and destination IPs are direct identifiers and can leak host-specific behavior.
- L4 source and destination ports can encode service identity and may not generalize across networks.
- DNS_QUERY_ID and related metadata are session-specific identifiers, not general network behavior features.
- Attack labels and hostname-like metadata can cause target leakage if mixed into training windows without care.

## 12. Recommended Evaluation Strategy

A. CIC-IDS2017 -> CIC-IDS2017: chronological 80/20 split within the dataset; fit scaler only on train; encode labels using train-only fit; generate temporal windows only within train and test partitions; never mix time windows across the split boundary.

B. CIC-IDS2018 -> CIC-IDS2018: same approach, applied either to the combined 2018 timeline or per file with dataset metadata retained.

C. NF-UNSW-NB15-v3 -> NF-UNSW-NB15-v3: use chronological splitting on flow start times, fit preprocessing only on train, create windows from prior observations, predict the next network state/attack label horizon, and do not allow train/test leakage through future features.

D/E. Cross-dataset transfer studies are valid only as explicit transfer-learning or domain-adaptation experiments with a shared canonical feature set and documented domain shift; they are not equivalent to same-dataset benchmarking.

## 13. Limitations

- NF-UNSW is a flow-derived NetFlow-like dataset with timestamps, but no explicit per-host or session identity is guaranteed across the entire record set.
- The current label taxonomy differs from CIC and cannot be blindly merged without loss of information.
- The dataset is best used as a temporal network-flow benchmark under a strict sliding-window study design, not as a direct replacement for the exact CIC schema.

## 14. Final Suitability Assessment

NF-UNSW-NB15-v3 is conditionally suitable for CrossThreat. It is usable for temporal forecasting and same-dataset benchmark experiments when treated as a separate dataset with explicit chronology, a canonical feature subset, and a carefully mapped label taxonomy. It is not directly compatible with CIC-IDS2017/2018 as a single merged schema without feature and label alignment and domain-shift controls.