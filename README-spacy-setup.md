# Configuration Presidio avec modèles SpaCy

## Vue d'ensemble

Cette configuration permet d'utiliser Presidio avec des modèles SpaCy pré-installés via un init container et un PVC, évitant les téléchargements réseau en runtime.

## Architecture

```
Init Container (spacy-init) -> PVC (spacy-models) -> Main Container (portal-checker)
```

### 1. Init Container
- **Image**: `fizzbuzz2/portal-checker-spacy-init:latest`
- **Fonction**: Copie les modèles SpaCy pré-installés vers le PVC
- **Modèles inclus**: `en_core_web_sm`, `en_core_web_md`

### 2. PVC (Persistent Volume Claim)
- **Nom**: `{release-name}-spacy-models`
- **Taille**: 1Gi (configurable via `presidio.storageSize`)
- **Mode d'accès**: ReadWriteOnce

### 3. Main Container
- **Mount**: `/app/spacy_models` (read-only)
- **Détection**: Fichier `.ready` indique que les modèles sont disponibles

## Configuration Helm

### Activation/Désactivation
```yaml
autoswagger:
  disablePresidio: false  # true pour désactiver complètement Presidio

presidio:
  initImage: "fizzbuzz2/portal-checker-spacy-init:latest"
  storageClass: ""        # Classe de stockage (vide = default)
  storageSize: "1Gi"      # Taille du PVC
```

### Ressources Init Container
- **CPU**: 100m request, 500m limit
- **Memory**: 128Mi request, 512Mi limit

## Construction des images

### 1. Image init container
```bash
docker build -f Dockerfile.spacy-init -t fizzbuzz2/portal-checker-spacy-init:latest .
docker push fizzbuzz2/portal-checker-spacy-init:latest
```

### 2. Deploy avec Presidio activé
```bash
helm upgrade --install portal-checker ./helm \
  --set autoswagger.enabled=true \
  --set autoswagger.disablePresidio=false
```

## Fonctionnement

### Si `disablePresidio=false`:
1. **Init container** s'exécute et copie les modèles vers le PVC
2. **Main container** démarre et vérifie `/app/spacy_models/.ready`
3. **Si disponible**: Charge les modèles SpaCy pour une détection PII avancée
4. **Si indisponible**: Fallback vers détection regex basique

### Si `disablePresidio=true`:
- Aucun init container
- Aucun PVC créé
- Détection regex basique uniquement

## Logs de diagnostic

```
🔍 Found SpaCy models at /app/spacy_models
✅ Loaded en_core_web_sm model from shared volume
✅ Presidio PII analyzer initialized with SpaCy models from shared volume
```

Ou en cas d'échec:
```
🔍 Using pattern-based PII detection (no SpaCy models)
✅ Presidio PII analyzer initialized (pattern-based mode)
```

## Avantages

- ✅ **Pas de téléchargement réseau** en runtime
- ✅ **Persistance** des modèles entre redémarrages
- ✅ **Activation conditionnelle** selon la configuration
- ✅ **Fallback gracieux** si les modèles ne sont pas disponibles
- ✅ **Compatible environnement d'entreprise** (pas de contraintes SSL)

## Dépannage

### PVC non créé
Vérifiez que `autoswagger.disablePresidio: false` dans les values.yaml

### Init container échoue
```bash
kubectl logs -f <pod-name> -c spacy-model-init
```

### Modèles non trouvés
```bash
kubectl exec <pod-name> -- ls -la /app/spacy_models/
```