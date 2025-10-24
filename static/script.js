// Récupération des données depuis Flask
window.initialData = window.initialData || [];
let currentData = [...initialData];
let sortConfig = {
    field: 'url',
    direction: 'asc'
};

// Cache pour les données Swagger
let swaggerData = null;

// Fonction pour mettre à jour les flèches de tri
function updateSortArrows() {
    // Reset all arrows
    document.getElementById('namespaceSort').textContent = '';
    document.getElementById('nameSort').textContent = '';
    document.getElementById('typeSort').textContent = '';
    document.getElementById('urlSort').textContent = '';
    document.getElementById('statusSort').textContent = '';
    document.getElementById('response_timeSort').textContent = '';
    document.getElementById('ssl_daysSort').textContent = '';

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

// Fonction pour obtenir l'emoji du status
function getStatusEmoji(status) {
    if (status === 200) return '✅';
    if (status === 301 || status === 302) return '🔄';
    if (status === 401) return '⚠️';
    if (status === 403) return '🚫';
    if (status === 404) return '❓';
    if (status === 405) return '⚠️';
    if (status === 408) return '⏱️';
    if (status === 429) return '🐌';
    if (status === 502 || status === 503) return '💥';
    return '❌';
}

// Fonction pour obtenir l'ingress class ou la gateway
function getIngressClassOrGateway(item) {
    const itemType = (item.type || '').toLowerCase();

    if (itemType === 'ingress' && item.ingress_class) {
        return `<span style="background: #e5f3ff; color: #0066cc; padding: 1px 4px; border-radius: 3px; font-size: 11px; white-space: nowrap;">${item.ingress_class}</span>`;
    } else if (itemType === 'httproute' && item.ingress_class) {
        // Pour HTTPRoute, ingress_class contient "gateway/{name}"
        return `<span style="background: #f0f9ff; color: #0284c7; padding: 1px 4px; border-radius: 3px; font-size: 11px; white-space: nowrap;">${item.ingress_class}</span>`;
    }
    return '-';
}

// Fonction pour formater les informations SSL
function formatSSLInfo(ssl_info) {
    if (!ssl_info) {
        console.debug('No SSL info');
        return '<span style="color: #999; font-size: 10px;">N/A</span>';
    }

    // Check if it's an HTTP-only URL
    if (ssl_info.http_only === true) {
        return '<span style="color: #ea580c; background: #ffedd5; padding: 2px 4px; border-radius: 3px; font-size: 10px; font-weight: 600;" title="⚠️ HTTP uniquement - Pas de certificat SSL">⚠️ HTTP</span>';
    }

    if (ssl_info.days_remaining === undefined) {
        console.debug('SSL info exists but no days_remaining:', ssl_info);
        return '<span style="color: #ea580c; background: #ffedd5; padding: 2px 4px; border-radius: 3px; font-size: 10px; font-weight: 600;" title="⚠️ Certificat SSL non disponible">⚠️ N/A</span>';
    }

    console.debug('Formatting SSL info:', ssl_info);

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
            <td>${item.type}</td>
            <td>${getIngressClassOrGateway(item)}</td>
            <td>${formatAnnotations(item.annotations)}</td>
            <td>${getSwaggerButton(item.url)}</td>
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
                <div class="swagger-security-title">🚨 Problèmes de sécurité détectés (${api.security_issues})</div>
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
                    ${endpoint.has_security ? '🔒' : '🔓'}
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
        console.log('Swagger data not available:', error);
    }
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
            alert(`✅ ${data.message}\n\nPour voir les changements, cliquez sur le bouton "Refresh 🔄" en haut de la page.`);
            // Return to home page
            window.location.href = '/';
        } else {
            alert(`❌ Erreur: ${data.error || data.message}`);
        }
    } catch (error) {
        console.error('Error excluding URL:', error);
        alert(`❌ Erreur lors de l'exclusion: ${error.message}`);
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
        button.innerHTML = '⏳';
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
                alert(`✅ Swagger trouvé pour ${url}!\n\n${data.result.title}\n${data.result.endpoint_count} endpoints détectés`);
                // Reload Swagger data and refresh table
                await loadSwaggerData();
                renderTable();
            } else {
                alert(`ℹ️ ${data.message}`);
            }
        } else {
            throw new Error(data.error || 'Erreur lors du scan');
        }

        // Restore button
        button.innerHTML = originalContent;
        button.disabled = false;

    } catch (error) {
        console.error('Error scanning Swagger:', error);
        alert(`❌ Erreur lors du scan Swagger: ${error.message}`);

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
    // Log des données initiales pour debug
    console.log('Initial data loaded:', window.initialData.length, 'items');
    if (window.initialData.length > 0) {
        console.log('Sample item:', window.initialData[0]);
        console.log('Sample SSL info:', window.initialData[0].ssl_info);
    }

    // Écouteurs d'événements
    document.getElementById('searchInput').addEventListener('input', handleSearch);

    // Écouteurs pour la modale annotations
    const annotationsModal = document.getElementById('annotationsModal');
    const annotationsCloseBtn = annotationsModal.querySelector('.modal-close');
    
    // Écouteurs pour la modale Swagger
    const swaggerModal = document.getElementById('swaggerModal');
    const swaggerCloseBtn = swaggerModal.querySelector('.swagger-modal-close');
    
    // Fermer les modales avec les boutons X
    annotationsCloseBtn.addEventListener('click', closeAnnotationsModal);
    swaggerCloseBtn.addEventListener('click', closeSwaggerModal);
    
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
    
    // Fermer les modales avec la touche Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAnnotationsModal();
            closeSwaggerModal();
        }
    });

    // Charger les données Swagger
    loadSwaggerData();

    // Rendu initial
    updateSortArrows();
    renderTable();
});