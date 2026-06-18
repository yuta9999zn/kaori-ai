# Kaori AI — Reasoning & Insight Layer v4.0
Adaptive · Criteria-Driven · Continuously Evolving Reasoning Infrastructure
Phiên bản: v4.0 (paradigm shift — Industry-Agnostic Profiling + Dynamic Criteria Registry + RAG-Driven Knowledge + Adaptive Formula Engine + Continuous Evolution Loop) Phát hành: Tháng 5 / 2026 Audience: ML Engineer · Backend Engineer · Product Lead · Architect · Data Analyst · Domain Expert Quan hệ với Pipeline Unified v1.1: Pipeline Unified xử lý data sạch + cognitive primitives. Doc này define HOW AI reasons adaptively — định hình doanh nghiệp, đánh giá theo tiêu chí mới nhất, formula thay đổi theo tiêu chí, doanh nghiệp luôn được tracked liên tục.

## Triết lý cốt lõi v4.0 — 7 nguyên tắc paradigm-shift
1. INDUSTRY-AGNOSTIC PROFILING
   Industry là OUTPUT của data signature analysis, không phải INPUT user khai
   System có thể profile bất kỳ doanh nghiệp nào, không cần biết "ngành gì" trước

2. DYNAMIC CRITERIA REGISTRY
   Tiêu chí đánh giá KHÔNG hard-code trong source code
   Mỗi criterion là object có lifecycle: proposed → active → superseded → retired
   Hot-reloadable, versioned, audit-trailed

3. RAG-DRIVEN KNOWLEDGE
   Tài liệu chuyên ngành mới nhất được ingested liên tục
   Material change → auto-update criteria + notify affected tenants
   Source authority hierarchy: Regulatory > Curated > Market > Internal > Tenant

4. ADAPTIVE FORMULA ENGINE
   Formulas KHÔNG hard-coded "retail churn = X"
   Là parameterized templates couple với criteria
   Khi criteria changes → formula re-derives, backtests, validates

5. PROFILE-AWARE REASONING
   Same data, different reasoning depth based on business profile
   Reasoning strategy adapt theo: lifecycle stage × maturity tier × archetype × health state

6. CONTINUOUS EVOLUTION LOOP
   Business state recomputed daily
   Criteria reviewed continuously (regulatory crawler daily, curated weekly)
   Formula validated quarterly
   Re-profile triggered automatically when major drift detected

7. CUSTOM-EXTENSIBLE BY TENANT
   Tenant có thể add criteria đặc thù (industry-specific or company-specific)
   Tenant criteria flow qua same lifecycle (proposed → review → active)
   Mixed với system criteria via priority resolution

## Mục lục
### PART I — TRIẾT LÝ
Phần 0. Paradigm Shift v4.0 · Stack Position · Quan hệ docs
### PART II — BUSINESS PROFILING ENGINE
Phần 1. Profile Anatomy (8-dimension business profile)
Phần 2. Profile Detection Pipeline (data signature → profile)
Phần 3. State Identification & Trajectory
Phần 4. Re-Profile Triggers (when business has materially changed)
### PART III — DYNAMIC CRITERIA REGISTRY
Phần 5. Criterion Anatomy (10 fields per criterion)
Phần 6. Criteria Lifecycle (proposed → active → superseded → retired)
Phần 7. Source Authority Hierarchy
Phần 8. Tenant-Custom & Tenant-Specific Criteria
Phần 9. Conflict Resolution (multiple criteria contradict)
### PART IV — RAG KNOWLEDGE ENGINE
Phần 10. 4-Tier Source Architecture
Phần 11. Continuous Ingestion Pipeline
Phần 12. Change Detection & Auto-Update
Phần 13. Material Change Notification
Phần 14. Anti-Hallucination & Provenance
### PART V — ADAPTIVE FORMULA ENGINE
Phần 15. Formula as Parameterized Template
Phần 16. Formula-Criteria Coupling
Phần 17. Adaptation Pipeline (criteria change → formula update)
Phần 18. Backtesting & Validation Before Switch
Phần 19. Formula Versioning & Rollback
Phần 20. Profile-Aware Formula Selection
### PART VI — INSIGHT GENERATION
Phần 21. Insight Engine Mechanics & 12-Step Pipeline
Phần 22. Threshold Discovery (statistical + historical + business)
Phần 23. Risk Detection (4 methods)
Phần 24. Alert System (severity, fatigue prevention)
Phần 25. Analysis Frameworks (6W2H · SWOT · Fishbone · Priority · 5Why)
### PART VII — REPORTS
Phần 26. Auto-Generated Reports (profile-aware, not industry-fixed)
Phần 27. Custom Report Builder
Phần 28. Distribution & Delivery
### PART VIII — TRUST & EXPLAINABILITY
Phần 29. Confidence Decomposition (4 components)
Phần 30. Explainability Hierarchy (3 levels)
Phần 31. Uncertainty Propagation
Phần 32. Constraint Engine — Safety Guardrails
### PART IX — ACTION GENERATION
Phần 33. Recommendation Engine
Phần 34. Improvement Roadmap (3 horizons)
### PART X — CONTINUOUS EVOLUTION
Phần 35. Continuous Re-Evaluation Loop
Phần 36. Tenant Maturity Tracking
Phần 37. System Self-Improvement
### PART XI — RISK MANAGEMENT
Phần 38. AI Insight Risk Inventory (24 risks)
Phần 39. Adaptive-System-Specific Risks (criteria injection, formula drift, etc.)
### PART XII — IMPLEMENTATION
Phần 40. Phase Scope (1/2/3)
Phần 41. Tech Stack & Architecture
Phần 42. Anti-patterns & Critical Success Factors
Phần 43. Quality KPIs

# PART I — TRIẾT LÝ
# Phần 0. Paradigm Shift v4.0
## 0.1 Stack Position
L5 Application:     User-facing reports/insights/alerts/recommendations
       ↑
       │   ← THIS DOC: Adaptive Reasoning Layer
       │
L4 Cognitive:       Action Runtime · Memory · Ontology · State Machines
                    [Pipeline Unified §5-7, §11]
       ↑
L3 AI/ML:           Models · LLM Gateway · Feature Store · Embeddings · RAG
                    [Pipeline Unified §9 + Phần 10-14 doc này]
       ↑
L2 Data Plane:      Bronze/Silver/Gold (clean data)
                    [Pipeline Unified §1-4, §8]
## 0.2 Why Paradigm Shift v4.0
Vấn đề của approaches cũ (v1.0 → v3.1): - Industry-first: Phải pre-define ngành nào, hard-code formulas → rigid - Static thresholds: Không adapt với regulatory changes - Same reasoning for all tenants in same industry → ignores within-industry diversity - Manual updates: Khi standards change, engineer phải redeploy - Không support custom criteria from tenant cleanly
Approach mới v4.0: - Industry-agnostic: System tự profile, không cần industry label - Dynamic criteria: Hot-reloadable, versioned, RAG-updated - Profile-aware reasoning: Each business gets reasoning tuned to its profile - Auto-updates: Material regulatory changes propagate automatically - Tenant-extensible: Custom criteria flow through same lifecycle
## 0.3 Architecture Overview
                    Clean data + Cognitive primitives
                    (Pipeline Unified §1-8)
                              │
                              ↓
               ┌──────────────────────────────────┐
               │  BUSINESS PROFILING ENGINE       │
               │  (Phần 1-4)                      │
               │  Output: 8-dim Business Profile  │
               └──────────────┬───────────────────┘
                              │
                              ↓
               ┌──────────────────────────────────┐
               │  CRITERIA REGISTRY               │  ← RAG Engine (Phần 10-14)
               │  (Phần 5-9)                      │  ← Tenant-Custom (Phần 8)
               │  Output: Active criteria list    │  ← Updated continuously
               │  for this profile                │
               └──────────────┬───────────────────┘
                              │
                              ↓
               ┌──────────────────────────────────┐
               │  ADAPTIVE FORMULA ENGINE         │
               │  (Phần 15-20)                    │
               │  Output: Active formulas tuned   │
               │  to current criteria + profile   │
               └──────────────┬───────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
   ┌──────────┐         ┌──────────┐         ┌──────────┐
   │ INSIGHTS │         │ REPORTS  │         │  STATE   │
   │ Phần     │         │ Phần     │         │ ASSESSMENT│
   │ 21-25    │         │ 26-28    │         │ Phần 3   │
   └────┬─────┘         └────┬─────┘         └────┬─────┘
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ↓
              ┌──────────────────────────────┐
              │  TRUST LAYER                 │
              │  (Phần 29-32)                │
              │  Confidence/Explain/Constraint│
              └──────────────┬───────────────┘
                             ↓
              ┌──────────────────────────────┐
              │  RECOMMENDATION ENGINE        │
              │  (Phần 33-34)                │
              └──────────────┬───────────────┘
                             ↓
              Action Runtime (Pipeline Unified §11)
                             ↓
                    Outcome → Memory feedback
                             ↓
              CONTINUOUS EVOLUTION LOOP (Phần 35-37)
                             │
                             └──────────→ Re-trigger profiling/criteria/formulas
## 0.4 Quan hệ docs

| Doc | Vai trò | Updated |
|---|---|---|
| Playbook v3 | 90-day operational deployment | Stable |
| SAD Skeleton | System architecture | Stable |
| Pipeline Unified v1.1 | Data flows + cognitive primitives | Stable |
| Reasoning Layer v4.0 (this) | Adaptive reasoning · profiling · criteria · formulas | NEW v4.0 |

Important: Pipeline Unified KHÔNG đổi. v4.0 chỉ refactor cách reasoning layer hoạt động trên top of clean data + primitives.

# PART II — BUSINESS PROFILING ENGINE
# Phần 1. Profile Anatomy — 8-Dimensional Business Profile
Vấn đề address: Khi đưa cho 1 doanh nghiệp, làm sao “định hình nó như nào”? Không thể chỉ “ngành = retail” — quá generic.
## 1.1 Multi-Dimensional Profile
Mỗi doanh nghiệp được mô tả bởi 8 dimensions độc lập:
┌────────────────────────────────────────────────────────┐
│  BUSINESS PROFILE = 8 dimensions                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  D1. INDUSTRY (auto-detected, multi-label)             │
│      e.g., {primary: 'retail', secondary: ['fb']}      │
│                                                        │
│  D2. SUB-DOMAIN                                        │
│      e.g., 'fashion_apparel' within retail             │
│                                                        │
│  D3. BUSINESS MODEL                                    │
│      [B2B/B2C/B2B2C, Transaction/Subscription/Hybrid,  │
│       Asset-light/Asset-heavy]                         │
│                                                        │
│  D4. SIZE                                              │
│      [Micro/Small/Medium/Large] by employees + revenue │
│                                                        │
│  D5. LIFECYCLE STAGE                                   │
│      [Startup/Growing/Established/Mature/              │
│       Transforming/Declining]                          │
│                                                        │
│  D6. ARCHETYPE (data maturity)                         │
│      [A1: Data-Chaotic SME / A2: Ops-Driven Mid /      │
│       A3: Data-Curious Growing / A4: Data-Mature Ent / │
│       A5: Compliance-Heavy Regulated]                  │
│                                                        │
│  D7. HEALTH STATE                                      │
│      [Thriving/Healthy/Stable/Struggling/Critical]     │
│      (5-dimensional composite — Phần 3)                │
│                                                        │
│  D8. REGULATORY ENVIRONMENT                            │
│      [Light/Moderate/Heavy/Critical]                   │
│      jurisdiction tags: [VN, ASEAN, US, EU]            │
└────────────────────────────────────────────────────────┘
Critical: No single dimension defines the business. Reasoning strategy uses ALL 8 dimensions to select criteria + formulas.
## 1.2 Profile Schema
business_profile:
  tenant_id: UUID
  computed_at: TIMESTAMP
  version: INTEGER  # increments when profile re-computed
  
  d1_industry:
    primary: string         # auto-detected
    secondary: list[string] # multi-domain tenants
    confidence: float       # detection confidence
    detection_method: string  # 'self_declared' | 'data_signature' | 'hybrid'
  
  d2_sub_domain:
    value: string           # e.g., 'fashion_apparel', 'cloud_kitchen'
    confidence: float
    candidates: list[string]  # alternative sub-domains considered
  
  d3_business_model:
    customer_type: ['B2C', 'B2B', 'B2B2C']  # multi-select
    revenue_model: 'transaction' | 'subscription' | 'hybrid'
    asset_intensity: 'asset_light' | 'asset_medium' | 'asset_heavy'
    geographic_scope: 'local' | 'regional' | 'national' | 'international'
  
  d4_size:
    employees: integer
    annual_revenue_vnd: numeric
    size_label: 'micro' | 'small' | 'medium' | 'large'
  
  d5_lifecycle_stage:
    value: string
    confidence: float
    age_years: float
    growth_rate: float
  
  d6_archetype:
    value: string  # A1-A5
    confidence: float
    detected_signals: list[string]  # which signals supported this
  
  d7_health_state:
    composite_score: float  # 0-100
    state_label: string
    dimensions: object  # Financial/Customer/Operational/Workforce/Strategic
    trend_30d: 'improving' | 'stable' | 'declining'
    weakest_dimension: string
  
  d8_regulatory:
    intensity: 'light' | 'moderate' | 'heavy' | 'critical'
    jurisdictions: list[string]
    applicable_frameworks: list[string]  # ['Basel III', 'IFRS 9', 'GDPR']
## 1.3 Why 8 dimensions, not just industry
SCENARIO 1: Two tenants both 'retail'
  Tenant A: Mature B2C fashion chain, 1000 employees, declining health
  Tenant B: Growing B2B2C beauty marketplace startup, 50 employees, thriving
  
  → Same industry, COMPLETELY different reasoning needs:
  - A needs cost optimization, retention, lifecycle analytics
  - B needs growth analytics, network effects, marketplace economics

SCENARIO 2: Tenant đa-ngành
  Restaurant chain với cloud kitchen + delivery fleet:
  → Industry primary: F&B
  → Industry secondary: [Logistics, Retail]
  → Sub-domain: 'cloud_kitchen'
  → Reasoning needs span 3 industries simultaneously

SCENARIO 3: Same business, different lifecycle
  Same company year 1 (Startup) vs year 10 (Mature):
  → Same industry, but reasoning priorities completely different
  → Startup: PMF metrics, runway, growth experiments
  → Mature: efficiency, defense against disruption, optimization
## 1.4 Dimension Independence
Each dimension đo độc lập — system không assume correlation:
# Wrong: assume "retail = always B2C"
if profile.industry == 'retail':
    reasoning_strategy = 'b2c_retail_default'  # ❌ ignores B2B retail

# Right: each dimension drives reasoning
reasoning_strategy = compose_strategy(
    industry=profile.d1_industry,
    business_model=profile.d3_business_model,  # may be B2B even in retail
    lifecycle=profile.d5_lifecycle_stage,
    archetype=profile.d6_archetype,
    health=profile.d7_health_state,
    regulatory=profile.d8_regulatory
)
## 1.5 Profile Storage
CREATE TABLE business_profiles (
  profile_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  version INTEGER NOT NULL,
  
  d1_industry JSONB,
  d2_sub_domain JSONB,
  d3_business_model JSONB,
  d4_size JSONB,
  d5_lifecycle_stage JSONB,
  d6_archetype JSONB,
  d7_health_state JSONB,
  d8_regulatory JSONB,
  
  detection_metadata JSONB,  -- which signals contributed
  computed_at TIMESTAMP,
  next_review_at TIMESTAMP,
  
  superseded_by UUID,  -- next version pointer
  superseded_at TIMESTAMP,
  supersession_reason TEXT,
  
  UNIQUE (tenant_id, version)
);

CREATE INDEX idx_active_profile ON business_profiles (tenant_id) 
  WHERE superseded_at IS NULL;
## 1.6 Acceptance Criteria — Phần 1
☐ All 8 dimensions populated for every tenant
☐ Each dimension has independent confidence score
☐ Profile versioned (history preserved)
☐ Profile accessible <50ms for reasoning queries
☐ Multi-domain tenants handled correctly (D1 secondary)

# Phần 2. Profile Detection Pipeline
Mục đích: Khi 1 tenant mới onboard, làm sao system tự profile mà không cần tenant khai chi tiết?
## 2.1 Detection Approaches per Dimension
D1 INDUSTRY:
  Primary signal: Data schema fingerprint
  Secondary: Self-declared (during signup)
  Tertiary: Entity type distribution
  
D2 SUB-DOMAIN:
  Primary: Product/service catalog analysis
  Secondary: Transaction patterns
  Tertiary: Tenant declaration
  
D3 BUSINESS MODEL:
  Primary: Transaction frequency + customer entity types
  Secondary: Payment patterns (subscription vs one-time)
  Tertiary: Self-declaration

D4 SIZE:
  Primary: Employee count + revenue from data
  Secondary: Self-declaration
  
D5 LIFECYCLE STAGE:
  Primary: Founding date + revenue trend (3 years)
  Secondary: Market share trend
  Tertiary: Self-declaration
  
D6 ARCHETYPE:
  Primary: Data quality score, source count, has data team
  Secondary: Reports usage patterns
  
D7 HEALTH STATE:
  Primary: 5-dimensional health computation (Phần 3)
  
D8 REGULATORY:
  Primary: Industry → applicable frameworks lookup
  Secondary: Jurisdiction (geo of operations)
  Tertiary: Tenant declaration of compliance regime
## 2.2 Industry Detection (D1) — Data Signature
class IndustryDetector:
    """
    Industry-agnostic: doesn't pre-suppose specific industries.
    Uses data signature to identify.
    """
    
    def detect(self, tenant):
        signals = {}
        
        # Signal 1: Schema fingerprint
        schema_sig = compute_schema_signature(tenant.tables)
        signals['schema'] = match_against_known_signatures(schema_sig)
        
        # Signal 2: Entity type distribution
        entity_dist = get_entity_type_distribution(tenant)
        signals['entities'] = match_industry_by_entities(entity_dist)
        
        # Signal 3: Transaction characteristics
        tx_chars = analyze_transaction_characteristics(tenant)
        # e.g., avg ticket size, frequency, refund rate
        signals['transactions'] = match_industry_by_tx_pattern(tx_chars)
        
        # Signal 4: Self-declared (if available)
        if tenant.declared_industry:
            signals['declared'] = tenant.declared_industry
        
        # Signal 5: External enrichment (company name lookup)
        if tenant.company_name:
            signals['external'] = lookup_company_industry(tenant.company_name)
        
        # Combine signals with weights
        weighted_industry = combine_signals(signals, weights={
            'schema': 0.30,
            'entities': 0.25,
            'transactions': 0.20,
            'declared': 0.15,
            'external': 0.10
        })
        
        return {
            'primary': weighted_industry.top1,
            'secondary': weighted_industry.also_present,  # if multi-domain
            'confidence': weighted_industry.confidence,
            'detection_method': 'multi_signal',
            'signals_used': list(signals.keys())
        }
### Schema fingerprint approach
# For each known industry, define expected entities + relationships
INDUSTRY_FINGERPRINTS = {
    'retail': {
        'must_have_entities': ['customer', 'product', 'transaction'],
        'common_entities': ['inventory', 'store', 'discount'],
        'rare_entities': ['supplier', 'warehouse']
    },
    'banking': {
        'must_have_entities': ['account', 'transaction', 'customer'],
        'common_entities': ['loan', 'deposit', 'branch'],
        'rare_entities': ['inventory', 'product_sku']
    },
    'healthcare': {
        'must_have_entities': ['patient', 'medical_record'],
        'common_entities': ['prescription', 'appointment', 'doctor'],
        'rare_entities': ['transaction']  # less prominent
    },
    # ... extensible — add more as patterns emerge
}

