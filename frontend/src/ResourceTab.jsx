import React, { useState } from 'react';
import {
  Truck, Home, AlertTriangle, ShieldAlert, CheckCircle, MapPin,
  Users, Zap, Radio, Activity, Package, Navigation, PhoneCall, Heart
} from 'lucide-react';

const RESOURCE_DATA = {
  mumbai: {
    pumps: [
      { id: 'P-MUM-01', location: 'Dharavi Basin Entry',    capacity: '5000 L/min', status: 'DEPLOY',  priority: 'CRITICAL', coords: '19.04°N 72.86°E' },
      { id: 'P-MUM-02', location: 'Mithi River Gate 3',     capacity: '3500 L/min', status: 'DEPLOY',  priority: 'HIGH',     coords: '19.07°N 72.85°E' },
      { id: 'P-MUM-03', location: 'Kurla Station Underpass',capacity: '2000 L/min', status: 'STANDBY', priority: 'HIGH',     coords: '19.07°N 72.88°E' },
      { id: 'P-MUM-04', location: 'Andheri Subway Point',   capacity: '2000 L/min', status: 'STANDBY', priority: 'MODERATE', coords: '19.12°N 72.84°E' },
    ],
    shelters: [
      { name: 'Bandra SIES College',    capacity: 1200, current: 0,   type: 'Primary',   coords: '19.04°N 72.84°E', contact: '022-2640-1234' },
      { name: 'Kurla Municipal School', capacity: 800,  current: 0,   type: 'Primary',   coords: '19.07°N 72.88°E', contact: '022-2511-5678' },
      { name: 'Dharavi Relief Camp',    capacity: 2500, current: 0,   type: 'Emergency', coords: '19.04°N 72.86°E', contact: '022-2407-9012' },
      { name: 'Govandi Sports Complex', capacity: 3000, current: 0,   type: 'Emergency', coords: '19.04°N 72.91°E', contact: '022-2556-3456' },
    ],
    emergency: [
      { zone: 'Zone A — Dharavi',        units: 6,  type: 'NDRF',   status: 'DEPLOYED' },
      { zone: 'Zone B — Kurla West',     units: 4,  type: 'SDRF',   status: 'STANDBY'  },
      { zone: 'Zone C — Sion Hospital',  units: 2,  type: 'Medical',status: 'READY'    },
      { zone: 'Zone D — Airport Zone',   units: 3,  type: 'Police', status: 'STANDBY'  },
    ],
  },
  chennai: {
    pumps: [
      { id: 'P-CHN-01', location: 'Adyar River Outfall',    capacity: '4000 L/min', status: 'DEPLOY',  priority: 'CRITICAL', coords: '13.00°N 80.27°E' },
      { id: 'P-CHN-02', location: 'Velachery Lake Pump Stn',capacity: '3000 L/min', status: 'DEPLOY',  priority: 'HIGH',     coords: '12.97°N 80.22°E' },
      { id: 'P-CHN-03', location: 'Tambaram Junction',      capacity: '2500 L/min', status: 'STANDBY', priority: 'MODERATE', coords: '12.92°N 80.11°E' },
      { id: 'P-CHN-04', location: 'Sholinganallur IT Zone',  capacity: '2000 L/min', status: 'STANDBY', priority: 'MODERATE', coords: '12.90°N 80.23°E' },
    ],
    shelters: [
      { name: 'Anna University Campus',  capacity: 2000, current: 0, type: 'Primary',   coords: '13.01°N 80.23°E', contact: '044-2235-1234' },
      { name: 'Velachery Govt School',   capacity: 600,  current: 0, type: 'Primary',   coords: '12.97°N 80.21°E', contact: '044-2244-5678' },
      { name: 'YMCA Ground, Nandanam',   capacity: 1800, current: 0, type: 'Emergency', coords: '13.03°N 80.24°E', contact: '044-2433-9012' },
      { name: 'Chennai Trade Centre',    capacity: 4000, current: 0, type: 'Emergency', coords: '13.05°N 80.21°E', contact: '044-2654-3456' },
    ],
    emergency: [
      { zone: 'Zone A — Adyar Basin',    units: 5, type: 'NDRF',   status: 'DEPLOYED' },
      { zone: 'Zone B — Velachery Lake', units: 3, type: 'SDRF',   status: 'STANDBY'  },
      { zone: 'Zone C — Sholinganallur', units: 2, type: 'Medical',status: 'READY'    },
      { zone: 'Zone D — Airport Buffer', units: 4, type: 'Police', status: 'STANDBY'  },
    ],
  },
  bengaluru: {
    pumps: [
      { id: 'P-BLR-01', location: 'Bellandur Lake Outlet',  capacity: '3500 L/min', status: 'STANDBY', priority: 'HIGH',     coords: '12.93°N 77.67°E' },
      { id: 'P-BLR-02', location: 'Varthur Kere Drain',     capacity: '2500 L/min', status: 'STANDBY', priority: 'HIGH',     coords: '12.94°N 77.74°E' },
      { id: 'P-BLR-03', location: 'Whitefield Main Road',   capacity: '2000 L/min', status: 'READY',   priority: 'MODERATE', coords: '12.97°N 77.75°E' },
      { id: 'P-BLR-04', location: 'Hebbal Flyover Drain',   capacity: '1500 L/min', status: 'READY',   priority: 'LOW',      coords: '13.04°N 77.60°E' },
    ],
    shelters: [
      { name: 'HAL Sports Ground',       capacity: 1500, current: 0, type: 'Primary',   coords: '12.95°N 77.66°E', contact: '080-2527-1234' },
      { name: 'Varthur Govt School',     capacity: 500,  current: 0, type: 'Primary',   coords: '12.94°N 77.74°E', contact: '080-2845-5678' },
      { name: 'NIMHANS Convention Ctr',  capacity: 2500, current: 0, type: 'Emergency', coords: '12.94°N 77.60°E', contact: '080-4611-9012' },
      { name: 'Palace Grounds',          capacity: 5000, current: 0, type: 'Emergency', coords: '12.99°N 77.59°E', contact: '080-2334-3456' },
    ],
    emergency: [
      { zone: 'Zone A — Bellandur',      units: 3, type: 'SDRF',   status: 'STANDBY'  },
      { zone: 'Zone B — Whitefield',     units: 2, type: 'SDRF',   status: 'READY'    },
      { zone: 'Zone C — City Medical',   units: 2, type: 'Medical',status: 'READY'    },
      { zone: 'Zone D — Traffic Control',units: 3, type: 'Police', status: 'READY'    },
    ],
  },
  pune: {
    pumps: [
      { id: 'P-PNQ-01', location: 'Mula River Gate 1',      capacity: '3000 L/min', status: 'STANDBY', priority: 'HIGH',     coords: '18.52°N 73.86°E' },
      { id: 'P-PNQ-02', location: 'Mutha River Outlet',     capacity: '2500 L/min', status: 'STANDBY', priority: 'HIGH',     coords: '18.51°N 73.87°E' },
      { id: 'P-PNQ-03', location: 'Hadapsar Low Zone',      capacity: '2000 L/min', status: 'READY',   priority: 'MODERATE', coords: '18.50°N 73.94°E' },
      { id: 'P-PNQ-04', location: 'Wagholi Bypass Drain',   capacity: '1500 L/min', status: 'READY',   priority: 'LOW',      coords: '18.56°N 73.98°E' },
    ],
    shelters: [
      { name: 'SP College Ground',       capacity: 900,  current: 0, type: 'Primary',   coords: '18.52°N 73.85°E', contact: '020-2553-1234' },
      { name: 'Hadapsar Civic School',   capacity: 600,  current: 0, type: 'Primary',   coords: '18.50°N 73.93°E', contact: '020-2687-5678' },
      { name: 'Balewadi Sports Complex', capacity: 3000, current: 0, type: 'Emergency', coords: '18.57°N 73.77°E', contact: '020-2720-9012' },
      { name: 'Shivajinagar Hall',       capacity: 1200, current: 0, type: 'Emergency', coords: '18.53°N 73.84°E', contact: '020-2553-3456' },
    ],
    emergency: [
      { zone: 'Zone A — Riverbed Zone',  units: 3, type: 'SDRF',   status: 'STANDBY'  },
      { zone: 'Zone B — Hadapsar',       units: 2, type: 'SDRF',   status: 'READY'    },
      { zone: 'Zone C — Sassoon Hosp.',  units: 2, type: 'Medical',status: 'READY'    },
      { zone: 'Zone D — PMC Control',    units: 2, type: 'Police', status: 'READY'    },
    ],
  },
};

