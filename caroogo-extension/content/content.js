// --- Token Extraction ---
// Strategy 1: Inject a script into the PAGE context to intercept fetch/XHR.
// This catches the Bearer token from any API call the SPA makes, even if
// the user is already logged in (the SPA will make API calls on load).
(function injectTokenInterceptor() {
  const script = document.createElement('script');
  script.textContent = `
    (function() {
      const EXTENSION_EVENT = '__CAROOGO_TOKEN_FOUND__';

      // Intercept fetch()
      const origFetch = window.fetch;
      window.fetch = function(...args) {
        try {
          let headers;
          if (args[1] && args[1].headers) {
            headers = args[1].headers;
          }
          if (headers) {
            let authVal = null;
            if (headers instanceof Headers) {
              authVal = headers.get('authorization') || headers.get('Authorization');
            } else if (typeof headers === 'object') {
              authVal = headers['authorization'] || headers['Authorization'];
            }
            if (authVal && authVal.startsWith('Bearer ')) {
              const token = authVal.split(' ')[1];
              document.dispatchEvent(new CustomEvent(EXTENSION_EVENT, { detail: { token } }));
            }
          }
        } catch(e) {}
        return origFetch.apply(this, args);
      };

      // Intercept XMLHttpRequest
      const origOpen = XMLHttpRequest.prototype.open;
      const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;
      XMLHttpRequest.prototype.open = function(...args) {
        this.__caroogoHeaders = {};
        return origOpen.apply(this, args);
      };
      XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
        if (name.toLowerCase() === 'authorization' && value.startsWith('Bearer ')) {
          const token = value.split(' ')[1];
          document.dispatchEvent(new CustomEvent(EXTENSION_EVENT, { detail: { token } }));
        }
        return origSetHeader.apply(this, arguments);
      };

      // Strategy 2: Also scan localStorage for Base44 SDK token
      function scanStorage() {
        // Base44 SDK typically stores token under a key containing 'token' or 'access_token'
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i);
          const val = localStorage.getItem(key);
          if (val && typeof val === 'string') {
            // Check direct JWT values
            if (val.startsWith('ey')) {
              try {
                const parts = val.split('.');
                if (parts.length === 3) {
                  JSON.parse(atob(parts[1]));
                  document.dispatchEvent(new CustomEvent(EXTENSION_EVENT, { detail: { token: val, source: 'localStorage:' + key } }));
                  return;
                }
              } catch(e) {}
            }
            // Check JSON objects that might contain a token
            if (val.startsWith('{') || val.startsWith('"')) {
              try {
                const parsed = JSON.parse(val);
                const tokenVal = parsed.access_token || parsed.token || parsed.accessToken || parsed.jwt;
                if (tokenVal && typeof tokenVal === 'string' && tokenVal.startsWith('ey')) {
                  document.dispatchEvent(new CustomEvent(EXTENSION_EVENT, { detail: { token: tokenVal, source: 'localStorage:' + key } }));
                  return;
                }
              } catch(e) {}
            }
          }
        }
      }

      // Scan immediately and after SPA hydrates
      scanStorage();
      setTimeout(scanStorage, 1500);
      setTimeout(scanStorage, 4000);
    })();
  `;
  document.documentElement.appendChild(script);
  script.remove();
})();

// Listen for the custom event from the injected page script
document.addEventListener('__CAROOGO_TOKEN_FOUND__', (e) => {
  const token = e.detail && e.detail.token;
  if (token) {
    chrome.runtime.sendMessage({ action: 'pushAuthToken', token });
    console.log('[Caroogo Extension] Token captured!', e.detail.source || 'from network intercept');
  }
});

