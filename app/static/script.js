const chatHistory = document.getElementById('chatHistory');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const suggestionChips = document.getElementById('suggestionChips');

// Drawer elements
const catalogDrawer = document.getElementById('catalogDrawer');
const toggleCatalogBtn = document.getElementById('toggleCatalogBtn');
const closeCatalogBtn = document.getElementById('closeCatalogBtn');
const catalogList = document.getElementById('catalogList');
const catalogSearchInput = document.getElementById('catalogSearchInput');
const filterCheckboxes = document.querySelectorAll('.filter-tag input');

// Modal elements
const compareModal = document.getElementById('compareModal');
const compareViewBtn = document.getElementById('compareViewBtn');
const closeCompareBtn = document.getElementById('closeCompareBtn');
const compareHeaders = document.getElementById('compareHeaders');
const compareBody = document.getElementById('compareBody');
const compareEmptyState = document.getElementById('compareEmptyState');
const compareCountSpan = document.getElementById('compareCount');

// Sidebar Context elements
const trackRole = document.querySelector('#trackRole .value');
const trackSkills = document.querySelector('#trackSkills .value');
const trackDuration = document.querySelector('#trackDuration .value');
const trackRemote = document.querySelector('#trackRemote .value');

// State Management
let messages = [];
let catalogAssessments = []; // Store fetched assessments
let selectedAssessments = new Map(); // Track all loaded assessments by name for comparison lookup
let compareList = new Set(); // Names of assessments currently being compared

// Test Type Code Mapping
const TEST_TYPE_MAP = {
    "A": "Ability & Aptitude",
    "B": "Situational Judgement (SJT)",
    "C": "Competency",
    "D": "Development",
    "E": "Assessment Exercise",
    "K": "Knowledge & Skills",
    "P": "Personality & Behaviour",
    "S": "Simulation"
};

// Initial Setup
document.addEventListener('DOMContentLoaded', () => {
    // Load local storage session if exists (optional, let's start fresh)
    fetchCatalogData();
    setupEventListeners();
});

function setupEventListeners() {
    // Input key/resize events
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if(this.value.trim() !== '') {
            sendBtn.removeAttribute('disabled');
        } else {
            sendBtn.setAttribute('disabled', 'true');
        }
    });

    userInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);
    newChatBtn.addEventListener('click', resetConversation);

    // Sidebar presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.getAttribute('data-prompt');
            sendPresetPrompt(prompt);
        });
    });

    // Suggestion chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const prompt = chip.getAttribute('data-prompt');
            sendPresetPrompt(prompt);
        });
    });

    // Catalog drawer triggers
    toggleCatalogBtn.addEventListener('click', () => {
        catalogDrawer.classList.toggle('open');
        if (catalogDrawer.classList.contains('open')) {
            renderCatalogList();
        }
    });
    closeCatalogBtn.addEventListener('click', () => catalogDrawer.classList.remove('open'));

    // Catalog filters & search
    catalogSearchInput.addEventListener('input', renderCatalogList);
    filterCheckboxes.forEach(cb => cb.addEventListener('change', renderCatalogList));

    // Comparison modal triggers
    compareViewBtn.addEventListener('click', openCompareModal);
    closeCompareBtn.addEventListener('click', () => compareModal.classList.remove('open'));
    
    // Close modal on click outside content
    compareModal.addEventListener('click', (e) => {
        if (e.target === compareModal) {
            compareModal.classList.remove('open');
        }
    });
}

// Fetch Catalog Data
async function fetchCatalogData() {
    try {
        const response = await fetch('/catalog');
        if (response.ok) {
            catalogAssessments = await response.json();
        } else {
            throw new Error('Catalog endpoint not available');
        }
    } catch (e) {
        console.warn("Using fallback local catalog data", e);
        // Fallback catalog list matching standard test traces
        catalogAssessments = [
            {
                "name": "Verify G+ (General Ability)",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-g-plus/",
                "description": "Combines numerical, deductive, and inductive reasoning.",
                "test_type": "A",
                "duration": 36,
                "remote_support": true,
                "adaptive_support": true,
                "category": "Cognitive Ability"
            },
            {
                "name": "OPQ32r",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/opq32r/",
                "description": "Occupational Personality Questionnaire for predicting workplace behavior.",
                "test_type": "P",
                "duration": 25,
                "remote_support": true,
                "adaptive_support": false,
                "category": "Personality & Behaviour"
            },
            {
                "name": "Java 8 (New)",
                "url": "https://www.shl.com/solutions/products/product-catalog/view/java-8-new/",
                "description": "Assesses knowledge of Java programming concepts and syntax.",
                "test_type": "K",
                "duration": 40,
                "remote_support": true,
                "adaptive_support": false,
                "category": "Knowledge & Skills"
            }
        ];
    }

    // Cache assessments into lookup map
    catalogAssessments.forEach(item => {
        selectedAssessments.set(item.name, item);
    });
}