const statusColor = s => ({ DEPLOY: '#ef4444', STANDBY: '#f59e0b', READY: '#10b981', DEPLOYED: '#ef4444' }[s] || '#64748b');
const priorityColor = p => ({ CRITICAL: '#ef4444', HIGH: '#f97316', MODERATE: '#f59e0b', LOW: '#10b981' }[p] || '#64748b');

export default function ResourceTab({ targetCity }) {
  const [activeCity, setActiveCity] = useState(targetCity || 'mumbai');
  const data = RESOURCE_DATA[activeCity] || RESOURCE_DATA.mumbai;

  const deployCount  = data.pumps.filter(p => p.status === 'DEPLOY').length;
  const standbyCount = data.pumps.filter(p => p.status === 'STANDBY').length;
  const totalCap     = data.shelters.reduce((a, s) => a + s.capacity, 0);

  return (
    <div className="resource-page animate-in">
      {/* Hero */}
      <div className="hero-banner hero-resource">
        <div className="hero-content" style={{ flexDirection: 'row', alignItems: 'center' }}>
          <div className="hero-left">
            <div className="hero-greeting"><Truck size={18} /><span>Emergency Resource Allocation</span></div>
            <div className="hero-city">Flood Response Command</div>
            <div className="hero-meta">
              <span>Pump deployment</span><span className="hero-dot">•</span>
              <span>Safe shelters</span><span className="hero-dot">•</span>
              <span>Emergency zones</span>
            </div>
          </div>
          {/* Summary pills */}
          <div style={{ display: 'flex', gap: 10, marginLeft: 'auto' }}>
            <div className="res-summary-pill" style={{ borderColor: '#ef444440', background: '#ef444410' }}>
              <Truck size={14} color="#ef4444" />
              <div><div style={{ color: '#ef4444', fontWeight: 800, fontFamily: 'JetBrains Mono' }}>{deployCount}</div><div style={{ fontSize: '.6rem', color: 'rgba(255,255,255,0.6)' }}>Pumps Deploy</div></div>
            </div>
            <div className="res-summary-pill" style={{ borderColor: '#10b98140', background: '#10b98110' }}>
              <Home size={14} color="#10b981" />
              <div><div style={{ color: '#10b981', fontWeight: 800, fontFamily: 'JetBrains Mono' }}>{totalCap.toLocaleString()}</div><div style={{ fontSize: '.6rem', color: 'rgba(255,255,255,0.6)' }}>Shelter Cap.</div></div>
            </div>
          </div>
        </div>
      </div>

      {/* City Tabs */}
      <div className="urban-city-tabs">
        {Object.keys(RESOURCE_DATA).map(city => (
          <button key={city} className={`uct-btn${activeCity === city ? ' active' : ''}`}
            style={{ '--uc': '#3b82f6' }} onClick={() => setActiveCity(city)}>
            <MapPin size={11} />
            {city.charAt(0).toUpperCase() + city.slice(1)}
          </button>
        ))}
      </div>

      <div className="resource-layout">

        {/* Pump Deployment */}
        <div className="card card-accent-orange">
          <div className="section-header">
            <div className="section-icon" style={{ background: '#f9731618', border: '1px solid #f9731630' }}>
              <Truck size={14} color="#f97316" />
            </div>
            <span className="section-title">Pump Deployment Orders</span>
            <span className="section-badge" style={{ color: '#f97316', borderColor: '#f9731640', background: '#f9731610' }}>
              {deployCount} ACTIVE
            </span>
          </div>
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.pumps.map(p => {
              const sc = statusColor(p.status);
              const pc = priorityColor(p.priority);
              return (
                <div key={p.id} className="resource-pump-card" style={{ borderLeftColor: sc }}>
                  <div className="rpc-header">
                    <span className="rpc-id" style={{ color: sc }}>{p.id}</span>
                    <span className="rpc-status" style={{ color: sc, background: `${sc}15`, border: `1px solid ${sc}30` }}>
                      {p.status}
                    </span>
                    <span className="rpc-priority" style={{ color: pc, background: `${pc}12`, border: `1px solid ${pc}25`, marginLeft: 4 }}>
                      {p.priority}
                    </span>
                  </div>
                  <div className="rpc-location"><MapPin size={11} />{p.location}</div>
                  <div className="rpc-meta">
                    <span><Package size={10} />{p.capacity}</span>
                    <span><Navigation size={10} />{p.coords}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Safe Shelters */}
        <div className="card card-accent-green">
          <div className="section-header">
            <div className="section-icon" style={{ background: '#10b98118', border: '1px solid #10b98130' }}>
              <Home size={14} color="#10b981" />
            </div>
            <span className="section-title">Designated Safe Shelters</span>
            <span className="section-badge" style={{ color: '#10b981', borderColor: '#10b98140', background: '#10b98110' }}>
              {totalCap.toLocaleString()} CAPACITY
            </span>
          </div>
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.shelters.map(s => (
              <div key={s.name} className="resource-shelter-card">
                <div className="rsc-header">
                  <div className="rsc-dot" style={{ background: s.type === 'Emergency' ? '#ef4444' : '#10b981' }} />
                  <span className="rsc-name">{s.name}</span>
                  <span className="rsc-type" style={{ color: s.type === 'Emergency' ? '#ef4444' : '#10b981' }}>{s.type}</span>
                </div>
                <div className="rsc-cap-row">
                  <div className="rsc-cap-bar">
                    <div className="rsc-cap-fill" style={{ width: `${(s.current / s.capacity) * 100}%` }} />
                  </div>
                  <span className="rsc-cap-val">0 / {s.capacity.toLocaleString()}</span>
                </div>
                <div className="rsc-meta">
                  <span><Navigation size={10} />{s.coords}</span>
                  <span><PhoneCall size={10} />{s.contact}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Emergency Response Zones */}
        <div className="card card-accent-blue">
          <div className="section-header">
            <div className="section-icon" style={{ background: '#3b82f618', border: '1px solid #3b82f630' }}>
              <ShieldAlert size={14} color="#3b82f6" />
            </div>
            <span className="section-title">Emergency Response Zones</span>
            <span className="section-badge" style={{ color: '#3b82f6', borderColor: '#3b82f640', background: '#3b82f610' }}>NDRF / SDRF</span>
          </div>
          <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {data.emergency.map((e, i) => {
              const sc = statusColor(e.status);
              return (
                <div key={i} className="resource-zone-card" style={{ borderLeftColor: sc }}>
                  <div className="rzc-header">
                    <span className="rzc-name">{e.zone}</span>
                    <span className="rzc-status" style={{ color: sc, background: `${sc}15`, border: `1px solid ${sc}30` }}>{e.status}</span>
                  </div>
                  <div className="rzc-meta">
                    <span><Users size={11} />{e.units} units</span>
                    <span><ShieldAlert size={11} />{e.type}</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Emergency Contacts */}
          <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: '.65rem', fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 4 }}>Emergency Hotlines</div>
            {[
              { label: 'NDRF Control Room', num: '011-24363260' },
              { label: 'State Disaster Authority', num: '1077' },
              { label: 'Flood Relief Helpline',    num: '1800-345-6789' },
            ].map(c => (
              <div key={c.label} className="rzc-contact">
                <PhoneCall size={11} color="#10b981" />
                <span style={{ color: 'var(--text2)' }}>{c.label}</span>
                <span style={{ marginLeft: 'auto', color: '#10b981', fontFamily: 'JetBrains Mono', fontSize: '.72rem', fontWeight: 600 }}>{c.num}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
