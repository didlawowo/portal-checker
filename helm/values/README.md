# Helm Values Override Files

Ce dossier contient les fichiers de valeurs spécifiques à différents environnements et cas d'usage.

## Fichiers

### `docker.yaml`
- **Usage** : Déploiements de branches de développement
- **Mise à jour** : Automatique via GitHub Actions sur push de branches non-master
- **Contenu** :
  - Tag d'image spécifique à la branche (`version-branch-commit`)
  - Configuration de développement (`FLASK_ENV=development`)
  - Annotations Git (branche, commit, timestamp)
  - Ressources augmentées pour le développement

## Utilisation

### Déploiement de branche de développement
```bash
# Via Task
task helm-install-docker

# Via Helm direct
helm upgrade --install portal-checker-dev ./helm \
  --namespace portal-checker-dev \
  --create-namespace \
  --values helm/values.yaml \
  --values helm/values/docker.yaml
```

### Déploiement production
```bash
# Via Task (utilise values.yaml seulement)
task helm-install

# Via Helm direct
helm upgrade --install portal-checker ./helm \
  --namespace portal-checker \
  --create-namespace \
  --values helm/values.yaml
```

## Workflow Automatique

1. **Push sur branche non-master** → Déclenche `.github/workflows/branch-build.yaml`
2. **Build image** avec tag `version-branch-commit`
3. **Mise à jour** de `docker.yaml` avec les nouvelles valeurs
4. **Commit automatique** des changements
5. **Déploiement possible** avec `task helm-install-docker`

## Structure du tag d'image

Format : `{version}-{branch}-{short_sha}`

Exemples :
- `2.8.1-feat-perf-f61c328`
- `2.8.1-bugfix-auth-a1b2c3d`
- `2.8.1-feature-ui-9x8y7z6`