def match_against_known_signatures(tenant_schema):
    matches = []
    for industry, fingerprint in INDUSTRY_FINGERPRINTS.items():
        score = 0
        for entity in fingerprint['must_have_entities']:
            if entity in tenant_schema.entities:
                score += 0.4
        for entity in fingerprint['common_entities']:
            if entity in tenant_schema.entities:
                score += 0.2
        for entity in fingerprint['rare_entities']:
            if entity in tenant_schema.entities:
                score -= 0.1  # presence reduces this industry likelihood
        matches.append((industry, score))
    return sorted(matches, key=lambda x: -x[1])
Industry-agnostic property: When new industry encountered (no fingerprint match), system returns ‘unknown_industry’ with low confidence. Triggers tenant interview workflow rather than miscategorize.
## 2.3 Sub-Domain Detection (D2)
def detect_sub_domain(tenant, primary_industry):
    """
    Within retail, is it fashion? supermarket? pharmacy?
    """
    if primary_industry == 'retail':
        # Look at product catalog characteristics
        products = sample_product_catalog(tenant)
        
        # Method 1: Product name embedding clustering
        product_embeddings = embed_products(products)
        clusters = cluster(product_embeddings)
        # Compare cluster to known sub-domain prototypes
        
        # Method 2: Transaction patterns
        # Fashion: seasonal peaks, return rate ~15-25%
        # Supermarket: daily traffic, return rate <2%
        # Pharmacy: regulated, prescription tracking required
        
        # Method 3: Entity types
        # Pharmacy has 'prescription', 'doctor_id'
        # Fashion has 'size_chart', 'season'
        
        return ranked_sub_domains
    
    # Similar logic for other industries
## 2.4 Detection Confidence & Fallback
def detect_with_fallback(tenant):
    profile = run_all_detectors(tenant)
    
    # If any dimension has confidence < 0.6, fallback to interview
    low_confidence_dims = [
        d for d in profile.dimensions if d.confidence < 0.6
    ]
    
    if low_confidence_dims:
        flag_for_interview(tenant, low_confidence_dims)
        # Customer Success agent contacts to confirm
        # Manual override updates profile + confidence
    
    return profile
## 2.5 Profile Detection Output Example
{
  "tenant_id": "tenant_abc",
  "version": 1,
  "computed_at": "2026-04-15T03:15:00Z",
  
  "d1_industry": {
    "primary": "retail",
    "secondary": ["fb"],  // tenant has cafe inside store
    "confidence": 0.91,
    "detection_method": "data_signature_strong_match"
  },
  
  "d2_sub_domain": {
    "value": "fashion_apparel",
    "confidence": 0.87,
    "candidates": ["fashion_apparel", "general_retail"]
  },
  
  "d3_business_model": {
    "customer_type": ["B2C"],
    "revenue_model": "transaction",
    "asset_intensity": "asset_medium",
    "geographic_scope": "national"
  },
  
  "d4_size": {
    "employees": 320,
    "annual_revenue_vnd": 85000000000,
    "size_label": "medium"
  },
  
  "d5_lifecycle_stage": {
    "value": "growing",
    "confidence": 0.83,
    "age_years": 4.2,
    "growth_rate": 0.32
  },
  
  "d6_archetype": {
    "value": "A2_OPS_DRIVEN_MID",
    "confidence": 0.79,
    "detected_signals": ["data_quality_65", "5_sources", "no_data_team"]
  },
  
  "d7_health_state": {
    "composite_score": 67,
    "state_label": "HEALTHY",
    "trend_30d": "stable"
  },
  
  "d8_regulatory": {
    "intensity": "moderate",
    "jurisdictions": ["VN"],
    "applicable_frameworks": ["VN_consumer_protection", "GDPR_partial"]
  }
}
## 2.6 Acceptance Criteria — Phần 2
☐ Detection runs on tenant onboarding day-1
☐ Each dimension has detection method documented
☐ Low-confidence dimensions trigger CS interview
☐ Schema fingerprint library extensible (add new industries without code change)
☐ Multi-domain tenants correctly detected
☐ Detection accuracy ≥85% validated against labeled tenant set

# Phần 3. State Identification & Trajectory
Mục đích: Trả lời “doanh nghiệp ở trạng thái gì”. Không chỉ snapshot mà cả trajectory (đang đi đâu).
## 3.1 State = Composite of Multi-Layer Signals
BUSINESS STATE = {
    HEALTH STATE          (5 dimensions, current snapshot)
    LIFECYCLE TRAJECTORY  (where in lifecycle, momentum)
    OPERATIONAL TEMPO     (steady / accelerating / decelerating)
    STRESS LEVEL          (calm / pressured / crisis)
    EXTERNAL POSITION     (market gaining / steady / losing)
}
## 3.2 Health State (5-Dimensional)
health_dimensions:
  
  financial_health (weight 25%):
    metrics:
      revenue_growth_yoy: target > 10%
      gross_margin: target > 35%
      net_margin: target > 8%
      cash_runway_months: target > 12
      ar_aging_30d_pct: target < 15%
      revenue_concentration_top10_pct: target < 40%
  
  customer_health (weight 25%):
    metrics:
      retention_rate_monthly: target > 90%
      churn_rate_monthly: target < 5%
      nps: target > 30
      clv_growth_yoy: target > 8%
      active_customer_growth: target > 5%
      customer_concentration: target < 30%
  
  operational_health (weight 20%):
    metrics:
      sla_compliance: target > 95%
      quality_metric: target varies by industry
      capacity_utilization: target 70-85%
      data_quality_score: target > 85
      process_cycle_time: target stable/improving
      incident_rate: target < 1/month
  
  workforce_health (weight 15%):
    metrics:
      employee_turnover_annual: target < 15%
      productivity_per_fte: target growing 5%+
      skill_coverage_critical_roles: target 100%
      training_hours_per_employee: target > 20
      employee_nps: target > 30
  
  strategic_health (weight 15%):
    metrics:
      market_share_change: target growing
      product_diversification: target balanced
      innovation_rate: new products/year
      competitive_position: vs competitors
      regulatory_compliance: target 100%
Note: Specific metric thresholds come from Criteria Registry (Phần 5-9), not hard-coded.
## 3.3 State Classification
def classify_state(composite_score):
    if composite_score >= 80: return 'THRIVING'
    elif composite_score >= 65: return 'HEALTHY'
    elif composite_score >= 50: return 'STABLE'
    elif composite_score >= 35: return 'STRUGGLING'
    else: return 'CRITICAL'
## 3.4 Trajectory Analysis
State is a snapshot. Trajectory tells us where it’s heading:
def compute_trajectory(tenant_id, window_days=90):
    history = get_health_history(tenant_id, window_days)
    
    # Slope (linear regression)
    slope, intercept, r_squared, p_value = linregress(history.dates, history.scores)
    
    # Acceleration (2nd derivative — slope of slope)
    recent_slope = compute_slope(history[-30:])
    older_slope = compute_slope(history[-90:-60])
    acceleration = recent_slope - older_slope
    
    # Volatility (std of changes)
    daily_changes = np.diff(history.scores)
    volatility = np.std(daily_changes)
    
    # Classify trajectory
    if abs(slope) < 0.1 and volatility < 1:
        trajectory = 'STABLE'
    elif slope > 0.5 and acceleration > 0:
        trajectory = 'IMPROVING_ACCELERATING'
    elif slope > 0.2:
        trajectory = 'IMPROVING'
    elif slope < -0.5 and acceleration < 0:
        trajectory = 'DECLINING_ACCELERATING'  # urgent
    elif slope < -0.2:
        trajectory = 'DECLINING'
    elif volatility > 3:
        trajectory = 'VOLATILE'
    else:
        trajectory = 'DRIFTING'
    
    return {
        'trajectory': trajectory,
        'slope': slope,
        'acceleration': acceleration,
        'volatility': volatility,
        'projected_30d': intercept + slope * 120,  # 30 days ahead
        'projected_state': classify_state(intercept + slope * 120)
    }
## 3.5 Operational Tempo
operational_tempo:
  metrics:
    transaction_velocity: txns/day rate of change
    decision_velocity: decisions made/day rate
    process_cycle_time_change: speeding up or slowing down
  
  classifications:
    accelerating: tempo +20%/quarter
    steady: ±5% range
    decelerating: tempo -20%/quarter
## 3.6 Stress Level
stress_level:
  signals:
    - cashflow_pressure (weight 0.30)
    - customer_concentration_risk (weight 0.20)
    - operational_incident_rate (weight 0.15)
    - employee_burnout_signals (weight 0.15)
    - regulatory_pressure (weight 0.10)
    - competitive_pressure (weight 0.10)
  
  classification:
    calm: composite < 30
    pressured: 30-60
    high_stress: 60-80
    crisis: > 80
## 3.7 External Position
external_position:
  metrics:
    market_share_trend: gaining / steady / losing
    industry_growth_relative: outpacing / matching / lagging
    customer_acquisition_cost_trend: improving / stable / worsening
    competitive_response_speed: leading / following / reacting
## 3.8 Composite State Output
{
  "tenant_id": "tenant_abc",
  "computed_at": "2026-04-15",
  
  "health": {
    "composite_score": 67,
    "label": "HEALTHY",
    "dimensions": {
      "financial": 72, "customer": 58,
      "operational": 71, "workforce": 65, "strategic": 61
    },
    "weakest": "customer", "strongest": "financial"
  },
  
  "trajectory": {
    "label": "STABLE",
    "slope": 0.05,
    "acceleration": -0.01,
    "volatility": 1.2,
    "projected_30d_score": 68,
    "projected_30d_label": "HEALTHY"
  },
  
  "operational_tempo": {
    "label": "STEADY",
    "transaction_velocity_change": 0.02
  },
  
  "stress_level": {
    "label": "PRESSURED",
    "composite": 45,
    "top_stressors": ["customer_concentration", "competitive_pressure"]
  },
  
  "external_position": {
    "market_share_trend": "steady",
    "industry_growth_relative": "matching"
  }
}
## 3.9 Why Multi-Layer State
Single “score” hides patterns:
Tenant A: Score 67 STABLE trajectory CALM → “doing fine, optimize”
Tenant B: Score 67 DECLINING_ACCELERATING HIGH_STRESS → “intervention NOW”
Same score, completely different reasoning needs.
## 3.10 Acceptance Criteria — Phần 3
☐ Health state computed daily
☐ Trajectory tracked over 90+ days
☐ Stress signals from 6+ sources
☐ State changes flagged immediately
☐ Projection accuracy validated retrospectively
☐ Multi-layer state visible in dashboards

# Phần 4. Re-Profile Triggers
Mục đích: Doanh nghiệp luôn thay đổi. Khi nào cần re-compute profile?
## 4.1 Trigger Types
re_profile_triggers:
  
  scheduled:
    cadence: quarterly  # default review
    full_recompute: true
    
  data_volume_threshold:
    rule: data ingested grew >50% since last profile
    action: incremental profile update
    
  data_diversity_change:
    rule: new entity types appearing in tenant data
    action: re-detect industry + sub-domain
    
  health_state_change:
    rule: state crossed major boundary (e.g., HEALTHY → STRUGGLING)
    action: re-detect lifecycle + archetype
    
  size_change:
    rule: employee count or revenue changed >25%
    action: update size dimension + dependent reasoning
    
  declared_change:
    rule: tenant manager updates profile manually
    action: incorporate + update affected dimensions
    
  regulatory_event:
    rule: jurisdiction's regulatory change affects this tenant
    action: update regulatory dimension + affected criteria
    
  external_market_event:
    rule: industry-wide event (e.g., COVID, regulation change)
    action: re-evaluate lifecycle stage + external position
## 4.2 Trigger Detection
class ReProfileTriggerMonitor:
    
    def check_all_triggers(self, tenant_id):
        triggers_fired = []
        current_profile = get_current_profile(tenant_id)
        
        # Scheduled
        if days_since(current_profile.computed_at) >= 90:
            triggers_fired.append('scheduled_quarterly')
        
        # Data volume
        new_data_volume = get_data_volume_since(current_profile.computed_at)
        baseline_volume = current_profile.detection_metadata.data_volume_at_detection
        if new_data_volume > 1.5 * baseline_volume:
            triggers_fired.append('data_volume_threshold')
        
        # Data diversity (new entity types)
        new_entities = detect_new_entity_types(tenant_id, since=current_profile.computed_at)
        if new_entities:
            triggers_fired.append(('data_diversity', new_entities))
        
        # Health state boundary crossing
        recent_state = get_current_health_state(tenant_id)
        previous_state = current_profile.d7_health_state
        if state_crossed_boundary(previous_state, recent_state):
            triggers_fired.append('health_state_boundary')
        
        # Size change
        recent_size = compute_current_size(tenant_id)
        baseline_size = current_profile.d4_size
        if size_changed_materially(baseline_size, recent_size):
            triggers_fired.append('size_change')
        
        # External market events
        market_events = check_market_event_feed(current_profile.industry)
        if market_events:
            triggers_fired.append(('external_event', market_events))
        
        return triggers_fired
    
    def execute_re_profile(self, tenant_id, triggers):
        if 'scheduled_quarterly' in triggers:
            # Full recompute
            new_profile = run_full_profile_detection(tenant_id)
        else:
            # Incremental — only update affected dimensions
            current = get_current_profile(tenant_id)
            new_profile = current.copy()
            for trigger in triggers:
                affected_dims = map_trigger_to_dimensions(trigger)
                for dim in affected_dims:
                    new_profile[dim] = re_detect_dimension(tenant_id, dim)
        
        # Compare old vs new
        diffs = compute_profile_diff(current, new_profile)
        
        if diffs.has_material_changes:
            # Increment version + supersede old
            save_new_profile_version(new_profile)
            
            # Trigger downstream re-evaluation
            trigger_criteria_review(tenant_id, diffs)
            trigger_formula_review(tenant_id, diffs)
            
            # Notify stakeholders
            notify_profile_change(tenant_id, diffs)
        
        return new_profile
## 4.3 Material Change Definition
Not every diff is “material”. Define what matters:
material_changes:
  
  always_material:
    - industry_primary changed
    - lifecycle_stage changed
    - regulatory_intensity changed
    - archetype changed
    - health_state crossed boundary
  
  material_if_threshold:
    - size: changed by >25%
    - sub_domain: confidence dropped >0.3
    - business_model.customer_type: added/removed B2B or B2C
    - business_model.revenue_model: changed
  
  not_material:
    - confidence scores changed slightly
    - specific metrics within same band
    - minor sub-dimension shifts
## 4.4 Re-Profile Cascade
When profile changes, downstream effects cascade:
Profile changed (Phần 4)
       ↓
Criteria Registry review (Phần 5-9)
  - Criteria valid for old profile may not for new
  - Activate new applicable criteria
  - Deactivate non-applicable
       ↓
Formula Engine review (Phần 15-20)
  - Formulas tied to old criteria may need swap
  - Backtest new formulas
  - Switch with sign-off
       ↓
Reasoning Strategy review
  - Archetype change → different depth, frequency
  - Lifecycle change → different KPI focus
       ↓
Recommendations re-generated (Phần 33)
       ↓
User notified of changes
## 4.5 Acceptance Criteria — Phần 4
☐ Trigger detection runs daily
☐ Quarterly scheduled re-profile mandatory
☐ Material change cascade fully automated
☐ Profile version history immutable
☐ Re-profile completes < 1 hour for typical tenant
☐ User notified before reasoning strategy changes (give option to delay)

# PART III — DYNAMIC CRITERIA REGISTRY
# Phần 5. Criterion Anatomy
Mục đích: Trả lời “lấy tiêu chí gì để đánh giá”. Mỗi tiêu chí KHÔNG hard-code — là first-class object với 10 fields định nghĩa rõ.
## 5.1 Criterion Schema
criterion:
  # Identity
  criterion_id: UUID  # immutable
  display_name: string  # human-readable
  display_name_vi: string
  
  # Categorization
  category: string  # 'financial' | 'customer' | 'operational' | 'workforce' | 'strategic' | 'regulatory'
  applies_to_dimensions:  # which profile dimensions this criterion applies to
    industries: list[string] | 'all'
    sub_domains: list[string] | 'all'
    business_models: list[string] | 'all'
    sizes: list[string] | 'all'
    lifecycle_stages: list[string] | 'all'
    archetypes: list[string] | 'all'
    regulatory_environments: list[string] | 'all'
  
  # Definition
  metric_name: string  # what's being measured
  measurement_unit: string  # %, VND, days, count, etc.
  computation_formula: string  # SQL or Python expression template
  
  # Thresholds (optional, can be statistically derived)
  thresholds:
    - level: 'excellent', value: '> 95%'
    - level: 'good', value: '85-95%'
    - level: 'acceptable', value: '70-85%'
    - level: 'concerning', value: '50-70%'
    - level: 'critical', value: '< 50%'
  
  # Source & authority
  source:
    tier: 1 | 2 | 3 | 4  # see Phần 7 hierarchy
    authority: 'regulatory' | 'curated' | 'market' | 'tenant'
    reference: URL or document_id
    issued_by: string  # 'SBV', 'Basel Committee', 'Kaori curated', etc.
    issued_date: date
    effective_date: date
    expires_date: date | null
  
  # Lifecycle
  status: 'proposed' | 'review' | 'active' | 'superseded' | 'retired'
  version: integer
  superseded_by: UUID | null  # next version pointer
  predecessor: UUID | null    # previous version
  
  # Metadata
  created_at: timestamp
  created_by: 'system' | 'tenant_X' | 'user_Y'
  approved_at: timestamp | null
  approved_by: string | null
  
  # Usage tracking
  used_by_formulas: list[formula_id]  # which formulas reference this
  active_for_tenants: list[tenant_id]  # who currently uses this
  
  # Audit
  change_log: list[
    {timestamp, change_type, changed_by, reason, before, after}
  ]
## 5.2 Example Criteria
### Example 1: Universal financial criterion
criterion:
  criterion_id: "crit_001"
  display_name: "Cash Runway (Months)"
  display_name_vi: "Số tháng cash flow còn lại"
  
  category: "financial"
  applies_to_dimensions:
    industries: "all"
    sub_domains: "all"
    business_models: "all"
    sizes: "all"
    lifecycle_stages: ["startup", "growing"]  # most relevant for early-stage
    archetypes: "all"
    regulatory_environments: "all"
  
  metric_name: "cash_runway_months"
  measurement_unit: "months"
  computation_formula: |
    SELECT current_cash_balance / nullif(monthly_burn_rate, 0)
    FROM gold.financial_state
    WHERE tenant_id = :tenant_id
  
  thresholds:
    - {level: "thriving", value: "> 18"}
    - {level: "healthy", value: "12-18"}
    - {level: "concerning", value: "6-12"}
    - {level: "critical", value: "< 6"}
  
  source:
    tier: 2
    authority: "curated"
    issued_by: "Kaori curated based on Y Combinator startup principles"
    issued_date: "2024-06-01"
    effective_date: "2024-06-01"
  
  status: "active"
  version: 1
