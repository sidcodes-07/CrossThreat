# Mission I: Dataset Landscape Justification

## Why CSE-CIC-IDS2018 for CrossThreat's Forecasting Engine?

This document justifies the choice of **CSE-CIC-IDS2018** over five alternative network-security datasets commonly used in intrusion detection research. The critical differentiator: **CSE-CIC-IDS2018 is the only large-scale dataset with genuine multi-stage, time-sequenced attack scheduling**, enabling realistic temporal forecasting.

---

## Dataset Comparison Table

| Criterion | CSE-CIC-IDS2018 | CIC-IDS2017 | CIC-DDoS2019 | UNSW-NB15 | NSL-KDD | ToN_IoT |
|-----------|---|---|---|---|---|---|
| **Year Released** | 2018 | 2017 | 2019 | 2015 | 1999 (KDD99 base) | 2021 |
| **Total Flows** | ~1.7M | ~2.3M | ~71M | 2.5M | 494K | 607K |
| **Duration (days)** | 10 days | 5 days | 1 day | 15 days | Static snapshot | 1 day |
| **Attack Types** | 11 | 8 | 3 (DDoS only) | 4 | 5 | 8 |
| **Temporal Sequencing** | **✓ Scheduled multi-day** | Limited (5 days) | ✗ Single day | ✓ 15 days | ✗ Static/batched | ✓ 1 day |
| **Multi-Stage Attacks** | **✓ Yes** | Limited | ✗ No | ✗ Single-flow | ✗ Single-flow | Limited |
| **Feature Quality** | 80 CICFlowMeter | 78 CICFlowMeter | 85 fields | 42 derived | 41 derived | 43 fields |
| **Recency** | 2018 (6 years) | 2017 (7 years) | 2019 (5 years) | 2015 (9 years) | 1999 (27 years) | 2021 (3 years) |
| **Benign Mix** | ✓ Realistic | ✓ Realistic | Limited | ✓ Realistic | ✗ Low | ✓ Realistic |
| **Labeling Granularity** | Per-flow + attack scenario | Per-flow | Per-flow | Per-flow | Per-flow | Per-flow |
| **Forecasting Suitability** | **EXCELLENT** | Moderate | Poor | Poor | Very Poor | Moderate |

---

## Detailed Analysis

### 1. **CSE-CIC-IDS2018** ✓ CHOSEN
**Strengths:**
- **10-day campaign**: Attacks scheduled across multiple days (days 1-7 train, 8-10 test)
- **Authentic temporal structure**: Each day has specific attack scenario (Brute Force on day 3, DoS on day 4, DDoS on day 5, Infiltration+Bot on day 7)
- **Multi-stage attacks**: Infiltration and Bot scenarios span 15-60 minutes, allowing observation of attack progression
- **80 features**: CICFlowMeter provides rich, domain-meaningful flow statistics
- **Large scale**: 1.7M flows, 450 internal hosts, realistic benign traffic mix
- **Published documentation**: Official attack schedule available; each attack window is time-aligned

**Weaknesses:**
- Relative age (2018); some modern attack patterns (Cloud, Kubernetes-native) not represented
- Synthetic attacks (not real-world captures); protocol mix may differ from production

**Why it's best for forecasting:**
- **Day-by-day scheduling provides sequential context** — model learns that certain attacks follow others (e.g., reconnaissance → exploitation)
- **Temporal dependencies are real** — not artifact of labeling; attacks actually happen at scheduled times
- **Multi-stage visibility** — can observe transition from initial access to lateral movement within a single 15-min window

---

### 2. **CIC-IDS2017**
**Strengths:**
- 2.3M flows; similar CICFlowMeter features to IDS2018
- 5-day schedule (Monday-Friday)
- 8 attack types

**Critical Weakness for Forecasting:**
- **Only 5 days**: Too short for meaningful temporal pattern learning; limited train/test time-separation without data leakage
- **Uneven attack distribution**: Some days have 2-3 attacks, others are benign-heavy; inconsistent scheduling
- **No multi-stage attack specification**: Attacks are labeled per-flow, not by attack campaign; no "Infiltration scenario 1" with start/end times

