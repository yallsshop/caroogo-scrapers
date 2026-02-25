chrome.webRequest.onSendHeaders.addListener(
    (details) => {
        for (let header of details.requestHeaders) {
            if (header.name.toLowerCase() === 'authorization' && header.value.startsWith('Bearer ')) {
                const token = header.value.split(' ')[1];
                chrome.storage.local.set({ caroogo_jwt: token, last_sync: Date.now() });
                break;
            }
        }
    },
    { urls: ["*://base44.app/api/apps/*"] },
    ["requestHeaders", "extraHeaders"]
);

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'generateAI') {
        handleAIGeneration(request.prompt).then(sendResponse);
        return true; // Indicates asynchronous response
    }

    if (request.action === 'chatAI') {
        handleAIChat(request.messages, request.context).then(sendResponse);
        return true;
    }

    // Content script found a token in page storage — store it
    if (request.action === 'pushAuthToken') {
        chrome.storage.local.set({ caroogo_jwt: request.token, last_sync: Date.now() });
        console.log('[Caroogo Background] Token received from content script.');
        sendResponse({ ok: true });
        return false;
    }

    if (request.action === 'getAuthToken') {
        chrome.storage.local.get(['caroogo_jwt'], (res) => {
            if (res.caroogo_jwt) {
                sendResponse({ token: res.caroogo_jwt });
            } else {
                // No token cached — ask any open CRM tabs to look for one
                chrome.tabs.query({ url: ['*://*.caroogocrm.com/*', '*://caroogocrm.com/*'] }, (tabs) => {
                    if (tabs.length > 0) {
                        chrome.tabs.sendMessage(tabs[0].id, { action: 'requestTokenFromPage' }, () => {
                            // Give the content script a moment to push the token
                            setTimeout(() => {
                                chrome.storage.local.get(['caroogo_jwt'], (res2) => {
                                    sendResponse({ token: res2.caroogo_jwt || null });
                                });
                            }, 500);
                        });
                    } else {
                        sendResponse({ token: null });
                    }
                });
            }
        });
        return true;
    }
});

async function handleAIGeneration(prompt) {
    const data = await chrome.storage.sync.get(['aiProvider', 'apiKey']);
    const aiProvider = data.aiProvider || 'gemini';
    const apiKey = data.apiKey;

    if (!apiKey) {
        return { error: 'API Key not configured. Please click the extension icon to set it up.' };
    }

    try {
        if (aiProvider === 'gemini') {
            return await callGemini(prompt, apiKey);
        } else {
            return await callOpenAI([{ role: 'user', content: prompt }], apiKey);
        }
    } catch (error) {
        return { error: error.message };
    }
}

async function handleAIChat(messages, context) {
    const data = await chrome.storage.sync.get(['aiProvider', 'apiKey']);
    const aiProvider = data.aiProvider || 'gemini';
    const apiKey = data.apiKey;

    if (!apiKey) return { error: 'API Key not configured. Click extension icon.' };

    try {
        const systemPrompt = "You are a helpful CRM assistant for automotive dealerships. You will be provided with the text content of the active CRM page for context. Be concise, professional, and directly helpful.\n\nCRM PAGE CONTEXT:\n" + context;

        if (aiProvider === 'gemini') {
            // For Gemini 1.5/2.5 we can simulate chat by appending history into a text prompt, 
            // or formatting properly. For simplicity in this demo, let's squish history into a prompt:
            let fullConversation = `System Instructions: ${systemPrompt}\n\n`;
            messages.forEach(msg => {
                fullConversation += `${msg.role.toUpperCase()}: ${msg.content}\n\n`;
            });
            fullConversation += "ASSISTANT: ";
            return await callGemini(fullConversation, apiKey);
        } else {
            // For OpenAI it's easier, we just map the array over.
            const oaiMessages = [
                { role: 'system', content: systemPrompt }
            ];
            messages.forEach(m => {
                // map assistant/user to standard openai roles
                oaiMessages.push({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content });
            });
            return await callOpenAI(oaiMessages, apiKey);
        }
    } catch (e) {
        return { error: e.message };
    }
}


async function callGemini(promptText, apiKey) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            contents: [{ parts: [{ text: promptText }] }]
        })
    });

    if (!response.ok) throw new Error('Failed to communicate with Gemini API');
    const data = await response.json();
    if (!data.candidates || data.candidates.length === 0) throw new Error('No response generated');
    return { result: data.candidates[0].content.parts[0].text };
}

async function callOpenAI(messages, apiKey) {
    const url = 'https://api.openai.com/v1/chat/completions';
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`
        },
        body: JSON.stringify({
            model: 'gpt-4o-mini',
            messages: messages
        })
    });

    if (!response.ok) throw new Error('Failed to communicate with OpenAI API');
    const data = await response.json();
    return { result: data.choices[0].message.content };
}
