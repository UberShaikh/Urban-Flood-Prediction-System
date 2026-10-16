import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, X, Zap } from 'lucide-react';
import './ChatbotPanel.css'; // New CSS file for just this component

const API = 'http://localhost:8001/api/v1';

export default function ChatbotPanel({ targetCity }) {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', text: "Hello! I am **AquaAlert Dispatcher** — your agentic flood intelligence assistant.\n\nI can help you with:\n- 🌊 **Live flood risk** for Mumbai, Pune, Bengaluru, Chennai\n- 📰 **Latest flood news** (GDELT real-time feed)\n- 🚨 **Emergency action protocol** — what to do RIGHT NOW\n- 🏙️ **Urban planning advice** — drainage, bioswales, sponge city\n\nWhat do you need?" }
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const [lastCity, setLastCity] = useState(null);
  const [isLLM, setIsLLM] = useState(false);
  const [toolsUsed, setToolsUsed] = useState([]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, chatLoading]);

  const handleSend = () => {
    if (!chatInput.trim() || chatLoading) return;

    const text = chatInput.trim();
    setChatInput('');
    setChatHistory(prev => [...prev, { role: 'user', text }]);
    setChatLoading(true);

    axios.post(`${API}/chat`, {
      message: text,
      city: targetCity,
      context_city: lastCity,
      history: chatHistory
        .filter(m => m.role !== 'ai' || chatHistory.indexOf(m) > 0) // skip welcome
        .slice(-10)  // last 10 messages for context window
        .map(m => ({ role: m.role === 'ai' ? 'model' : 'user', text: m.text }))
    })
      .then(r => {
        setChatHistory(prev => [...prev, { role: 'ai', text: r.data.reply }]);
        if (r.data.city) setLastCity(r.data.city);
        setIsLLM(!!r.data.is_llm);
        setToolsUsed(r.data.tools_used || []);
        setChatLoading(false);
      })
      .catch(() => {
        setChatHistory(prev => [...prev, { role: 'ai', text: "I'm having trouble connecting to the analytics engine right now." }]);
        setChatLoading(false);
      });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <>
      <div className={`cb-panel ${chatOpen ? 'open' : ''}`}>
        <div className="cb-header">
          <div className="cb-header-brand">
            <div className="cb-avatar">
              <Bot size={18} />
            </div>
            <div className="cb-title">Technical Dispatcher</div>
          </div>

          <div className="cb-header-meta">
            <div className={`cb-mode-badge ${isLLM ? 'active' : 'fallback'}`}>
              <span className="cb-dot"></span>
              {isLLM ? 'AGENTIC LLM' : 'ANALYTICAL'}
            </div>

            {isLLM && toolsUsed.length > 0 && (
              <div className="cb-tool-badge">
                {toolsUsed.slice(0, 2).map(t => ({
                  get_risk_data: '🌊 Risk',
                  fetch_flood_news: '📰 News',
                  get_emergency_protocol: '🚨 Emergency',
                  get_urban_planning_advice: '🏙️ Planning'
                }[t] || t)).join(' • ')}
                {toolsUsed.length > 2 && ` +${toolsUsed.length - 2}`}
              </div>
            )}
          </div>

          <button className="cb-close-btn" onClick={() => setChatOpen(false)}>
            <X size={16} />
          </button>
        </div>

        <div className="cb-messages">
          {chatHistory.map((msg, i) => (
            <div key={i} className={`cb-message-row ${msg.role}`}>
              {msg.role === 'ai' && (
                <div className="cb-msg-avatar">
                  <Bot size={14} />
                </div>
              )}
              <div className={`cb-bubble ${msg.role}`}>
                {msg.role === 'ai' ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                ) : (
                  msg.text
                )}
              </div>
            </div>
          ))}
          {chatLoading && (
            <div className="cb-message-row ai">
              <div className="cb-msg-avatar">
                <Bot size={14} />
              </div>
              <div className="cb-bubble ai typing-indicator">
                <span>●</span><span>●</span><span>●</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="cb-input-area">
          <div className="cb-input-wrapper">
            <input
              className="cb-input"
              placeholder="Ask about flood risk, news, emergency steps..."
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              disabled={chatLoading || !chatInput.trim()}
              onClick={handleSend}
              className="cb-send-btn"
            >
              <Zap size={18} fill="currentColor" />
            </button>
          </div>
        </div>
      </div>

      <button className={`cb-trigger ${chatOpen ? 'hidden' : ''}`} onClick={() => setChatOpen(true)}>
        <Bot size={26} />
      </button>
    </>
  );
}