**Verdict:** Can be used for **generalization testing** (train on IDS2018, test on IDS2017) but not ideal for primary model training.

---

### 3. **CIC-DDoS2019**
**Strengths:**
- Very large (71M flows); focuses on modern DDoS attack types
- 85 network fields; comprehensive feature set

**Critical Weaknesses for Forecasting:**
- **Single day**: No temporal sequencing; all attacks happen in one 24-hour window
- **DDoS-only**: Only 3 attack types; missing diversified threat landscape (Infiltration, Brute Force, SQL Injection, etc.)
- **No multi-stage capability**: Each DDoS attack is atomic; no progression or scenario-based structure
- **Poor generalization**: Model trained on DDoS-only cannot detect Infiltration or Bot traffic

**Verdict:** Suitable for **DDoS-specific detector**, not for general cyber-threat forecasting.

---

### 4. **UNSW-NB15**
**Strengths:**
- 2.5M flows; 15-day span; 42 derived features
- 4 attack categories (Reconnaissance, Exploitation, Backdoor, DoS)

**Weaknesses for Forecasting:**
- **No temporal attack sequencing**: Each flow is independently labeled; no knowledge of "this reconnaissance precedes this exploitation"
- **Derived features (not raw flows)**: Features are aggregated post-hoc, losing temporal fine-grain
- **Limited temporal granularity**: 15-day span but no documented attack schedule; arbitrary attack placement
- **No scenario-level labeling**: Cannot trace multi-step attack campaigns

**Verdict:** Good for **single-flow classification**, poor for **next-stage prediction**.

---

### 5. **NSL-KDD**
**Strengths:**
- Cleaned version of KDD99; removes duplicate records
- 494K flows; 5 attack types

**Critical Weaknesses (Dataset is Outdated & Static):**
- **1999 vintage**: 27 years old; attack patterns are obsolete (no modern web exploits, no cloud-native threats, no encrypted traffic)
- **Static snapshot**: One-time collection; no temporal dimension; all data from ~1-week in 1999
- **Poor protocol mix**: Predominantly TCP/UDP; minimal HTTP/HTTPS/DNS; not representative of 2020s traffic
- **Synthetic "KDD99 cup" data**: Artificially generated, with known statistical biases and labeling errors
- **Only 41 features**: Sparse network-flow representation; missing modern flow statistics

**Verdict:** **Unsuitable** for modern threat forecasting. Primarily of historical/benchmark interest only.

---

### 6. **ToN_IoT**
**Strengths:**
- Recent (2021); IoT-focused; 607K flows
- 8 attack types including botnet, ransomware, backdoor

**Weaknesses for Forecasting:**
- **IoT-specific**: Architecture is IoT sensors → gateway → cloud; not representative of enterprise networks
- **Single day**: Limited temporal structure; no multi-day campaign sequencing
- **Imbalanced classes**: Few examples of rare attacks; poor support for minority-class forecasting

**Verdict:** Good for **IoT-specific IDS**, not for general enterprise threat forecasting.

---

## Why CSE-CIC-IDS2018 Stands Alone

### The Forecasting Problem Requires Temporal Sequencing

**Standard Classification Task** (what most datasets provide):
```
Input: Single flow or aggregate window
Output: Is this flow malicious? → [Benign, Attack Type]
Problem: No temporal context; cannot predict *next* attack
```

**Forecasting Task** (what CrossThreat needs):
```
Input: Sequence of observed host states (windows 1-5)
Output: What attack-type host state will occur at window 6?
Problem: Requires understanding of attack *progression* and *scheduling*
```

**Only CSE-CIC-IDS2018 provides this:**
- Day 1-2: Baseline benign traffic
- Day 3-4: Brute Force attacks begin
- Day 5-6: DoS/DDoS campaigns
- Day 7: Infiltration + Bot command-and-control
- Days 8-10: Mixed attacks (SQL Injection, Heartbleed, etc.)

This **realistic attack scheduling** allows the model to learn:
1. "After 48 hours of benign traffic, brute-force attempts typically start"
2. "Brute-force success is often followed by lateral movement (Bot)"
3. "DoS attacks are typically volumetric, sustained for 30-60 minutes"

