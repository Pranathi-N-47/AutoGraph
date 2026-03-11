// =====================================================================
// TAB SWITCHING
// =====================================================================
function switchTab(name) {
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.querySelectorAll('.tab-btn').forEach(b => {
        if (b.textContent.toLowerCase().includes(name === 'text' ? 'text' : 'image'))
            b.classList.add('active');
    });
}

// =====================================================================
// MERMAID INIT
// =====================================================================
mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    flowchart: { htmlLabels: false }
});

let panZoomInstance = null;
let renderCounter = 0;

// =====================================================================
// COLOR APPLIER
// =====================================================================
function applyColorsToMermaid(code) {
    const unifiedColors = document.getElementById('unified-colors').checked;
    const actionCol   = document.getElementById('col-action').value;
    const decisionCol = document.getElementById('col-decision').value;
    const textCol     = document.getElementById('col-text').value;
    const startCol    = unifiedColors ? actionCol : document.getElementById('col-start').value;
    const endCol      = unifiedColors ? actionCol : document.getElementById('col-end').value;

    const lines = code.split('\n').filter(l => !l.trim().startsWith('style '));
    if (lines.length <= 1) return code;

    let nodeIds = [], decisionNodes = new Set(), outgoing = new Set(), seen = new Set();
    const nodeRegex    = /\b([A-Za-z_]\w*)\s*[\[{\(]/g;
    const diamondRegex = /\b([A-Za-z_]\w*)\s*\{/g;
    const arrowRegex   = /\b([A-Za-z_]\w*)\s*(?:\[[^\]]*\]|\{[^\}]*\}|\([^\)]*\))?\s*--/g;

    lines.slice(1).forEach(line => {
        let match;
        const nodeRx = new RegExp(nodeRegex);
        while ((match = nodeRx.exec(line)) !== null) {
            if (!seen.has(match[1]) && !["graph","flowchart","style","classDef","click"].includes(match[1])) {
                seen.add(match[1]); nodeIds.push(match[1]);
            }
        }
        const diamondRx = new RegExp(diamondRegex);
        while ((match = diamondRx.exec(line)) !== null) decisionNodes.add(match[1]);
        const arrowRx = new RegExp(arrowRegex);
        while ((match = arrowRx.exec(line)) !== null) outgoing.add(match[1]);
    });

    const terminalNodes = new Set([...nodeIds].filter(x => !outgoing.has(x)));
    const startNode = nodeIds.length > 0 ? nodeIds[0] : null;

    const styleLines = [];
    nodeIds.forEach(id => {
        let color = actionCol;
        if (id === startNode)            color = startCol;
        else if (terminalNodes.has(id))  color = endCol;
        else if (decisionNodes.has(id))  color = decisionCol;
        styleLines.push(`style ${id} fill:${color},color:${textCol},stroke:${color}`);
    });

    return [...lines, ...styleLines].join('\n');
}

// =====================================================================
// RENDER
// =====================================================================
async function renderDiagram() {
    const rawCode     = document.getElementById('mermaid-code').value;
    const coloredCode = applyColorsToMermaid(rawCode);
    const container   = document.getElementById('diagram-preview');

    try {
        if (panZoomInstance) { panZoomInstance.destroy(); panZoomInstance = null; }
        container.innerHTML = '';

        renderCounter++;
        const { svg } = await mermaid.render(`mermaid-svg-${renderCounter}`, coloredCode);
        container.innerHTML = svg;
        const svgElement = container.querySelector('svg');

        svgElement.removeAttribute('width');
        svgElement.removeAttribute('height');
        svgElement.removeAttribute('style');
        svgElement.style.width  = '100%';
        svgElement.style.height = '100%';

        panZoomInstance = svgPanZoom(svgElement, {
            zoomEnabled: true,
            controlIconsEnabled: true,
            fit: true,
            center: true,
            minZoom: 0.1,
            maxZoom: 50,
            zoomScaleSensitivity: 0.2
        });
    } catch (err) {
        console.error(err);
        container.innerHTML = `<div style="color:red; padding: 20px;">Syntax Error in Mermaid Code</div>`;
    }
}

// =====================================================================
// EVENT LISTENERS — TEXT TAB
// =====================================================================
document.getElementById('unified-colors').addEventListener('change', (e) => {
    document.getElementById('col-start').disabled = e.target.checked;
    document.getElementById('col-end').disabled   = e.target.checked;
    renderDiagram();
});

document.getElementById('mermaid-code').addEventListener('input', renderDiagram);

['col-action', 'col-decision', 'col-start', 'col-end', 'col-text'].forEach(id => {
    document.getElementById(id).addEventListener('input', renderDiagram);
});

document.getElementById('btn-generate').addEventListener('click', async () => {
    const btn         = document.getElementById('btn-generate');
    const statusMsg   = document.getElementById('status-text');
    const userText    = document.getElementById('user-text').value;
    const orientation = document.getElementById('orientation').value;

    btn.disabled        = true;
    btn.innerText       = 'Talking to Backend…';
    statusMsg.innerText = '';

    try {
        const response = await fetch('http://127.0.0.1:5000/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: userText, orientation })
        });
        if (!response.ok) throw new Error('Backend Error');
        const data = await response.json();
        if (data.warning) {
            statusMsg.style.color = '#e65100';
            statusMsg.innerText   = '⚠️ ' + data.warning;
        }
        document.getElementById('mermaid-code').value = data.mermaid_code;
        renderDiagram();
    } catch (err) {
        statusMsg.style.color = '#d32f2f';
        statusMsg.innerText   = 'Connection failed. Is the backend running?';
    } finally {
        btn.disabled  = false;
        btn.innerText = 'Generate Flowchart';
    }
});

