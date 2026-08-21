pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

const themeToggle = document.getElementById('themeToggle');
const homeBtn = document.getElementById('homeBtn');
const brandHomeBtn = document.getElementById('brandHomeBtn');
const langToggle = document.getElementById('langToggle');
const langLabel = document.getElementById('langLabel');
const toastEl = document.getElementById('toast');
const fileInput = document.getElementById('fileInput');
const selectBtn = document.getElementById('selectBtn');
const addMoreBtn = document.getElementById('addMoreBtn');
const uploadBtn = document.getElementById('uploadBtn');
const cancelBtn = document.getElementById('cancelBtn');
const zipBtn = document.getElementById('zipBtn');

const uploadScreen = document.getElementById('uploadScreen');
const workspaceScreen = document.getElementById('workspaceScreen');
const filesGrid = document.getElementById('filesGrid');
const fileBadge = document.getElementById('fileBadge');

const resultsSummary = document.getElementById('resultsSummary');
const sumOrigSize = document.getElementById('sumOrigSize');
const sumNewSize = document.getElementById('sumNewSize');
const sumSavings = document.getElementById('sumSavings');
const unitSelect = document.getElementById('unitSelect');

let selectedFiles = [];
let processedFiles = [];
let lastTotalOrig = 0;
let lastTotalNew = 0;
let currentAbortController = null;

// --- I18N (NL / EN) ---
const translations = {
    nl: {
        homeTitle: 'Terug naar start',
        themeTitle: 'Schakel thema',
        heroTitle: 'Comprimeer PDF bestanden',
        heroSubtitle: 'Verklein de bestandsgrootte van je documenten in seconden.',
        dropTitle: 'Sleep je PDF-bestanden hierheen',
        dropSubtitle: 'of klik om te bladeren',
        chooseFilesBtn: 'Kies bestanden',
        filesLabel: 'Bestanden',
        addMoreBtn: '+ Toevoegen',
        statOriginal: 'Origineel',
        statNew: 'Nieuw',
        statSavings: 'Besparing',
        zipBtn: '📦 Download Alles als ZIP',
        panelCompression: 'Compressie',
        qMaxTitle: 'Maximale compressie',
        qMaxDesc: 'Laagste bestandsgrootte',
        qRecTitle: 'Aanbevolen',
        qRecDesc: 'Goede balans tussen kwaliteit en grootte',
        qHighTitle: 'Hoge kwaliteit',
        qHighDesc: 'Minimale compressie',
        panelOptions: 'Opties',
        maxSizeLabel: 'Gewenste max. grootte (MB)',
        unitLabel: 'Eenheid weergave',
        unitAuto: 'Automatisch (KB / MB)',
        unitKB: 'Altijd KB',
        unitMB: 'Altijd MB',
        startBtn: 'Start Compressie',
        cancelBtn: 'Annuleren',
        compressingText: 'Comprimeren...',
        cancelledText: 'Geannuleerd',
        connectionFailedText: 'Verbinding mislukt',
        downloadLink: '⬇ Download',
        zipMissing: 'ZIP bibliotheek niet geladen',
        downloadPrefix: 'gecomprimeerd_',
        zipFilename: 'gecomprimeerd_bestanden.zip',
        invalidPdfSingle: 'is geen geldig PDF-bestand en is overgeslagen.',
        invalidPdfMultiple: 'zijn geen geldige PDF-bestanden en zijn overgeslagen.',
        noValidFiles: 'Geen van de geselecteerde bestanden is een geldig PDF-bestand.',
    },
    en: {
        homeTitle: 'Back to home',
        themeTitle: 'Toggle theme',
        heroTitle: 'Compress PDF files',
        heroSubtitle: 'Reduce the file size of your documents in seconds.',
        dropTitle: 'Drag your PDF files here',
        dropSubtitle: 'or click to browse',
        chooseFilesBtn: 'Choose files',
        filesLabel: 'Files',
        addMoreBtn: '+ Add',
        statOriginal: 'Original',
        statNew: 'New',
        statSavings: 'Savings',
        zipBtn: '📦 Download All as ZIP',
        panelCompression: 'Compression',
        qMaxTitle: 'Maximum compression',
        qMaxDesc: 'Lowest file size',
        qRecTitle: 'Recommended',
        qRecDesc: 'Good balance between quality and size',
        qHighTitle: 'High quality',
        qHighDesc: 'Minimal compression',
        panelOptions: 'Options',
        maxSizeLabel: 'Desired max. size (MB)',
        unitLabel: 'Display unit',
        unitAuto: 'Automatic (KB / MB)',
        unitKB: 'Always KB',
        unitMB: 'Always MB',
        startBtn: 'Start Compression',
        cancelBtn: 'Cancel',
        compressingText: 'Compressing...',
        cancelledText: 'Cancelled',
        connectionFailedText: 'Connection failed',
        downloadLink: '⬇ Download',
        zipMissing: 'ZIP library not loaded',
        downloadPrefix: 'compressed_',
        zipFilename: 'compressed_files.zip',
        invalidPdfSingle: 'is not a valid PDF file and was skipped.',
        invalidPdfMultiple: 'are not valid PDF files and were skipped.',
        noValidFiles: 'None of the selected files is a valid PDF file.',
    }
};