### Example 2: Industry-specific regulatory criterion
criterion:
  criterion_id: "crit_002"
  display_name: "NPL Ratio (SBV Compliance)"
  display_name_vi: "Tỷ lệ nợ xấu (theo quy định SBV)"
  
  category: "regulatory"
  applies_to_dimensions:
    industries: ["banking"]
    sub_domains: ["retail_banking", "corporate_banking"]
    sizes: "all"
    regulatory_environments: ["heavy", "critical"]
  
  metric_name: "npl_ratio"
  measurement_unit: "%"
  computation_formula: |
    SELECT 
      sum(case when days_past_due >= 90 then outstanding_amount else 0 end) /
      sum(outstanding_amount) * 100 AS npl_ratio
    FROM silver.loan_portfolio
    WHERE tenant_id = :tenant_id
      AND report_date = :report_date
  
  thresholds:
    - {level: "excellent", value: "< 1%"}
    - {level: "good", value: "1-2%"}
    - {level: "acceptable", value: "2-3%"}
    - {level: "regulatory_warning", value: "3-5%"}
    - {level: "critical_intervention_zone", value: "> 5%"}
  
  source:
    tier: 1  # regulatory = highest authority
    authority: "regulatory"
    reference: "https://sbv.gov.vn/circular_41_2016"
    issued_by: "SBV (State Bank of Vietnam)"
    issued_date: "2016-12-30"
    effective_date: "2017-01-01"
  
  status: "active"
  version: 1
### Example 3: Tenant-custom criterion
criterion:
  criterion_id: "crit_tenant_xyz_001"
  display_name: "Same-Day Delivery Rate (Custom)"
  display_name_vi: "Tỷ lệ giao trong ngày"
  
  category: "operational"
  applies_to_dimensions:
    # Restricted to this tenant only
    tenant_specific: "tenant_xyz"
  
  metric_name: "same_day_delivery_rate"
  measurement_unit: "%"
  computation_formula: |
    SELECT count(case when delivered_at <= order_placed_at + interval '24 hours' then 1 end)::float
           / count(*) * 100
    FROM silver.orders
    WHERE tenant_id = 'tenant_xyz'
      AND order_date BETWEEN :start AND :end
  
  thresholds:
    # Tenant-defined targets
    - {level: "target", value: "> 90%"}
    - {level: "below_target", value: "70-90%"}
    - {level: "concerning", value: "< 70%"}
  
  source:
    tier: 4
    authority: "tenant"
    issued_by: "tenant_xyz manager"
    issued_date: "2026-03-15"
    effective_date: "2026-04-01"
  
  status: "active"
  version: 1
  
  approved_at: "2026-03-20"
  approved_by: "tenant_xyz_manager_linh"
## 5.3 Criterion Storage
CREATE TABLE criteria_registry (
  criterion_id UUID PRIMARY KEY,
  display_name VARCHAR(500),
  display_name_vi VARCHAR(500),
  
  category VARCHAR(50),
  applies_to_dimensions JSONB,  -- which profile dims
  
  metric_name VARCHAR(200),
  measurement_unit VARCHAR(50),
  computation_formula TEXT,
  
  thresholds JSONB,
  source JSONB,
  
  status VARCHAR(20),  -- proposed/review/active/superseded/retired
  version INTEGER,
  superseded_by UUID,
  predecessor UUID,
  
  created_at TIMESTAMP,
  created_by VARCHAR(200),
  approved_at TIMESTAMP,
  approved_by VARCHAR(200),
  effective_date DATE,
  expires_date DATE,
  
  used_by_formulas JSONB,
  active_for_tenants JSONB,
  
  change_log JSONB
);

CREATE INDEX idx_active_criteria ON criteria_registry (status, category) 
  WHERE status = 'active';
CREATE INDEX idx_criteria_tenant ON criteria_registry USING GIN (active_for_tenants);
CREATE INDEX idx_criteria_industry ON criteria_registry USING GIN ((applies_to_dimensions->'industries'));
## 5.4 Criterion Selection per Tenant
When evaluating a tenant, system selects applicable criteria:
def select_active_criteria(tenant_id):
    profile = get_business_profile(tenant_id)
    
    # Query all active criteria matching this profile
    applicable = query("""
        SELECT * FROM criteria_registry
        WHERE status = 'active'
          AND (applies_to_dimensions->'industries' = '"all"'::jsonb
               OR applies_to_dimensions->'industries' ?| ARRAY[:industry])
          AND (applies_to_dimensions->'sub_domains' = '"all"'::jsonb
               OR applies_to_dimensions->'sub_domains' ?| ARRAY[:sub_domain])
          AND (applies_to_dimensions->'lifecycle_stages' = '"all"'::jsonb
               OR applies_to_dimensions->'lifecycle_stages' ?| ARRAY[:lifecycle])
          AND (applies_to_dimensions->'archetypes' = '"all"'::jsonb
               OR applies_to_dimensions->'archetypes' ?| ARRAY[:archetype])
          -- ... other dimension filters
    """, {
        'industry': profile.d1_industry.primary,
        'sub_domain': profile.d2_sub_domain.value,
        'lifecycle': profile.d5_lifecycle_stage.value,
        'archetype': profile.d6_archetype.value
    })
    
    # Add tenant-specific custom criteria
    custom = query("""
        SELECT * FROM criteria_registry
        WHERE applies_to_dimensions->>'tenant_specific' = :tenant_id
          AND status = 'active'
    """, {'tenant_id': tenant_id})
    
    all_criteria = applicable + custom
    
    # Resolve conflicts (Phần 9)
    resolved = resolve_criteria_conflicts(all_criteria)
    
    return resolved
## 5.5 Acceptance Criteria — Phần 5
☐ Criteria stored as first-class objects (not in code)
☐ Each criterion has all 10 anatomy fields
☐ Selection per tenant <100ms
☐ Tenant-custom criteria isolated
☐ Computation formulas validated (parseable, executable)
☐ Change log immutable

# Phần 6. Criteria Lifecycle
Mục đích: Tiêu chí KHÔNG static. Có lifecycle như documents — proposed → reviewed → active → superseded → retired.
## 6.1 Lifecycle States
                   ┌──────────┐
                   │ PROPOSED │  (created by RAG ingestion or user)
                   └────┬─────┘
                        ↓
                   ┌──────────┐
                   │  REVIEW  │  (under expert + tenant review)
                   └────┬─────┘
                        ↓
                  ┌─────┴─────┐
                  ↓           ↓
            ┌──────────┐  ┌──────────┐
            │  ACTIVE  │  │ REJECTED │
            └────┬─────┘  └──────────┘
                 ↓
                 ↓ (when newer version approved)
            ┌──────────────┐
            │  SUPERSEDED  │  (history preserved, not used)
            └──────┬───────┘
                   ↓ (after retention period)
            ┌──────────────┐
            │   RETIRED    │
            └──────────────┘
## 6.2 State Transitions
state_transitions:
  
  proposed_to_review:
    trigger: "Auto-promoted after RAG ingestion + initial validation"
    or: "User submits new criterion"
    actions:
      - assign_reviewer (domain expert + relevant managers)
      - notify_reviewers
  
  review_to_active:
    requires:
      - domain_expert_approval
      - if_regulatory: compliance_team_approval
      - backtest_passed (run criterion on historical data)
      - no_conflicts_with_existing
    
    actions:
      - increment_version
      - mark_predecessor_superseded (if updating existing)
      - notify_affected_tenants (if material change)
      - trigger_formula_engine_review (Phần 17)
  
  review_to_rejected:
    triggers:
      - reviewer_rejects
      - backtest_failed
      - conflicts_unresolved
    actions:
      - log_rejection_reason
      - notify_proposer
  
  active_to_superseded:
    trigger: "New version of same criterion approved"
    actions:
      - new_version_takes_over
      - old_kept_for_audit history
  
  superseded_to_retired:
    trigger: "Retention period passed (default 7 years for regulatory)"
    actions:
      - archive_to_cold_storage
      - keep_only_summary_metadata
## 6.3 New Criterion Creation Workflow
def propose_new_criterion(source, content):
    """
    Source can be: RAG ingestion / user / system detection
    """
    
    # Step 1: Parse and validate
    criterion = parse_criterion(content)
    validation = validate_criterion_format(criterion)
    if not validation.passed:
        return reject_with_reason(validation.errors)
    
    # Step 2: Check for duplicates
    similar = find_similar_existing_criteria(criterion)
    if similar:
        return route_to_supersession_workflow(criterion, similar)
    
    # Step 3: Backtest on historical data
    backtest_results = run_backtest(criterion, sample_tenants=10)
    if not backtest_results.acceptable:
        return reject_with_reason("Backtest failed: " + backtest_results.issues)
    
    # Step 4: Save as PROPOSED
    new_criterion = save_criterion(criterion, status='proposed')
    
    # Step 5: Trigger review workflow
    assign_reviewers(new_criterion)
    
    return new_criterion
## 6.4 Supersession Workflow
When new version of criterion proposed:
def propose_supersession(existing_criterion_id, new_content):
    existing = get_criterion(existing_criterion_id)
    
    # Create new version
    new_version = create_criterion_version(
        existing,
        new_content,
        version=existing.version + 1
    )
    
    # Compute diff
    diff = compute_criterion_diff(existing, new_version)
    
    # Determine if material
    if is_material_change(diff):
        # Material: needs full review
        assign_full_review(new_version)
        notify_affected_tenants_of_pending_change(existing, diff)
    else:
        # Non-material: lighter approval (e.g., metadata-only)
        assign_lightweight_review(new_version)
    
    # Backtest on real tenant data
    backtest_results = run_backtest_compare(existing, new_version)
    if backtest_results.materially_different:
        flag_for_extra_scrutiny(new_version, backtest_results)
    
    return new_version
## 6.5 Material Change Definition
material_changes_to_criterion:
  
  always_material:
    - threshold values changed > 20%
    - computation_formula changed
    - applies_to_dimensions narrowed/widened significantly
  
  material_if_regulatory:
    - any change to regulatory criteria triggers compliance review
    - jurisdiction expansion
    - effective_date change
  
  not_material:
    - display_name spelling fix
    - source URL update
    - typo correction in description
## 6.6 Backtest Process
Before promoting to ACTIVE, run backtest:
def run_backtest_compare(old_criterion, new_criterion):
    # Sample tenants where this criterion applies
    test_tenants = sample_applicable_tenants(new_criterion, n=20)
    
    results = []
    for tenant in test_tenants:
        # Compute metric per old vs new
        old_value = compute(old_criterion, tenant, period='last_quarter')
        new_value = compute(new_criterion, tenant, period='last_quarter')
        
        # Compute classification per old thresholds vs new
        old_class = classify(old_value, old_criterion.thresholds)
        new_class = classify(new_value, new_criterion.thresholds)
        
        results.append({
            'tenant_id': tenant.id,
            'old_value': old_value, 'new_value': new_value,
            'old_class': old_class, 'new_class': new_class,
            'class_changed': old_class != new_class,
            'magnitude_diff': abs(old_value - new_value)
        })
    
    # Aggregate
    classification_change_rate = sum(r['class_changed'] for r in results) / len(results)
    avg_magnitude_diff = mean([r['magnitude_diff'] for r in results])
    
    return {
        'samples': len(results),
        'classification_change_rate': classification_change_rate,
        'avg_magnitude_diff': avg_magnitude_diff,
        'materially_different': classification_change_rate > 0.20,
        'detailed_results': results,
        'acceptable': classification_change_rate < 0.50  # >50% change rate suspicious
    }
## 6.7 Acceptance Criteria — Phần 6
☐ All criteria have explicit lifecycle state
☐ State transitions audit-logged
☐ Supersession workflow handles material changes correctly
☐ Backtest runs before any criterion goes ACTIVE
☐ Affected tenants notified of pending material changes
☐ Retention policy enforced (regulatory criteria archived 7+ years)

# Phần 7. Source Authority Hierarchy
Mục đích: Khi multiple sources có conflicting criteria, ai win?
## 7.1 4-Tier Authority Hierarchy
TIER 1: REGULATORY (highest authority)
  Examples:
    - SBV circulars, Bộ Y tế thông tư, Bộ Tài chính
    - Basel III/IV, IFRS 9/17, IFRS 17, GAAP
    - Industry regulators (SEC, FDA, MAS)
  Authority: ABSOLUTE — must comply
  Override: only by newer regulatory issuance
  
TIER 2: KAORI CURATED (high authority)
  Examples:
    - Validated through 50+ tenants
    - Vetted by Kaori domain experts
    - Industry standards adoption
  Authority: HIGH — production-ready
  Override: by Tier 1 (newer regulation) or by curator update
  
TIER 3: MARKET/INDUSTRY (medium authority)
  Examples:
    - McKinsey, BCG, Bain industry reports
    - Gartner, Forrester
    - Academic publications (HBR, MIT Sloan)
    - Local: VietData, FiinGroup
  Authority: MEDIUM — advisory
  Override: by Tier 1, Tier 2, or replacement market source
  
TIER 4: TENANT-SPECIFIC (high authority for that tenant only)
  Examples:
    - Tenant's own SOPs, policies
    - Internal targets set by management
    - Custom KPIs unique to that company
  Authority: HIGH for that tenant — they decide
  Override: only by tenant themselves
  Cannot conflict with: Tier 1 (regulatory minimums)
## 7.2 Conflict Resolution Rules
def resolve_conflict(criterion_a, criterion_b):
    """
    Both apply to same metric, different thresholds.
    """
    # Rule 1: Regulatory always wins
    if criterion_a.source.tier == 1 and criterion_b.source.tier > 1:
        return criterion_a
    if criterion_b.source.tier == 1 and criterion_a.source.tier > 1:
        return criterion_b
    
    # Rule 2: If both regulatory, newer one wins
    if criterion_a.source.tier == 1 and criterion_b.source.tier == 1:
        return max([criterion_a, criterion_b], key=lambda c: c.source.effective_date)
    
    # Rule 3: Tenant-specific (Tier 4) can OVERRIDE Tier 2-3 for that tenant
    # (their own targets supersede generic recommendations)
    # BUT cannot violate Tier 1
    if criterion_a.source.tier == 4 and criterion_b.source.tier in [2, 3]:
        # Validate tenant criterion doesn't violate any Tier 1
        regulatory = find_applicable_tier_1(criterion_a.metric_name)
        if regulatory and violates(criterion_a, regulatory):
            return criterion_b  # tenant criterion invalid
        return criterion_a  # tenant criterion wins
    
    # Rule 4: Among Tier 2-3, newer wins
    return max([criterion_a, criterion_b], key=lambda c: c.source.effective_date)
## 7.3 Multi-Criterion Aggregation
When multiple criteria apply to same metric (no conflict, just multiple perspectives):
def aggregate_thresholds(criteria_list):
    """
    Multiple criteria for same metric → choose strictest applicable.
    """
    # Example: Cash runway
    # Criterion A (Tier 2 Kaori): warning < 12 months
    # Criterion B (Tier 4 tenant target): warning < 18 months (more conservative)
    
    # Use STRICTEST threshold — more conservative protects tenant
    strictest = compute_strictest(criteria_list)
    
    return {
        'effective_threshold': strictest,
        'sourced_from': strictest.source,
        'all_applicable': criteria_list,
        'reasoning': "Strictest applicable threshold used for safety"
    }
## 7.4 Source Trust Scoring
Within same tier, not all sources equal:
trust_scoring:
  tier_1_regulatory:
    sbv_official: 1.0
    basel_committee: 1.0
    ifrs_foundation: 1.0
    industry_regulator: 0.95
  
  tier_2_curated:
    kaori_validated_50_plus_tenants: 0.95
    kaori_validated_10_50_tenants: 0.85
    kaori_proposed_pending_validation: 0.65
  
  tier_3_market:
    mckinsey: 0.85
    bcg: 0.85
    bain: 0.85
    gartner: 0.80
    forrester: 0.80
    hbr: 0.75
    decision_lab_vn: 0.70
    fiingroup: 0.75
    blog_post_unverified: 0.30
  
  tier_4_tenant:
    tenant_manager_approved: 0.90
    tenant_user_proposed: 0.60
## 7.5 Acceptance Criteria — Phần 7
☐ All criteria tagged with tier
☐ Conflict resolution algorithm tested with adversarial cases
☐ Tenant criteria cannot violate regulatory minimums
☐ Source trust scoring applied consistently
☐ Audit log: which criterion won when conflicts resolved

# Phần 8. Tenant-Custom & Tenant-Specific Criteria
Mục đích: Address “nếu thêm tiêu chí, tiêu chí đặc thù thì sao”.
## 8.1 Tenant Criterion Workflow
Tenant Manager wants to add criterion (e.g., "Same-day delivery rate")
       ↓
Step 1: Open Criterion Builder UI
  - Select category (operational/customer/etc.)
  - Define metric (name, computation, unit)
  - Set thresholds (per tenant target)
  - Optional: provide industry context (RAG search)
       ↓
Step 2: System validates
  - Format check
  - Computation parseable
  - No conflict with regulatory criteria
  - SQL injection / safety check
       ↓
Step 3: Backtest on tenant's historical data
  - Compute metric for last 90 days
  - Show distribution
  - Confirm thresholds are reasonable (not impossible)
       ↓
Step 4: Tenant Manager reviews backtest + approves
       ↓
Step 5: Optional — Submit to Kaori library
  If criterion proves valuable, can promote to Tier 2
       ↓
Step 6: Activate as Tenant-Specific (Tier 4)
  Status: ACTIVE for this tenant
## 8.2 Criterion Builder UI
┌────────────────────────────────────────────────────────────┐
│ Add Custom Criterion                                       │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ Display Name:    [Same-day Delivery Rate              ]   │
│ Vietnamese:      [Tỷ lệ giao trong ngày               ]   │
│                                                            │
│ Category:        [Operational ▼]                          │
│                                                            │
│ ─── Computation ──────────────────────────────────────    │
│                                                            │
│ Metric Name:     [same_day_delivery_rate              ]   │
│ Unit:            [%]                                       │
│                                                            │
│ How is it computed?                                        │
│ ┌───────────────────────────────────────────────────┐   │
│ │ SELECT count(case when                              │   │
│ │   delivered_at <= order_placed_at + interval '24h' │   │
│ │   then 1 end)::float / count(*) * 100             │   │
│ │ FROM silver.orders                                  │   │
│ │ WHERE order_date BETWEEN :start AND :end           │   │
│ └───────────────────────────────────────────────────┘   │
│                                                            │
│ [▶ Validate SQL] [📊 Preview on your data]                │
│                                                            │
│ ─── Thresholds ───────────────────────────────────────    │
│                                                            │
│ Target (good):       [> 90%]                              │
│ Below target:        [70-90%]                             │
│ Concerning:          [< 70%]                              │
│                                                            │
│ ─── Backtest ─────────────────────────────────────────    │
│                                                            │
│ [Run on last 90 days]                                     │
│                                                            │
│ Results: avg 87%, range 72-94%                            │
│ Distribution histogram: [chart]                           │
│ Days in each band: target=12, below=68, concerning=10    │
│                                                            │
│ ─── Optional: Suggest to Kaori library ──────────────    │
│                                                            │
│ ☐ Submit to Kaori for community library consideration    │
│                                                            │
│ [Cancel] [Save as Draft] [Approve & Activate]             │
└────────────────────────────────────────────────────────────┘
## 8.3 Custom Criterion Validation
def validate_custom_criterion(criterion, tenant_id):
    issues = []
    
    # Check 1: SQL safety (no DROP, DELETE, UPDATE)
    sql_safe = sql_injection_check(criterion.computation_formula)
    if not sql_safe:
        issues.append("SQL contains unsafe operations")
    
    # Check 2: Computation feasibility
    try:
        # Dry run on small sample
        sample_result = run_on_sample(criterion.computation_formula, tenant_id)
    except Exception as e:
        issues.append(f"SQL doesn't execute: {e}")
    
    # Check 3: No conflict with regulatory
    metric_name = criterion.metric_name
    applicable_regulatory = get_applicable_regulatory(metric_name, tenant_id)
    if applicable_regulatory:
        if violates(criterion, applicable_regulatory):
            issues.append(f"Conflicts with regulatory: {applicable_regulatory.id}")
    
    # Check 4: Threshold sanity
    if not is_monotonic(criterion.thresholds):
        issues.append("Thresholds not monotonic (excellent should be > critical)")
    
    # Check 5: Permissions
    if not tenant_has_permission(tenant_id, 'add_custom_criteria'):
        issues.append("Tenant plan doesn't include custom criteria")
    
    return ValidationResult(passed=len(issues) == 0, issues=issues)