// =====================================================================
// EVENT LISTENERS — VISION TAB
// =====================================================================
const imageInput  = document.getElementById('image-input');
const imageThumb  = document.getElementById('image-preview-thumb');
const btnGenImage = document.getElementById('btn-generate-image');
const uploadArea  = document.getElementById('upload-area');

uploadArea.addEventListener('dragover',  (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', ()  => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        imageInput.files = e.dataTransfer.files;
        handleFileSelect();
    }
});

imageInput.addEventListener('change', handleFileSelect);

function handleFileSelect() {
    const file = imageInput.files[0];
    if (!file) return;
    imageThumb.src          = URL.createObjectURL(file);
    imageThumb.style.display = 'block';
    btnGenImage.disabled    = false;
}

btnGenImage.addEventListener('click', async () => {
    const file        = imageInput.files[0];
    const statusMsg   = document.getElementById('status-vision');
    const orientation = document.getElementById('vision-orientation').value;

    if (!file) { statusMsg.innerText = 'Please select an image first.'; return; }

    btnGenImage.disabled  = true;
    btnGenImage.innerText = 'Analysing Image…';
    statusMsg.innerText   = '';

    try {
        const formData = new FormData();
        formData.append('image', file);
        formData.append('orientation', orientation);

        const response = await fetch('http://127.0.0.1:5000/generate-image', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(err.detail || 'Backend Error');
        }

        const data = await response.json();
        if (data.warning) {
            statusMsg.style.color = '#e65100';
            statusMsg.innerText   = '⚠️ ' + data.warning;
        }
        document.getElementById('mermaid-code').value = data.mermaid_code;
        renderDiagram();
    } catch (err) {
        statusMsg.style.color = '#d32f2f';
        statusMsg.innerText   = 'Error: ' + err.message;
    } finally {
        btnGenImage.disabled  = false;
        btnGenImage.innerText = 'Convert Image';
    }
});

// =====================================================================
// EXPORT
// =====================================================================
document.getElementById('btn-live').addEventListener('click', () => {
    const code  = applyColorsToMermaid(document.getElementById('mermaid-code').value);
    const state = { code, mermaid: { theme: 'default' } };
    const b64   = btoa(JSON.stringify(state));
    window.open(`https://mermaid.live/edit#base64:${b64}`, '_blank');
});

document.getElementById('btn-download').addEventListener('click', async () => {
    const btn  = document.getElementById('btn-download');
    const orig = btn.innerText;
    btn.innerText = 'Generating…';
    btn.disabled  = true;

    try {
        const coloredCode = applyColorsToMermaid(document.getElementById('mermaid-code').value);
        const uniqueId    = 'export-' + Date.now();
        const { svg }     = await mermaid.render(uniqueId, coloredCode);

        const tempDiv     = document.createElement('div');
        tempDiv.innerHTML = svg;
        const svgElem     = tempDiv.querySelector('svg');

        const viewBox = svgElem.getAttribute('viewBox').split(' ');
        const width   = parseFloat(viewBox[2]);
        const height  = parseFloat(viewBox[3]);

        svgElem.setAttribute('width', width);
        svgElem.setAttribute('height', height);
        svgElem.style.backgroundColor = '#ffffff';
        svgElem.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        svgElem.setAttribute('xmlns:xhtml', 'http://www.w3.org/1999/xhtml');

        let svgData = new XMLSerializer().serializeToString(svgElem);
        svgData     = svgData.replace(/@import\s+url\([^)]+\);?/g, '');

        const base64Data = btoa(unescape(encodeURIComponent(svgData)));
        const imgSource  = `data:image/svg+xml;base64,${base64Data}`;

        const img       = new Image();
        img.crossOrigin = 'Anonymous';
        img.onload = () => {
            const canvas  = document.createElement('canvas');
            canvas.width  = width  * 2;
            canvas.height = height * 2;
            const ctx     = canvas.getContext('2d');
            ctx.scale(2, 2);
            ctx.drawImage(img, 0, 0);

            const a    = document.createElement('a');
            a.href     = canvas.toDataURL('image/png');
            a.download = 'autograph-diagram.png';
            a.click();

            btn.innerText = orig;
            btn.disabled  = false;
        };
        img.onerror = () => {
            alert('Browser failed to parse the SVG data.');
            btn.innerText = orig;
            btn.disabled  = false;
        };
        img.src = imgSource;

    } catch (err) {
        console.error('Export failed:', err);
        alert('Failed to generate image. Check console for details.');
        btn.innerText = orig;
        btn.disabled  = false;
    }
});

// =====================================================================
// INITIAL RENDER
// =====================================================================
renderDiagram();