**Other datasets lack this structure** — attacks are either:
- Randomly interspersed (no pattern to learn)
- Single-day aggregates (too short for sequence learning)
- Static snapshots (no temporal dynamics)

---

## Recommendation for Future Work

| Task | Recommended Dataset |
|------|---|
| **Multi-stage attack forecasting** | **CSE-CIC-IDS2018** ← Primary choice |
| **Generalization testing** | CSE-CIC-IDS2017 (different attack mix, same era) |
| **DDoS-specific detection** | CIC-DDoS2019 (high-volume DDoS focus) |
| **IoT-specific detection** | ToN_IoT (IoT architecture) |
| **Benchmark/academic paper** | NSL-KDD (established baseline, but outdated) |
| ~~Modern threat landscape~~ | ~~UNSW-NB15~~ (static, no temporal structure) |

---

## One-Paragraph Justification (Executive Summary)

CSE-CIC-IDS2018 is the **definitive choice** for CrossThreat's temporal forecasting engine because it is the only large-scale publicly available dataset that combines (1) **genuine multi-day attack sequencing** with documented attack timing (enabling the model to learn realistic threat progression), (2) **multi-stage attack campaigns** (Infiltration and Bot scenarios spanning 15-60 minutes, showing attack evolution), and (3) **sufficient scale and feature richness** (1.7M flows, 80 CICFlowMeter features, 450 hosts) to train deep temporal models. Alternative datasets (CIC-IDS2017, UNSW-NB15, NSL-KDD, ToN_IoT, CIC-DDoS2019) are either too short (single/few days), lack temporal sequencing (static snapshots or random attack placement), focus on single attack types (DDoS-only), or are obsolete (NSL-KDD from 1999). The day-by-day attack schedule is the **irreplaceable enabler** of temporal forecasting; without it, a model cannot distinguish between coincidental traffic patterns and true attack progression signals.

---

## References

1. **CSE-CIC-IDS2018** (Canadian Institute for Cybersecurity)
   - Sharafaldin, I., Lashkari, A. H., & Ghorbani, A. A. (2018). *Toward generating a new intrusion detection dataset and intrusion traffic characterization.* 
   - URL: https://www.unb.ca/cic/datasets/ids-2018.html
   - Features: 80 CICFlowMeter attributes; 10-day campaign; 11 attack types

2. **CIC-IDS2017**
   - Sharafaldin, I., Lashkari, A. H., & Ghorbani, A. A. (2017). *Developing realistic datasets for intrusion detection systems.* 
   - URL: https://www.unb.ca/cic/datasets/ids-2017.html

3. **UNSW-NB15** (UNSW Sydney)
   - Moustafa, N., & Slay, J. (2015). *UNSW-NB15: A comprehensive data set for network intrusion detection systems.* 
   - URL: https://www.unsw.adfa.edu.au/unsw-canberra-cyber/cybersecurity/UNSW-NB15-Datasets/

4. **NSL-KDD** (NSERC, Canada)
   - Tavallaee, M., Bagheri, E., Lu, W., & Ghorbani, A. A. (2009). *A detailed analysis of the KDD cup 99 data set.* 
   - URL: https://www.unb.ca/cic/datasets/nsl-kdd.html

5. **ToN_IoT** (University of New South Wales)
   - Sarhan, M., Layeghy, S., & Portmann, M. (2021). *ToN_IoT—The Cyber Threat Landscape of the Internet of Things.* 
   - URL: https://www.unsw.adfa.edu.au/unsw-canberra-cyber/ton-iot-datasets/

6. **CIC-DDoS2019**
   - Sharafaldin, I., Lashkari, A. H., Hakak, S., & Ghorbani, A. A. (2019). *Developing Realistic Distributed Denial of Service (DDoS) Dataset and Taxonomy.* 
   - URL: https://www.unb.ca/cic/datasets/ddos-2019.html

---

**Conclusion:** CSE-CIC-IDS2018's **day-by-day attack scheduling is not just an advantage—it is the fundamental architectural requirement** for any temporal cyber-threat forecasting system. Its absence in all alternative datasets makes CSE-CIC-IDS2018 the only defensible choice for CrossThreat's mission.
