// State
let frontIdFile = null;
let backIdFile = null;
let selfieFile = null;
let frontExtractedId = null;
let backExtractedId = null;
let idsMatch = false;

// Translation state - store OCR results for translation
let frontOcrResults = null;
let backOcrResults = null;
let frontTranslations = null;  // Map of original -> translated
let backTranslations = null;
let frontShowTranslated = false;
let backShowTranslated = false;

// Elements - Front ID
const frontUploadArea = document.getElementById('front-upload-area');
const frontIdInput = document.getElementById('front-id-input');
const frontPreview = document.getElementById('front-preview');
const frontPrompt = document.getElementById('front-prompt');
const frontResults = document.getElementById('front-results');

// Elements - Back ID
const backUploadArea = document.getElementById('back-upload-area');
const backIdInput = document.getElementById('back-id-input');
const backPreview = document.getElementById('back-preview');
const backPrompt = document.getElementById('back-prompt');
const backResults = document.getElementById('back-results');

// Elements - Common
const extractFrontBtn = document.getElementById('extract-front-btn');
const extractBackBtn = document.getElementById('extract-back-btn');
const compareBtn = document.getElementById('compare-btn');
const validationStatus = document.getElementById('validation-status');

// Elements - Selfie
const selfieUploadArea = document.getElementById('selfie-upload-area');
const selfieInput = document.getElementById('selfie-input');
const selfiePreview = document.getElementById('selfie-preview');
const selfiePrompt = document.getElementById('selfie-prompt');
const verifyBtn = document.getElementById('verify-btn');
const verifyResults = document.getElementById('verify-results');

const loading = document.getElementById('loading');

// Setup upload areas
setupUploadArea(frontUploadArea, frontIdInput, frontPreview, frontPrompt, (file) => {
    frontIdFile = file;
    resetFrontResults();
    updateExtractFrontButton();
});

setupUploadArea(backUploadArea, backIdInput, backPreview, backPrompt, (file) => {
    backIdFile = file;
    resetBackResults();
    updateExtractBackButton();
});

setupUploadArea(selfieUploadArea, selfieInput, selfiePreview, selfiePrompt, (file) => {
    selfieFile = file;
    updateVerifyButton();
});

// Extract Front button - process front side only
extractFrontBtn.addEventListener('click', async () => {
    if (!frontIdFile) return;

    showLoading();
    frontExtractedId = null;
    idsMatch = false;
    validationStatus.classList.add('hidden');

    try {
        const frontData = await extractId(frontIdFile);
        displayResults(frontData, frontResults, 'front');
        if (frontData.success && frontData.ocr_result?.extracted_id) {
            frontExtractedId = frontData.ocr_result.extracted_id;
        }
    } catch (error) {
        displayError('Failed to process front image: ' + error.message, frontResults);
    }

    updateCompareButton();
    updateVerifyButton();
    hideLoading();
});

// Extract Back button - process back side only
extractBackBtn.addEventListener('click', async () => {
    if (!backIdFile) return;

    showLoading();
    backExtractedId = null;
    idsMatch = false;
    validationStatus.classList.add('hidden');

    try {
        const backData = await extractId(backIdFile);
        displayResults(backData, backResults, 'back');
        if (backData.success && backData.ocr_result?.extracted_id) {
            backExtractedId = backData.ocr_result.extracted_id;
        }
    } catch (error) {
        displayError('Failed to process back image: ' + error.message, backResults);
    }

    updateCompareButton();
    updateVerifyButton();
    hideLoading();
});

// Compare button - validate if both IDs match
compareBtn.addEventListener('click', () => {
    if (!frontExtractedId || !backExtractedId) return;
    validateIds();
});

