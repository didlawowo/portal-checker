// Récupération des données depuis Flask
window.initialData = window.initialData || [];
window.autoswaggerEnabled = window.autoswaggerEnabled !== undefined ? window.autoswaggerEnabled : false;
let currentData = [...initialData];
let sortConfig = {
    field: 'url',
    direction: 'asc'
};

// Cache pour les données Swagger
let swaggerData = null;

// Fonction pour mettre à jour les flèches de tri
function updateSortArrows() {
    // Reset all arrows - use optional chaining for elements that may not exist
    const sortElements = ['namespaceSort', 'nameSort', 'urlSort', 'statusSort', 'response_timeSort', 'ssl_daysSort'];
    sortElements.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '';
    });

    // Set arrow for current sort field
    const arrow = sortConfig.direction === 'asc' ? '↑' : '↓';
    const elementId = sortConfig.field + 'Sort';
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = arrow;
    }
}

// Fonction pour trier les données
function sortTable(field) {
    if (sortConfig.field === field) {
        sortConfig.direction = sortConfig.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortConfig.field = field;
        sortConfig.direction = 'asc';
    }

    currentData.sort((a, b) => {
        let aVal = a[field] || '';
        let bVal = b[field] || '';
        
        // Convert to string for consistent comparison
        aVal = String(aVal).toLowerCase();
        bVal = String(bVal).toLowerCase();
        
        let comparison = 0;
        if (aVal < bVal) comparison = -1;
        if (aVal > bVal) comparison = 1;
        return sortConfig.direction === 'asc' ? comparison : -comparison;
    });

    updateSortArrows();
    renderTable();
}

// Fonction pour obtenir la classe CSS du status
function getStatusClass(status) {
    if (status === 200) return 'status-200';
    if (status === 301 || status === 302) return 'status-301';
    if (status === 401) return 'status-401';
    if (status === 403) return 'status-403';
    if (status === 404) return 'status-404';
    if (status === 405) return 'status-405';
    if (status === 408) return 'status-408';
    if (status === 429) return 'status-429';
    if (status === 502 || status === 503) return 'status-502';
    return 'status-error';
}

// SVG icons for status display
const statusIcons = {
    success: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/></svg>',
    redirect: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46A7.93 7.93 0 0020 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74A7.93 7.93 0 004 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg>',
    warning: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
    forbidden: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8 0-1.85.63-3.55 1.69-4.9L16.9 18.31C15.55 19.37 13.85 20 12 20zm6.31-3.1L7.1 5.69C8.45 4.63 10.15 4 12 4c4.42 0 8 3.58 8 8 0 1.85-.63 3.55-1.69 4.9z"/></svg>',
    notFound: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11 18h2v-2h-2v2zm1-16C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm0-14c-2.21 0-4 1.79-4 4h2c0-1.1.9-2 2-2s2 .9 2 2c0 2-3 1.75-3 5h2c0-2.25 3-2.5 3-5 0-2.21-1.79-4-4-4z"/></svg>',
    timeout: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>',
    rateLimit: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M13.5.67s.74 2.65.74 4.8c0 2.06-1.35 3.73-3.41 3.73-2.07 0-3.63-1.67-3.63-3.73l.03-.36C5.21 7.51 4 10.62 4 14c0 4.42 3.58 8 8 8s8-3.58 8-8C20 8.61 17.41 3.8 13.5.67zM11.71 19c-1.78 0-3.22-1.4-3.22-3.14 0-1.62 1.05-2.76 2.81-3.12 1.77-.36 3.6-1.21 4.62-2.58.39 1.29.59 2.65.59 4.04 0 2.65-2.15 4.8-4.8 4.8z"/></svg>',
    error: '<svg class="status-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12 19 6.41z"/></svg>'
};

