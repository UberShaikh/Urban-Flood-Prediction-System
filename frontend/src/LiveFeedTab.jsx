import { useState, useEffect, useCallback } from 'react';
import {
  Newspaper, CloudRain, Brain, RefreshCw, AlertTriangle, CheckCircle,
  Clock, MapPin, ExternalLink, Zap, Activity, Radio
} from 'lucide-react';
import axios from 'axios';

const API = 'http://localhost:8001/api/v1';

const SEV = {
  HIGH: { color: '#e05555', bg: 'rgba(204,68,68,0.18)', label: 'HIGH' },
  MEDIUM: { color: '#d4924a', bg: 'rgba(192,128,48,0.18)', label: 'MED' },
  LOW: { color: '#3aaa5a', bg: 'rgba(42,138,74,0.18)', label: 'LOW' },
  INFO: { color: '#4a85c0', bg: 'rgba(58,96,144,0.18)', label: 'INFO' },
};

const formatTime = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const diff = Math.floor((Date.now() - d) / 1000);
    let relative = '—';
    if (diff < 60) relative = `${diff}s ago`;
    else if (diff < 3600) relative = `${Math.floor(diff / 60)}m ago`;
    else if (diff < 86400) relative = `${Math.floor(diff / 3600)}h ago`;
    else relative = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });

    const fullDate = d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const fullTime = d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false });

    return { relative, full: `${fullDate} ${fullTime}` };
  } catch { return { relative: '—', full: '—' }; }
};

const TYPE_META = {
  news: { icon: '📰', label: 'NEWS', accent: '#4a85c0' },
  weather: { icon: '🌧', label: 'WEATHER', accent: '#3a90b0' },
  ai_alert: { icon: '🧠', label: 'AI ALERT', accent: '#8a5abc' },
};

function FeedCard({ item }) {
  const tm = TYPE_META[item.type] || TYPE_META.news;
  const sv = SEV[item.severity] || SEV.INFO;
  const borderCol = item.severity ? sv.color : tm.accent;
  const timeInfo = formatTime(item.time);

  return (
    <div className="lf-card" style={{ borderLeftColor: borderCol }}>
      <div className="lf-card-top">
        <span className="lf-card-type" style={{ color: tm.accent }}>
          {tm.icon} {tm.label}
        </span>
        {item.severity && (
          <span className="lf-sev-badge" style={{ color: sv.color, background: sv.bg }}>
            {sv.label}
          </span>
        )}
        <span className="lf-card-time" title={timeInfo.full}>
          <Clock size={9} /> {timeInfo.relative}
        </span>
      </div>

      <div className="lf-card-title">
        {item.type === 'news' && item.url && item.url !== '#'
          ? <a href={item.url} target="_blank" rel="noreferrer" className="lf-news-link">
            {item.title} <ExternalLink size={11} />
          </a>
          : item.title
        }
      </div>

      {item.description && (
        <div className="lf-card-desc">{item.description}</div>
      )}

      <div className="lf-card-footer">
        {item.location && <span><MapPin size={9} /> {item.location}</span>}
        {item.source && <span className="lf-source">{item.source}</span>}
        <span className="lf-full-date">{timeInfo.full}</span>
      </div>
    </div>
  );
}