let currentLang = localStorage.getItem('lang') || 'nl';

function t(key) {
    return (translations[currentLang] && translations[currentLang][key]) || translations.nl[key] || key;
}

function applyLanguage(lang) {
    currentLang = translations[lang] ? lang : 'nl';
    localStorage.setItem('lang', currentLang);
    document.documentElement.setAttribute('lang', currentLang);
    if (langLabel) langLabel.innerText = currentLang.toUpperCase();

    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        el.innerText = t(key);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const key = el.getAttribute('data-i18n-title');
        el.setAttribute('title', t(key));
    });

    // Herteken de al zichtbare grootte-teksten (bv. "Comprimeren...") in de nieuwe taal
    if (typeof refreshSizeDisplays === 'function' && selectedFiles.length > 0) {
        refreshSizeDisplays();
    }
}

if (langToggle) {
    langToggle.addEventListener('click', () => {
        const newLang = currentLang === 'nl' ? 'en' : 'nl';
        applyLanguage(newLang);
    });
}

applyLanguage(currentLang);

// --- TOAST MELDINGEN ---
let toastTimeout = null;
function showToast(message) {
    if (!toastEl) return;
    toastEl.innerText = message;
    toastEl.classList.add('show');
    if (toastTimeout) clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toastEl.classList.remove('show');
    }, 4000);
}

// De merknaam linksboven werkt nu ook als home-knop
if (brandHomeBtn) {
    brandHomeBtn.addEventListener('click', resetToHome);
    brandHomeBtn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            resetToHome();
        }
    });
}

function resetToHome() {
    // Breek eventuele lopende compressie af voordat we alles wissen.
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
    }
    selectedFiles = [];
    processedFiles = [];
    lastTotalOrig = 0;
    lastTotalNew = 0;
    resultsSummary.style.display = 'none';
    zipBtn.style.display = 'none';
    cancelBtn.style.display = 'none';
    uploadBtn.disabled = false;
    workspaceScreen.style.display = 'none';
    uploadScreen.style.display = 'flex';
}

if (homeBtn) homeBtn.addEventListener('click', resetToHome);

const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });
}

if (selectBtn) selectBtn.addEventListener('click', () => fileInput.click());
if (addMoreBtn) addMoreBtn.addEventListener('click', () => fileInput.click());

const dropZone = document.getElementById('dropZone');
if (dropZone) {
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            handleFiles(Array.from(e.dataTransfer.files));
        }
    });
}

if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        handleFiles(Array.from(e.target.files));
        fileInput.value = '';
    });
}

function handleFiles(files) {
    const validPdfs = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    const invalidFiles = files.filter(f => !f.name.toLowerCase().endsWith('.pdf'));

    if (invalidFiles.length) {
        const names = invalidFiles.map(f => f.name).join(', ');
        const reason = invalidFiles.length === 1 ? t('invalidPdfSingle') : t('invalidPdfMultiple');
        showToast(`${names} ${reason}`);
    }

    if (!validPdfs.length) {
        if (!invalidFiles.length) return;
        if (!files.length) return;
        // Alleen ongeldige bestanden geselecteerd: er is al een melding getoond hierboven.
        return;
    }

    selectedFiles = [...selectedFiles, ...validPdfs];
    renderWorkspace();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    if (selectedFiles.length === 0) {
        workspaceScreen.style.display = 'none';
        uploadScreen.style.display = 'flex';
    } else {
        renderWorkspace();
    }
}