// Send Message
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    // Reset input state
    userInput.value = '';
    userInput.style.height = 'auto';
    sendBtn.setAttribute('disabled', 'true');

    // Add user message to screen & state
    appendMessage(text, 'user');
    messages.push({ role: "user", content: text });
    
    // Heuristic Context Tracker Update
    updateContextTracker(text);

    // Show typing
    const indicatorId = showTypingIndicator();
    scrollToBottom();

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: messages })
        });

        const data = await response.json();
        
        // Remove typing indicator
        document.getElementById(indicatorId).remove();

        // Add to state and display
        messages.push({ role: "assistant", content: data.reply });
        
        // Save any newly found assessments in response into our lookup map
        if (data.recommendations) {
            data.recommendations.forEach(rec => {
                if (!selectedAssessments.has(rec.name)) {
                    selectedAssessments.set(rec.name, {
                        name: rec.name,
                        url: rec.url,
                        test_type: rec.test_type,
                        description: "Recommended SHL individual test solution.",
                        duration: null,
                        remote_support: true,
                        adaptive_support: false
                    });
                }
            });
        }

        appendMessage(data.reply, 'ai', data.recommendations);
        
        // Proactively refine context values from chatbot's structured results if available
        if (data.recommendations && data.recommendations.length > 0) {
            const firstRec = selectedAssessments.get(data.recommendations[0].name) || data.recommendations[0];
            if (firstRec.category) {
                trackRole.textContent = firstRec.category;
            }
        }

    } catch (error) {
        console.error('Error:', error);
        document.getElementById(indicatorId).remove();
        appendMessage("Sorry, I encountered an issue connecting to the server. Please try again.", 'ai');
        messages.pop(); // Revert user message from state
    }
}

// Preset Prompts helper
function sendPresetPrompt(promptText) {
    userInput.value = promptText;
    userInput.dispatchEvent(new Event('input'));
    sendMessage();
}

// Custom simple Markdown formatter
function formatMarkdown(text) {
    let formatted = escapeHtml(text);
    
    // Bold: **text**
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Bullet points: * item or - item
    const lines = formatted.split('\n');
    let inList = false;
    let listHTML = [];
    
    for (let line of lines) {
        const cleanLine = line.trim();
        if (cleanLine.startsWith('* ') || cleanLine.startsWith('- ')) {
            if (!inList) {
                listHTML.push('<ul>');
                inList = true;
            }
            listHTML.push(`<li>${cleanLine.substring(2)}</li>`);
        } else {
            if (inList) {
                listHTML.push('</ul>');
                inList = false;
            }
            listHTML.push(line);
        }
    }
    
    if (inList) {
        listHTML.push('</ul>');
    }
    
    return listHTML.join('\n');
}

