// Global state
let sessionId = null;
let currentTab = 'triage';
let fileStorage = {
    triage: [],
    reports: [],
    scribe: [],
    translator: [],
    polypharmacy: []
};

const API_BASE = 'http://localhost:8000/api';

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    initializeSession();
    setupTabNavigation();
    setupDragDrop();
    setupFileInputs();
    setupProcessButtons();
});

async function initializeSession() {
    try {
        const response = await fetch(`${API_BASE}/session/create`, {
            method: 'POST'
        });
        const data = await response.json();
        sessionId = data.session_id;
        document.getElementById('session-id').textContent = sessionId.substring(0, 8) + '...';
        showToast('Session created successfully', 'success');
    } catch (error) {
        console.error('Error creating session:', error);
        showToast('Failed to create session', 'error');
    }
}

// ==================== TAB NAVIGATION ====================
function setupTabNavigation() {
    const navBtns = document.querySelectorAll('.nav-btn');
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active from all nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Mark nav button as active
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    currentTab = tabName;
}

// ==================== FILE HANDLING ====================
function setupDragDrop() {
    const tabs = ['triage', 'reports', 'scribe', 'translator', 'polypharmacy'];
    
    tabs.forEach(tab => {
        const dragDrop = document.getElementById(`${tab}-drag-drop`);
        if (!dragDrop) return;
        
        dragDrop.addEventListener('dragover', (e) => {
            e.preventDefault();
            dragDrop.classList.add('drag-over');
        });
        
        dragDrop.addEventListener('dragleave', () => {
            dragDrop.classList.remove('drag-over');
        });
        
        dragDrop.addEventListener('drop', (e) => {
            e.preventDefault();
            dragDrop.classList.remove('drag-over');
            handleFileSelect(tab, e.dataTransfer.files);
        });
    });
}

function setupFileInputs() {
    const tabs = ['triage', 'reports', 'scribe', 'translator', 'polypharmacy'];
    
    tabs.forEach(tab => {
        const input = document.getElementById(`${tab}-input`);
        if (!input) return;
        
        input.addEventListener('change', (e) => {
            handleFileSelect(tab, e.target.files);
        });
    });
}

function handleFileSelect(tab, files) {
    const maxFiles = (tab === 'translator') ? 1 : 10;
    
    if (files.length === 0) return;
    if (files.length > maxFiles) {
        showToast(`Maximum ${maxFiles} file(s) allowed`, 'error');
        return;
    }
    
    // Clear previous files
    fileStorage[tab] = [];
    
    // Store file objects
    Array.from(files).forEach(file => {
        if (file.type.startsWith('image/')) {
            fileStorage[tab].push(file);
        }
    });
    
    updatePreview(tab);
    
    // Enable process button
    const processBtn = document.getElementById(`${tab}-process`);
    if (processBtn && fileStorage[tab].length > 0) {
        processBtn.disabled = false;
    }
}

function updatePreview(tab) {
    const previewContainer = document.getElementById(`${tab}-preview`);
    previewContainer.innerHTML = '';
    
    fileStorage[tab].forEach((file, index) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const item = document.createElement('div');
            item.className = 'preview-item';
            item.innerHTML = `
                <img src="${e.target.result}" alt="Preview ${index + 1}">
                <button class="remove-btn" onclick="removeFile('${tab}', ${index})">✕</button>
            `;
            previewContainer.appendChild(item);
        };
        reader.readAsDataURL(file);
    });
    
    // Show file count
    if (fileStorage[tab].length > 0) {
        const fileCount = document.createElement('div');
        fileCount.className = 'file-count';
        fileCount.textContent = `${fileStorage[tab].length} file(s) selected`;
        previewContainer.prepend(fileCount);
    }
}

function removeFile(tab, index) {
    fileStorage[tab].splice(index, 1);
    updatePreview(tab);
    
    const processBtn = document.getElementById(`${tab}-process`);
    if (processBtn && fileStorage[tab].length === 0) {
        processBtn.disabled = true;
    }
}

// ==================== PROCESS BUTTONS ====================
function setupProcessButtons() {
    const tabs = ['triage', 'reports', 'scribe', 'translator', 'polypharmacy'];
    
    tabs.forEach(tab => {
        const btn = document.getElementById(`${tab}-process`);
        if (btn) {
            btn.addEventListener('click', () => processTab(tab));
        }
    });
}