function formatBytes(bytes) {
    const unit = unitSelect ? unitSelect.value : 'auto';

    if (unit === 'KB') return (bytes / 1024).toFixed(1) + ' KB';
    if (unit === 'MB') return (bytes / (1024 * 1024)).toFixed(2) + ' MB';

    if (bytes < 1024 * 1024) {
        return (bytes / 1024).toFixed(1) + ' KB';
    }
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

if (unitSelect) {
    unitSelect.addEventListener('change', () => {
        // BUGFIX: dit riep voorheen renderWorkspace() aan, wat de hele grid
        // (incl. thumbnails, voortgang en downloadknoppen) opnieuw opbouwde
        // en zo alle al gecomprimeerde resultaten wiste. Nu wordt alleen
        // de weergegeven tekst bijgewerkt.
        if (selectedFiles.length > 0) refreshSizeDisplays();
    });
}

function refreshSizeDisplays() {
    selectedFiles.forEach((file, index) => {
        const sizeText = document.getElementById(`size-text-${index}`);
        if (!sizeText) return;

        const processed = processedFiles[index];
        if (processed && processed.name === file.name) {
            sizeText.style.color = 'var(--text)';
            sizeText.innerText = `${formatBytes(file.size)} → ${formatBytes(processed.blob.size)}`;
        } else {
            sizeText.innerText = formatBytes(file.size);
        }
    });

    if (resultsSummary.style.display !== 'none' && processedFiles.length > 0) {
        showSummary(lastTotalOrig, lastTotalNew);
    }
}

async function generatePDFThumbnail(file, imgElement, placeholderElement) {
    try {
        const arrayBuffer = await file.arrayBuffer();
        const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        const page = await pdf.getPage(1);

        const viewport = page.getViewport({ scale: 1.5 });
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.height = viewport.height;
        canvas.width = viewport.width;

        await page.render({ canvasContext: context, viewport: viewport }).promise;

        imgElement.src = canvas.toDataURL();
        imgElement.style.display = 'block';
        if (placeholderElement) placeholderElement.style.display = 'none';
    } catch (err) {
        console.warn('Kan geen preview maken voor:', file.name, err);
    }
}

function renderWorkspace() {
    uploadScreen.style.display = 'none';
    workspaceScreen.style.display = 'flex';
    fileBadge.innerText = selectedFiles.length;

    filesGrid.innerHTML = '';
    selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.innerHTML = `
            <button class="btn-close" onclick="removeFile(${index})">&times;</button>
            <div class="file-preview-container">
                <span class="preview-placeholder" id="placeholder-${index}">📄</span>
                <img class="file-preview-img" id="preview-img-${index}" style="display: none;" alt="Preview">
            </div>
            <div class="file-meta">
                <div class="file-title" title="${file.name}">${file.name}</div>
                <div class="file-size-info" id="size-text-${index}">${formatBytes(file.size)}</div>
            </div>
            <div class="progress-track">
                <div class="progress-fill" id="progress-${index}"></div>
            </div>
            <div id="download-target-${index}"></div>
        `;
        filesGrid.appendChild(item);

        const imgEl = item.querySelector(`#preview-img-${index}`);
        const phEl = item.querySelector(`#placeholder-${index}`);
        generatePDFThumbnail(file, imgEl, phEl);
    });
}

document.querySelectorAll('.option-card').forEach(card => {
    card.addEventListener('click', () => {
        document.querySelectorAll('.option-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        card.querySelector('input[type="radio"]').checked = true;
    });
});

if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
        if (currentAbortController) {
            currentAbortController.abort();
        }
        cancelBtn.style.display = 'none';
        uploadBtn.disabled = false;
    });
}

if (uploadBtn) {
    uploadBtn.addEventListener('click', processFiles);
}

