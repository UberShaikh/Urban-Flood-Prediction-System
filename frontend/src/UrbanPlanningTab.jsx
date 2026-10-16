import React, { useState } from 'react';
import {
  Building2, AlertTriangle, CheckCircle, ShieldAlert, MapPin,
  TrendingUp, Layers, Zap, ArrowRight, Info, Leaf, Home, Droplets
} from 'lucide-react';

const URBAN_DATA = {
  mumbai: {
    encroachmentLevel: 'CRITICAL',
    encroachmentPct: 78,
    constructionZones: [
      { zone: 'Dharavi Basin', risk: 'CRITICAL', reason: 'Below sea level, zero drainage', action: 'Construction ban enforced' },
      { zone: 'Kurla Floodplain', risk: 'HIGH', reason: 'Active drainage channel blocked', action: 'Immediate clearance required' },
      { zone: 'Andheri Lowlands', risk: 'HIGH', reason: 'Water table saturation zone', action: 'No new permits to be issued' },
      { zone: 'Bandra-Kurla Complex', risk: 'MODERATE', reason: 'Reclaimed land, subsidence risk', action: 'Structural audit mandatory' },
    ],
    suggestions: [
      { icon: Droplets, tag: 'Drainage', text: 'Increase drainage capacity in Dharavi Basin by 3x. Install underground retention tanks.' },
      { icon: Building2, tag: 'Zoning', text: 'Enforce strict no-construction buffer of 500m from Mithi River banks.' },
      { icon: Leaf, tag: 'Green Infra', text: 'Deploy mangrove restoration along 12km of coastal buffer zone to reduce wave surge.' },
      { icon: Home, tag: 'Relocation', text: 'Relocate 4,200 households from Zone A (Dharavi) to elevated cluster housing.' },
    ],
    sdgScore: 42,
    drainageCoverage: 38,
    greenCoverage: 12,
  },
  chennai: {
    encroachmentLevel: 'HIGH',
    encroachmentPct: 61,
    constructionZones: [
      { zone: 'Adyar Estuary', risk: 'CRITICAL', reason: 'Estuarine flood corridor', action: 'Full construction moratorium' },
      { zone: 'Velachery Lake Bed', risk: 'HIGH', reason: 'Former lake, filled illegally', action: 'Environmental tribunal review' },
      { zone: 'Sholinganallur', risk: 'HIGH', reason: 'Backwater zone, reclaimed', action: 'Retrofit drainage mandatory' },
      { zone: 'Pallikaranai Marsh', risk: 'MODERATE', reason: 'Wetland buffer degraded', action: 'Wetland restoration plan' },
    ],
    suggestions: [
      { icon: Droplets, tag: 'Drainage', text: 'Restore 57 lakes and water bodies in greater Chennai area.' },
      { icon: Building2, tag: 'Zoning', text: 'Enforce coastal regulation zone CRZ-III for all new constructions.' },
      { icon: Leaf, tag: 'Green Infra', text: 'Protect and expand Pallikaranai marshland as natural flood buffer.' },
      { icon: Home, tag: 'Planning', text: 'Implement storm-water master plan for 820 km of road network.' },
    ],
    sdgScore: 54,
    drainageCoverage: 45,
    greenCoverage: 18,
  },
  bengaluru: {
    encroachmentLevel: 'MODERATE',
    encroachmentPct: 44,
    constructionZones: [
      { zone: 'Bellandur Lake', risk: 'HIGH', reason: 'Severely polluted, flooding risk', action: 'Buffer zone enforcement' },
      { zone: 'Varthur Kere', risk: 'HIGH', reason: 'Lake bed encroachment', action: 'Demolition of illegal structures' },
      { zone: 'Whitefield Low Zone', risk: 'MODERATE', reason: 'Rapid urban expansion, poor drain', action: 'Stormwater system upgrade' },
      { zone: 'Hebbal Flyover Area', risk: 'LOW', reason: 'Managed retention pond nearby', action: 'Continue monitoring' },
    ],
    suggestions: [
      { icon: Droplets, tag: 'Lakes', text: 'Rejuvenate 189 lakes in the BBMP area. Current 81 are encroached.' },
      { icon: Building2, tag: 'Zoning', text: 'Enforce 30m rajakaluve (storm-drain) buffer — no construction permitted.' },
      { icon: Leaf, tag: 'Green Infra', text: 'Increase tree canopy from 18% to 33% to reduce urban heat and runoff.' },
      { icon: Home, tag: 'Planning', text: 'Develop 12 decentralized stormwater retention pods across IT corridor.' },
    ],
    sdgScore: 67,
    drainageCoverage: 58,
    greenCoverage: 22,
  },
  pune: {
    encroachmentLevel: 'MODERATE',
    encroachmentPct: 39,
    constructionZones: [
      { zone: 'Mula-Mutha Riverbed', risk: 'HIGH', reason: 'Riverbed construction, flood risk', action: 'Remove illegal structures' },
      { zone: 'Hadapsar Lowlands', risk: 'MODERATE', reason: 'Water accumulation zone', action: 'Elevation-based permits only' },
      { zone: 'Khadakwasla Buffer', risk: 'MODERATE', reason: 'Downstream dam release zone', action: 'Early warning infrastructure' },
      { zone: 'Wagholi Expansion', risk: 'LOW', reason: 'Rapid growth, drainage lag', action: 'Mandatory infra plan with permits' },
    ],
    suggestions: [
      { icon: Droplets, tag: 'Drainage', text: 'Upgrade Mula-Mutha river embankment and install automated flood gates.' },
      { icon: Building2, tag: 'Zoning', text: 'Enforce 100m no-construction buffer from Khadakwasla reservoir.' },
      { icon: Leaf, tag: 'Green Infra', text: 'Restore Pashan lake ecosystem and wetland corridor to Western Ghats.' },
      { icon: Home, tag: 'Planning', text: 'Implement real-time dam discharge alerts for downstream settlements.' },
    ],
    sdgScore: 71,
    drainageCoverage: 63,
    greenCoverage: 28,
  },
};