function EWSBanner({ ews }) {
  if (!ews) return null;
  const isHigh = ews.score >= 3;
  return (
    <div className="lf-ews-banner" style={{
      borderColor: `${ews.color}50`,
      background: `${ews.color}08`,
    }}>
      {/* Left: status + action */}
      <div className="lf-ews-left">
        <div className="lf-ews-header">
          {isHigh
            ? <AlertTriangle size={16} color={ews.color} />
            : <CheckCircle size={16} color={ews.color} />}
          <span className="lf-ews-status" style={{ color: ews.color }}>
            {ews.status}
          </span>
          <span className="lf-ews-score" style={{ background: `${ews.color}20`, color: ews.color }}>
            Score {ews.score}/4
          </span>
        </div>
        <p className="lf-ews-action">{ews.action}</p>
        {ews.factors?.length > 0 && (
          <div className="lf-ews-factors">
            {ews.factors.map((f, i) => (
              <span key={i} className="lf-factor-tag">· {f}</span>
            ))}
          </div>
        )}
      </div>

      {/* Right: timeline */}
      {ews.timeline?.length > 0 && (
        <div className="lf-ews-right">
          <div className="lf-tl-title">RISK FORECAST</div>
          {ews.timeline.map(t => {
            const col = t.risk >= 60 ? '#cc4444' : t.risk >= 30 ? '#c08030' : '#2a8a4a';
            return (
              <div key={t.hour} className="lf-tl-row">
                <span className="lf-tl-hour">{t.hour}</span>
                <div className="lf-tl-track">
                  <div className="lf-tl-fill" style={{ width: `${t.risk}%`, background: col }} />
                </div>
                <span className="lf-tl-val" style={{ color: col }}>{t.risk}%</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function LiveFeedTab({ targetCity, simDate }) {
  const [feed, setFeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('all');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [cacheStatus, setCacheStatus] = useState('fresh'); // 'fresh', 'cached', 'expired'

  const city = targetCity || 'mumbai';
  const CACHE_KEY = `live_feed_${city}`;
  const CACHE_EXPIRY_MS = 15 * 60 * 1000; // 15 minutes

  // Get cache from localStorage
  const getCache = useCallback(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (!cached) return null;

      const { data, timestamp } = JSON.parse(cached);
      const now = Date.now();
      const age = now - timestamp;

      // Check if cache is still valid
      if (age < CACHE_EXPIRY_MS) {
        console.log(`✅ Using cached data (${Math.round(age / 1000)}s old)`);
        setCacheStatus('cached');
        return { data, timestamp };
      } else {
        console.log(`⏰ Cache expired (${Math.round(age / 1000)}s old)`);
        setCacheStatus('expired');
        localStorage.removeItem(CACHE_KEY);
        return null;
      }
    } catch (e) {
      console.error('Cache read error:', e);
      return null;
    }
  }, [CACHE_KEY]);

  // Save cache to localStorage
  const saveCache = useCallback((data) => {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        data,
        timestamp: Date.now()
      }));
      console.log('✅ Cache saved');
    } catch (e) {
      console.error('Cache write error:', e);
    }
  }, [CACHE_KEY]);

  const fetchFeed = useCallback(async (forceRefresh = false) => {
    // Check cache first (unless force refresh)
    if (!forceRefresh) {
      const cached = getCache();
      if (cached) {
        setFeed(cached.data);
        setLastUpdate(new Date(cached.timestamp));
        setLoading(false);
        return;
      }
    }

    // Cache miss or force refresh - fetch from API
    setLoading(true);
    setCacheStatus('fresh');
    try {
      const r = await axios.get(`${API}/live-feed/${city}`, { 
        params: simDate ? { sim_date: simDate } : {},
        timeout: 15000 
      });
      setFeed(r.data);
      setLastUpdate(new Date());
      saveCache(r.data);
      console.log('✅ Fresh data from API');
    } catch (err) {
      console.error('Failed to fetch live feed:', err);
      // Try to use expired cache as fallback
      const expiredCache = localStorage.getItem(CACHE_KEY);
      if (expiredCache) {
        try {
          const { data } = JSON.parse(expiredCache);
          setFeed(data);
          setCacheStatus('expired');
          console.log('⚠️ Using expired cache as fallback');
        } catch (e) {
          setFeed({ news: [], weather_events: [], ai_alerts: [], early_warning: null });
        }
      } else {
        setFeed({ news: [], weather_events: [], ai_alerts: [], early_warning: null });
      }
      setLastUpdate(new Date());
    }
    setLoading(false);
  }, [city, simDate, getCache, saveCache]);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);
  useEffect(() => {
    // Auto-refresh every 60 seconds (but use cache if available)
    const iv = setInterval(() => fetchFeed(false), 60000);
    return () => clearInterval(iv);
  }, [fetchFeed]);

  const allItems = feed ? [
    ...(feed.ai_alerts || []),
    ...(feed.weather_events || []),
    ...(feed.news || []),
  ].sort((a, b) => new Date(b.time) - new Date(a.time)) : [];

  const filtered = (
    tab === 'ai' ? (feed?.ai_alerts || []) :
      tab === 'weather' ? (feed?.weather_events || []) :
        tab === 'news' ? (feed?.news || []) :
          allItems
  ).sort((a, b) => new Date(b.time) - new Date(a.time));

  const TABS = [
    { id: 'all', icon: Activity, label: 'ALL NEWS', count: allItems.length },
    { id: 'news', icon: Newspaper, label: 'INDIA NEWS', count: feed?.news?.length || 0 },
    { id: 'weather', icon: CloudRain, label: 'WEATHER', count: feed?.weather_events?.length || 0 },
    { id: 'ai', icon: Brain, label: 'AI ALERTS', count: feed?.ai_alerts?.length || 0 },
  ];

  return (
    <div className="lf-page animate-in">

      {/* EWS Banner */}
      <EWSBanner ews={feed?.early_warning} />

      {/* Feed header */}
      <div className="lf-feed-header">
        {/* Tab pills */}
        <div className="lf-tab-row">
          {TABS.map(t => (
            <button key={t.id}
              className={`lf-tab-pill${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}>
              <t.icon size={11} />
              <span>{t.label}</span>
              <span className="lf-pill-count">{t.count}</span>
            </button>
          ))}
        </div>

        {/* Meta + Refresh */}
        <div className="lf-feed-meta">
          {lastUpdate && (
            <span className="lf-update-time">
              <Radio size={9} /> {formatTime(lastUpdate.toISOString()).relative}
              {cacheStatus === 'cached' && <span style={{ marginLeft: '8px', fontSize: '.65rem', color: '#7a8898' }}>📦 (cached)</span>}
              {cacheStatus === 'expired' && <span style={{ marginLeft: '8px', fontSize: '.65rem', color: '#d4924a' }}>⏰ (expired)</span>}
            </span>
          )}
          <button className="lf-refresh-btn" onClick={() => fetchFeed(true)} disabled={loading} title="Force refresh (bypass cache)">
            <RefreshCw size={10} className={loading ? 'spin-slow' : ''} />
            {loading ? 'LOADING...' : 'REFRESH'}
          </button>
        </div>
      </div>

      {/* Feed grid */}
      <div className="lf-feed-grid">
        {loading && !feed && (
          <div className="lf-state-box" style={{ gridColumn: '1/-1' }}>
            <div className="scan-bar"><div className="scan-fill" /></div>
            <span>FETCHING LIVE INTEL...</span>
          </div>
        )}
        {!loading && filtered.length === 0 && (
          <div className="lf-state-box" style={{ gridColumn: '1/-1' }}>
            <Zap size={24} /><span>No news articles found for the last 30 days</span>
            <small>Try refreshing or check the News API configuration</small>
          </div>
        )}
        {filtered.map((item, i) => <FeedCard key={i} item={item} />)}
      </div>

    </div>
  );
}