// Verify button - direct face comparison
verifyBtn.addEventListener('click', async () => {
    if (!idsMatch || !selfieFile || !frontIdFile) return;

    showLoading();

    try {
        const formData = new FormData();
        formData.append('id_card', frontIdFile);  // Send front ID image directly
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
async function extractId(file) {
    const formData = new FormData();
    formData.append('image', file);

    const response = await fetch('/extract-id', {
        method: 'POST',
        body: formData
    });

    return await response.json();
}

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

function resetFrontResults() {
    // Reset front extraction state
    frontExtractedId = null;
    idsMatch = false;
    validationStatus.classList.add('hidden');
    frontResults.innerHTML = '<p class="placeholder">Upload front side to see results</p>';

    // Reset selfie and verification when front changes
    resetSelfieAndVerification();
    updateCompareButton();
}

function resetBackResults() {
    // Reset back extraction state
    backExtractedId = null;
    idsMatch = false;
    validationStatus.classList.add('hidden');
    backResults.innerHTML = '<p class="placeholder">Upload back side to see results</p>';

    // Reset selfie and verification when back changes
    resetSelfieAndVerification();
    updateCompareButton();
}

function resetSelfieAndVerification() {
    selfieFile = null;
    selfiePreview.classList.add('hidden');
    selfiePrompt.classList.remove('hidden');
    selfieUploadArea.classList.remove('has-image');
    selfieInput.value = '';
    verifyResults.innerHTML = '';
    updateVerifyButton();
}

function validateIds() {
    validationStatus.classList.remove('hidden', 'match', 'mismatch');

    if (frontExtractedId && backExtractedId) {
        if (frontExtractedId === backExtractedId) {
            idsMatch = true;
            validationStatus.classList.add('match');
            validationStatus.innerHTML = `✓ IDs Match: <strong>${frontExtractedId}</strong>`;
        } else {
            idsMatch = false;
            validationStatus.classList.add('mismatch');
            validationStatus.innerHTML = `✗ IDs Don't Match: Front (${frontExtractedId}) ≠ Back (${backExtractedId})`;
        }
    } else if (frontExtractedId || backExtractedId) {
        idsMatch = false;
        validationStatus.classList.add('mismatch');
        const found = frontExtractedId ? `Front: ${frontExtractedId}` : `Back: ${backExtractedId}`;
        validationStatus.innerHTML = `⚠ ID found only on one side (${found})`;
    } else {
        idsMatch = false;
        validationStatus.classList.add('mismatch');
        validationStatus.innerHTML = '✗ No ID detected on either side';
    }

    updateVerifyButton();
}

function displayResults(data, container, side = 'front') {
    if (!data.success) {
        container.innerHTML = `
            <div class="result-item">
                <span class="result-label">Error</span>
                <span class="result-value error">${data.error || 'Unknown error'}</span>
            </div>
        `;
        return;
    }

    const ocr = data.ocr_result;

    // Store OCR results for translation
    if (side === 'front') {
        frontOcrResults = ocr.text_results || [];
        frontTranslations = null;
        frontShowTranslated = false;
    } else {
        backOcrResults = ocr.text_results || [];
        backTranslations = null;
        backShowTranslated = false;
    }

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

    // Check if there's Arabic text to translate
    const hasArabic = (ocr.text_results || []).some(t => t.detected_language === 'ar');

    // Show detailed text results with per-text language
    if (ocr.text_results && ocr.text_results.length > 0) {
        html += `
            <div class="texts-list">
                <div class="texts-header">
                    <span class="texts-label">Extracted Text</span>
                    ${hasArabic ? `<button class="translate-btn" id="translate-${side}-btn" onclick="toggleTranslation('${side}')">🌐 Translate</button>` : ''}
                </div>
                <div class="texts-content" id="texts-${side}">
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

    container.innerHTML = html;
}

// Translation functions
async function toggleTranslation(side) {
    const btn = document.getElementById(`translate-${side}-btn`);
    const textsContainer = document.getElementById(`texts-${side}`);
    const ocrResults = side === 'front' ? frontOcrResults : backOcrResults;
    let translations = side === 'front' ? frontTranslations : backTranslations;
    let showTranslated = side === 'front' ? frontShowTranslated : backShowTranslated;

    if (!ocrResults || ocrResults.length === 0) return;

    // If already showing translated, toggle back to original
    if (showTranslated) {
        displayOriginalTexts(textsContainer, ocrResults);
        btn.textContent = '🌐 Translate';
        btn.classList.remove('translated');
        if (side === 'front') frontShowTranslated = false;
        else backShowTranslated = false;
        return;
    }

    // If we don't have translations yet, fetch them
    if (!translations) {
        btn.textContent = '⏳ Translating...';
        btn.disabled = true;

        try {
            // Get only Arabic texts
            const arabicTexts = ocrResults
                .filter(t => t.detected_language === 'ar')
                .map(t => t.text);

            if (arabicTexts.length === 0) {
                btn.textContent = '🌐 Translate';
                btn.disabled = false;
                return;
            }

            const response = await fetch('/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texts: arabicTexts })
            });

            const data = await response.json();

            if (data.success) {
                // Create a map of original -> translated
                translations = {};
                data.translations.forEach(t => {
                    translations[t.original] = t.translated;
                });

                if (side === 'front') frontTranslations = translations;
                else backTranslations = translations;
            } else {
                throw new Error(data.error || 'Translation failed');
            }
        } catch (error) {
            console.error('Translation error:', error);
            btn.textContent = '❌ Error';
            btn.disabled = false;
            setTimeout(() => {
                btn.textContent = '🌐 Translate';
            }, 2000);
            return;
        }

        btn.disabled = false;
    }

    // Display translated texts
    displayTranslatedTexts(textsContainer, ocrResults, translations);
    btn.textContent = '🔄 Show Original';
    btn.classList.add('translated');
    if (side === 'front') frontShowTranslated = true;
    else backShowTranslated = true;
}

function displayOriginalTexts(container, ocrResults) {
    container.innerHTML = ocrResults.map(t =>
        `<span class="text-with-lang"><span class="text-lang">${t.detected_language_display}</span> ${escapeHtml(t.text)}</span>`
    ).join('');
}

function displayTranslatedTexts(container, ocrResults, translations) {
    container.innerHTML = ocrResults.map(t => {
        if (t.detected_language === 'ar' && translations[t.text]) {
            // Show both original and translated for Arabic
            return `<span class="text-with-lang translated">
                <span class="text-lang">🇬🇧 EN</span>
                <span class="translated-text">${escapeHtml(translations[t.text])}</span>
                <span class="original-text-small">(${escapeHtml(t.text)})</span>
            </span>`;
        } else {
            // Non-Arabic text stays the same
            return `<span class="text-with-lang"><span class="text-lang">${t.detected_language_display}</span> ${escapeHtml(t.text)}</span>`;
        }
    }).join('');
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

function displayError(message, container) {
    container.innerHTML = `
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

function updateExtractFrontButton() {
    extractFrontBtn.disabled = !frontIdFile;
}

function updateExtractBackButton() {
    extractBackBtn.disabled = !backIdFile;
}

function updateCompareButton() {
    compareBtn.disabled = !frontExtractedId || !backExtractedId;
}

function updateVerifyButton() {
    verifyBtn.disabled = !idsMatch || !selfieFile;
}

function showLoading() {
    loading.classList.remove('hidden');
}

function hideLoading() {
    loading.classList.add('hidden');
}
