# Ressources de test pour Portal Checker

Ce dossier contient des ressources Kubernetes pour tester portal-checker avec Docker Desktop.

## Déploiement

```bash
# Appliquer toutes les ressources
kubectl apply -f k8s-test/

# Ou individuellement
kubectl apply -f k8s-test/namespace.yaml
kubectl apply -f k8s-test/test-app-deployment.yaml
kubectl apply -f k8s-test/test-app-service.yaml
kubectl apply -f k8s-test/test-ingress.yaml
kubectl apply -f k8s-test/test-ingress-excluded.yaml
```

## Vérification

```bash
# Vérifier les ressources
kubectl get all -n portal-checker-test
kubectl get ingress -n portal-checker-test

# Vérifier la découverte par portal-checker
curl http://localhost:5001/refresh
curl http://localhost:5001/
```

## Ressources créées

1. **Namespace** : `portal-checker-test`
2. **Deployment** : `test-app` (nginx simple)
3. **Service** : `test-app-service` 
4. **Ingress** : `test-app-ingress` avec 2 hosts :
   - `test-app.local/`
   - `test-api.local/api`
5. **Ingress exclu** : `test-excluded-ingress` avec annotation `portal-checker.io/exclude: "true"`

## Annotations testées

- `portal-checker.io/exclude: "false"` - Ingress inclus
- `portal-checker.io/exclude: "true"` - Ingress exclu
- `portal-checker.io/description` - Description personnalisée
- `portal-checker.io/category` - Catégorie

## Nettoyage

```bash
kubectl delete namespace portal-checker-test
```