## 8.4 Tenant Criterion Promotion to Library
If tenant criterion valuable + applicable widely → promote to Tier 2:
def evaluate_for_library_promotion(tenant_criterion):
    """
    Quarterly: review high-quality tenant criteria for library promotion.
    """
    # Quality signals
    signals = {
        'engagement': tenant_criterion.usage_count > 1000,
        'tenant_satisfaction': tenant_criterion.thumbs_up_rate > 0.7,
        'broad_applicability': estimate_applicable_tenants(tenant_criterion) > 50,
        'no_overlaps': not has_existing_similar_in_library(tenant_criterion),
        'tenant_consents_to_share': tenant_criterion.share_consent
    }
    
    score = sum(signals.values()) / len(signals)
    
    if score > 0.8:
        # Propose promotion
        anonymized_version = anonymize_criterion(tenant_criterion)
        propose_for_library(anonymized_version, source='community_promotion')
        notify_tenant("Your criterion proposed for community library — credit to you")
    
    return score
## 8.5 Tenant Criterion Quotas
criterion_quotas_per_plan:
  PILOT:
    custom_criteria: 0
  ENT_BASIC:
    custom_criteria: 5
  ENT_MID:
    custom_criteria: 20
  ENT_MAX:
    custom_criteria: unlimited
## 8.6 Acceptance Criteria — Phần 8
☐ Tenant Criterion Builder UI functional
☐ Validation prevents SQL injection
☐ Backtest on historical data before activation
☐ Tenant criteria isolated (don’t leak to other tenants)
☐ Promotion path to library exists with consent
☐ Quotas enforced per plan

# Phần 9. Conflict Resolution
Mục đích: Multiple criteria apply to same metric → who wins?
## 9.1 Resolution Algorithm
def resolve_criteria_conflicts(applicable_criteria):
    """
    Group by metric_name, resolve conflicts within each group.
    """
    grouped = group_by(applicable_criteria, 'metric_name')
    
    resolved = []
    conflicts_log = []
    
    for metric_name, criteria_for_metric in grouped.items():
        if len(criteria_for_metric) == 1:
            resolved.append(criteria_for_metric[0])
            continue
        
        # Multiple criteria for same metric → resolve
        winner, log = apply_resolution_rules(criteria_for_metric)
        resolved.append(winner)
        conflicts_log.append(log)
    
    return resolved, conflicts_log

def apply_resolution_rules(competing_criteria):
    """
    Apply hierarchy rules in priority order.
    """
    # Rule 1: Regulatory wins
    regulatory = [c for c in competing_criteria if c.source.tier == 1]
    if regulatory:
        winner = newest(regulatory)
        return winner, f"Regulatory tier 1: {winner.id} wins"
    
    # Rule 2: Tenant-specific overrides Tier 2-3
    tenant_specific = [c for c in competing_criteria if c.source.tier == 4]
    if tenant_specific:
        # But check no violation of any Tier 1 (regulatory minimum)
        ts_criterion = tenant_specific[0]
        regulatory_for_metric = find_regulatory_min(ts_criterion.metric_name)
        if regulatory_for_metric and violates(ts_criterion, regulatory_for_metric):
            return regulatory_for_metric, f"Tenant criterion violates regulatory"
        return ts_criterion, f"Tenant override applied"
    
    # Rule 3: Higher tier wins
    sorted_by_tier = sorted(competing_criteria, key=lambda c: c.source.tier)
    if sorted_by_tier[0].source.tier < sorted_by_tier[1].source.tier:
        winner = sorted_by_tier[0]
        return winner, f"Higher tier wins"
    
    # Rule 4: Same tier — newest effective date
    same_tier = [c for c in competing_criteria if c.source.tier == sorted_by_tier[0].source.tier]
    winner = max(same_tier, key=lambda c: c.source.effective_date)
    return winner, f"Newest effective date"
## 9.2 Conflict Display to User
When conflict resolved silently, log for transparency:
┌──────────────────────────────────────────────────────────┐
│ Criteria Resolution Log                                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│ Metric: NPL Ratio                                        │
│                                                          │
│ Applicable criteria found: 2                             │
│   1. SBV Circular 41 (Tier 1, regulatory)               │
│      Threshold: > 5% = critical                          │
│   2. Tenant target (Tier 4, your config)                │
│      Threshold: > 3% = warning                           │
│                                                          │
│ ✓ Both used:                                             │
│   - Regulatory threshold = compliance benchmark          │
│   - Your target = aspirational benchmark                 │
│                                                          │
│ Display: dual threshold marker                           │
│                                                          │
└──────────────────────────────────────────────────────────┘
## 9.3 Edge Cases
edge_cases:
  
  case_1_complementary_not_conflicting:
    scenario: Regulatory says "must be < 5%", tenant target says "aspire < 3%"
    resolution: Both shown — regulatory as compliance line, tenant as aspirational
    
  case_2_outdated_in_force:
    scenario: Tier 1 regulatory exists but is being deprecated, Tier 2 reflects new standard
    resolution: Regulatory still wins until effective_date of new regulation
    notify: "New standard effective YYYY-MM-DD"
  
  case_3_jurisdictional:
    scenario: Tenant operates in 2 countries with different regulations
    resolution: Apply STRICTER for both (as both must be met)
  
  case_4_definition_disagreement:
    scenario: Same metric name but different formulas (e.g., "churn" defined differently)
    resolution: Treat as separate criteria, label clearly
## 9.4 Acceptance Criteria — Phần 9
☐ Conflict resolution deterministic (same inputs → same output)
☐ Resolution audit-logged
☐ Tenant visibility into resolution decisions
☐ Regulatory minimums never violated
☐ Edge cases handled with explicit logic

# PART IV — RAG KNOWLEDGE ENGINE
# Phần 10. 4-Tier Source Architecture
Mục đích: Address “tiêu chí đó có phải mới nhất không”. RAG là backbone, không phải supplement.
## 10.1 Why RAG First-Class (not optional)
Hard-coded criteria sẽ outdated trong 12 tháng: - Regulations update mỗi quarter (SBV circulars) - Industry standards evolve (Basel III → IV) - Best practices từ research mỗi tháng - Local nuances (VN-specific patterns)
→ RAG là mandatory infrastructure, không phải nice-to-have.
## 10.2 4-Tier Architecture
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  TIER 1: REGULATORY (highest authority, daily refresh)       │
│  ────────────────────────────────────────────────────       │
│  Sources:                                                    │
│    - sbv.gov.vn (banking circulars)                         │
│    - moh.gov.vn (Bộ Y tế guidelines)                        │
│    - mof.gov.vn (Bộ Tài chính)                              │
│    - moit.gov.vn (Bộ Công Thương)                           │
│    - gso.gov.vn (statistics)                                │
│    - bis.org (Basel committee)                              │
│    - ifrs.org (accounting standards)                         │
│    - iso.org (standards)                                     │
│  Refresh: daily crawl with diff detection                    │
│  Authority: ABSOLUTE                                         │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TIER 2: KAORI CURATED (high authority, monthly review)      │
│  ────────────────────────────────────────────────────       │
│  Sources:                                                    │
│    - Internal expert-validated whitepapers                   │
│    - Best practices distilled from 50+ tenants              │
│    - Industry benchmarks (Kaori-curated)                     │
│  Refresh: monthly, manual review                             │
│  Authority: HIGH (production-ready)                          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TIER 3: MARKET/INDUSTRY (medium authority, weekly)          │
│  ────────────────────────────────────────────────────       │
│  Sources:                                                    │
│    Paid:                                                     │
│      - mckinsey.com/insights                                 │
│      - bcg.com/publications                                  │
│      - bain.com/insights                                     │
│      - gartner.com (with subscription)                       │
│    Free:                                                     │
│      - hbr.org                                               │
│      - sloanreview.mit.edu                                   │
│      - cbinsights.com                                        │
│    VN:                                                       │
│      - vietdata.vn                                           │
│      - fiingroup.com                                         │
│      - decisionlab.com                                       │
│  Refresh: weekly                                             │
│  Authority: MEDIUM (advisory)                                │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TIER 4: TENANT-SPECIFIC (high for that tenant, on-upload)  │
│  ────────────────────────────────────────────────────       │
│  Sources:                                                    │
│    - Tenant's own SOPs, policies                            │
│    - Past meeting notes, decision rationales                 │
│    - Internal playbooks                                      │
│    - Custom KPI definitions                                  │
│  Refresh: on-upload + on-edit                                │
│  Authority: HIGH for that tenant only                        │
│  Isolation: strict per-tenant                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
## 10.3 Tier Capabilities Matrix

| Capability | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---|
| Auto-creates criteria | ✓ (high impact) | ✓ (review) | ✗ (advisory only) | ✓ (tenant initiates) |
| Updates existing criteria | ✓ (regulatory updates) | ✓ (curator review) | Suggestion only | ✓ (tenant only) |
| Cross-tenant applicability | ✓ | ✓ | ✓ | ✗ |
| Audit-grade trustability | ABSOLUTE | HIGH | MEDIUM | HIGH (within tenant) |
| Override priority | Highest | 2nd | 3rd | High for tenant |
| Required for Phase 1? | YES | YES | Partial | YES |


# Phần 11. Continuous Ingestion Pipeline
Source (crawl/upload)
       ↓
Format normalize (PDF→text, HTML→text, DOCX→text)
       ↓
Semantic chunking (preserve context boundaries)
  - Regulatory: chunk by Article/Section
  - Industry reports: chunk by section + headings
  - Whitepapers: chunk by topic
  - Standard size: ~500 tokens with 50-token overlap
       ↓
Metadata enrichment:
  - tier (1-4)
  - industry tags, sub-domain tags
  - jurisdiction
  - date_published, date_effective, date_obsolete
  - authority_score (0-1)
  - language (VN/EN)
  - document_type (regulation, whitepaper, blog, policy)
       ↓
Quality scoring:
  - Source authority (Tier 1 = 1.0, blog = 0.3)
  - Freshness (exponential decay)
  - Relevance (topic coherence)
       ↓
Deduplication (cross-source dedup with fingerprinting)
       ↓
Embedding generation:
  - VN: PhoBERT-large, viBERT
  - EN: BGE-large, e5-large
  - Multi-lingual: BGE-M3
       ↓
Vector store write (per-tier namespace)
  - Tier 1-3: shared vector store
  - Tier 4: per-tenant isolated namespace
       ↓
Criterion extraction (NEW):
  - Identify rules/thresholds in document
  - Extract as criterion proposals
  - Route to Phần 6 lifecycle (PROPOSED state)
## 11.1 Criterion Extraction from Documents
When ingesting regulatory or industry doc, auto-extract potential criteria:
def extract_criteria_from_document(document):
    """
    LLM-assisted extraction of structured criteria from unstructured docs.
    """
    
    # Stage 1: Identify candidate sections
    sections_with_thresholds = find_sections_containing(
        document,
        patterns=[
            'must be', 'should be', 'minimum', 'maximum',
            '≥', '≤', '>', '<',
            'at least', 'no more than',
            'phải', 'tối thiểu', 'tối đa'  # VN
        ]
    )
    
    # Stage 2: LLM-structured extraction
    candidates = []
    for section in sections_with_thresholds:
        prompt = f"""
        Extract any quantitative criteria from this regulatory text.
        
        Text:
        {section.text}
        
        Output JSON for each criterion found:
        {{
            "metric_name": "...",
            "measurement_unit": "...",
            "threshold_rule": "...",
            "applicable_to": "...",
            "source_quote": "<exact quote>"
        }}
        
        If no quantitative criterion, return empty list.
        """
        extracted = llm.generate(prompt, response_format='json')
        candidates.extend(extracted)
    
    # Stage 3: Validate + dedupe
    validated = []
    for candidate in candidates:
        if validate_extraction(candidate, source_document=document):
            # Check if similar criterion already exists
            if not has_duplicate(candidate):
                # Create as PROPOSED state for human review
                criterion = create_proposed_criterion(candidate, source=document)
                validated.append(criterion)
    
    return validated
## 11.2 Crawl Schedules
crawl_schedules:
  
  tier_1_regulatory:
    frequency: daily at 02:00 UTC
    sources:
      sbv.gov.vn:
        endpoints: [/circulars, /policies, /announcements]
        diff_strategy: hash-based change detection
        notify_on_change: ["compliance_team", "ml_team", "affected_tenants"]
      moh.gov.vn:
        endpoints: [/thong-tu, /quy-dinh]
      bis.org:
        endpoints: [/publ]
    
  tier_2_curated:
    frequency: monthly review
    process: editorial calendar
    
  tier_3_market:
    frequency: weekly
    sources:
      mckinsey.com:
        endpoints: [/business-functions/strategy/our-insights]
        rate_limit: respect robots.txt
      hbr.org:
        endpoints: [/topic/business-management]
      decisionlab.com:
        endpoints: [/insights]
    
  tier_4_tenant:
    frequency: on-upload + on-edit (event-driven)
## 11.3 Ingestion Quality Gates
def ingestion_quality_gate(document, candidate_criteria):
    """
    Don't promote bad data into criteria registry.
    """
    
    # Gate 1: Source authority verified
    if document.source_url not in WHITELISTED_SOURCES:
        return reject("Source not whitelisted")
    
    # Gate 2: Document parseable
    if document.parse_quality_score < 0.7:
        return reject("Document parsing failed quality")
    
    # Gate 3: Criteria extraction confidence
    high_confidence_criteria = [c for c in candidate_criteria if c.confidence > 0.75]
    if len(high_confidence_criteria) == 0 and len(candidate_criteria) > 0:
        # All low confidence → flag for human review
        flag_for_review(candidate_criteria)
    
    # Gate 4: No regression risk
    for candidate in candidate_criteria:
        if would_supersede_existing(candidate):
            existing = find_existing(candidate)
            if existing.source.tier <= candidate.source.tier:
                # Don't auto-supersede higher-authority with lower
                if not is_newer_regulation(candidate, existing):
                    flag_conflict(candidate, existing)
    
    return accept(high_confidence_criteria)
## 11.4 Acceptance Criteria — Phần 11
☐ Daily regulatory crawl operational
☐ Diff detection vs previous version
☐ Criterion extraction accuracy ≥75%
☐ Quality gates prevent low-trust criteria entering registry
☐ Multi-language support (VN + EN)
☐ Per-tenant isolation enforced for Tier 4

# Phần 12. Change Detection & Auto-Update
Mục đích: Khi regulator publish circular mới, system phải detect + propagate to affected tenants.
## 12.1 Change Detection Pipeline
class RegulatoryChangeDetector:
    
    def detect_daily(self, source):
        """
        Compare today's crawl to yesterday's.
        """
        today = crawl_source(source)
        yesterday = get_previous_crawl(source)
        
        changes = []
        
        # Detect new documents
        new_docs = today.documents - yesterday.documents
        for doc in new_docs:
            changes.append(Change(
                type='new_document',
                document=doc,
                source=source,
                detected_at=now()
            ))
        
        # Detect updated documents
        for doc_id in (today.documents & yesterday.documents):
            today_hash = today.documents[doc_id].content_hash
            yesterday_hash = yesterday.documents[doc_id].content_hash
            if today_hash != yesterday_hash:
                changes.append(Change(
                    type='document_updated',
                    document=today.documents[doc_id],
                    diff=compute_diff(today.documents[doc_id], yesterday.documents[doc_id]),
                    source=source
                ))
        
        # Detect deprecated documents
        deprecated = yesterday.documents - today.documents
        for doc in deprecated:
            changes.append(Change(
                type='document_deprecated',
                document=doc,
                source=source
            ))
        
        return changes
    
    def assess_materiality(self, change):
        """
        Is this change material enough to require action?
        """
        if change.type == 'new_document':
            return Material(severity='HIGH')  # always review new regs
        
        if change.type == 'document_updated':
            # Analyze the diff
            if affects_thresholds(change.diff):
                return Material(severity='HIGH')
            elif affects_definitions(change.diff):
                return Material(severity='HIGH')
            elif affects_examples_only(change.diff):
                return Material(severity='LOW')
            else:
                return Material(severity='MEDIUM')
        
        if change.type == 'document_deprecated':
            return Material(severity='HIGH')  # may break compliance
        
        return Material(severity='LOW')
## 12.2 Auto-Update Workflow
Regulatory change detected
       ↓
Materiality assessment
       ↓
   ┌───┴───┐
   ↓       ↓
HIGH    LOW/MED
material material
   ↓       ↓
Compliance review needed     Auto-process
   ↓       ↓
  ┌─┴─┐  Background:
  ↓   ↓  - Extract any new criteria
Email Notify  - Update existing as needed
compliance ML team  - Background to PROPOSED state
team            - Run backtest
                - Schedule monthly review
   ↓
Compliance reviews → approve/modify/reject
   ↓
If approved:
  - Criteria created/updated in PROPOSED state
  - Backtest run
  - Affected tenants identified
  - Notification scheduled
   ↓
If material affecting ACTIVE criteria:
  - Plan transition (effective date in future)
  - Notify affected tenants in advance
  - Provide sunset period for old criteria
   ↓
Effective date arrives:
  - Old criteria → SUPERSEDED
  - New criteria → ACTIVE
  - Formula Engine review (Phần 17)
## 12.3 Acceptance Criteria — Phần 12
☐ Daily change detection operational
☐ Materiality assessment correct ≥80% on test cases
☐ Auto-process for low-material works without intervention
☐ High-material always escalated to compliance
☐ Audit log immutable

# Phần 13. Material Change Notification
When criteria materially change, affected tenants must be notified.
## 13.1 Notification Decision
def determine_notification(change, criterion):
    """
    Who needs to know about this change?
    """
    
    affected_tenants = get_active_users_of_criterion(criterion.id)
    
    # Severity-based notification tier
    if change.materiality == 'HIGH':
        return NotificationPlan(
            tenants=affected_tenants,
            channels=['email', 'in_app', 'dashboard_banner'],
            urgency='IMMEDIATE',
            includes_action_required=True
        )
    
    if change.materiality == 'MEDIUM':
        return NotificationPlan(
            tenants=affected_tenants,
            channels=['email', 'in_app'],
            urgency='WITHIN_24H',
            includes_summary=True
        )
    
    if change.materiality == 'LOW':
        return NotificationPlan(
            tenants=affected_tenants,
            channels=['monthly_digest'],
            urgency='IN_DIGEST'
        )
## 13.2 Notification Content
Subject: [Compliance Update] SBV Circular 41 amended — review impact on your reports

Dear [Manager Name],

A regulatory change affects criteria currently used in your Kaori reports:

────────────────────────────────────────────────
What changed:
  Circular: SBV 41/2016 → amended by SBV 12/2026 (effective 2026-07-01)
  Impact on: NPL Ratio criterion
  Change: NPL classification rules updated for fintech entities
────────────────────────────────────────────────

How this affects you:
  ✓ 3 reports use NPL Ratio criterion
  ✓ 1 active alert based on NPL threshold
  ✓ Your dashboard "Risk Overview" tile

────────────────────────────────────────────────

Action required by 2026-06-15:
  □ Review proposed new criterion (link)
  □ Confirm transition is automatic OR
  □ Customize for your specific case

If no action by 2026-07-01: new criterion auto-applies, old preserved for 1 year reference

────────────────────────────────────────────────

[Review Now] [Learn More] [Contact Support]
## 13.3 Notification Quotas
notification_throttling:
  per_user_per_week:
    high_materiality: unlimited (all sent)
    medium: max 5 (rest in digest)
    low: weekly digest only
  
  fatigue_prevention:
    if_user_dismissed_3_consecutive: switch to monthly digest
    if_user_acknowledged_all: continue normal

# Phần 14. Anti-Hallucination & Provenance
Mục đích: RAG có thể inject hallucination nếu không validate. Critical safeguards.
## 14.1 Anti-Hallucination Rules
def rag_anti_hallucination_check(response, retrieved_context):
    
    # Rule 1: Every cited number must appear in retrieved context
    cited_numbers = extract_numbers_with_citations(response)
    for num, citation_id in cited_numbers:
        if not number_in_chunk(num, retrieved_context[citation_id], tolerance=0.001):
            raise HallucinationDetected(f"Cited [{citation_id}] but {num} not in source")
    
    # Rule 2: Quoted phrases exact match
    quoted_phrases = extract_quotes(response)
    for phrase, citation_id in quoted_phrases:
        if not phrase_in_chunk(phrase, retrieved_context[citation_id]):
            raise HallucinationDetected(f"Quote not exact in source")
    
    # Rule 3: No claims without citation
    claims = extract_claims_without_citation(response)
    if claims:
        raise UncitedClaimError(f"Uncited claims: {claims}")
    
    # Rule 4: Cross-source contradictions
    contradictions = detect_cross_source_contradictions(response, retrieved_context)
    if contradictions:
        return ResponseWithContradictionWarning(response, contradictions)
    
    return response
## 14.2 Provenance Chain
Every criterion has full provenance traced:
criterion_provenance:
  criterion_id: "crit_002"
  
  source_chain:
    - level: "registry"
      action: "created"
      timestamp: "2026-04-15 10:32"
      from_source: "sbv.gov.vn/circular_41_2016"
      extraction_confidence: 0.92
      reviewer: "compliance_lead_minh"
      reviewer_decision: "approved"
    
    - level: "extraction"
      method: "llm_assisted"
      llm_model: "qwen-14b-v3"
      prompt_version: "v2.1"
      extraction_chunk_id: "chunk_aaa"
    
    - level: "source_document"
      document_id: "doc_sbv_41_2016"
      url: "https://sbv.gov.vn/.../circular_41_2016.pdf"
      ingested_at: "2024-01-10"
      content_hash: "sha256:..."
  
  immutable: true
  audit_trail_required: yes
## 14.3 Tenant Audit Access
Tenant compliance team can audit any criterion:
Audit query: "Why is NPL threshold 5%?"
       ↓
System returns:
  - Criterion ID + version
  - Source chain (provenance)
  - Original document quote
  - Translation if applicable
  - Effective date + history
  - All other tenants using this criterion (anonymized count)
  - Computed result history for this tenant
## 14.4 Acceptance Criteria — Phần 14
☐ Anti-hallucination check 100% on RAG outputs
☐ Every criterion has full provenance chain
☐ Provenance immutable (append-only)
☐ Tenant audit access available
☐ Quote exactness validated
☐ No silent fallback to “general knowledge” without citation

# PART V — ADAPTIVE FORMULA ENGINE
# Phần 15. Formula as Parameterized Template
Mục đích: Address “công thức và thuật toán khi thay đổi tiêu chí đánh giá có thay đổi được không”. Formula KHÔNG hard-code — là parameterized templates couple với criteria.
## 15.1 Formula Anatomy
formula:
  formula_id: UUID
  display_name: string
  
  # What it computes
  computes: list[metric_name]  # which metrics this formula produces
  
  # Template (parameterized)
  template_type: 'sql' | 'python' | 'composite'
  template_body: string
    # Use placeholders: {{criterion.X.threshold}}, {{tenant.field}}
  
  # Parameters (from coupled criteria)
  parameters:
    - name: "threshold_warning"
      sourced_from: "criterion_id_X.thresholds.warning"
      type: numeric
    - name: "lookback_days"
      sourced_from: "criterion_id_X.lookback_days"
      default: 90
  
  # Inputs (from data)
  data_sources: list[table_name]
  required_columns: list[column_name]
  
  # Validation
  expected_output_range: [min, max] | null
  expected_output_type: numeric | classification | series
  
  # Coupled criteria
  coupled_criteria: list[criterion_id]
    # When any of these criteria changes, formula re-evaluates
  
  # Lifecycle (similar to criteria)
  status: 'proposed' | 'review' | 'active' | 'superseded' | 'retired'
  version: integer
  superseded_by: UUID | null
  
  # Performance
  expected_runtime_ms: integer
  optimization_notes: string
  
  # Audit
  created_at, created_by, approved_at, approved_by
  change_log: list[changes]
## 15.2 Example Formulas
### Formula 1: NPL Ratio (parameterized)
formula_npl_ratio:
  formula_id: "form_001"
  display_name: "NPL Ratio Computation"
  
  computes: ["npl_ratio"]
  
  template_type: "sql"
  template_body: |
    SELECT 
      sum(case when days_past_due >= {{criterion.npl_threshold_dpd.value}}
               then outstanding_amount else 0 end) /
      sum(outstanding_amount) * 100 AS npl_ratio
    FROM silver.loan_portfolio
    WHERE tenant_id = :tenant_id
      AND report_date = :report_date
  
  parameters:
    - name: "npl_threshold_dpd"  # days past due to count as NPL
      sourced_from: "criterion_npl_classification.dpd_threshold"
      type: integer
      default: 90
  
  data_sources: ["silver.loan_portfolio"]
  required_columns: ["days_past_due", "outstanding_amount", "tenant_id", "report_date"]
  
  coupled_criteria:
    - "crit_npl_classification"    # if SBV changes DPD threshold from 90 to 60
    - "crit_npl_threshold"         # if threshold for "concerning" changes
  
  expected_output_range: [0, 100]
  expected_output_type: numeric
  
  status: "active"
  version: 1
### Formula 2: Customer LTV (parameterized)
formula_customer_ltv:
  formula_id: "form_002"
  display_name: "Customer Lifetime Value"
  
  computes: ["customer_ltv"]
  
  template_type: "sql"
  template_body: |
    WITH purchase_stats AS (
      SELECT customer_id,
        avg(net_amount) AS aov,
        count(*) AS total_purchases,
        date_diff('month', min(transaction_date), max(transaction_date)) AS lifespan_months
      FROM silver.transactions
      WHERE tenant_id = :tenant_id
        AND transaction_date >= current_date - interval '{{criterion.ltv_lookback.value}} months'
      GROUP BY customer_id
    )
    SELECT customer_id,
      aov * (total_purchases / nullif(lifespan_months, 0)) * {{criterion.ltv_horizon.value}} AS predicted_ltv
    FROM purchase_stats;
  
  parameters:
    - name: "ltv_lookback"
      sourced_from: "criterion_ltv_window.lookback_months"
      type: integer
      default: 24
    - name: "ltv_horizon"
      sourced_from: "criterion_ltv_window.horizon_months"
      type: integer
      default: 24
  
  coupled_criteria:
    - "crit_ltv_window"
    - "crit_ltv_methodology"
  
  status: "active"
  version: 1
### Formula 3: Composite Health Score (cross-criterion)
formula_health_composite:
  formula_id: "form_003"
  display_name: "Composite Health Score"
  
  computes: ["health_composite_score"]
  
  template_type: "composite"
  template_body: |
    composite = sum(dimension_score[d] * weight[d] for d in dimensions)
    
    where:
      dimensions = {{criterion.health_dimensions.list}}
      weight[d] = {{criterion.health_weights[d]}}
      dimension_score[d] = compute_dimension(d, tenant_id)
  
  coupled_criteria:
    - "crit_health_dimensions"    # what dimensions to include
    - "crit_health_weights"       # weights per dimension
    - "crit_dimension_metrics"    # which metrics in each dimension
  
  status: "active"
  version: 1
## 15.3 Formula Storage
CREATE TABLE formulas_registry (
  formula_id UUID PRIMARY KEY,
  display_name VARCHAR(500),
  
  computes JSONB,
  template_type VARCHAR(20),
  template_body TEXT,
  parameters JSONB,
  
  data_sources JSONB,
  required_columns JSONB,
  
  expected_output_range JSONB,
  expected_output_type VARCHAR(50),
  
  coupled_criteria JSONB,  -- list of criterion IDs
  
  status VARCHAR(20),
  version INTEGER,
  superseded_by UUID,
  
  expected_runtime_ms INTEGER,
  
  created_at TIMESTAMP,
  created_by VARCHAR(200),
  approved_at TIMESTAMP,
  approved_by VARCHAR(200),
  
  change_log JSONB
);

CREATE INDEX idx_active_formulas ON formulas_registry (status) WHERE status = 'active';
CREATE INDEX idx_formula_coupled ON formulas_registry USING GIN (coupled_criteria);
## 15.4 Acceptance Criteria — Phần 15
☐ Every formula stored as parameterized template
☐ Parameters sourced from criteria registry (not hard-coded)
☐ Coupled criteria explicitly tracked
☐ Template body validated before save (parseable, executable)
☐ Performance metadata tracked

# Phần 16. Formula-Criteria Coupling
Mục đích: When criteria changes → formulas using those criteria must update.
## 16.1 Coupling Graph
                  ┌─────────────────────────────┐
                  │  Criterion: crit_npl        │
                  │  Threshold: NPL > 5% = bad  │
                  └─────────────┬───────────────┘
                                │
                  ┌─────────────┴───────────────┐
                  ↓                             ↓
       ┌────────────────────┐          ┌────────────────────┐
       │ Formula: form_npl_ │          │ Formula: form_risk_│
       │ ratio              │          │ scoring            │
       │ (uses crit_npl)    │          │ (uses crit_npl)    │
       └────────────────────┘          └────────────────────┘
                  │                             │
                  └─────────────┬───────────────┘
                                ↓
              ┌────────────────────────────────┐
              │ When crit_npl threshold changes:│
              │   Both formulas re-evaluate     │
              └────────────────────────────────┘
## 16.2 Coupling Detection
def find_affected_formulas(criterion_id):
    """When criterion changes, which formulas affected?"""
    return query("""
        SELECT * FROM formulas_registry
        WHERE coupled_criteria @> ARRAY[:criterion_id]::jsonb
          AND status = 'active'
    """, {'criterion_id': criterion_id})
## 16.3 Backwards Coupling: Which criteria does this formula depend on?
def get_formula_dependencies(formula_id):
    formula = get_formula(formula_id)
    return formula.coupled_criteria
## 16.4 Acceptance Criteria — Phần 16
☐ Coupling explicit in both directions (criteria → formulas, formulas → criteria)
☐ Coupling graph queryable
☐ Adding new formula auto-detects coupled criteria from template
☐ Validation prevents breaking changes (criterion deletion if formulas use it)

# Phần 17. Adaptation Pipeline (Criteria Change → Formula Update)
Mục đích: When criterion materially changes, formulas couple với it phải re-evaluate. Đây là answer cho “công thức có thay đổi được không khi tiêu chí thay đổi” — YES, automated pipeline.
## 17.1 Adaptation Pipeline
Criterion materially changed (Phần 6 supersession)
       ↓
Find all coupled formulas (Phần 16)
       ↓
For each affected formula:
       ↓
   Step 1: Generate new formula version
     - Substitute new criterion parameter values
     - Keep template structure
     - Increment version
       ↓
   Step 2: Backtest old vs new (Phần 18)
     - Run on sample tenants
     - Compare outputs
     - Detect material differences
       ↓
   Step 3: Validation gates
     - Output range still valid?
     - Performance still acceptable?
     - No regression in confidence?
       ↓
   Step 4: Routing
     ├── If non-material diff → auto-promote to ACTIVE
     ├── If material diff but low risk → require ML lead approval
     └── If material + high risk → require full review (data + product + compliance)
       ↓
   Step 5: Effective date
     - Default: 30 days after approval
     - Affected tenants notified
     - Old formula preserved for 90 days for comparison
       ↓
   Step 6: Switch
     - Old → SUPERSEDED
     - New → ACTIVE
     - Recompute affected metrics for affected tenants
     - Update dashboards/reports/alerts
## 17.2 Adaptation Pipeline Code
class FormulaAdaptationPipeline:
    
    def on_criterion_change(self, old_criterion, new_criterion, materiality):
        affected_formulas = find_affected_formulas(old_criterion.id)
        
        adaptation_jobs = []
        for formula in affected_formulas:
            job = AdaptationJob(
                formula_id=formula.id,
                old_criterion=old_criterion,
                new_criterion=new_criterion,
                materiality=materiality
            )
            adaptation_jobs.append(self.process_job(job))
        
        return adaptation_jobs
    
    def process_job(self, job):
        formula = get_formula(job.formula_id)
        
        # Step 1: Generate new version
        new_formula = self.generate_new_version(formula, job.new_criterion)
        
        # Step 2: Backtest
        backtest = self.backtest_compare(formula, new_formula)
        
        # Step 3: Validation gates
        validation = self.validate_new_formula(new_formula, backtest)
        if not validation.passed:
            return AdaptationResult(
                status='blocked',
                reason=validation.reasons
            )
        
        # Step 4: Routing
        if backtest.materially_different:
            if backtest.risk_high:
                review_required = ['data_lead', 'product_lead', 'compliance']
            else:
                review_required = ['ml_lead']
            
            new_formula.status = 'review'
            assign_reviewers(new_formula, review_required)
            
            return AdaptationResult(
                status='review_required',
                reviewers=review_required
            )
        else:
            # Auto-promote
            new_formula.status = 'active'
            old_formula.status = 'superseded'
            new_formula.effective_date = datetime.now() + timedelta(days=30)
            
            # Notify
            self.notify_affected_tenants(formula, new_formula)
            
            return AdaptationResult(
                status='auto_promoted',
                effective_date=new_formula.effective_date
            )
    
    def generate_new_version(self, formula, new_criterion):
        new_formula = formula.clone()
        new_formula.version = formula.version + 1
        new_formula.predecessor = formula.id
        
        # Substitute new parameter values
        for param in new_formula.parameters:
            if param.sourced_from.startswith(new_criterion.id):
                param.current_value = new_criterion.get_value(param.sourced_from_field)
        
        # Re-render template body
        new_formula.rendered_body = render_template(
            new_formula.template_body, 
            new_formula.parameters
        )
        
        return new_formula
## 17.3 Acceptance Criteria — Phần 17
☐ Pipeline triggered automatically on criterion change
☐ All affected formulas processed
☐ Auto-promote vs review routing correct
☐ Affected tenants notified before effective date
☐ Old formula preserved during transition
☐ Metrics recomputed correctly with new formula

# Phần 18. Backtesting & Validation Before Switch
Mục đích: Don’t switch to new formula blindly. Validate first.
## 18.1 Backtest Framework
def backtest_compare_formulas(old_formula, new_formula, sample_size=20):
    """
    Run both formulas on sample tenants, compare outputs.
    """
    # Sample tenants where this formula applies
    test_tenants = sample_tenants_using_formula(old_formula.id, n=sample_size)
    
    results = []
    for tenant in test_tenants:
        # Run both formulas on same data + period
        old_output = run_formula(old_formula, tenant, period='last_90_days')
        new_output = run_formula(new_formula, tenant, period='last_90_days')
        
        result = {
            'tenant_id': tenant.id,
            'old_value': old_output.value,
            'new_value': new_output.value,
            'diff_absolute': abs(new_output.value - old_output.value),
            'diff_relative': (new_output.value - old_output.value) / nullif(old_output.value, 1),
            'diff_classification': old_output.classification != new_output.classification,
            'affected_recommendations': count_affected_recommendations(tenant, old_formula, new_formula)
        }
        results.append(result)
    
    # Aggregate
    summary = {
        'samples': len(results),
        'avg_diff_relative': mean([r['diff_relative'] for r in results]),
        'classification_change_rate': sum(r['diff_classification'] for r in results) / len(results),
        'recommendations_affected_total': sum(r['affected_recommendations'] for r in results),
        'materially_different': mean([abs(r['diff_relative']) for r in results]) > 0.20,
        'risk_high': sum(r['diff_classification'] for r in results) / len(results) > 0.30
    }
    
    return BacktestResult(summary=summary, detailed=results)
## 18.2 Validation Gates
def validate_new_formula(new_formula, backtest):
    """
    Multi-gate validation. ALL gates must pass.
    """
    gates = {}
    
    # Gate 1: Output sanity
    gates['output_in_range'] = check_output_in_expected_range(new_formula)
    
    # Gate 2: Performance acceptable
    gates['performance'] = check_runtime(new_formula) <= new_formula.expected_runtime_ms * 1.2
    
    # Gate 3: No catastrophic regression
    gates['no_catastrophic'] = backtest.summary.classification_change_rate < 0.50
    
    # Gate 4: Consistency
    gates['consistent'] = check_idempotent(new_formula)
    
    # Gate 5: Data type sanity
    gates['type_sanity'] = check_output_type_matches(new_formula)
    
    # Gate 6: Edge cases
    gates['edge_cases'] = check_edge_cases(new_formula, [
        'zero_data', 'single_record', 'all_nulls', 'extreme_outliers'
    ])
    
    return ValidationResult(
        passed=all(gates.values()),
        gates=gates,
        reasons=[k for k,v in gates.items() if not v]
    )
## 18.3 Approval Routing
approval_routing:
  
  auto_approve:
    - all_gates_passed AND
    - backtest.materially_different == False AND
    - non_regulatory_formula
  
  ml_lead_approval:
    - all_gates_passed AND
    - (backtest.materially_different OR coupling_count > 5)
  
  full_review:
    - regulatory_formula OR
    - high_impact_formula (used by 100+ tenants) OR
    - backtest.classification_change_rate > 0.30
  
  reject:
    - any_gate_failed
## 18.4 Shadow Mode Deployment
For high-stakes formulas, run NEW alongside OLD for period before switch:
def deploy_shadow_mode(new_formula, period_days=30):
    """
    Run new formula in parallel with old, compare in production for N days.
    """
    new_formula.status = 'shadow'
    new_formula.shadow_until = datetime.now() + timedelta(days=period_days)
    
    # During shadow:
    # - Both formulas computed
    # - Old serves user (production)
    # - New logged for analysis
    # - After 30 days, compare actual outcomes
    
    schedule_shadow_review(new_formula, days=period_days)
## 18.5 Acceptance Criteria — Phần 18
☐ Backtest runs on ≥20 sample tenants
☐ All 6 validation gates pass before promote
☐ Approval routing enforces by impact level
☐ Shadow mode available for high-stakes
☐ Backtest results stored permanently for audit

