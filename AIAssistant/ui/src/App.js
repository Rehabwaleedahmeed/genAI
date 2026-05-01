import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { FiSend, FiShoppingBag, FiTrendingUp, FiDatabase } from 'react-icons/fi';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([]);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    // Add user message
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, { type: 'user', content: input }]);
    
    // Update conversation history
    const newHistory = [...conversationHistory, userMessage];
    setConversationHistory(newHistory);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        messages: newHistory,
        user_id: 'web_user'
      });

      const assistantMessage = response.data.message;
      setMessages(prev => [...prev, { 
        type: 'assistant', 
        content: assistantMessage,
        tool_used: response.data.tool_used
      }]);

      // Update conversation history with assistant response
      setConversationHistory(prev => [...prev, {
        role: 'assistant',
        content: assistantMessage
      }]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        type: 'assistant', 
        content: 'Sorry, I encountered an error. Please make sure the backend server is running on http://localhost:8000',
        error: true 
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const suggestedQueries = [
    "Do you have black t-shirts in size M?",
    "What are the trending summer styles?",
    "Show me winter coats available",
    "Tell me about your current promotions",
    "I need formal wear for an event"
  ];

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <div className="logo">
            <FiShoppingBag size={32} />
            <h1>StyleHub AI Assistant</h1>
          </div>
          <p className="tagline">Your Personal Fashion Consultant</p>
        </div>
      </header>

      <main className="main-content">
        <div className="chat-container">
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="welcome-section">
                <div className="welcome-card">
                  <h2>Welcome to StyleHub!</h2>
                  <p>I'm your AI fashion consultant. I can help you:</p>
                  <ul className="features">
                    <li><FiDatabase size={20} /> Search our local inventory</li>
                    <li><FiTrendingUp size={20} /> Get fashion trend advice</li>
                    <li><FiShoppingBag size={20} /> Find the perfect outfit</li>
                  </ul>
                </div>

                <div className="suggested-queries">
                  <p className="suggestions-title">Try asking me:</p>
                  <div className="suggestions-grid">
                    {suggestedQueries.map((query, index) => (
                      <button
                        key={index}
                        className="suggestion-btn"
                        onClick={() => {
                          setInput(query);
                        }}
                      >
                        {query}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="messages-list">
                {messages.map((msg, index) => (
                  <div key={index} className={`message ${msg.type}`}>
                    <div className="message-content">
                      <p>{msg.content}</p>
                      {msg.tool_used && (
                        <div className="tool-used">
                          Used: <strong>{msg.tool_used}</strong>
                        </div>
                      )}
                      {msg.error && (
                        <div className="error-message">Error</div>
                      )}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="message assistant">
                    <div className="message-content">
                      <div className="loading-indicator">
                        <span></span><span></span><span></span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <div className="input-section">
            <div className="input-wrapper">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me about our clothing, styles, or get fashion advice..."
                rows="3"
                disabled={loading}
              />
              <button 
                onClick={sendMessage} 
                disabled={loading || !input.trim()}
                className="send-button"
              >
                <FiSend size={20} />
              </button>
            </div>
            <p className="helper-text">
              I can search our inventory, find fashion trends, and help with styling recommendations!
            </p>
          </div>
        </div>
      </main>

      <footer className="app-footer">
        <p>StyleHub AI Assistant © 2026. Powered by Advanced AI Technology.</p>
      </footer>
    </div>
  );
}

export default App;
