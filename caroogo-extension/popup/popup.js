document.addEventListener('DOMContentLoaded', () => {
    const providerSelect = document.getElementById('ai-provider');
    const apiKeyInput = document.getElementById('api-key');
    const saveBtn = document.getElementById('save-btn');
    const btnText = saveBtn.querySelector('.btn-text');
    const spinner = saveBtn.querySelector('.spinner');
    const statusMessage = document.getElementById('status-message');

    // Load existing settings
    chrome.storage.sync.get(['aiProvider', 'apiKey'], (result) => {
        if (result.aiProvider) {
            providerSelect.value = result.aiProvider;
        }
        if (result.apiKey) {
            apiKeyInput.value = result.apiKey;
        }
    });

    // Save settings
    saveBtn.addEventListener('click', () => {
        const aiProvider = providerSelect.value;
        const apiKey = apiKeyInput.value.trim();

        // UI Feedback
        btnText.classList.add('hidden');
        spinner.classList.remove('hidden');
        saveBtn.disabled = true;

        chrome.storage.sync.set({ aiProvider, apiKey }, () => {
            setTimeout(() => {
                btnText.classList.remove('hidden');
                spinner.classList.add('hidden');
                saveBtn.disabled = false;

                statusMessage.classList.remove('hidden');
                statusMessage.classList.add('show');

                setTimeout(() => {
                    statusMessage.classList.remove('show');
                    setTimeout(() => statusMessage.classList.add('hidden'), 300);
                }, 3000);
            }, 500); // Small artificial delay for visual feedback
        });
    });
});