# Phần 19. Formula Versioning & Rollback
Mục đích: If new formula causes issues post-deployment, rollback fast.
## 19.1 Version History
CREATE TABLE formula_versions (
  formula_id UUID,
  version INTEGER,
  template_body TEXT,
  parameters JSONB,
  status VARCHAR(20),
  
  effective_date DATE,
  superseded_at TIMESTAMP,
  
  deployment_log JSONB,
  rollback_log JSONB,
  
  PRIMARY KEY (formula_id, version)
);
## 19.2 Rollback Triggers
rollback_triggers:
  
  manual:
    by: ['data_lead', 'product_lead', 'incident_commander']
    immediate: yes
  
  automatic:
    - error_rate_spike (>5% formula execution errors in 1h)
    - output_anomaly (>20% values outside expected range)
    - tenant_complaints (>5 in 24h)
    - performance_degradation (runtime > 2x expected)
## 19.3 Rollback Procedure
def rollback_formula(formula_id, reason):
    current = get_active_formula(formula_id)
    previous = get_predecessor(current)
    
    # Switch back
    current.status = 'rolled_back'
    current.rollback_log = {
        'rolled_back_at': now(),
        'rolled_back_by': current_user(),
        'reason': reason,
        'previous_version': previous.version
    }
    
    previous.status = 'active'
    previous.effective_date = now()
    
    # Recompute affected metrics
    affected_tenants = get_users_of_formula(formula_id)
    for tenant in affected_tenants:
        recompute_metrics_for_formula(tenant, previous)
    
    # Notify
    notify_rollback(formula_id, affected_tenants, reason)
## 19.4 Acceptance Criteria — Phần 19
☐ Version history complete (all versions preserved)
☐ Rollback completes in <15 minutes
☐ Auto-rollback triggers operational
☐ Affected metrics recomputed post-rollback
☐ Tenants notified of rollback

# Phần 20. Profile-Aware Formula Selection
Mục đích: Same metric, different profile → different formula. Address “công thức tối ưu cho profile cụ thể”.
## 20.1 Multi-Variant Formulas
For some metrics, multiple formulas exist for different profiles:
formula_variants_example:
  
  metric: "customer_churn_probability"
  
  variants:
    - variant_id: "churn_simple_rules"
      applies_to:
        archetypes: ["A1_DATA_CHAOTIC_SME"]
        sizes: ["micro", "small"]
      template: "rule-based: recency > 60 + frequency_drop > 50% → CHURN_RISK"
      complexity: low
    
    - variant_id: "churn_logistic_regression"
      applies_to:
        archetypes: ["A2_OPS_DRIVEN_MID", "A3_DATA_CURIOUS"]
        sizes: ["small", "medium"]
      template: "logistic regression on RFM features"
      complexity: medium
      requires: "≥6 months data, ≥1000 customers"
    
    - variant_id: "churn_xgboost"
      applies_to:
        archetypes: ["A4_DATA_MATURE_ENTERPRISE"]
      template: "gradient boosting on 50+ features"
      complexity: high
      requires: "≥18 months data, ≥10000 customers"
    
    - variant_id: "churn_survival_analysis"
      applies_to:
        archetypes: ["A4"]
        size: ["large"]
        special: "ENT_MAX with deep analytics"
      template: "Cox proportional hazards model"
      complexity: very_high
## 20.2 Selection Algorithm
def select_best_formula_variant(metric, tenant):
    profile = get_business_profile(tenant.id)
    available_variants = get_formula_variants(metric)
    
    # Filter by applicability
    applicable = [
        v for v in available_variants
        if profile_matches_applies_to(profile, v.applies_to)
    ]
    
    # Filter by data sufficiency
    sufficient = [
        v for v in applicable
        if tenant_meets_requirements(tenant, v.requires)
    ]
    
    # Pick highest complexity that's sufficient
    if not sufficient:
        return get_fallback_variant(metric)
    
    chosen = max(sufficient, key=lambda v: complexity_rank(v.complexity))
    
    return chosen
## 20.3 Cold-Start Handling
When tenant new, simpler formula:
def handle_cold_start(metric, tenant):
    history_days = get_tenant_history_days(tenant.id)
    
    if history_days < 30:
        # Use industry default values, simplest formula
        return get_industry_default_formula(metric, tenant.industry)
    
    elif history_days < 90:
        # Use rule-based simple formula
        return get_rule_based_formula(metric)
    
    elif history_days < 180:
        # Use simple statistical formula
        return get_statistical_formula(metric, complexity='medium')
    
    else:
        # Mature: use best variant
        return select_best_formula_variant(metric, tenant)
## 20.4 Tenant Maturity Evolution
As tenant evolves (more data, better data quality), upgrade formula automatically:
def check_formula_upgrade_eligible(tenant_id):
    """
    Run quarterly. Has tenant matured enough for better formula?
    """
    profile = get_business_profile(tenant_id)
    active_formulas = get_active_formulas_for_tenant(tenant_id)
    
    upgrade_candidates = []
    for formula in active_formulas:
        # Check if a better variant now applicable
        better_variant = find_better_variant(formula, profile)
        if better_variant:
            upgrade_candidates.append({
                'old': formula,
                'new': better_variant,
                'reason': "Tenant data maturity sufficient for {better_variant.complexity}"
            })
    
    if upgrade_candidates:
        notify_tenant_manager(
            "Your data has matured. Upgrade analytics to deeper formulas?",
            upgrade_candidates
        )
## 20.5 Acceptance Criteria — Phần 20
☐ Multi-variant formulas defined for key metrics
☐ Selection algorithm picks best variant per profile
☐ Cold-start fallback works for new tenants
☐ Tenant maturity tracked + upgrade prompted
☐ User can see which variant applied + why

# PART VI — INSIGHT GENERATION
# Phần 21. Insight Engine Mechanics
Mục đích: Trả lời “AI generate insight bằng cách nào”. Engine works on top of Profiling + Criteria + Formulas.
## 21.1 3 Trục Insight Foundation
INSIGHT = f(SOURCES, BASELINES, METHODS)
       
Trục 1: SOURCES   — data sources (Pipeline Unified §1-7)
Trục 2: BASELINES — comparison reference (criteria-driven)
Trục 3: METHODS   — detection algorithms (formula-driven)
## 21.2 Detection Methods (8 công thức)
### M1. Threshold Detection
if current_value < threshold.alert_low or current_value > threshold.alert_high:
    fire_insight(severity='HIGH', method='threshold')
# threshold values from criteria registry
### M2. Z-score (Statistical Anomaly)
Z = (X - μ) / σ
|Z| > 3 ⟹ anomaly (p < 0.003)
### M3. IQR (Robust Outlier)
Q1, Q3 = quartile_25, quartile_75
IQR = Q3 - Q1
outlier if X < Q1 - 1.5×IQR  OR  X > Q3 + 1.5×IQR
### M4. Mann-Kendall (Trend)
S = Σ sign(yⱼ - yᵢ) for all i<j
Z_MK = S / √Var(S)
|Z_MK| > 1.96 ⟹ significant trend
### M5. KL Divergence (Distribution Shift)
KL(P || Q) = Σ P(x) × log( P(x) / Q(x) )
KL > 0.5 ⟹ distributions diverge
### M6. Cosine Similarity (Pattern Match)
similarity(A, B) = (A · B) / (||A|| × ||B||)
> 0.85 ⟹ strong match
### M7. Changepoint (Bayesian Online)
P(changepoint at t | data) > 0.5 ⟹ regime shift
### M8. SHAP (Diagnostic — WHY)
φᵢ = Σ_{S⊆F\{i}} [|S|! × (|F|-|S|-1)! / |F|!] × [v(S∪{i}) - v(S)]
## 21.3 Master Scoring Formula
InsightScore = w₁·Magnitude + w₂·Surprise + w₃·Actionability + w₄·Recency

Default: (0.3, 0.3, 0.3, 0.1)
def compute_magnitude(current, baseline):
    if baseline == 0: return 0
    raw_ratio = abs(current - baseline) / abs(baseline)
    return 2 / (1 + exp(-raw_ratio * 3)) - 1

def compute_surprise(current, distribution):
    z = abs((current - distribution.mean) / distribution.std)
    if z > 3: return 1.0
    elif z > 2: return 0.7
    elif z > 1: return 0.3
    else: return 0.1

def compute_actionability(insight):
    score = 0
    if insight.has_recommended_action: score += 0.4
    if insight.responsible_team_known: score += 0.3
    if insight.action_within_tenant_capability: score += 0.3
    return score

def compute_recency(data_timestamp):
    age_days = (now() - data_timestamp).days
    return exp(-age_days / 30)
### Score → Severity
Score > 0.7   → CRITICAL
0.5 - 0.7     → HIGH
0.3 - 0.5     → MEDIUM
< 0.3         → LOW
## 21.4 12-Step Pipeline (Profile-Aware)
Step 1: Data refresh (3am)
       ↓
Step 2: Load business profile (Phần 1)
        + Active criteria for this profile (Phần 5)
        + Active formulas (Phần 15)
       ↓
Step 3: Generate candidate insight pool
   For each (metric × baseline_type × method):
     Run detection → if triggered, candidate
       ↓
Step 4: Score every candidate
       ↓
Step 5: Filter by score threshold
       ↓
Step 6: Dedupe (same insight from multiple methods → 1)
       ↓
Step 7: Cluster related insights
       ↓
Step 8: Apply Uncertainty Propagation (Phần 31)
       ↓
Step 9: Apply Archetype Filter (D6 from profile)
        - A1 SME: top 3 simple
        - A4 Enterprise: top 20 detailed
       ↓
Step 10: Apply Constraint Engine (Phần 32)
        Block insights → recommendations violating constraints
       ↓
Step 11: Compose narrative (LLM, anti-hallucination)
       ↓
Step 12: Generate explainability levels (Phần 30)
        Surface via Reports (Phần 26) or Alerts (Phần 24)
## 21.5 Acceptance Criteria — Phần 21
☐ Engine generates ≥30 candidates/day per active tenant
☐ All 8 detection methods implemented
☐ Master scoring formula validated
☐ Anti-hallucination 100%
☐ Pipeline E2E < 10min per tenant

# Phần 22. Threshold Discovery
Mục đích: Threshold values come from Criteria Registry, but for cold-start or non-criteria-defined thresholds, use 3-method discovery.
## 22.1 3 Methods
M1. STATISTICAL  — distribution-based (P5/P25/P75/P95)
M2. HISTORICAL   — tenant's own past as baseline
M3. BUSINESS     — industry benchmarks + tenant targets
## 22.2 Statistical Method
def percentile_thresholds(data_series):
    return {
        'low_unusual': np.percentile(data_series, 5),
        'low_warning': np.percentile(data_series, 25),
        'high_warning': np.percentile(data_series, 75),
        'high_unusual': np.percentile(data_series, 95),
        'extreme': np.percentile(data_series, 99),
    }

def iqr_thresholds(data_series):
    q1, q3 = np.percentile(data_series, [25, 75])
    iqr = q3 - q1
    return {
        'lower_outlier': q1 - 1.5 * iqr,
        'upper_outlier': q3 + 1.5 * iqr,
    }

def zscore_thresholds(data_series):
    mean, std = data_series.mean(), data_series.std()
    return {
        'normal': (mean - 1*std, mean + 1*std),
        'unusual': (mean - 2*std, mean + 2*std),
        'anomaly': (mean - 3*std, mean + 3*std),
    }
## 22.3 Historical Method
def historical_thresholds(tenant_id, metric_name, lookback_days=90):
    history = get_metric_history(tenant_id, metric_name, lookback_days)
    seasonal = detect_seasonality(history)
    
    if seasonal.is_seasonal:
        baseline = seasonal.detrended_mean
        std = seasonal.detrended_std
    else:
        baseline = history.mean()
        std = history.std()
    
    return {
        'baseline': baseline,
        'normal_range': (baseline - std, baseline + std),
        'warning_low': baseline - 2*std,
        'warning_high': baseline + 2*std,
        'alert_low': baseline - 3*std,
        'alert_high': baseline + 3*std,
        'context': {'seasonal': seasonal.is_seasonal}
    }
## 22.4 Business Method
From Criteria Registry (Phần 5-9). Strictest applicable wins.
## 22.5 Combination Algorithm
def propose_threshold(tenant_id, metric_name):
    # Try criteria registry first (priority)
    criteria_threshold = get_from_criteria_registry(metric_name, tenant_id)
    if criteria_threshold:
        return criteria_threshold  # registry wins
    
    # Fallback to discovery
    statistical = statistical_thresholds(get_metric_data(tenant_id, metric_name))
    historical = historical_thresholds(tenant_id, metric_name)
    
    if historical.samples_used >= 90 and historical.is_stable:
        return {
            'threshold': historical.warning_threshold,
            'confidence': 'high',
            'rationale': 'Historical baseline'
        }
    elif len(metric_data) >= 30:
        return {
            'threshold': statistical.unusual_high,
            'confidence': 'medium',
            'rationale': 'Statistical P95'
        }
    else:
        return {
            'threshold': None,
            'confidence': 'low',
            'rationale': 'Insufficient data',
            'recommendation': 'Wait 30+ days or set manually'
        }
## 22.6 Threshold Lifecycle
Re-evaluate every 30 days:
Day 30: Re-compute with new data
  ↓
Compare proposed vs current
  ↓
If significant deviation (>20%):
  → Notify Manager
  → Show data behind change
  → Manager approves/rejects

# Phần 23. Risk Detection
6 categories:
  A. Customer Risk  | B. Revenue Risk  | C. Operational Risk
  D. Financial Risk | E. Strategic Risk | F. Compliance Risk

4 methods:
  M1. Threshold-based  | M2. Pattern-based
  M3. Predictive Model | M4. Anomaly-based
## 23.1 Pattern-Based Detection
risk_patterns_examples:
  - pattern_id: "vip_recency_growing"
    detection: "VIP AND recency_days > P75 AND trend=increasing 4 weeks"
    risk: "churn_risk"
    severity: "HIGH"
    revenue_at_risk: "ltv * 0.6"
  
  - pattern_id: "top_customer_complaint"
    detection: "complaint.severity >= 'MEDIUM' AND customer.ltv > P90"
    severity: "CRITICAL"
  
  - pattern_id: "rapid_consecutive_returns"
    detection: "count(returns in 7 days) >= 3"
    risk: "fraud_risk OR satisfaction_risk"
    severity: "MEDIUM"
## 23.2 Risk Scoring
Risk Score = Probability × Impact × Imminence × (1/Reversibility)
             (0-1)         (VND)    (1-10)      (1-10)

→ CRITICAL > 100, HIGH > 30, MEDIUM > 10, LOW

# Phần 24. Alert System
## 24.1 Alert Anatomy (6 components)
alert:
  what: specific event
  why: root cause hypothesis
  when_detected, when_action_needed
  primary_owner, notify_also
  suggested_actions (with effort + impact)
  evidence (data sources, charts, similar past)
## 24.2 Severity Routing

| Severity | Response | Channels | Auto-escalate |
|---|---|---|---|
| CRITICAL | Immediate | All | Unack 1h → escalate |
| HIGH | Within 4h | Email + Slack + in-app | Unack 24h |
| MEDIUM | Same day | Email + in-app | No |
| LOW | Next day | In-app only | No |

## 24.3 Alert Fatigue Prevention
def should_suppress_alert(new_alert, recent):
    # Duplicate within hour
    if any(a.is_duplicate_of(new_alert) for a in recent.last_hour):
        return True
    
    # Frequency cap (>3/day for non-CRITICAL)
    metric_alerts = [a for a in recent.last_day if a.metric == new_alert.metric]
    if len(metric_alerts) > 3 and new_alert.severity != 'CRITICAL':
        return True
    
    # Existing unacknowledged same direction
    if any(a.metric == new_alert.metric and a.direction == new_alert.direction
           and a.acknowledged_at is None for a in recent.unacknowledged):
        return True
    
    # Quiet hours (unless CRITICAL)
    if is_quiet_hours(now()) and new_alert.severity != 'CRITICAL':
        return defer_until_morning
    
    return False
## 24.4 Confidence-Based Filter
Alert confidence < 0.5 → Don't send
0.5-0.7 → Send only if HIGH severity
> 0.7 → Send normal

# Phần 25. Analysis Frameworks
5 frameworks auto-populated from data:
## 25.1 Frameworks Catalog

| Framework | When to use |
|---|---|
| 6W2H | Drill into 1 specific issue |
| SWOT | Strategic position assessment |
| Fishbone (6M) | Root cause operational problem |
| Priority Matrix (RICE/ICE) | Prioritize multiple options |
| 5 Why | Deep dive 1 specific failure |

## 25.2 Auto-Population Rules
Every framework auto-populated from data with: - Citations for every claim - Anti-hallucination validation - LLM temperature 0.3 (low creativity, stick to facts) - User can edit before save
## 25.3 Selection Guide
def recommend_framework(situation):
    if situation.type == 'specific_issue_drill':
        return ['6W2H', '5_Why', 'Fishbone']
    elif situation.type == 'strategic_review':
        return ['SWOT']
    elif situation.type == 'multi_options':
        return ['Priority_Matrix']
    elif situation.type == 'operational_failure':
        return ['Fishbone', '5_Why']
    elif situation.type == 'health_check':
        return ['SWOT', '6W2H']

# PART VII — REPORTS
# Phần 26. Auto-Generated Reports (Profile-Aware)
Khác biệt v4.0: Reports không industry-fixed templates — dynamic based on profile.
## 26.1 Report Selection
def select_reports_for_tenant(tenant_id):
    profile = get_business_profile(tenant_id)
    
    # All applicable reports based on profile dimensions
    applicable = query_reports(filters={
        'industries': [profile.d1_industry.primary],
        'business_models': profile.d3_business_model,
        'lifecycle_stages': [profile.d5_lifecycle_stage.value],
        'archetypes': [profile.d6_archetype.value],
        'size': [profile.d4_size.size_label]
    })
    
    # Adapt content depth based on archetype
    for report in applicable:
        report = adapt_to_archetype(report, profile.d6_archetype.value)
    
    # Filter by tenant subscription quotas
    selected = filter_by_quota(applicable, tenant_id)
    
    return selected
## 26.2 Report Template (Profile-Aware)
report_template:
  template_id: string
  display_name: string
  
  # Profile applicability
  applies_to:
    industries: list | 'all'
    sub_domains: list | 'all'
    lifecycle_stages: list | 'all'
    archetypes: list | 'all'
    health_states: list | 'all'
  
  # Sections (with archetype variants)
  sections:
    - id: "executive_summary"
      type: "summary_box"
      data_source: "from criteria registry"
      archetype_variants:
        A1_SME: "simple_3_section"
        A4_Enterprise: "full_15_section"
    
    - id: "lifecycle_distribution"
      type: "chart"
      criteria_used: ["crit_lifecycle_states"]  # criteria-driven
    
    # ... more sections
  
  cadence: "daily"
  delivery_time: "07:00"
  recipients_default: ["dept_manager"]
## 26.3 Auto-Composition Engine
Same as v3.0/v3.1 — LLM composes narrative on top of structured data with anti-hallucination.

# Phần 27. Custom Report Builder
User-created reports với drag-drop UI + LLM-assisted NL-to-report.
(Mostly same mechanics as previous versions — see TOC.)

# Phần 28. Distribution & Delivery
(Email/Slack/Webhook/PDF — same mechanics as previous versions.)