// Strategy 3: Content script also scans storage directly (shares same storage as page)
function scanStorageFromContentScript() {
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    const val = localStorage.getItem(key);
    if (!val || typeof val !== 'string') continue;

    // Direct JWT
    if (val.startsWith('ey')) {
      try {
        const parts = val.split('.');
        if (parts.length === 3) {
          JSON.parse(atob(parts[1]));
          chrome.runtime.sendMessage({ action: 'pushAuthToken', token: val });
          console.log('[Caroogo Extension] Token from content script localStorage scan, key:', key);
          return;
        }
      } catch(e) {}
    }

    // JSON with nested token
    if (val.startsWith('{')) {
      try {
        const parsed = JSON.parse(val);
        const tokenVal = parsed.access_token || parsed.token || parsed.accessToken || parsed.jwt;
        if (tokenVal && typeof tokenVal === 'string' && tokenVal.startsWith('ey')) {
          chrome.runtime.sendMessage({ action: 'pushAuthToken', token: tokenVal });
          console.log('[Caroogo Extension] Token from content script JSON parse, key:', key);
          return;
        }
      } catch(e) {}
    }
  }
  console.log('[Caroogo Extension] No JWT found in localStorage. Keys present:',
    Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)));
}

scanStorageFromContentScript();
setTimeout(scanStorageFromContentScript, 2000);
setTimeout(scanStorageFromContentScript, 5000);

// Listen for explicit requests from the background to grab the token
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'requestTokenFromPage') {
    scanStorageFromContentScript();
    sendResponse({ ok: true });
  }
});

