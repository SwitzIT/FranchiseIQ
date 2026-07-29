import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, Loader2 } from 'lucide-react';
import useAppStore from '../store/useAppStore';
import { sendChatMessage } from '../services/api';

const SUGGESTED = [
  "What's my best district?",
  "Compare my top 3 picks",
  "Which stores need attention?",
  "How do I upload franchise requests?",
];

export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I can help you understand your analysis or navigate FranchiseIQ. Ask me anything about your top picks, KPIs, or stores."
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const { sessionId, results } = useAppStore();

  useEffect(() => {
    if (open && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, open]);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  const handleSend = async (textOverride) => {
    const text = (textOverride ?? input).trim();
    if (!text || loading) return;
    const userMsg = { role: 'user', content: text };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput('');
    setLoading(true);
    try {
      const conv = newHistory.slice(-10);
      const reply = await sendChatMessage(conv, sessionId);
      setMessages(prev => [...prev, { role: 'assistant', content: reply }]);
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "Sorry, I had trouble responding. Please try again."
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const showSuggestions = messages.length <= 1 && !loading;

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-lg flex items-center justify-center text-white z-[60] hover:scale-105 transition-transform"
          style={{ background: 'linear-gradient(135deg, #6C4CF1, #8B5CF6)' }}
          aria-label="Open chat"
        >
          <MessageSquare size={22} />
        </button>
      )}

      {open && (
        <div
          className="fixed bottom-6 right-6 w-[380px] max-w-[calc(100vw-2rem)] h-[580px] max-h-[calc(100vh-2rem)] bg-white rounded-2xl shadow-2xl flex flex-col z-[60] overflow-hidden"
          style={{ border: '1px solid rgba(108, 76, 241, 0.15)' }}
        >
          <div
            className="px-5 py-4 flex items-center justify-between text-white shrink-0"
            style={{ background: 'linear-gradient(135deg, #6C4CF1, #8B5CF6)' }}
          >
            <div>
              <div className="font-bold text-sm">FranchiseIQ Assistant</div>
              <div className="text-[11px] opacity-80">Ask anything about your analysis</div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-white opacity-80 hover:opacity-100 p-1"
              aria-label="Close chat"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${m.role === 'user'
                    ? 'bg-purple-600 text-white rounded-br-md'
                    : 'bg-white text-gray-800 shadow-sm rounded-bl-md border border-gray-100'
                    }`}
                >
                  {m.content}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white px-4 py-3 rounded-2xl shadow-sm rounded-bl-md border border-gray-100">
                  <Loader2 size={16} className="animate-spin text-purple-600" />
                </div>
              </div>
            )}

            {showSuggestions && (
              <div className="pt-3 space-y-2">
                <div className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider px-1">
                  Try asking
                </div>
                {SUGGESTED.map(s => (
                  <button
                    key={s}
                    onClick={() => handleSend(s)}
                    className="block w-full text-left text-xs px-3 py-2 bg-white border border-gray-200 rounded-lg hover:border-purple-300 hover:bg-purple-50 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="px-3 py-3 bg-white border-t border-gray-100 shrink-0">
            <div className="flex items-center gap-2 bg-gray-50 rounded-full px-4 py-2 border border-gray-200 focus-within:border-purple-400 transition-colors">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask a question..."
                className="flex-1 bg-transparent outline-none text-sm"
                disabled={loading}
              />
              <button
                onClick={() => handleSend()}
                disabled={loading || !input.trim()}
                className="text-purple-600 disabled:opacity-30 hover:scale-110 transition-transform"
                aria-label="Send"
              >
                <Send size={16} />
              </button>
            </div>
            <div className="text-[10px] text-gray-400 text-center mt-2">
              I only explain your data. I won't share methodology.
            </div>
          </div>
        </div>
      )}
    </>
  );
}