# PART VIII — TRUST & EXPLAINABILITY
# Phần 29. Confidence Decomposition
4-component breakdown:
Total Confidence = f(
    DATA confidence (0.30),
    MODEL confidence (0.25),
    CALIBRATION confidence (0.25),
    CONTEXT confidence (0.20)
)

Geometric mean weighted (conservative)
def compute_data_confidence(features):
    completeness = 1 - (null_count / total_count)
    recency = exp(-avg_age_days / 30)
    source_quality = avg(get_source_quality_scores(features))
    return clip(completeness * recency * source_quality, 0.1, 1.0)

def compute_model_confidence(model_output):
    return max(model_output.probabilities)

def compute_calibration_confidence(model_id, tenant_id):
    recent_ece = get_recent_ece(model_id, tenant_id, last_days=30)
    if recent_ece < 0.05: return 1.0
    elif recent_ece < 0.10: return 0.85
    elif recent_ece < 0.15: return 0.70
    else: return 0.30

def compute_context_confidence(features, tenant_id):
    similar = memory.retrieve(tenant_id, query=features, type='episodic', top_k=20)
    if len(similar) < 5: return 0.4  # cold start
    outcome_consistency = compute_outcome_consistency(
        [s.outcome for s in similar if s.outcome is not None]
    )
    return clip(0.5 + outcome_consistency * 0.5, 0.4, 1.0)
## 29.1 Confidence Breakdown UI
┌──────────────────────────────────────────────────────────┐
│ INSIGHT: VIP retention dropping                          │
│ ────────────────────────────────────────────────────    │
│ Total Confidence: 0.61 (REVIEW NEEDED)                   │
│                                                          │
│ Why low? Confidence breakdown:                           │
│   📊 Data: 0.85 ✓                                       │
│   🎯 Model: 0.79 ✓                                      │
│   ⚖️  Calibration: 0.42 ⚠                               │
│   🧠 Context: 0.55 ⚠                                    │
│                                                          │
│ ⚠ Calibration low: model recent predictions ≠ actuals    │
│ ⚠ Context low: System hasn't seen many similar cases    │
│                                                          │
│ Recommendation: Manager review before action.            │
└──────────────────────────────────────────────────────────┘

# Phần 30. Explainability Hierarchy (3 Levels)
LEVEL 1: EXECUTIVE  — 1 line summary
LEVEL 2: ANALYST    — metrics + factors + comparison
LEVEL 3: AUDITOR    — full lineage + raw data
### Level 1
"234 VIP at risk · 187M revenue at stake · Recommend retention voucher (12x ROI)"
### Level 2
SUBJECT: VIP Retention Risk Q1 2026

KEY METRICS:
- Affected: 234 VIPs (10% of base)
- Revenue at risk: 187M VND (CI: 165M-209M)
- Trend: 38% recency increase WoW

TOP FACTORS (SHAP):
1. Voucher campaign gap (38%)
2. Email engagement decline (29%)
3. Inventory stockouts (24%)

CONFIDENCE: 0.78 (TRUSTED) — see breakdown
### Level 3
Full audit-grade with: decision_id, timestamp, all input features, model details, lineage chain, audit log, memory references, constraint checks.

# Phần 31. Uncertainty Propagation
Confidence propagates through layers:
Data Quality → Feature Quality → Model Confidence → 
Insight Confidence → Recommendation Confidence
def propagate_uncertainty(decision):
    data_quality = get_data_quality(decision.tenant_id)
    feature_quality = data_quality * 0.95
    model_conf = decision.model_intrinsic_confidence * feature_quality
    insight_conf = model_conf ** decision.insight_complexity_factor
    
    # Block if too low for action irreversibility
    if decision.action_reversibility < 0.5:
        confidence_required = 0.85
    else:
        confidence_required = 0.6
    
    if insight_conf < confidence_required:
        return BlockedRecommendation(
            reason="Insufficient confidence for irreversible action",
            confidence=insight_conf,
            required=confidence_required
        )
    
    return Recommendation(confidence=insight_conf)

# Phần 32. Constraint Engine — Safety Guardrails
## 32.1 6 Categories
1. BUDGET CONSTRAINTS
2. ROLE CONSTRAINTS
3. LEGAL/POLICY CONSTRAINTS
4. CONTRADICTION CONSTRAINTS
5. CAPACITY CONSTRAINTS
6. SAFETY CONSTRAINTS
## 32.2 Constraint Schema
constraint:
  constraint_id: UUID
  category: string
  
  applies_to:
    action_types: list
    tenant_archetypes: list | 'all'
  
  rule: string  # parseable expression
  
  data_required: list
  
  violation_severity: 'BLOCK' | 'WARN' | 'REQUIRE_APPROVAL'
  
  violation_message: string
  
  override_allowed:
    by_role: list
    requires_reason: bool
    requires_explicit_acknowledgment: bool
## 32.3 Validation Pipeline
def validate(recommendation, context):
    violations = []
    warnings = []
    
    for constraint in active_constraints:
        if not constraint.applies_to(recommendation):
            continue
        
        result = constraint.check(recommendation, context)
        
        if result.violated:
            if constraint.violation_severity == 'BLOCK':
                violations.append(result)
            elif constraint.violation_severity == 'WARN':
                warnings.append(result)
    
    return ValidationResult(
        passed=len(violations) == 0,
        blocking_violations=violations,
        warnings=warnings
    )

# PART IX — ACTION GENERATION
# Phần 33. Recommendation Engine
Mục đích: Insight → Action. Profile-aware, criteria-aware, constraint-validated.
## 33.1 Recommendation Anatomy
recommendation:
  rec_id: UUID
  
  # Source
  insight_id: UUID  # which insight triggered this
  business_profile_snapshot: object  # profile at recommendation time
  active_criteria_snapshot: list  # criteria active at this time
  
  # Action
  action_type: string  # 'send_voucher', 'reorder_inventory', 'reassign_account', etc.
  description: string
  description_vi: string
  
  # Justification
  rationale: string  # why this recommendation
  expected_outcome: object
    metric: string
    expected_lift: numeric  # e.g., +15% retention
    confidence_interval: [low, high]
  
  # Cost/Effort
  effort_required: 'low' | 'medium' | 'high'
  estimated_cost_vnd: numeric
  estimated_time_hours: numeric
  
  # Resources needed
  responsible_team: string
  required_capabilities: list
  
  # Constraints validated
  constraint_validation: object
    passed: bool
    blocking_violations: list
    warnings: list
  
  # Confidence
  confidence: numeric
  confidence_breakdown: object
  
  # Lifecycle
  status: 'proposed' | 'approved' | 'in_progress' | 'completed' | 'cancelled'
  proposed_at, approved_at, executed_at, completed_at
  approved_by: string
  
  # Outcome tracking
  actual_outcome: object | null  # filled post-execution
  outcome_vs_expected: object | null
## 33.2 Recommendation Generation Pipeline
Insight (from Phần 21)
       ↓
Step 1: Pattern Match — recommendation catalog lookup
   "VIP retention dropping" → known patterns:
     - Send retention voucher
     - Personal CSM outreach
     - Inventory restock priority
       ↓
Step 2: Profile-Aware Filtering
   Tenant archetype A1 SME → simpler actions only
   Tenant archetype A4 Enterprise → multi-step playbooks OK
       ↓
Step 3: Criteria-Aware Validation
   Recommendation must align with active criteria
   E.g., "Increase risk exposure" blocked if criteria say "reduce risk"
       ↓
Step 4: Effort/Impact Estimation
   ROI = expected_lift × revenue_at_risk / estimated_cost
       ↓
Step 5: Constraint Engine Validation (Phần 32)
   - Budget check
   - Role authorization
   - Capacity check
   - Legal/policy check
       ↓
Step 6: Confidence Computation
   Pull from insight confidence + propagate through action plan
       ↓
Step 7: Sort by Score
   Score = (Impact × Confidence × Reversibility) / Effort
       ↓
Step 8: Top-N selection per archetype
   A1: top 1 simple action
   A4: top 5 with ranking
       ↓
Step 9: Compose narrative + explanation (3-level per Phần 30)
       ↓
Surface to Manager via Reports/Alerts
## 33.3 Recommendation Scoring
def score_recommendation(rec):
    impact = rec.expected_outcome.expected_lift * get_revenue_at_risk(rec.insight)
    confidence = rec.confidence
    reversibility = rec.action_reversibility  # 0-1, easy-to-undo = 1
    effort = rec.effort_required_normalized  # 0.1-1, low-effort = 0.1
    risk_penalty = 1 - rec.action_risk_score
    
    score = (impact * confidence * reversibility * risk_penalty) / effort
    
    return score
## 33.4 Recommendation Catalog
Pre-built playbooks library:
recommendation_catalog:
  
  - pattern: "vip_retention_decline"
    actions:
      - id: "retention_voucher_personalized"
        applies_to: 
          archetypes: ["A2", "A3", "A4"]
          industries: ["retail", "fb", "ecommerce"]
        effort: low
        expected_lift: "12% retention recovery"
        cost_estimate_per_customer: 50000
      
      - id: "csm_personal_outreach"
        applies_to:
          archetypes: ["A4"]
          customer_segment: "VIP"
        effort: medium
        expected_lift: "25% retention recovery"
        requires: "CSM team"
  
  - pattern: "inventory_stockout_top_seller"
    actions:
      - id: "expedited_reorder"
        applies_to: ["retail", "ecommerce"]
        effort: low
      - id: "supplier_diversification"
        applies_to: ["retail"]
        effort: high
  
  # ... extensible catalog
## 33.5 Acceptance Criteria — Phần 33
☐ Recommendations always tied to insight + criteria
☐ All recommendations pass Constraint Engine
☐ Profile-aware filtering enforced
☐ Outcome tracking 100% of executed actions
☐ Catalog extensible without code change

# Phần 34. Improvement Roadmap (3 Horizons)
Mục đích: Single recommendation = tactical. Roadmap = strategic 3-horizon plan.
## 34.1 3 Horizons
HORIZON 1: 0-3 months  — Quick wins (low effort, high impact)
HORIZON 2: 3-12 months — Strategic improvements (medium effort)
HORIZON 3: 12-36 months — Transformations (high effort, high impact)
## 34.2 Roadmap Structure
improvement_roadmap:
  tenant_id: UUID
  generated_at: timestamp
  business_profile_snapshot: object
  
  horizon_1_quick_wins:
    duration: "0-3 months"
    items:
      - title: "Implement VIP retention voucher program"
        rationale: "10% VIP at risk, ROI 12x"
        effort: "Low (2 weeks)"
        cost: "5M VND"
        expected_impact: "+187M VND retained revenue"
        owner: "Marketing"
        kpi_to_track: "vip_retention_rate"
      # ... more items
    total_expected_impact: numeric
  
  horizon_2_strategic:
    duration: "3-12 months"
    items:
      - title: "Implement customer 360 data platform"
        rationale: "Foundation for advanced personalization"
        effort: "High (6 months)"
        cost: "500M VND"
        expected_impact: "Enable Horizon 3 transformation"
        dependencies: ["Horizon 1 complete"]
      # ...
  
  horizon_3_transformations:
    duration: "12-36 months"
    items:
      - title: "AI-powered dynamic pricing"
        rationale: "Industry-leading position"
        effort: "Very High (18 months)"
        cost: "2B VND"
        expected_impact: "+15% gross margin"
        dependencies: ["Horizon 2 platform complete"]
      # ...

  total_summary:
    total_horizon_1_impact: 500M VND
    total_horizon_2_impact: 2B VND
    total_horizon_3_impact: 8B VND
    npv_total: 7.5B VND
## 34.3 Roadmap Adaptation
Roadmap re-evaluated when: - Profile changes (Phần 4 triggers) - Major strategic shift declared by tenant - Roadmap items completed/failed - External market events
def adapt_roadmap(tenant_id, change_event):
    current_roadmap = get_active_roadmap(tenant_id)
    
    if change_event.type == 'profile_changed':
        # Re-evaluate which items still relevant
        for item in current_roadmap.all_items:
            if not still_applicable(item, new_profile):
                item.status = 'no_longer_applicable'
        
        # Generate new items if gaps
        new_items = generate_for_new_profile(new_profile)
        current_roadmap.add(new_items)
    
    elif change_event.type == 'item_completed':
        # Promote dependent items
        promote_unblocked_items(current_roadmap, completed_item=change_event.item)
    
    elif change_event.type == 'major_market_event':
        # Re-prioritize all
        re_score_all_items(current_roadmap, new_context=change_event)
    
    save_roadmap_version(current_roadmap)
## 34.4 Acceptance Criteria — Phần 34
☐ Every active tenant has current roadmap
☐ 3 horizons populated with real items (not template)
☐ Items linked to insights + criteria + recommendations
☐ Roadmap auto-adapts on triggers
☐ Progress tracking per horizon

# PART X — CONTINUOUS EVOLUTION
# Phần 35. Continuous Re-Evaluation Loop
Mục đích: Address core concern — “doanh nghiệp luôn thay đổi → liên tục update”. This is the heart of v4.0 adaptive system.
## 35.1 Evolution Loop Architecture
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│      ┌──────────────┐                                       │
│      │   PROFILE    │ ← re-detected on triggers (Phần 4)   │
│      │   (Phần 1-4) │                                       │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────┐                                       │
│      │  CRITERIA    │ ← updated by RAG (Phần 12)           │
│      │  (Phần 5-9)  │ ← refreshed quarterly                │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────┐                                       │
│      │  FORMULAS    │ ← adapt when criteria change          │
│      │ (Phần 15-20) │   (Phần 17 pipeline)                 │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────┐                                       │
│      │  REASONING   │ ← per-tenant per-day                  │
│      │ (Phần 21-32) │                                       │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────┐                                       │
│      │   ACTIONS    │ ← outcomes tracked                    │
│      │ (Phần 33-34) │                                       │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────┐                                       │
│      │  OUTCOMES    │ ← feedback loop                       │
│      │  & MEMORY    │                                       │
│      └──────┬───────┘                                       │
│             │                                               │
│             ↓                                               │
│      ┌──────────────────────────────┐                      │
│      │  TRIGGERS:                   │                      │
│      │  - State change?             │                      │
│      │  - New regulation?           │                      │
│      │  - Outcome unexpected?       │                      │
│      │  - Performance drift?        │                      │
│      └──────────────┬───────────────┘                      │
│                     │                                       │
│                     │  triggers re-evaluation               │
│                     └───────────→ back to PROFILE          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
## 35.2 Re-Evaluation Cadences
re_evaluation_cadences:
  
  daily:
    - business_state_recompute (Phần 3)
    - insight_generation (Phần 21)
    - alert_evaluation (Phần 24)
    - regulatory_change_detection (Phần 12)
  
  weekly:
    - tenant_engagement_analysis
    - threshold_appropriateness_check
    - tier_3_market_source_crawl
  
  monthly:
    - tenant_profile_drift_check
    - criteria_freshness_review
    - formula_performance_review
    - tenant_archetype_re-detection
    - tenant_curated_criterion_review
    - roadmap_progress_review
  
  quarterly:
    - full_profile_re_detection (mandatory, Phần 4)
    - active_criteria_reconciliation
    - formula_engine_audit
    - tenant_health_trend_analysis
    - cross_tenant_pattern_validation
  
  annually:
    - knowledge_source_audit (which sources still valid)
    - master_method_evaluation
    - industry_coverage_review
    - constraint_engine_review
## 35.3 Event-Driven Re-Evaluation
class EvolutionLoopOrchestrator:
    
    def on_event(self, event):
        if event.type == 'data_quality_drop':
            self.flag_affected_insights()
            self.notify_data_team()
        
        elif event.type == 'profile_drift_detected':
            self.trigger_re_profile(event.tenant_id)
        
        elif event.type == 'regulatory_update':
            self.trigger_criteria_review(event.affected_criteria)
            self.trigger_formula_adaptation(event.affected_formulas)
            self.notify_affected_tenants(event)
        
        elif event.type == 'outcome_unexpected':
            self.trigger_recommendation_review(event.recommendation)
            self.update_pattern_catalog(event)
        
        elif event.type == 'performance_drift':
            self.trigger_model_retraining(event.model)
        
        elif event.type == 'major_market_event':
            self.trigger_global_re_evaluation()
## 35.4 Drift Detection
def detect_drift(tenant_id):
    """Run daily — detect drift in multiple dimensions."""
    drifts = []
    
    # Drift 1: Profile drift
    current_profile = get_current_profile(tenant_id)
    profile_signal = compute_profile_signature(get_current_data(tenant_id))
    if signature_diverges(profile_signal, current_profile.signature):
        drifts.append(Drift(type='profile_drift'))
    
    # Drift 2: Performance drift  
    expected_perf = current_profile.expected_metric_ranges
    actual_perf = get_recent_metrics(tenant_id, days=30)
    if metrics_outside_expected(actual_perf, expected_perf):
        drifts.append(Drift(type='performance_drift'))
    
    # Drift 3: Recommendation outcome drift
    recent_recs = get_recent_recommendations(tenant_id, days=90)
    actual_outcomes = [r.actual_outcome for r in recent_recs if r.actual_outcome]
    expected_outcomes = [r.expected_outcome for r in recent_recs if r.actual_outcome]
    
    if mean_diff(actual_outcomes, expected_outcomes) > 0.3:
        drifts.append(Drift(type='recommendation_outcome_drift'))
    
    # Drift 4: Engagement drift
    engagement = compute_engagement(tenant_id, days=30)
    if engagement < baseline * 0.7:
        drifts.append(Drift(type='engagement_drift'))
    
    return drifts
## 35.5 Acceptance Criteria — Phần 35
☐ Daily/weekly/monthly/quarterly cadences automated
☐ Drift detection running daily
☐ Event-driven triggers operational
☐ Loop closure: outcomes feed back to refine profiling/criteria/formulas
☐ Audit log: every re-evaluation logged with reason

# Phần 36. Tenant Maturity Tracking
Mục đích: Tenants mature over time. System should detect + leverage.
## 36.1 Maturity Dimensions
tenant_maturity:
  
  data_maturity:
    metrics: [data_quality_score, source_count, history_months, data_team_exists]
    levels: [chaotic, basic, organized, advanced, optimized]
  
  process_maturity:
    metrics: [process_documentation, automation_level, error_rate, cycle_time_consistency]
    levels: [ad_hoc, repeatable, defined, managed, optimizing]  # CMM-inspired
  
  analytics_maturity:
    metrics: [reports_used, dashboards_active, custom_metrics_count, advanced_features_used]
    levels: [descriptive, diagnostic, predictive, prescriptive, autonomous]
  
  decision_maturity:
    metrics: [decisions_data_driven, time_to_decision, decision_outcome_tracking]
    levels: [intuition, mixed, data_supported, data_driven, data_native]
## 36.2 Maturity Computation
def compute_tenant_maturity(tenant_id):
    profile = get_business_profile(tenant_id)
    usage = get_tenant_usage_metrics(tenant_id)
    outcomes = get_outcome_tracking(tenant_id)
    
    return {
        'data_maturity': compute_data_maturity(profile, usage),
        'process_maturity': compute_process_maturity(profile),
        'analytics_maturity': compute_analytics_maturity(usage),
        'decision_maturity': compute_decision_maturity(outcomes),
        'composite_maturity_index': weighted_composite(...)
    }
