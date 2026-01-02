// State
let idCardFile = null;
let selfieFile = null;
let extractedId = null;

// Elements
const idUploadArea = document.getElementById('id-upload-area');
const idCardInput = document.getElementById('id-card-input');
const idPreview = document.getElementById('id-preview');
const uploadPrompt = document.getElementById('upload-prompt');
const extractBtn = document.getElementById('extract-btn');
const resultsContent = document.getElementById('results-content');

const selfieUploadArea = document.getElementById('selfie-upload-area');
const selfieInput = document.getElementById('selfie-input');
const selfiePreview = document.getElementById('selfie-preview');
const selfiePrompt = document.getElementById('selfie-prompt');
const verifyBtn = document.getElementById('verify-btn');
const verifyResults = document.getElementById('verify-results');

const loading = document.getElementById('loading');

// Setup upload areas
setupUploadArea(idUploadArea, idCardInput, idPreview, uploadPrompt, (file) => {
    idCardFile = file;
    extractBtn.disabled = false;
});

setupUploadArea(selfieUploadArea, selfieInput, selfiePreview, selfiePrompt, (file) => {
    selfieFile = file;
    updateVerifyButton();
});

// Extract button
extractBtn.addEventListener('click', async () => {
    if (!idCardFile) return;

    showLoading();

    try {
        const formData = new FormData();
        formData.append('image', idCardFile);

        const response = await fetch('/extract-id', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        displayResults(data);

        if (data.success && data.ocr_result?.extracted_id) {
            extractedId = data.ocr_result.extracted_id;
            updateVerifyButton();
        }
    } catch (error) {
        displayError('Failed to process image: ' + error.message);
    }

    hideLoading();
});

// Verify button
verifyBtn.addEventListener('click', async () => {
    if (!extractedId || !selfieFile) return;

    showLoading();

    try {
        const formData = new FormData();
        formData.append('id_number', extractedId);
        formData.append('selfie', selfieFile);

        const response = await fetch('/verify', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        displayVerifyResults(data);
    } catch (error) {
        verifyResults.innerHTML = `
            <div class="result-item">
                <span class="result-label">Error</span>
                <span class="result-value error">${error.message}</span>
            </div>
        `;
    }

    hideLoading();
});

// Functions
function setupUploadArea(area, input, preview, prompt, onFile) {
    area.addEventListener('click', () => input.click());

    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.classList.add('dragover');
    });

    area.addEventListener('dragleave', () => {
        area.classList.remove('dragover');
    });

    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            handleFile(file, area, preview, prompt, onFile);
        }
    });

    input.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFile(file, area, preview, prompt, onFile);
        }
    });
}

function handleFile(file, area, preview, prompt, onFile) {
    const reader = new FileReader();
    reader.onload = (e) => {
        preview.src = e.target.result;
        preview.classList.remove('hidden');
        prompt.classList.add('hidden');
        area.classList.add('has-image');
    };
    reader.readAsDataURL(file);
    onFile(file);
}

function displayResults(data) {
    if (!data.success) {
        resultsContent.innerHTML = `
            <div class="result-item">
                <span class="result-label">Error</span>
                <span class="result-value error">${data.error || 'Unknown error'}</span>
            </div>
        `;
        return;
    }

    const ocr = data.ocr_result;
    let html = '';

    if (ocr.extracted_id) {
        html += `
            <div class="result-item">
                <span class="result-label">ID Number</span>
                <span class="result-value large">${ocr.extracted_id}</span>
            </div>
        `;
    }

    if (ocr.id_type) {
        html += `
            <div class="result-item">
                <span class="result-label">ID Type</span>
                <span class="result-value"><span class="tag">${ocr.id_type.toUpperCase()}</span></span>
            </div>
        `;
    }

    if (ocr.detected_languages_display && ocr.detected_languages_display.length > 0) {
        html += `
            <div class="result-item">
                <span class="result-label">Languages</span>
                <span class="result-value">${ocr.detected_languages_display.join(', ')}</span>
            </div>
        `;
    }

    if (ocr.confidence) {
        const pct = (ocr.confidence * 100).toFixed(0);
        html += `
            <div class="result-item">
                <span class="result-label">Confidence</span>
                <span class="result-value">${pct}%</span>
            </div>
        `;
    }

    // Show detailed text results with per-text language
    if (ocr.text_results && ocr.text_results.length > 0) {
        html += `
            <div class="texts-list">
                <span class="texts-label">Extracted Text (with language)</span>
                <div class="texts-content">
                    ${ocr.text_results.map(t => `<span class="text-with-lang"><span class="text-lang">${t.detected_language_display}</span> ${escapeHtml(t.text)}</span>`).join('')}
                </div>
            </div>
        `;
    } else if (ocr.all_texts && ocr.all_texts.length > 0) {
        html += `
            <div class="texts-list">
                <span class="texts-label">All Extracted Text</span>
                <div class="texts-content">
                    ${ocr.all_texts.map(t => `<span>${escapeHtml(t)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    if (!html) {
        html = '<p class="placeholder">No ID found in image</p>';
    }

    resultsContent.innerHTML = html;
}

function displayVerifyResults(data) {
    if (!data.success) {
        verifyResults.innerHTML = `
            <div class="result-item">
                <span class="result-label">Error</span>
                <span class="result-value error">${data.error || 'Verification failed'}</span>
            </div>
        `;
        return;
    }

    const score = data.similarity_score;
    const match = score >= 0.6;
    const pct = (score * 100).toFixed(1);

    verifyResults.innerHTML = `
        <div class="result-item">
            <span class="result-label">Similarity Score</span>
            <span class="result-value large ${match ? 'success' : 'error'}">${pct}%</span>
        </div>
        <div class="result-item">
            <span class="result-label">Verification Result</span>
            <span class="result-value large ${match ? 'success' : 'error'}">${match ? '✓ Match' : '✗ No Match'}</span>
        </div>
    `;
}

function displayError(message) {
    resultsContent.innerHTML = `
        <div class="result-item">
            <span class="result-label">Error</span>
            <span class="result-value error">${message}</span>
        </div>
    `;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateVerifyButton() {
    verifyBtn.disabled = !extractedId || !selfieFile;
}

function showLoading() {
    loading.classList.remove('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}