const createUI = () => {
  if (document.getElementById('caroogo-crm-sidebar-container')) return;

  const container = document.createElement('div');
  container.id = 'caroogo-crm-sidebar-container';
  container.className = 'collapsed';

  container.innerHTML = `
    <button id="caroogo-toggle-btn" title="Toggle AI Assistant">✨</button>
    <div id="caroogo-sidebar">
      <div class="caroogo-header">
        <div class="caroogo-logo">AI</div>
        <div class="caroogo-title">Caroogo Companion</div>
      </div>
      
      <div class="caroogo-tabs">
        <div class="caroogo-tab active" data-target="chat">Chat</div>
        <div class="caroogo-tab" data-target="tools">Quick Tools</div>
      </div>
      
      <div class="caroogo-views">
        <!-- Chat View -->
        <div class="caroogo-view active" id="caroogo-view-chat">
          <div class="caroogo-chat-messages" id="caroogo-chat-messages">
            <div class="caroogo-msg ai">Hi! I can help you analyze this page or answer any questions about the current lead.</div>
          </div>
          <div class="caroogo-chat-input-area">
            <div class="caroogo-input-wrap">
              <textarea id="caroogo-chat-input" placeholder="Ask about this lead... (Press Enter to send)"></textarea>
              <button class="caroogo-send-btn" id="caroogo-send-btn">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.01 21L23 12L2.01 3L2 10l15 2l-15 2z" fill="currentColor"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Tools View -->
        <div class="caroogo-view" id="caroogo-view-tools">
          <div class="caroogo-tools-container">
            <button class="caroogo-tool-btn" id="caroogo-tool-analyze">
              <div class="caroogo-tool-title">📊 Analyze Context</div>
              <div class="caroogo-tool-desc">Summarize the information available on the current page to get quick insights.</div>
            </button>
            
            <button class="caroogo-tool-btn" id="caroogo-tool-email">
              <div class="caroogo-tool-title">✉️ Draft Follow-up Email</div>
              <div class="caroogo-tool-desc">Create a polite and encouraging email to the customer based on this page.</div>
            </button>
            
            <button class="caroogo-tool-btn" id="caroogo-tool-sms">
              <div class="caroogo-tool-title">📱 Draft SMS Reminder</div>
              <div class="caroogo-tool-desc">Generate a short text message to confirm their interest or appointment.</div>
            </button>

            <div class="caroogo-tool-result" id="caroogo-tool-result"></div>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(container);

  // --- Logic ---
  const toggleBtn = document.getElementById('caroogo-toggle-btn');
  const tabs = document.querySelectorAll('.caroogo-tab');
  const views = document.querySelectorAll('.caroogo-view');

  // Chat DOM
  const chatMessages = document.getElementById('caroogo-chat-messages');
  const chatInput = document.getElementById('caroogo-chat-input');
  const sendBtn = document.getElementById('caroogo-send-btn');

  // Tools DOM
  const btnAnalyze = document.getElementById('caroogo-tool-analyze');
  const btnEmail = document.getElementById('caroogo-tool-email');
  const btnSms = document.getElementById('caroogo-tool-sms');
  const toolResult = document.getElementById('caroogo-tool-result');
  const allToolBtns = [btnAnalyze, btnEmail, btnSms];

  // Store chat history
  let conversationHistory = [];

  // Toggle Sidebar
  window.__caroogoIsSidebarOpen = false;
  toggleBtn.addEventListener('click', () => {
    container.classList.toggle('collapsed');
    window.__caroogoIsSidebarOpen = !container.classList.contains('collapsed');
    if (window.__caroogoIsSidebarOpen) {
      document.body.style.marginRight = 'var(--caroogo-sidebar-width)';
    } else {
      document.body.style.marginRight = '0';
    }
  });

  // Tab switching
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      views.forEach(v => v.classList.remove('active'));
      tab.classList.add('active');
      const targetId = `caroogo-view-${tab.dataset.target}`;
      document.getElementById(targetId).classList.add('active');
    });
  });

  // Get Page Context Helper
  const getPageContext = () => document.body.innerText.substring(0, 2000);

  // Loading Indicator Helper
  const getLoadingHtml = () => `<div class="caroogo-loading">
    <div class="caroogo-dot"></div><div class="caroogo-dot"></div><div class="caroogo-dot"></div>
  </div>`;

  // --- Chat Logic ---
  const appendMessage = (text, sender) => {
    const msgDiv = document.createElement('div');
    msgDiv.className = `caroogo-msg ${sender}`;
    msgDiv.innerHTML = text.replace(/\n/g, '<br/>');
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  const handleSendChat = async () => {
    const text = chatInput.value.trim();
    if (!text) return;

    // UI Update
    appendMessage(text, 'user');
    chatInput.value = '';
    sendBtn.disabled = true;
    conversationHistory.push({ role: 'user', content: text });

    // Temporarily add loading message
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'caroogo-msg ai';
    loadingDiv.innerHTML = getLoadingHtml();
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    const context = getPageContext();

    try {
      const response = await chrome.runtime.sendMessage({
        action: 'chatAI',
        messages: conversationHistory,
        context: context
      });

      loadingDiv.remove();

      if (response.error) {
        appendMessage(`<span style="color:#ef4444">${response.error}</span>`, 'ai');
      } else {
        appendMessage(response.result, 'ai');
        conversationHistory.push({ role: 'assistant', content: response.result });
      }
    } catch (e) {
      loadingDiv.remove();
      appendMessage(`<span style="color:#ef4444">Connection error. Reload page.</span>`, 'ai');
    } finally {
      sendBtn.disabled = false;
    }
  };

  sendBtn.addEventListener('click', handleSendChat);
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendChat();
    }
  });

  // --- Quick Tools Logic ---
  const runTool = async (promptMsg) => {
    allToolBtns.forEach(b => b.disabled = true);
    toolResult.classList.remove('show');
    toolResult.innerHTML = getLoadingHtml();
    toolResult.classList.add('show');

    const context = getPageContext();
    const fullPrompt = `Context from CRM screen:\n${context}\n\nUser Task: ${promptMsg}`;

    try {
      const response = await chrome.runtime.sendMessage({ action: 'generateAI', prompt: fullPrompt });
      if (response.error) {
        toolResult.innerHTML = `<span style="color:#ef4444">${response.error}</span>`;
      } else {
        toolResult.innerHTML = response.result.replace(/\n/g, '<br/>');
        // Auto-Copy
        navigator.clipboard.writeText(response.result).catch(() => { });
        toolResult.innerHTML += `<div style="color:var(--caroogo-primary); font-size:11px; margin-top:8px; text-align:right;">Copied to clipboard! ✓</div>`;
      }
    } catch (e) {
      toolResult.innerHTML = `<span style="color:#ef4444">Connection error.</span>`;
    } finally {
      allToolBtns.forEach(b => b.disabled = false);
    }
  };

  btnAnalyze.addEventListener('click', () => runTool('Analyze this page context and provide a brief 3-5 bullet point summary of the most important aspects.'));
  btnEmail.addEventListener('click', () => runTool('Draft a professional and highly personalized follow-up email to this person based on their details.'));
  btnSms.addEventListener('click', () => runTool('Draft a short, friendly SMS text message following up with this person. No more than 2 sentences.'));
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', createUI);
} else {
  createUI();
}

let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    createUI();
  }
}).observe(document, { subtree: true, childList: true });