## 36.3 Maturity-Driven Adaptations
maturity_driven_adaptations:
  
  when_data_maturity_increases:
    - upgrade formula variants (Phần 20)
    - enable advanced features (predictive models)
    - increase insight surfacing volume (more capacity to consume)
  
  when_decision_maturity_increases:
    - reduce hand-holding in narratives
    - surface more quantitative outputs
    - add advanced frameworks (Bayesian, causal)
  
  when_process_maturity_increases:
    - enable automation suggestions
    - cross-process optimization recommendations
  
  when_analytics_maturity_increases:
    - enable self-service analytics features
    - reduce mediated reasoning (let user explore directly)
## 36.4 Maturity Notification
"Your data has matured to Level 3 (Organized)"
       ↓
"Unlock predictive analytics — would you like:"
  ☐ Customer churn prediction model
  ☐ Demand forecasting
  ☐ Predictive maintenance (manufacturing)
       ↓
Tenant opts in → upgrade applies
## 36.5 Acceptance Criteria — Phần 36
☐ Maturity tracked across 4 dimensions monthly
☐ Maturity progression visible to tenant
☐ Auto-suggestions when maturity unlocks new capabilities
☐ System adapts complexity based on maturity

# Phần 37. System Self-Improvement
Mục đích: System learns from outcomes across all tenants → improves itself.
## 37.1 Learning Loops
learning_loops:
  
  loop_1_recommendation_outcome:
    cadence: continuous
    inputs: [recommendation, actual_outcome, expected_outcome]
    learning: pattern catalog refinement
    output: updated recommendation effectiveness scores
  
  loop_2_threshold_calibration:
    cadence: monthly
    inputs: [threshold, alert_outcomes, false_positive_rates]
    learning: threshold tuning per profile
    output: refined default thresholds
  
  loop_3_criteria_efficacy:
    cadence: quarterly
    inputs: [criteria, tenant outcomes using these criteria]
    learning: which criteria predict good outcomes
    output: criteria authority scoring updates
  
  loop_4_pattern_discovery:
    cadence: monthly
    inputs: [aggregated tenant data, success patterns]
    learning: new patterns to add to catalog
    output: candidate patterns for review
  
  loop_5_archetype_refinement:
    cadence: quarterly
    inputs: [tenant profiles + outcomes]
    learning: archetype boundaries that better predict outcomes
    output: updated archetype definitions
## 37.2 Cross-Tenant Privacy-Preserving Learning
def cross_tenant_learning_privacy_safe():
    """
    Learn patterns without exposing tenant data.
    """
    # Aggregate to industry level (k-anonymity ≥ 10)
    # Differential privacy for aggregate statistics
    # No tenant-specific patterns leak
    
    # Example: "Across 80 retail tenants, recommendation X has 67% success rate"
    # NOT: "Tenant ABC's strategy works"
    
    aggregated = aggregate_with_dp(
        all_recommendations,
        epsilon=1.0,
        min_cohort_size=10
    )
    
    # Update global pattern catalog
    update_patterns(aggregated)
    
    # NEVER write back tenant-specific data to global catalog
## 37.3 Self-Improvement Constraints
constraints_on_self_improvement:
  
  must_not_do:
    - leak_tenant_data_in_aggregates
    - update_tier_1_regulatory_criteria_automatically (always human review)
    - make_changes_without_audit_log
    - degrade_existing_tenant_outcomes_for_global_optimization
  
  must_do:
    - human_review_for_material_pattern_updates
    - announce_changes_in_release_notes
    - allow_tenant_opt_out_of_global_learning
    - maintain_explainability_post_learning
## 37.4 Acceptance Criteria — Phần 37
☐ Learning loops operational
☐ Privacy-preserving aggregation enforced
☐ Material updates require human review
☐ Tenant opt-out respected
☐ Audit log of all self-improvement updates

# PART XI — RISK MANAGEMENT
# Phần 38. AI Insight Risk Inventory (24 Risks)
Mục đích: Catalog risks specific to AI generating insights.
## 38.1 6 Categories Overview
A. Generation Risks    (5 risks)
B. Interpretation     (4 risks)
C. Operational        (5 risks)
D. User Behavior      (4 risks)
E. System/Adversarial (3 risks)
F. Compliance/Ethical (3 risks)
                Total: 24 risks
## 38.2 Category A — Generation

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| A1 | False Positive | HIGH | Insight→action→outcome tracking | FDR correction; min confidence 0.65 |
| A2 | False Negative | HIGH | AI vs human analyst quarterly | Multiple methods parallel; pattern catalog fresh |
| A3 | Hallucination | CRITICAL | Number/quote validation | LLM temp 0.3; post-gen validation; strict citation |
| A4 | Bias Amplification | HIGH | Fairness metrics audit | Fairness constraints; Constraint Engine |
| A5 | Causation Confusion | MEDIUM | Manual review causal claims | Use “correlate” until A/B validated |

## 38.3 Category B — Interpretation

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| B1 | Anchoring Bias | HIGH | Approval-without-modification rate | Show alternatives top-3; uncertainty highlighted |
| B2 | Oversimplification | MEDIUM | Single-number reliance | Multi-dim breakdown always shown |
| B3 | Context Blindness | MEDIUM | Cross-reference calendar/campaigns | Inject context; suppress expected anomalies |
| B4 | Information Overload | HIGH | Engagement rate tracking | Strict caps per archetype; smart digests |

## 38.4 Category C — Operational

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| C1 | Model Drift | HIGH | Phần 35 drift detection | Auto-retrain; calibration monitoring |
| C2 | Stale Catalog | MEDIUM | Quarterly review | Expiration dates; auto-flag unused |
| C3 | Cross-Tenant Contamination | HIGH | Pattern source audit | Strict isolation; provenance tracking |
| C4 | Threshold Erosion | MEDIUM | Track threshold changes | Manager approval; floor at industry benchmark |
| C5 | Pipeline Cascade Failure | CRITICAL | Data quality scorecard | Halt insight gen if quality < 60 |

## 38.5 Category D — User Behavior

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| D1 | Over-Automation | HIGH | % auto-approved | HIGH-impact cannot auto-approve |
| D2 | Adversarial User (Gaming) | HIGH | Veracity detection (Pipeline §19.14) | Cross-reference; manager review |
| D3 | Confirmation Bias | MEDIUM | Dismissal patterns by user | Surface dismissed-type insights |
| D4 | Insight Fatigue | HIGH | Engagement decline | Adaptive surfacing volume |

## 38.6 Category E — System/Adversarial

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| E1 | Data Poisoning | HIGH | Anomalous training data | Source validation; outlier detection |
| E2 | Prompt Injection | HIGH | Input sanitization | Strict templates; output validation |
| E3 | Model Inversion | HIGH | Membership inference tests | Differential privacy; aggregate-only |

## 38.7 Category F — Compliance/Ethical

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| F1 | Privacy Leak via Inference | CRITICAL | k-anonymity check | Min cohort size 10; suppress rare combos |
| F2 | Discrimination | CRITICAL | Fairness audit | Constraint Engine; human review high-stakes |
| F3 | Regulatory Violation | CRITICAL | Industry compliance rules | Industry constraint packs; compliance review |


# Phần 39. Adaptive-System-Specific Risks (NEW)
Mục đích: v4.0 adaptive system introduces NEW risk categories specific to dynamic criteria + adaptive formulas.
## 39.1 New Risk Categories
G. Criteria Registry Risks (5 risks)
H. Adaptive Formula Risks (4 risks)
I. RAG-Specific Risks (3 risks)
J. Continuous Evolution Risks (3 risks)
                       Total: 15 new risks
## 39.2 Category G — Criteria Registry Risks

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| G1 | Criteria Injection Attack | CRITICAL | Source authority validation | Whitelist sources; strict tier authority |
| G2 | Criteria Conflict Cascade | HIGH | Dry-run before activation | Conflict resolution algorithm; dry-run |
| G3 | Tenant Criterion Abuse | MEDIUM | Quotas + admin review | Quota per plan; abuse detection |
| G4 | Criteria Versioning Confusion | HIGH | Version pin per query | Explicit version pinning; audit log |
| G5 | Stale Active Criterion | MEDIUM | Freshness scoring | Auto-flag if not reviewed 12+ months |

## 39.3 Category H — Adaptive Formula Risks

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| H1 | Formula Drift Without Detection | HIGH | Continuous backtest comparison | Shadow mode; monitoring |
| H2 | Formula Cascade Break | CRITICAL | Coupling graph validation | Pre-deployment cascade simulation |
| H3 | Adaptive Loop Instability | HIGH | Convergence checks | Damping; stability validation |
| H4 | Formula Approval Bypass | CRITICAL | Audit log + dual-control | 2-person rule for high-stakes |

## 39.4 Category I — RAG-Specific Risks

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| I1 | RAG Source Compromise | CRITICAL | Source integrity checks | Hash-based integrity; multi-source verify |
| I2 | RAG Retrieval Poisoning | HIGH | Relevance scoring + validation | Cross-encoder re-rank; authority filter |
| I3 | Citation Fabrication | CRITICAL | Citation existence check | Provenance validation; quote exactness |

## 39.5 Category J — Continuous Evolution Risks

| ID | Risk | Severity | Detection | Mitigation |
|---|---|---|---|---|
| J1 | Re-evaluation Loop Storm | HIGH | Loop frequency monitoring | Rate limiting; cooldown periods |
| J2 | Self-Improvement Regression | HIGH | A/B compare before promote | Shadow learning; opt-in rollout |
| J3 | Profile Thrashing | MEDIUM | Profile change frequency | Hysteresis; minimum stability period |

## 39.6 Risk Severity Matrix (39 Total Risks)
                          Likelihood
                       LOW  MED  HIGH  
Severity         ┌─────┬────┬────┬────┐
CRITICAL (8)     │ A3  │ F1 │ G1 │    │
                 │ C5  │ F2 │ H4 │    │
                 │ E1  │ F3 │ I1 │    │
                 │ I3  │ H2 │    │    │
HIGH (15)        │ E2  │ A2 │ A4 │ B1 │
                 │ E3  │ B4 │ C1 │ D1 │
                 │     │ C3 │ D2 │ D4 │
                 │     │ G2 │ G4 │ H1 │
                 │     │ H3 │ I2 │ J1 │
                 │     │ J2 │    │    │
MEDIUM (12)      │     │ A5 │ B2 │ B3 │
                 │     │ C2 │ C4 │ D3 │
                 │     │ G3 │ G5 │ J3 │
LOW (4)          │     │    │    │    │
                 └─────┴────┴────┴────┘

Phase 1 priority: Address all CRITICAL (8) + HIGH (15) = 23 risks
Phase 2: Add MEDIUM mitigations
## 39.7 Risk Monitoring Dashboard
risk_monitoring_dashboard:
  
  daily_metrics:
    - hallucination_rate (target < 0.5%)
    - false_positive_rate (target < 20%)
    - model_drift_alerts (count)
    - constraint_violations (count)
    - veracity_violations (count)
    - criteria_injection_attempts (count, target = 0)
    - formula_cascade_failures (count, target = 0)
    - rag_citation_validation_failures (count)
  
  weekly_metrics:
    - insight_engagement_rate
    - dismissal_patterns
    - approval_without_review_rate
    - cross_tenant_isolation_audit
    - criteria_freshness_distribution
    - formula_drift_indicators
  
  monthly_metrics:
    - fairness_audit_results
    - calibration_drift trend
    - pattern_catalog_freshness
    - compliance_review_summary
    - tenant_criterion_quality_scores
    - adaptive_loop_stability_metrics
## 39.8 Incident Response
incident_response_v4:
  
  P0_critical:
    response_time: < 15 min
    examples:
      - hallucination producing financial harm
      - criteria injection attack detected
      - regulatory violation
      - privacy leak
    actions:
      - halt affected pipelines
      - notify CTO + compliance
      - preserve evidence
      - rollback if necessary
  
  P1_high:
    response_time: < 4h
    examples:
      - model drift detected
      - mass false positives
      - formula cascade failure
      - profile thrashing
    actions:
      - investigate root cause
      - rollback if needed
      - notify product + ML team
  
  P2_medium:
    response_time: < 1 day
    examples:
      - pattern catalog stale
      - alert overload
      - tenant criterion abuse
    actions:
      - schedule fix in next sprint
      - communicate workaround

# PART XII — IMPLEMENTATION
# Phần 40. Phase Scope (1/2/3)
## 40.1 Phase 1 (Months 1-4) — Foundation
phase_1_scope:
  
  business_profiling:
    - 8-dimensional profile schema implemented
    - Industry detection (data signature for top 6 industries)
    - State + trajectory tracking daily
    - Re-profile quarterly
  
  criteria_registry:
    - First-class objects with lifecycle
    - 200+ initial criteria curated
    - Tenant-custom criteria UI
    - Conflict resolution operational
  
  rag_engine:
    - Tier 1 (regulatory) crawler operational for SBV + key sources
    - Tier 2 (curated) library built
    - Tier 4 (tenant) upload operational
    - Anti-hallucination 100%
  
  adaptive_formulas:
    - Parameterized template system
    - Coupling tracked
    - Adaptation pipeline manual approval
    - Versioning + rollback
  
  reasoning:
    - All 8 detection methods
    - Master scoring formula
    - Profile-aware filtering
    - 5 analysis frameworks
  
  trust_layer:
    - Confidence decomposition (4 components)
    - 3-level explainability
    - Constraint engine (6 categories)
  
  not_in_phase_1:
    - Tier 3 paid market sources
    - Self-improvement loops
    - Multi-agent decomposition
    - Cross-tenant learning
## 40.2 Phase 2 (Months 5-12) — Expansion
phase_2_scope:
  
  - Tier 3 market source integration
  - Self-improvement loops 1-2
  - Master expertise tier 2 for retail + F&B
  - Industry expansion (+6 industries Tier 1)
  - Federated learning prototype
  - Advanced predictive models
  - Cross-tenant pattern discovery (privacy-preserved)
## 40.3 Phase 3 (Year 2+) — Mastery
phase_3_scope:
  
  - Tier 3 master expertise (1-2 industries deep)
  - Multi-agent decomposition
  - Causal inference engine
  - Simulation/what-if modeling
  - Reinforcement learning for recommendations
  - Autonomous criterion proposal

# Phần 41. Tech Stack & Architecture
tech_stack:
  
  data_layer:
    - PostgreSQL 15+ (criteria registry, formulas, profiles)
    - ClickHouse (analytics + aggregations)
    - pgvector OR Weaviate (vector store for RAG)
    - Redis (hot cache)
  
  compute:
    - Python 3.11+ (reasoning logic)
    - PySpark / DuckDB (batch processing)
    - FastAPI (API layer)
  
  ml:
    - scikit-learn, xgboost, lifelines (classical)
    - PyTorch (deep learning)
    - HuggingFace Transformers (embeddings)
    - LangChain or LlamaIndex (RAG orchestration)
  
  llm:
    - Anthropic Claude (primary for reasoning)
    - OpenAI GPT-4 (alternative)
    - Local models (Qwen, Llama) for sensitive ops
  
  infra:
    - Kubernetes (orchestration)
    - Argo Workflows (pipeline orchestration)
    - Prometheus + Grafana (monitoring)
    - OpenTelemetry (tracing)
  
  storage:
    - S3-compatible (documents, ingestion)
    - MinIO for self-hosted
  
  search:
    - Elasticsearch / OpenSearch (BM25)
    - pgvector / Qdrant (dense vector)
    - Cross-encoder for reranking

# Phần 42. Anti-patterns
anti_patterns:
  
  AP1_hard_coding_thresholds_in_application_code:
    why_bad: violates dynamic criteria principle
    instead: store in criteria registry
  
  AP2_industry_first_branching:
    why_bad: rigid; misses sub-domain
    instead: profile-based composable strategy
  
  AP3_skipping_backtest_before_promote:
    why_bad: silent regressions
    instead: mandatory backtest gates
  
  AP4_rag_without_provenance:
    why_bad: hallucination + audit failure
    instead: full citation chain
  
  AP5_silent_self_improvement:
    why_bad: opaque changes; tenant trust loss
    instead: announce + opt-out + audit log
  
  AP6_profile_thrashing:
    why_bad: instability; reasoning churn
    instead: hysteresis + min stability period
  
  AP7_skipping_constraint_engine:
    why_bad: unsafe recommendations
    instead: ALL recommendations validated
  
  AP8_cross_tenant_pattern_leak:
    why_bad: privacy violation
    instead: strict isolation + DP for aggregates
  
  AP9_outdated_criteria_used:
    why_bad: outdated reasoning; compliance risk
    instead: freshness scoring + auto-flag
  
  AP10_recommendation_without_outcome_tracking:
    why_bad: no learning; can't improve
    instead: 100% outcome tracking

# Phần 43. Quality KPIs
quality_kpis:
  
  reasoning_quality:
    insight_precision: ≥ 80% (validated by user feedback)
    insight_recall: ≥ 80% (vs human analyst quarterly)
    hallucination_rate: < 0.5%
    confidence_calibration_ece: < 0.10
    false_positive_rate: < 20%
  
  system_performance:
    insight_pipeline_e2e: < 10min per tenant
    rag_query_latency: < 500ms p95
    formula_execution: < 3s typical
    profile_detection: < 30min for new tenant
    re_profile_completion: < 1h
  
  adaptive_system_health:
    criteria_freshness_pct: ≥ 90% reviewed last 12 months
    formula_drift_alerts_per_month: < 5
    tenant_profile_thrash_rate: < 5%
    rag_citation_accuracy: 100%
    self_improvement_regressions: 0 P0 incidents
  
  user_experience:
    insight_engagement_rate: ≥ 70% read
    recommendation_approval_rate: 60-90% (range = healthy)
    alert_response_time: median < 4h
    explanation_satisfaction: ≥ 4/5
    tenant_retention_yoy: ≥ 95%
  
  trust_metrics:
    constraint_violations: 0 unresolved
    privacy_audits_passed: 100%
    fairness_audits_passed: 100%
    compliance_reviews_passed: 100%
    audit_log_completeness: 100%

# Tóm tắt v4.0 vs v3.1

| Aspect | v3.1 | v4.0 (paradigm shift) |
|---|---|---|
| Industry approach | Industry-first (6 hard-coded) | Industry-agnostic profiling (8-dim) |
| Criteria | Hard-coded thresholds | Dynamic registry, hot-reloadable |
| Knowledge updates | Manual updates | RAG-driven, daily regulatory crawl |
| Formulas | Static functions | Parameterized templates, adapt to criteria |
| State tracking | Snapshot daily | Continuous + trajectory + tempo + stress |
| Tenant evolution | Static archetype | Multi-dim maturity tracking |
| Custom criteria | Limited | Full lifecycle, builder UI, library promotion |
| Conflict resolution | Implicit | Explicit hierarchy + algorithm |
| Risks covered | 24 | 39 (added 15 adaptive-system-specific) |
| Self-improvement | Manual | Privacy-preserving learning loops |
| Sections | 27 | 43 |
| Parts | 10 | 12 |
| Words | ~23,100 | ~28,000+ |

## Triết lý fundamental
v3.1: "Pre-define rules, apply to industries"

v4.0: "Define adaptive infrastructure;
       Profile any business;
       Discover relevant criteria from current knowledge;
       Adapt formulas as criteria evolve;
       Track continuous changes;
       Learn from outcomes;
       All transparent + auditable + tenant-controllable"
Key insight: v4.0 không cần biết “doanh nghiệp này thuộc ngành gì” trước. System tự profile, tự pick criteria mới nhất từ RAG, tự adapt formula theo criteria, tự re-evaluate khi business thay đổi. Industry chỉ là 1 trong 8 dimensions, không phải starting point.