// Fonction pour obtenir l'icône du status
function getStatusEmoji(status) {
    if (status === 200) return statusIcons.success;
    if (status === 301 || status === 302) return statusIcons.redirect;
    if (status === 401) return statusIcons.warning;
    if (status === 403) return statusIcons.forbidden;
    if (status === 404) return statusIcons.notFound;
    if (status === 405) return statusIcons.warning;
    if (status === 408) return statusIcons.timeout;
    if (status === 429) return statusIcons.rateLimit;
    if (status === 502 || status === 503) return statusIcons.error;
    return statusIcons.error;
}

// Fonction pour formater la colonne Info (Type + Class + Annotations)
function formatInfoColumn(item) {
    const parts = [];

    // Type badge
    const itemType = (item.type || '').toLowerCase();
    if (itemType === 'ingress') {
        parts.push(`<span class="info-badge info-type-ingress" title="Ingress">ing</span>`);
    } else if (itemType === 'httproute') {
        parts.push(`<span class="info-badge info-type-httproute" title="HTTPRoute">http</span>`);
    }

    // Class/Gateway badge
    if (item.ingress_class) {
        const fullName = item.ingress_class;
        // Pour les gateways, on extrait juste le nom court
        let shortName = fullName;
        if (fullName.includes('/')) {
            const parts = fullName.split('/');
            shortName = parts[parts.length - 1];
        }
        if (shortName.length > 10) {
            shortName = shortName.slice(0, 10) + '…';
        }
        parts.push(`<span class="info-badge info-class" title="${fullName}">${shortName}</span>`);
    }

    // Annotations badge (si présent)
    const annotationsHtml = formatAnnotationsCompact(item.annotations);
    if (annotationsHtml !== '-') {
        parts.push(annotationsHtml);
    }

    return parts.length > 0 ? `<div class="info-column">${parts.join('')}</div>` : '-';
}

// Fonction pour formater les annotations de manière compacte
function formatAnnotationsCompact(annotations) {
    if (!annotations) return '-';

    try {
        if (typeof annotations === 'string') {
            try {
                annotations = JSON.parse(annotations);
            } catch (e) {
                return annotations.trim() ? annotations : '-';
            }
        }

        const annotationKeys = Object.keys(annotations || {});
        if (annotationKeys.length === 0) {
            return '-';
        }

        const dataId = 'data-' + Math.random().toString(36).slice(2, 11);
        window.annotationsData = window.annotationsData || {};
        window.annotationsData[dataId] = annotations;

        return `<span class="info-badge info-annotations" onclick="showAnnotationsModal('${dataId}')" title="${annotationKeys.length} annotation${annotationKeys.length > 1 ? 's' : ''}">${annotationKeys.length}</span>`;
    } catch (error) {
        return '-';
    }
}

// Fonction pour formater les informations SSL
function formatSSLInfo(ssl_info) {
    if (!ssl_info) {
        return '<span style="color: #999; font-size: 10px;">N/A</span>';
    }

    // Check if it's an HTTP-only URL
    if (ssl_info.http_only === true) {
        return '<span style="color: #ea580c; background: #ffedd5; padding: 2px 4px; border-radius: 3px; font-size: 10px; font-weight: 600;" title="HTTP uniquement - Pas de certificat SSL">HTTP</span>';
    }

    if (ssl_info.days_remaining === undefined) {
        return '<span style="color: #ea580c; background: #ffedd5; padding: 2px 4px; border-radius: 3px; font-size: 10px; font-weight: 600;" title="Certificat SSL non disponible">N/A</span>';
    }

    const days = ssl_info.days_remaining;
    let color, bgColor;

    if (days < 0) {
        // Expiré
        color = '#dc2626';
        bgColor = '#fee2e2';
    } else if (days <= 15) {
        // Critique (< 15 jours)
        color = '#dc2626';
        bgColor = '#fee2e2';
    } else if (days <= 30) {
        // Avertissement (15-30 jours)
        color = '#ea580c';
        bgColor = '#ffedd5';
    } else {
        // OK (> 30 jours)
        color = '#16a34a';
        bgColor = '#dcfce7';
    }

    const expiryDate = new Date(ssl_info.expiry_date);
    const formattedDate = expiryDate.toLocaleDateString('fr-FR', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });

    const title = `Expire le ${formattedDate} (${days} jour${days > 1 ? 's' : ''})`;

    return `
        <span style="
            background: ${bgColor};
            color: ${color};
            padding: 2px 4px;
            border-radius: 3px;
            font-size: 10px;
            white-space: nowrap;
            display: inline-block;
            font-weight: 600;
            line-height: 1;
        " title="${title}">
            ${days}j
        </span>
    `;
}