const riskColor = r => ({ CRITICAL: '#ef4444', HIGH: '#f97316', MODERATE: '#f59e0b', LOW: '#10b981' }[r] || '#64748b');

export default function UrbanPlanningTab({ targetCity, liveData }) {
  const [activeCity, setActiveCity] = useState(targetCity || 'mumbai');
  const data = URBAN_DATA[activeCity] || URBAN_DATA.mumbai;
  const enColor = riskColor(data.encroachmentLevel);

  return (
    <div className="urban-page animate-in">
      {/* Hero */}
      <div className="hero-banner hero-urban">
        <div className="hero-content" style={{ flexDirection: 'row', alignItems: 'center' }}>
          <div className="hero-left">
            <div className="hero-greeting"><Building2 size={18} /><span>Urban Planning Intelligence</span></div>
            <div className="hero-city">Encroachment & Infrastructure Risk</div>
            <div className="hero-meta">
              <span>GIS spatial analysis</span><span className="hero-dot">•</span>
              <span>SDG 11 compliance</span><span className="hero-dot">•</span>
              <span>4 cities monitored</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, marginLeft: 'auto' }}>
            <div className="sdg-hero-badge sdg-11">🏙️ SDG 11</div>
            <div className="sdg-hero-badge sdg-13">🌍 SDG 13</div>
          </div>
        </div>
      </div>

      {/* City Selector */}
      <div className="urban-city-tabs">
        {Object.keys(URBAN_DATA).map(city => {
          const d = URBAN_DATA[city];
          const c = riskColor(d.encroachmentLevel);
          return (
            <button key={city} className={`uct-btn${activeCity === city ? ' active' : ''}`}
              style={{ '--uc': c }} onClick={() => setActiveCity(city)}>
              <span className="uct-dot" style={{ background: c, boxShadow: `0 0 6px ${c}` }} />
              {city.charAt(0).toUpperCase() + city.slice(1)}
              <span className="uct-badge" style={{ color: c, background: `${c}15`, border: `1px solid ${c}30` }}>
                {d.encroachmentLevel}
              </span>
            </button>
          );
        })}
      </div>

      <div className="urban-layout">
        {/* Left: Encroachment Overview + Metrics */}
        <div className="urban-left">
          {/* Encroachment Score */}
          <div className="card card-accent-orange">
            <div className="section-header">
              <div className="section-icon" style={{ background: `${enColor}18`, border: `1px solid ${enColor}30` }}>
                <AlertTriangle size={14} color={enColor} />
              </div>
              <span className="section-title">Encroachment Risk Index</span>
              <span className="section-badge" style={{ color: enColor, borderColor: `${enColor}40`, background: `${enColor}10` }}>
                {data.encroachmentLevel}
              </span>
            </div>
            <div className="urban-enc-body">
              <div className="urban-enc-gauge">
                <svg viewBox="0 0 120 70" width="100%" style={{ maxWidth: 200 }}>
                  <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke="var(--surface3)" strokeWidth="10" strokeLinecap="round" />
                  <path d="M10,60 A50,50 0 0,1 110,60" fill="none" stroke={enColor} strokeWidth="10" strokeLinecap="round"
                    strokeDasharray={`${(data.encroachmentPct / 100) * 157} 157`}
                    style={{ filter: `drop-shadow(0 0 4px ${enColor})` }} />
                  <text x="60" y="58" textAnchor="middle" fill={enColor} fontSize="18" fontWeight="800" fontFamily="JetBrains Mono">{data.encroachmentPct}%</text>
                  <text x="60" y="70" textAnchor="middle" fill="var(--muted2)" fontSize="7">DRAINAGE ENCROACHMENT</text>
                </svg>
              </div>
              <div className="urban-metrics-mini">
                <div className="umm-item">
                  <div className="umm-label">Drainage Coverage</div>
                  <div className="umm-bar-bg"><div className="umm-bar-fill" style={{ width: `${data.drainageCoverage}%`, background: '#38bdf8' }} /></div>
                  <div className="umm-val" style={{ color: '#38bdf8' }}>{data.drainageCoverage}%</div>
                </div>
                <div className="umm-item">
                  <div className="umm-label">Green Cover</div>
                  <div className="umm-bar-bg"><div className="umm-bar-fill" style={{ width: `${data.greenCoverage}%`, background: '#10b981' }} /></div>
                  <div className="umm-val" style={{ color: '#10b981' }}>{data.greenCoverage}%</div>
                </div>
                <div className="umm-item">
                  <div className="umm-label">SDG 11 Compliance Score</div>
                  <div className="umm-bar-bg"><div className="umm-bar-fill" style={{ width: `${data.sdgScore}%`, background: '#818cf8' }} /></div>
                  <div className="umm-val" style={{ color: '#818cf8' }}>{data.sdgScore}/100</div>
                </div>
              </div>
            </div>
          </div>

          {/* Suggestions */}
          <div className="card card-accent-green">
            <div className="section-header">
              <div className="section-icon" style={{ background: '#10b98118', border: '1px solid #10b98130' }}>
                <Zap size={14} color="#10b981" />
              </div>
              <span className="section-title">Planning Recommendations</span>
              <span className="section-badge" style={{ color: '#10b981', borderColor: '#10b98140', background: '#10b98110' }}>AI SUGGESTIONS</span>
            </div>
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {data.suggestions.map((s, i) => (
                <div key={i} className="urban-suggestion">
                  <div className="us-icon"><s.icon size={14} color="#10b981" /></div>
                  <div>
                    <span className="us-tag">{s.tag}</span>
                    <p className="us-text">{s.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: High-Risk Construction Zones */}
        <div className="urban-right">
          <div className="card" style={{ height: '100%' }}>
            <div className="section-header">
              <div className="section-icon" style={{ background: '#f97316 18', border: '1px solid #f9731630' }}>
                <MapPin size={14} color="#f97316" />
              </div>
              <span className="section-title">High-Risk Construction Zones</span>
              <span className="section-badge" style={{ color: '#f97316', borderColor: '#f9731640', background: '#f9731610' }}>
                {data.constructionZones.length} ZONES
              </span>
            </div>
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {data.constructionZones.map((z, i) => {
                const c = riskColor(z.risk);
                return (
                  <div key={i} className="urban-zone-card" style={{ borderLeftColor: c, '--zc': c }}>
                    <div className="uzc-header">
                      <div className="uzc-dot" style={{ background: c, boxShadow: `0 0 6px ${c}` }} />
                      <span className="uzc-name">{z.zone}</span>
                      <span className="uzc-risk" style={{ color: c, background: `${c}15`, border: `1px solid ${c}30` }}>{z.risk}</span>
                    </div>
                    <div className="uzc-reason"><Info size={10} />{z.reason}</div>
                    <div className="uzc-action"><ArrowRight size={10} color={c} /><span style={{ color: c }}>{z.action}</span></div>
                  </div>
                );
              })}
            </div>

            {/* SDG Footer */}
            <div className="urban-sdg-footer">
              <div className="usf-item"><span className="usf-dot" style={{ background: '#10b981' }} />Aligned with SDG 11.5 — Reduce disaster losses in cities</div>
              <div className="usf-item"><span className="usf-dot" style={{ background: '#3b82f6' }} />Aligned with SDG 13.1 — Strengthen climate resilience</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
