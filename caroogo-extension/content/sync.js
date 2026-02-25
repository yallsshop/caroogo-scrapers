// This script runs only on the wrapper dashboard domain (e.g. localhost:3000)
// It polls the extension for a JWT token and posts it to the page when found.
// This handles the case where the user opens the dashboard first, then logs
// into the CRM in a popup — the extension intercepts the token and this
// script picks it up on the next poll cycle.

let synced = false;
let pollTimer = null;

function trySync() {
    chrome.runtime.sendMessage({ action: 'getAuthToken' }, (response) => {
        if (chrome.runtime.lastError) {
            // Extension context invalidated, stop polling
            if (pollTimer) clearInterval(pollTimer);
            return;
        }

        if (response && response.token && !synced) {
            try {
                const payloadStr = atob(response.token.split('.')[1]);
                const payload = JSON.parse(payloadStr);
                const email = payload.email || payload.sub || payload.upn || payload.unique_name || 'user@caroogocrm.com';

                window.postMessage({
                    type: 'CAROOGO_AUTH_SYNC',
                    payload: {
                        token: response.token,
                        email: email
                    }
                }, '*');
                synced = true;
                if (pollTimer) clearInterval(pollTimer);
                console.log('[Caroogo Extension] Successfully synced CRM auth token to dashboard.');
            } catch (e) {
                console.error('[Caroogo Extension] Error parsing JWT payload', e);
            }
        }
    });
}

// Announce presence to the dashboard immediately (even before we have a token)
window.postMessage({ type: 'CAROOGO_EXTENSION_PRESENT' }, '*');

// Try immediately on load
trySync();

// Then poll every 2 seconds until we get a token (handles popup login flow)
pollTimer = setInterval(trySync, 2000);

// Listen for the dashboard requesting a sync (e.g. user clicked "Login via CRM")
window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CAROOGO_REQUEST_SYNC') {
        window.postMessage({ type: 'CAROOGO_EXTENSION_PRESENT' }, '*');
        synced = false; // Reset so we can sync a fresh token
        trySync();
        // Restart polling in case it was stopped
        if (!pollTimer) {
            pollTimer = setInterval(trySync, 2000);
        }
    }
});

// Stop polling after 5 minutes to save resources
setTimeout(() => {
    if (pollTimer && !synced) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}, 5 * 60 * 1000);