async function processFiles() {
    if (!selectedFiles.length) return;

    const selectedRadio = document.querySelector('input[name="quality"]:checked');
    const quality = selectedRadio ? selectedRadio.value : '/ebook';
    const maxTargetMB = document.getElementById('maxTargetMB') ? document.getElementById('maxTargetMB').value : 10;

    uploadBtn.disabled = true;
    cancelBtn.style.display = 'block';
    resultsSummary.style.display = 'none';
    zipBtn.style.display = 'none';
    processedFiles = [];

    const abortController = new AbortController();
    currentAbortController = abortController;

    let totalOrig = 0;
    let totalNew = 0;

    // Comprimeer één bestand; wordt hieronder met een concurrency-limiet
    // aangeroepen zodat bestanden niet meer op elkaar hoeven te wachten
    // (voorheen: sequentiële for-loop met await per bestand).
    async function compressOne(i) {
        const file = selectedFiles[i];
        totalOrig += file.size;

        const progressFill = document.getElementById(`progress-${i}`);
        const sizeText = document.getElementById(`size-text-${i}`);

        if (sizeText) {
            sizeText.style.color = 'var(--text)';
            sizeText.innerText = t('compressingText');
        }
        if (progressFill) progressFill.style.width = '50%';

        const formData = new FormData();
        formData.append('file', file);
        formData.append('quality', quality);
        formData.append('max_target_mb', maxTargetMB);

        try {
            // AANGEPAST: Relatieve URL zodat het via de cloud goed werkt
            const response = await fetch('/compress_single', {
                method: 'POST',
                body: formData,
                signal: abortController.signal,
            });

            if (!response.ok) throw new Error(`Server status: ${response.status}`);

            const blob = await response.blob();
            totalNew += blob.size;
            // BUGFIX: bewaar op dezelfde index als selectedFiles i.p.v. altijd
            // te pushen. Anders schuiven de resultaten op zodra één bestand
            // mislukt, en komen latere downloads/groottes niet meer overeen
            // met de juiste kaart.
            processedFiles[i] = { name: file.name, blob: blob };

            if (progressFill) progressFill.style.width = '100%';
            if (sizeText) {
                sizeText.innerText = `${formatBytes(file.size)} → ${formatBytes(blob.size)}`;
            }

            renderCardDownload(i, blob, file.name);

        } catch (err) {
            if (err.name === 'AbortError') {
                if (sizeText) {
                    sizeText.innerText = t('cancelledText');
                    sizeText.style.color = 'var(--text-muted)';
                }
                if (progressFill) progressFill.style.width = '0%';
                return;
            }
            console.error('Compressiefout:', err);
            if (sizeText) {
                sizeText.innerText = t('connectionFailedText');
                sizeText.style.color = 'var(--danger)';
            }
            if (progressFill) progressFill.style.width = '0%';
        }
    }

    // Max. aantal gelijktijdige uploads. Hoger dan 1 (voorheen effectief de
    // situatie door de sequentiële loop), maar begrensd zodat de server
    // (en de eigen internetverbinding van de gebruiker) niet overspoeld
    // wordt bij bijv. 20 bestanden tegelijk.
    const CONCURRENCY_LIMIT = 3;
    let nextIndex = 0;

    async function worker() {
        while (nextIndex < selectedFiles.length) {
            if (abortController.signal.aborted) return;
            const i = nextIndex;
            nextIndex += 1;
            await compressOne(i);
        }
    }

    const workers = Array.from(
        { length: Math.min(CONCURRENCY_LIMIT, selectedFiles.length) },
        () => worker()
    );
    await Promise.all(workers);

    cancelBtn.style.display = 'none';
    currentAbortController = null;
    uploadBtn.disabled = false;

    if (processedFiles.length > 0) {
        lastTotalOrig = totalOrig;
        lastTotalNew = totalNew;
        showSummary(totalOrig, totalNew);
        if (zipBtn) zipBtn.style.display = 'block';
    }
}

function renderCardDownload(index, blob, originalName) {
    const target = document.getElementById(`download-target-${index}`);
    if (!target) return;

    target.innerHTML = '';

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.className = 'download-btn';
    link.href = url;
    link.download = `${t('downloadPrefix')}${originalName}`;
    link.innerText = t('downloadLink');
    target.appendChild(link);
}

function showSummary(origBytes, newBytes) {
    sumOrigSize.innerText = formatBytes(origBytes);
    sumNewSize.innerText = formatBytes(newBytes);

    const savings = origBytes > 0 
        ? Math.max(0, Math.round(((origBytes - newBytes) / origBytes) * 100))
        : 0;
    
    sumSavings.innerText = `-${savings}%`;
    resultsSummary.style.display = 'flex';
}

if (zipBtn) {
    zipBtn.addEventListener('click', async () => {
        if (typeof JSZip === 'undefined') {
            alert(t('zipMissing'));
            return;
        }
        const zip = new JSZip();
        processedFiles.forEach(item => {
            if (item) zip.file(`${t('downloadPrefix')}${item.name}`, item.blob);
        });

        const zipContent = await zip.generateAsync({ type: 'blob' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(zipContent);
        link.download = t('zipFilename');
        link.click();
    });
}