async function processTab(tab) {
    if (fileStorage[tab].length === 0) {
        showToast('No files selected', 'error');
        return;
    }
    
    showLoading(true);
    
    try {
        const formData = new FormData();
        fileStorage[tab].forEach(file => {
            formData.append('files', file);
        });
        formData.append('session_id', sessionId);
        
        let endpoint = '';
        switch (tab) {
            case 'triage':
                endpoint = '/triage/process';
                break;
            case 'reports':
                endpoint = '/reports/process';
                break;
            case 'scribe':
                endpoint = '/scribe/process';
                break;
            case 'translator':
                endpoint = '/translator/process';
                break;
            case 'polypharmacy':
                endpoint = '/polypharmacy/process';
                break;
        }
        
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const result = await response.json();
        displayResults(tab, result);
        showToast('Processing completed successfully', 'success');
    } catch (error) {
        console.error('Error processing:', error);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// ==================== RESULTS DISPLAY ====================
function displayResults(tab, result) {
    const resultsContainer = document.getElementById(`${tab}-results`);
    resultsContainer.innerHTML = '';
    
    if (result.status !== 'success') {
        resultsContainer.innerHTML = `<p class="result-error">Error: ${result.error || 'Unknown error'}</p>`;
        return;
    }
    
    // Build results HTML based on tab
    let html = '';
    
    switch (tab) {
        case 'triage':
            html += buildTriageResults(result);
            break;
        case 'reports':
            html += buildReportsResults(result);
            break;
        case 'scribe':
            html += buildScribeResults(result);
            break;
        case 'translator':
            html += buildTranslatorResults(result);
            break;
        case 'polypharmacy':
            html += buildPolypharmacyResults(result);
            break;
    }
    
    resultsContainer.innerHTML = html;
}

function buildTriageResults(result) {
    const vitals = result.vitals_extraction;
    const physical = result.physical_assessment;
    const analysis = result.triage_analysis;
    
    let html = `
        <div class="result-item">
            <div class="result-label">📊 Vitals Extracted</div>
            <div class="result-content">
                ${buildVitalsTable(vitals)}
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">👁️ Physical Assessment</div>
            <div class="result-content">
                ${buildPhysicalAssessment(physical)}
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">🚑 Triage Analysis</div>
            <div class="result-content">
                ${buildTriageAnalysis(analysis)}
            </div>
        </div>
    `;
    
    return html;
}

function buildPhysicalAssessment(physical) {
    if (!physical) return '<p class="no-data">No physical assessment available</p>';
    
    let html = '<div class="physical-assessment">';
    
    if (physical.physical_condition) {
        html += `
            <div class="assessment-item">
                <span class="assessment-label">🩺 Overall Condition</span>
                <span class="assessment-value">${physical.physical_condition}</span>
            </div>
        `;
    }
    
    if (physical.distress_level) {
        let distressClass = 'info';
        let distressIcon = '🟢';
        if (physical.distress_level === 'Severe') { distressClass = 'danger'; distressIcon = '🔴'; }
        else if (physical.distress_level === 'Moderate') { distressClass = 'warning'; distressIcon = '🟡'; }
        else if (physical.distress_level === 'Mild') { distressClass = 'warning'; distressIcon = '🟡'; }
        
        html += `
            <div class="assessment-item">
                <span class="assessment-label">⚠️ Distress Level</span>
                <span class="assessment-badge ${distressClass}">${distressIcon} ${physical.distress_level}</span>
            </div>
        `;
    }
    
    if (physical.breathing_assessment) {
        html += `
            <div class="assessment-item">
                <span class="assessment-label">🫁 Breathing</span>
                <span class="assessment-value">${physical.breathing_assessment}</span>
            </div>
        `;
    }
    
    if (physical.consciousness) {
        let consciousnessClass = physical.consciousness === 'alert' ? 'success' : 
                                physical.consciousness === 'drowsy' ? 'warning' : 'danger';
        html += `
            <div class="assessment-item">
                <span class="assessment-label">🧠 Consciousness</span>
                <span class="assessment-badge ${consciousnessClass}">${physical.consciousness}</span>
            </div>
        `;
    }
    
    if (physical.visible_signs && physical.visible_signs.length > 0) {
        html += `
            <div class="assessment-item full-width">
                <span class="assessment-label">👀 Visible Signs</span>
                <div class="signs-list">
                    ${physical.visible_signs.map(sign => `<span class="sign-badge">${sign}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildVitalsTable(vitals) {
    if (!vitals) return '<p class="no-data">No vitals extracted</p>';
    
    let html = '<div class="vitals-grid">';
    const vitalsMap = {
        pulse: { label: '💓 Pulse', unit: 'bpm' },
        bp: { label: '🩺 Blood Pressure', unit: 'mmHg' },
        spo2: { label: '🫁 SpO2', unit: '%' },
        temperature: { label: '🌡️ Temperature', unit: '°C' }
    };
    
    for (const [key, config] of Object.entries(vitalsMap)) {
        const value = vitals[key];
        const displayValue = value === null || value === undefined ? 'Not recorded' : `${value} ${config.unit}`;
        html += `
            <div class="vital-item">
                <span class="vital-label">${config.label}</span>
                <span class="vital-value ${value === null ? 'missing' : ''}">${displayValue}</span>
            </div>
        `;
    }
    
    if (vitals.physical_signs) {
        html += `
            <div class="vital-item full-width">
                <span class="vital-label">👀 Physical Observations</span>
                <span class="vital-value">${vitals.physical_signs}</span>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildTriageAnalysis(analysis) {
    if (!analysis) return '<p class="no-data">No analysis available</p>';
    
    let statusClass = 'warning';
    let statusIcon = '🟡';
    if (analysis.priority === 'RED') { statusClass = 'danger'; statusIcon = '🔴'; }
    if (analysis.priority === 'GREEN') { statusClass = 'success'; statusIcon = '🟢'; }
    
    let html = `
        <div class="priority-badge ${statusClass}">
            <span class="priority-icon">${statusIcon}</span>
            <span class="priority-text">${analysis.priority || 'Unknown'} Priority</span>
        </div>
    `;
    
    if (analysis.justification_english) {
        html += `
            <div class="justification">
                <h4>🗣️ English</h4>
                <p>${analysis.justification_english}</p>
            </div>
        `;
    }
    
    if (analysis.justification_hindi) {
        html += `
            <div class="justification">
                <h4>🗣️ हिंदी</h4>
                <p>${analysis.justification_hindi}</p>
            </div>
        `;
    }
    
    if (analysis.recommended_action) {
        html += `
            <div class="action-box">
                <h4>💡 Recommended Action</h4>
                <p>${analysis.recommended_action}</p>
            </div>
        `;
    }
    
    // Show vitals flags if present
    if (analysis.key_vital_flags && analysis.key_vital_flags.length > 0) {
        html += `
            <div class="flags-list">
                <h4>⚠️ Vital Signs Concerns</h4>
                <ul>${analysis.key_vital_flags.map(flag => `<li class="vital-flag">${flag}</li>`).join('')}</ul>
            </div>
        `;
    }
    
    // Show physical flags if present
    if (analysis.physical_flags && analysis.physical_flags.length > 0) {
        html += `
            <div class="flags-list">
                <h4>👁️ Physical Assessment Concerns</h4>
                <ul>${analysis.physical_flags.map(flag => `<li class="physical-flag">${flag}</li>`).join('')}</ul>
            </div>
        `;
    }
    
    if (analysis.assessment_basis) {
        html += `
            <div class="assessment-basis">
                <span class="basis-badge">📋 Based on: ${analysis.assessment_basis}</span>
            </div>
        `;
    }
    
    return html;
}

function buildReportsResults(result) {
    const tests = result.extracted_tests;
    const explanations = result.patient_explanations;
    
    let html = `
        <div class="result-item">
            <div class="result-label">🔬 Extracted Tests</div>
            <div class="result-content">
                ${buildTestsTable(tests)}
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">📖 Patient Explanation</div>
            <div class="result-content">
                ${buildPatientExplanation(explanations)}
            </div>
        </div>
    `;
    return html;
}

function buildTestsTable(tests) {
    if (!tests || tests.length === 0) {
        return '<p class="no-data">⚠️ No test data extracted. The image might need better quality or different angle.</p>';
    }
    
    let html = '<div class="tests-table">';
    html += `
        <div class="test-header">
            <span>Test Name</span>
            <span>Result</span>
            <span>Reference Range</span>
            <span>Status</span>
        </div>
    `;
    
    for (const test of tests) {
        const statusClass = test.status === 'Normal' ? 'normal' : 
                           test.status === 'High' ? 'high' : 
                           test.status === 'Low' ? 'low' : 'unknown';
        
        html += `
            <div class="test-row">
                <span class="test-name">${test.test_name || 'Unknown'}</span>
                <span class="test-result">${test.result || 'N/A'} ${test.unit || ''}</span>
                <span class="test-range">${test.reference_range || 'N/A'}</span>
                <span class="test-status ${statusClass}">${test.status || 'Unknown'}</span>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildPatientExplanation(explanations) {
    if (!explanations || !explanations.explanations) {
        return '<p class="no-data">No explanations available</p>';
    }
    
    let html = '<div class="explanations-list">';
    
    for (const exp of explanations.explanations) {
        const statusIcon = exp.status === 'Normal' ? '✅' : 
                          exp.status === 'Concerning' ? '⚠️' : '❓';
        
        html += `
            <div class="explanation-item">
                <div class="exp-header">
                    <span class="exp-test-name">${statusIcon} ${exp.test_name}</span>
                    <span class="exp-status ${exp.status?.toLowerCase()}">${exp.status}</span>
                </div>
                <p class="exp-description">${exp.simple_explanation}</p>
                ${exp.analogy ? `<p class="exp-analogy">💡 <em>${exp.analogy}</em></p>` : ''}
            </div>
        `;
    }
    
    if (explanations.next_steps && explanations.next_steps.length > 0) {
        html += `
            <div class="next-steps">
                <h4>📋 Next Steps</h4>
                <ul>${explanations.next_steps.map(step => `<li>${step}</li>`).join('')}</ul>
            </div>
        `;
    }
    
    if (explanations.warning_signs) {
        html += `
            <div class="warning-signs">
                <h4>🚨 Warning Signs</h4>
                <p>${explanations.warning_signs}</p>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildScribeResults(result) {
    const notes = result.transcribed_notes;
    const summary = result.doctor_summary;
    
    let html = `
        <div class="result-item">
            <div class="result-label">✍️ Transcribed Notes</div>
            <div class="result-content">
                ${buildTranscribedNotes(notes)}
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">📋 Executive Summary</div>
            <div class="result-content">
                ${buildExecutiveSummary(summary)}
            </div>
        </div>
    `;
    return html;
}

function buildTranscribedNotes(notes) {
    if (!notes) return '<p class="no-data">No notes transcribed</p>';
    
    let html = '<div class="notes-sections">';
    
    if (notes.chief_complaints && notes.chief_complaints.length > 0) {
        html += `
            <div class="notes-section">
                <h4>🩺 Chief Complaints</h4>
                <ul class="complaints-list">
                    ${notes.chief_complaints.map(complaint => `<li>${complaint}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (notes.duration) {
        html += `
            <div class="notes-section">
                <h4>⏳ Duration of Illness</h4>
                <p class="duration-text">${notes.duration}</p>
            </div>
        `;
    }
    
    if (notes.previous_medications && notes.previous_medications.length > 0) {
        html += `
            <div class="notes-section">
                <h4>💊 Previous Medications</h4>
                <ul class="medications-list">
                    ${notes.previous_medications.map(med => `<li>${med}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (notes.allergies && notes.allergies.length > 0) {
        html += `
            <div class="notes-section">
                <h4>⚠️ Allergies</h4>
                <ul class="allergies-list">
                    ${notes.allergies.map(allergy => `<li class="allergy-item">${allergy}</li>`).join('')}
                </ul>
            </div>
        `;
    } else {
        html += `
            <div class="notes-section">
                <h4>⚠️ Allergies</h4>
                <p class="no-allergies">No allergies noted</p>
            </div>
        `;
    }
    
    if (notes.examination_findings && notes.examination_findings.length > 0) {
        html += `
            <div class="notes-section">
                <h4>🔍 Examination Findings</h4>
                <ul class="findings-list">
                    ${notes.examination_findings.map(finding => `<li>${finding}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildExecutiveSummary(summary) {
    if (!summary) return '<p class="no-data">No executive summary available</p>';
    
    let html = '<div class="executive-summary">';
    
    if (summary.executive_summary && summary.executive_summary.length > 0) {
        html += `
            <div class="summary-points">
                <h4>📌 Key Points</h4>
                <ol class="summary-list">
                    ${summary.executive_summary.map(point => `<li class="summary-point">${point}</li>`).join('')}
                </ol>
            </div>
        `;
    }
    
    if (summary.critical_flags && summary.critical_flags.length > 0) {
        html += `
            <div class="critical-flags">
                <h4>🚨 Critical Flags</h4>
                <ul class="flags-list">
                    ${summary.critical_flags.map(flag => `<li class="flag-item">${flag}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (summary.doctor_focus_time) {
        html += `
            <div class="focus-time">
                <span class="time-badge">⏱️ ${summary.doctor_focus_time}</span>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildTranslatorResults(result) {
    const translation = result.translation;
    const validation = result.validation;
    
    let html = `
        <div class="result-item">
            <div class="result-label">🌐 Translation</div>
            <div class="result-value">
                <pre>${JSON.stringify(translation, null, 2)}</pre>
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">✔️ Validation</div>
            <div class="result-value">
                <pre>${JSON.stringify(validation, null, 2)}</pre>
            </div>
        </div>
    `;
    return html;
}

function buildPolypharmacyResults(result) {
    const medicines = result.medicines_extracted;
    const analysis = result.safety_analysis;
    
    let html = `
        <div class="result-item">
            <div class="result-label">💊 Medicines Detected</div>
            <div class="result-content">
                ${buildMedicinesList(medicines)}
            </div>
        </div>
        <div class="result-item">
            <div class="result-label">⚠️ Safety Analysis</div>
            <div class="result-content">
                ${buildSafetyAnalysis(analysis)}
            </div>
        </div>
    `;
    
    return html;
}

function buildMedicinesList(medicines) {
    if (!medicines || medicines.length === 0) {
        return '<p class="no-data">⚠️ No medicines detected. Please ensure images show medicine strips or prescriptions clearly.</p>';
    }
    
    let html = '<div class="medicines-grid">';
    
    for (const med of medicines) {
        html += `
            <div class="medicine-card">
                <div class="med-header">
                    <span class="brand-name">${med.brand_name || '[Unclear]'}</span>
                    <span class="generic-name">${med.generic_name || '[Unclear]'}</span>
                </div>
                <div class="med-details">
                    <span class="strength">💪 ${med.strength || '[Unclear]'}</span>
                    <span class="form">💊 ${med.form || '[Unclear]'}</span>
                    ${med.frequency ? `<span class="frequency">⏰ ${med.frequency}</span>` : ''}
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    return html;
}

function buildSafetyAnalysis(analysis) {
    if (!analysis) return '<p class="no-data">No safety analysis available</p>';
    
    let urgencyClass = 'info';
    let urgencyIcon = '💙';
    if (analysis.urgency === 'High') { urgencyClass = 'danger'; urgencyIcon = '🔴'; }
    if (analysis.urgency === 'Medium') { urgencyClass = 'warning'; urgencyIcon = '🟡'; }
    if (analysis.urgency === 'Low') { urgencyClass = 'success'; urgencyIcon = '🟢'; }
    
    let html = `
        <div class="urgency-badge ${urgencyClass}">
            <span class="urgency-icon">${urgencyIcon}</span>
            <span class="urgency-text">${analysis.urgency || 'Unknown'} Urgency</span>
        </div>
    `;
    
    if (analysis.drug_interactions && analysis.drug_interactions.length > 0) {
        html += `
            <div class="interactions-section">
                <h4>⚠️ Drug Interactions</h4>
                <ul class="interactions-list">
                    ${analysis.drug_interactions.map(interaction => `<li class="interaction-item">${interaction}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (analysis.duplicate_medications && analysis.duplicate_medications.length > 0) {
        html += `
            <div class="duplicates-section">
                <h4>🔄 Duplicate Medications</h4>
                <ul class="duplicates-list">
                    ${analysis.duplicate_medications.map(dup => `<li class="duplicate-item">${dup}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (analysis.safety_warnings && analysis.safety_warnings.length > 0) {
        html += `
            <div class="warnings-section">
                <h4>🚨 Safety Warnings</h4>
                <ul class="warnings-list">
                    ${analysis.safety_warnings.map(warning => `<li class="warning-item">${warning}</li>`).join('')}
                </ul>
            </div>
        `;
    }
    
    if (analysis.recommendation) {
        html += `
            <div class="recommendation-box">
                <h4>💡 Pharmacist Recommendation</h4>
                <p>${analysis.recommendation}</p>
            </div>
        `;
    }
    
    return html;
}

// ==================== UI HELPERS ====================
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
}