// Fonction pour rendre le tableau
function renderTable() {
    const tbody = document.getElementById('resultsTable');
    tbody.innerHTML = '';

    currentData.forEach(item => {
        // Stocker les jours SSL pour le tri
        if (item.ssl_info && item.ssl_info.days_remaining !== undefined) {
            item.ssl_days = item.ssl_info.days_remaining;
        } else {
            item.ssl_days = 9999; // Valeur par défaut pour les URLs sans SSL
        }

        const tr = document.createElement('tr');

        // Préparer l'URL pour l'affichage (sans doubler le protocole)
        const displayUrl = item.url.startsWith('http') ? item.url : `https://${item.url}`;
        const linkUrl = displayUrl;

        tr.innerHTML = `
            <td>${item.namespace}</td>
            <td>${item.name}</td>
            <td>${formatInfoColumn(item)}</td>
            ${window.autoswaggerEnabled ? `<td>${getSwaggerButton(item.url)}</td>` : ''}
            <td>${formatSSLInfo(item.ssl_info)}</td>
            <td><a href="${linkUrl}" target="_blank" title="${displayUrl}">${displayUrl}</a></td>
            <td>
                <span class="status-badge ${getStatusClass(item.status)}">
                    ${getStatusEmoji(item.status)} ${item.status}
                </span>
            </td>
            <td>${item.response_time ? Math.round(item.response_time) + ' ms' : '-'}</td>
            <td style="text-align: center;">
                ${item.status >= 400 ? `<button class="exclude-btn" onclick="excludeUrl('${item.url}')" title="Exclure cette URL">×</button>` : '-'}
            </td>
            <td>${item.details || ''}</td>`;
        tbody.appendChild(tr);
    });
}

// Fonction pour formater les annotations - bouton compact avec nombre
function formatAnnotations(annotations) {
    if (!annotations) return '-';

    try {
        // Si c'est déjà une chaîne, essayez de l'analyser comme JSON
        if (typeof annotations === 'string') {
            try {
                annotations = JSON.parse(annotations);
            } catch (e) {
                // Si ce n'est pas du JSON valide, retournez tel quel si non vide
                return annotations.trim() ? annotations : '-';
            }
        }

        // Vérifier si l'objet annotations a des propriétés
        const annotationKeys = Object.keys(annotations || {});
        if (annotationKeys.length === 0) {
            return '-';
        }

        // Générer un ID unique pour ce bloc d'annotations
        const dataId = 'data-' + Math.random().toString(36).substr(2, 9);

        // Stocker les données d'annotations pour la modale
        window.annotationsData = window.annotationsData || {};
        window.annotationsData[dataId] = annotations;

        // Créer un bouton compact avec le nombre
        return `
            <button class="annotations-btn" onclick="showAnnotationsModal('${dataId}')" title="${annotationKeys.length} annotation${annotationKeys.length > 1 ? 's' : ''}">
                ${annotationKeys.length}
            </button>
        `;
    } catch (error) {
        // En cas d'erreur, retourner un tiret si vide ou le texte brut
        const stringValue = String(annotations);
        return stringValue.trim() ? stringValue : '-';
    }
}