// Append Message UI
function appendMessage(text, sender, recommendations = []) {
    const group = document.createElement('div');
    group.className = `message-group ${sender}`;
    
    const icon = sender === 'user' ? 'fa-user' : 'fa-robot';
    const contentHTML = sender === 'user' ? escapeHtml(text) : formatMarkdown(text);
    
    let html = `
        <div class="avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="message-content">
            <div class="bubble">${contentHTML}</div>
    `;

    // Render cards for AI recommendations
    if (recommendations && recommendations.length > 0) {
        html += `<div class="recommendations-container">`;
        recommendations.forEach(rec => {
            // Retrieve full assessment details if available
            const details = selectedAssessments.get(rec.name) || {
                name: rec.name,
                url: rec.url,
                test_type: rec.test_type,
                description: "Assessment from the SHL Catalog.",
                duration: null,
                remote_support: true,
                adaptive_support: false
            };

            const typeLabel = TEST_TYPE_MAP[details.test_type] || `Type ${details.test_type}`;
            const durationLabel = details.duration ? `${details.duration} mins` : "Duration varies";
            const isComparing = compareList.has(details.name);
            const activeClass = isComparing ? 'active' : '';
            const compareTitle = isComparing ? 'Remove from comparison' : 'Compare assessment';

            html += `
                <div class="rec-card" data-name="${escapeHtml(details.name)}">
                    <div class="rec-header">
                        <h3>${escapeHtml(details.name)}</h3>
                        <span class="badge ${details.test_type}">${escapeHtml(details.test_type)}</span>
                    </div>
                    <div class="rec-desc">${escapeHtml(details.description)}</div>
                    <div class="rec-meta">
                        <div class="meta-item"><i class="fa-solid fa-clock"></i> <span>${durationLabel}</span></div>
                        <div class="meta-item"><i class="fa-solid fa-earth-americas"></i> <span>${details.remote_support ? 'Remote' : 'On-site'}</span></div>
                        ${details.adaptive_support ? '<div class="meta-item"><i class="fa-solid fa-chart-line"></i> <span>Adaptive</span></div>' : ''}
                    </div>
                    <div class="rec-actions">
                        <a href="${escapeHtml(details.url)}" target="_blank" class="rec-link">
                            View Test <i class="fa-solid fa-arrow-up-right-from-square"></i>
                        </a>
                        <button class="compare-btn ${activeClass}" data-name="${escapeHtml(details.name)}" onclick="toggleCompare('${escapeHtml(details.name)}', this)" title="${compareTitle}">
                            <i class="fa-solid fa-scale-balanced"></i>
                        </button>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    }

    html += `</div>`;
    group.innerHTML = html;
    
    chatHistory.appendChild(group);
    scrollToBottom();
}

// Typing Indicator helper
function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const group = document.createElement('div');
    group.id = id;
    group.className = 'message-group ai';
    
    group.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content">
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
    `;
    
    chatHistory.appendChild(group);
    return id;
}

// Reset Conversation
function resetConversation() {
    messages = [];
    compareList.clear();
    updateCompareCount();
    
    // Clear chat display
    chatHistory.innerHTML = `
        <div class="message-group ai">
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content">
                <div class="bubble">Session reset. How can I help you find the right SHL assessment today?</div>
            </div>
        </div>
    `;
    
    // Clear sidebar context
    trackRole.textContent = "Not specified";
    trackSkills.textContent = "None";
    trackDuration.textContent = "No limit";
    trackRemote.textContent = "Optional";
}

// Update Active Context Sidebar Tracker
function updateContextTracker(text) {
    const textLower = text.toLowerCase();
    
    // Skill matches
    const skills = [];
    if (textLower.includes('java')) skills.push('Java');
    if (textLower.includes('python')) skills.push('Python');
    if (textLower.includes('c++') || textLower.includes('cplusplus')) skills.push('C++');
    if (textLower.includes('javascript') || textLower.includes(' js ')) skills.push('JavaScript');
    if (textLower.includes('sql')) skills.push('SQL');
    if (textLower.includes('coding') || textLower.includes('programming')) skills.push('Coding');
    
    if (skills.length > 0) {
        trackSkills.textContent = skills.join(', ');
    }

    // Role matches
    if (textLower.includes('engineer') || textLower.includes('developer')) {
        trackRole.textContent = "Software Engineering";
    } else if (textLower.includes('leader') || textLower.includes('manager') || textLower.includes('leadership')) {
        trackRole.textContent = "Leadership / Management";
    } else if (textLower.includes('sales') || textLower.includes('account executive')) {
        trackRole.textContent = "Sales";
    } else if (textLower.includes('support') || textLower.includes('customer service')) {
        trackRole.textContent = "Customer Service";
    } else if (textLower.includes('general') || textLower.includes('graduate')) {
        trackRole.textContent = "General Entry";
    }

    // Duration matches
    const minutesMatch = textLower.match(/under\s+(\d+)\s+min/i) || textLower.match(/less\s+than\s+(\d+)\s+min/i) || textLower.match(/(\d+)\s+min/i);
    if (minutesMatch) {
        trackDuration.textContent = `≤ ${minutesMatch[1]} mins`;
    }

    // Remote Testing matches
    if (textLower.includes('remote') || textLower.includes('home')) {
        trackRemote.textContent = "Required";
    } else if (textLower.includes('on-site') || textLower.includes('office') || textLower.includes('invigilated')) {
        trackRemote.textContent = "On-site / Supervised";
    }
}

// Catalog Drawer Render
function renderCatalogList() {
    const query = catalogSearchInput.value.toLowerCase().trim();
    
    // Get checked test types
    const activeTypes = Array.from(filterCheckboxes)
        .filter(cb => cb.checked)
        .map(cb => cb.value);

    // Filter catalog
    const filtered = catalogAssessments.filter(item => {
        const matchesQuery = item.name.toLowerCase().includes(query) || 
                             item.description.toLowerCase().includes(query) ||
                             (item.category && item.category.toLowerCase().includes(query));
        const matchesType = activeTypes.includes(item.test_type);
        return matchesQuery && matchesType;
    });

    if (filtered.length === 0) {
        catalogList.innerHTML = `<div class="catalog-loading">No assessments match filters.</div>`;
        return;
    }

    catalogList.innerHTML = '';
    filtered.forEach(item => {
        const typeLabel = TEST_TYPE_MAP[item.test_type] || `Type ${item.test_type}`;
        const isComparing = compareList.has(item.name);
        const activeClass = isComparing ? 'active' : '';

        const card = document.createElement('div');
        card.className = 'catalog-card';
        card.innerHTML = `
            <div class="catalog-card-header">
                <h4>${escapeHtml(item.name)}</h4>
                <span class="badge ${item.test_type}">${escapeHtml(item.test_type)}</span>
            </div>
            <div class="catalog-card-desc">${escapeHtml(item.description)}</div>
            <div class="catalog-card-actions">
                <a href="${escapeHtml(item.url)}" target="_blank" class="view-link">
                    View Catalog <i class="fa-solid fa-arrow-up-right-from-square"></i>
                </a>
                <button class="compare-btn ${activeClass}" data-name="${escapeHtml(item.name)}" onclick="toggleCompare('${escapeHtml(item.name)}', this)" title="${compareList.has(item.name) ? 'Remove from comparison' : 'Compare assessment'}">
                    <i class="fa-solid fa-scale-balanced"></i>
                </button>
            </div>
        `;
        catalogList.appendChild(card);
    });
}

// Toggle Compare Selection
window.toggleCompare = function(name, btnElement) {
    if (compareList.has(name)) {
        compareList.delete(name);
        btnElement.classList.remove('active');
        btnElement.title = "Compare assessment";
    } else {
        compareList.add(name);
        btnElement.classList.add('active');
        btnElement.title = "Remove from comparison";
    }
    
    // Sync active class across all copies of this button (e.g. in chat cards and catalog cards)
    document.querySelectorAll(`.compare-btn[data-name="${CSS.escape(name)}"]`).forEach(btn => {
        btn.classList.toggle('active', compareList.has(name));
        btn.title = compareList.has(name) ? "Remove from comparison" : "Compare assessment";
    });
    
    updateCompareCount();
};

function updateCompareCount() {
    compareCountSpan.textContent = compareList.size;
    if (compareList.size > 0) {
        compareViewBtn.style.background = 'rgba(99, 102, 241, 0.2)';
        compareViewBtn.style.borderColor = 'var(--accent)';
    } else {
        compareViewBtn.style.background = 'var(--card-bg)';
        compareViewBtn.style.borderColor = 'var(--card-border)';
    }
}

// Build Comparison Modal
function openCompareModal() {
    compareHeaders.innerHTML = '<th>Feature</th>';
    compareBody.innerHTML = '';
    
    if (compareList.size === 0) {
        compareHeaders.style.display = 'none';
        compareEmptyState.style.display = 'flex';
        compareModal.classList.add('open');
        return;
    }
    
    compareHeaders.style.display = 'table-row';
    compareEmptyState.style.display = 'none';

    const selectedList = [];
    compareList.forEach(name => {
        const item = selectedAssessments.get(name);
        if (item) selectedList.push(item);
    });

    // 1. Add headers
    selectedList.forEach(item => {
        const th = document.createElement('th');
        th.textContent = item.name;
        compareHeaders.appendChild(th);
    });

    // 2. Features list to compare
    const features = [
        { label: "Category", key: "category" },
        { label: "Test Type", key: "test_type", format: (val) => `${val} - ${TEST_TYPE_MAP[val] || ''}` },
        { label: "Duration", key: "duration", format: (val) => val ? `${val} minutes` : "Not specified" },
        { label: "Remote Support", key: "remote_support", format: (val) => val ? "✅ Yes" : "❌ No" },
        { label: "Adaptive (IRT)", key: "adaptive_support", format: (val) => val ? "✅ Yes (Adaptive)" : "❌ No (Linear)" },
        { label: "Description", key: "description" },
        { 
            label: "Action", 
            key: "url", 
            format: (val) => `<a href="${val}" target="_blank" class="rec-link" style="padding: 6px 12px; font-size:12px;">View Test</a>` 
        }
    ];

    features.forEach(feat => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td><strong>${feat.label}</strong></td>`;
        
        selectedList.forEach(item => {
            const rawVal = item[feat.key];
            const displayVal = feat.format ? feat.format(rawVal) : (rawVal || 'N/A');
            const td = document.createElement('td');
            td.innerHTML = displayVal;
            tr.appendChild(td);
        });
        
        compareBody.appendChild(tr);
    });

    compareModal.classList.add('open');
}

// Helpers
function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
