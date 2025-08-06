// Récupération des données depuis Flask
window.initialData = window.initialData || [];
let currentData = [...initialData];
let sortConfig = {
    field: 'url',
    direction: 'asc'
};

// Fonction pour mettre à jour les flèches de tri
function updateSortArrows() {
    // Reset all arrows
    document.getElementById('namespaceSort').textContent = '';
    document.getElementById('nameSort').textContent = '';
    document.getElementById('typeSort').textContent = '';
    document.getElementById('urlSort').textContent = '';
    document.getElementById('statusSort').textContent = '';
    document.getElementById('response_timeSort').textContent = '';
    
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
    if (item.type === 'Ingress' && item.ingress_class) {
        return `<span style="background: #e5f3ff; color: #0066cc; padding: 1px 4px; border-radius: 3px; font-size: 11px; white-space: nowrap;">${item.ingress_class}</span>`;
    } else if (item.type === 'HTTPRoute' && item.gateway) {
        return `<span style="background: #f0f9ff; color: #0284c7; padding: 1px 4px; border-radius: 3px; font-size: 11px; white-space: nowrap;">${item.gateway}</span>`;
    }
    return '-';
}

// Fonction pour rendre le tableau
function renderTable() {
    const tbody = document.getElementById('resultsTable');
    tbody.innerHTML = '';

    currentData.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${item.namespace}</td>
            <td>${item.name}</td>
            <td>${item.type}</td>
            <td>${getIngressClassOrGateway(item)}</td>
            <td>${formatAnnotations(item.annotations)}</td>
            <td><a href="https://${item.url}" target="_blank" title="https://${item.url}">https://${item.url}</a></td>
            <td>
                <span class="status-badge ${getStatusClass(item.status)}">
                    ${getStatusEmoji(item.status)} ${item.status}
                </span>
            </td>
            <td>${item.response_time ? Math.round(item.response_time) + ' ms' : '-'}</td>
            <td>${item.details || ''}</td> `;
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

    // Écouteurs pour la modale
    const modal = document.getElementById('annotationsModal');
    const closeBtn = document.querySelector('.modal-close');
    
    // Fermer la modale avec le bouton X
    closeBtn.addEventListener('click', closeAnnotationsModal);
    
    // Fermer la modale en cliquant en dehors
    modal.addEventListener('click', function(event) {
        if (event.target === modal) {
            closeAnnotationsModal();
        }
    });
    
    // Fermer la modale avec la touche Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAnnotationsModal();
        }
    });

    // Rendu initial
    updateSortArrows();
    renderTable();
});