// Fonction pour afficher la modale avec les annotations
function showAnnotationsModal(dataId) {
    const annotations = window.annotationsData[dataId];
    if (!annotations) return;

    const modal = document.getElementById('annotationsModal');
    const modalBody = document.getElementById('modalBody');
    const modalTitle = document.getElementById('modalTitle');

    // Mettre à jour le titre
    const annotationKeys = Object.keys(annotations);
    modalTitle.textContent = `Annotations (${annotationKeys.length})`;

    // Construire le contenu
    let content = '';
    for (const [key, value] of Object.entries(annotations)) {
        let displayValue = value;
        let valueClass = '';
        
        if (typeof value === 'object') {
            displayValue = JSON.stringify(value, null, 2);
            valueClass = 'json';
        }
        
        content += `
            <div class="annotation-item">
                <div class="annotation-key">${key}</div>
                <div class="annotation-value ${valueClass}">${displayValue}</div>
            </div>
        `;
    }

    modalBody.innerHTML = content;
    modal.style.display = 'block';
}

// Fonction pour fermer la modale
function closeAnnotationsModal() {
    const modal = document.getElementById('annotationsModal');
    modal.style.display = 'none';
}

// Fonction pour récupérer le bouton Swagger
function getSwaggerButton(url) {
    const normalizedUrl = url.replace(/^https?:\/\//, '');

    // Vérifier si une API Swagger existe pour cette URL
    if (swaggerData && swaggerData.results && swaggerData.results.length > 0) {
        const api = swaggerData.results.find(api => {
            const apiHost = api.host.replace(/^https?:\/\//, '');
            return apiHost === normalizedUrl || normalizedUrl.startsWith(apiHost);
        });

        if (api) {
            const securityClass = api.security_issues > 0 ? 'security-warning' : '';
            const title = `${api.title} (${api.endpoint_count} endpoints${api.security_issues > 0 ? ', ' + api.security_issues + ' problèmes de sécurité' : ''})`;

            return `
                <button class="swagger-btn ${securityClass}" onclick="showSwaggerModal('${api.host}')" title="${title}">
                    API${api.security_issues > 0 ? ' !' : ''}
                </button>
            `;
        }
    }

    // No Swagger data found - show scan button
    return `
        <button class="swagger-scan-btn" onclick="scanSwagger('${url.replace(/'/g, "\\'")}', event)" title="Scanner pour Swagger/OpenAPI">
            ?
        </button>
    `;
}

// Fonction pour afficher la modale Swagger
function showSwaggerModal(host) {
    if (!swaggerData || !swaggerData.results) return;

    const api = swaggerData.results.find(api => api.host === host);
    if (!api) return;
    
    const modal = document.getElementById('swaggerModal');
    const modalBody = document.getElementById('swaggerModalBody');
    const modalTitle = document.getElementById('swaggerModalTitle');
    
    modalTitle.textContent = `API Swagger - ${api.title}`;
    
    let content = `
        <div class="swagger-api-header">
            <div class="swagger-api-title">${api.title}</div>
            <div class="swagger-api-info">
                Version: ${api.version} | Host: ${api.host} | ${api.endpoint_count} endpoint${api.endpoint_count > 1 ? 's' : ''}
            </div>
            ${api.description ? `<div class="swagger-api-info" style="margin-top: 8px;">${api.description}</div>` : ''}
        </div>
    `;
    
    // Afficher les problèmes de sécurité s'il y en a
    if (api.security_issues > 0 && (api.pii_detected.length > 0 || api.secrets_detected.length > 0)) {
        content += `
            <div class="swagger-security-issues">
                <div class="swagger-security-title"><svg class="inline-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg> Problèmes de sécurité détectés (${api.security_issues})</div>
        `;
        
        if (api.pii_detected.length > 0) {
            content += '<div style="margin-bottom: 8px;"><strong>PII détectée:</strong></div>';
            api.pii_detected.forEach(pii => {
                content += `<div class="swagger-security-item">${pii}</div>`;
            });
        }
        
        if (api.secrets_detected.length > 0) {
            content += '<div style="margin-bottom: 8px;"><strong>Secrets détectés:</strong></div>';
            api.secrets_detected.forEach(secret => {
                content += `<div class="swagger-security-item">${secret}</div>`;
            });
        }
        
        content += '</div>';
    }
    
    // Afficher les endpoints
    content += '<div class="swagger-endpoints">';
    content += `<h4>Endpoints (${api.endpoint_count})</h4>`;
    
    api.endpoints.forEach((endpoint, index) => {
        const methodClass = endpoint.method.toLowerCase();
        const endpointId = `endpoint-${index}`;
        
        content += `
            <div class="swagger-endpoint">
                <div class="swagger-endpoint-header" onclick="toggleSwaggerEndpoint('${endpointId}')">
                    <span class="swagger-method ${methodClass}">${endpoint.method}</span>
                    <span class="swagger-path">${endpoint.path}</span>
                    ${endpoint.has_security ? '<svg class="inline-icon lock-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z"/></svg>' : '<svg class="inline-icon unlock-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h1.9c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z"/></svg>'}
                </div>
                <div class="swagger-endpoint-details" id="${endpointId}">
                    ${endpoint.description ? `<p><strong>Description:</strong> ${endpoint.description}</p>` : ''}
                    ${endpoint.tags.length > 0 ? `<p><strong>Tags:</strong> ${endpoint.tags.join(', ')}</p>` : ''}
                    <p><strong>Paramètres:</strong> ${endpoint.parameter_count}</p>
                    <p><strong>Sécurité:</strong> ${endpoint.has_security ? 'Protégé' : 'Non protégé'}</p>
                    <p><strong>URL complète:</strong> <code>${endpoint.url}</code></p>
                </div>
            </div>
        `;
    });
    
    content += '</div>';
    
    modalBody.innerHTML = content;
    modal.style.display = 'block';
}

// Fonction pour basculer l'affichage des détails d'un endpoint
function toggleSwaggerEndpoint(endpointId) {
    const details = document.getElementById(endpointId);
    if (details.style.display === 'none' || details.style.display === '') {
        details.style.display = 'block';
    } else {
        details.style.display = 'none';
    }
}

// Fonction pour fermer la modale Swagger
function closeSwaggerModal() {
    const modal = document.getElementById('swaggerModal');
    modal.style.display = 'none';
}

// Fonction pour charger les données Swagger
async function loadSwaggerData() {
    try {
        const response = await fetch('/api/swagger');
        if (response.ok) {
            swaggerData = await response.json();
            // Rerender le tableau pour mettre à jour les boutons Swagger
            renderTable();
        }
    } catch (error) {
        // Swagger data not available - silent fail
    }
}

// Fonction pour afficher les URLs exclues
async function showExcludedUrls() {
    const modal = document.getElementById('excludedUrlsModal');
    const modalBody = document.getElementById('excludedUrlsModalBody');

    // Afficher la modale avec le message de chargement
    modal.style.display = 'block';
    modalBody.innerHTML = '<p class="loading-text">Chargement...</p>';

    try {
        const response = await fetch('/api/excluded-urls');

        if (!response.ok) {
            throw new Error(`Erreur HTTP ${response.status}`);
        }

        const data = await response.json();
        const excludedUrls = data.excluded_urls || [];

        if (excludedUrls.length === 0) {
            modalBody.innerHTML = '<p class="no-data">Aucune URL exclue</p>';
        } else {
            let html = '<div class="excluded-urls-list">';
            html += `<p class="excluded-count">Nombre d'URLs exclues: <strong>${excludedUrls.length}</strong></p>`;
            html += '<ul class="excluded-list">';

            excludedUrls.forEach(url => {
                html += `<li class="excluded-item">${url}</li>`;
            });

            html += '</ul></div>';
            modalBody.innerHTML = html;
        }
    } catch (error) {
        modalBody.innerHTML = '<p class="error-text">Erreur lors du chargement des URLs exclues</p>';
    }
}

// Fonction pour fermer la modale des URLs exclues
function closeExcludedUrlsModal() {
    const modal = document.getElementById('excludedUrlsModal');
    modal.style.display = 'none';
}

// Fonction pour exclure une URL
async function excludeUrl(url) {
    if (!confirm(`Voulez-vous vraiment exclure l'URL "${url}" ?\n\nElle sera ajoutée au fichier excluded-urls.yaml et ne sera plus testée.`)) {
        return;
    }

    try {
        const response = await fetch('/api/exclude', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });

        const data = await response.json();

        if (response.ok) {
            alert(`${data.message}\n\nPour voir les changements, cliquez sur le bouton "Refresh" en haut de la page.`);
            // Return to home page
            window.location.href = '/';
        } else {
            alert(`Erreur: ${data.error || data.message}`);
        }
    } catch (error) {
        alert(`Erreur lors de l'exclusion: ${error.message}`);
    }
}

// Fonction pour scanner une URL pour Swagger/OpenAPI
async function scanSwagger(url, event) {
    try {
        // Encode URL for path parameter
        const encodedUrl = encodeURIComponent(url);

        // Show loading indicator
        const button = event.target;
        const originalContent = button.innerHTML;
        button.innerHTML = '<svg class="inline-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>';
        button.disabled = true;

        const response = await fetch(`/api/swagger/scan/${encodedUrl}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (response.ok) {
            if (data.result) {
                alert(`Swagger trouvé pour ${url}!\n\n${data.result.title}\n${data.result.endpoint_count} endpoints détectés`);
                // Reload Swagger data and refresh table
                await loadSwaggerData();
                renderTable();
            } else {
                alert(data.message);
            }
        } else {
            throw new Error(data.error || 'Erreur lors du scan');
        }

        // Restore button
        button.innerHTML = originalContent;
        button.disabled = false;

    } catch (error) {
        alert(`Erreur lors du scan Swagger: ${error.message}`);

        // Restore button on error
        if (button) {
            button.innerHTML = '?';
            button.disabled = false;
        }
    }
}

// Fonction de recherche
function handleSearch(event) {
    const searchTerm = event.target.value.toLowerCase();
    currentData = initialData.filter(item => {
        const searchableFields = [
            item.url || '',
            item.status ? item.status.toString() : '',
            item.namespace || '',
            item.name || '',
            item.type || '',
            item.ingress_class || '',
            item.gateway || '',
            item.details || '',
            item.annotations ? JSON.stringify(item.annotations) : ''
        ];

        return searchableFields.some(field =>
            field.toLowerCase().includes(searchTerm)
        );
    });
    renderTable();
}

// Initialisation au chargement du DOM
document.addEventListener('DOMContentLoaded', function() {
    // Écouteurs d'événements
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    // Écouteurs pour la modale annotations
    const annotationsModal = document.getElementById('annotationsModal');
    const annotationsCloseBtn = annotationsModal.querySelector('.modal-close');
    
    // Écouteurs pour la modale Swagger
    const swaggerModal = document.getElementById('swaggerModal');
    const swaggerCloseBtn = swaggerModal.querySelector('.swagger-modal-close');

    // Écouteurs pour la modale URLs exclues
    const excludedUrlsModal = document.getElementById('excludedUrlsModal');
    const excludedUrlsCloseBtn = excludedUrlsModal.querySelector('.excluded-modal-close');

    // Fermer les modales avec les boutons X
    annotationsCloseBtn.addEventListener('click', closeAnnotationsModal);
    swaggerCloseBtn.addEventListener('click', closeSwaggerModal);
    excludedUrlsCloseBtn.addEventListener('click', closeExcludedUrlsModal);
    
    // Fermer les modales en cliquant en dehors
    annotationsModal.addEventListener('click', function(event) {
        if (event.target === annotationsModal) {
            closeAnnotationsModal();
        }
    });
    
    swaggerModal.addEventListener('click', function(event) {
        if (event.target === swaggerModal) {
            closeSwaggerModal();
        }
    });

    excludedUrlsModal.addEventListener('click', function(event) {
        if (event.target === excludedUrlsModal) {
            closeExcludedUrlsModal();
        }
    });

    // Fermer les modales avec la touche Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAnnotationsModal();
            closeSwaggerModal();
            closeExcludedUrlsModal();
        }
    });

    // Charger les données Swagger seulement si activé
    if (window.autoswaggerEnabled) {
        loadSwaggerData();
    }

    // Rendu initial
    updateSortArrows();
    renderTable();
});