#!/bin/bash

echo "🚀 Déploiement des ressources de test pour Portal Checker"
echo "========================================================"

# Vérifier que kubectl est disponible
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl n'est pas installé ou accessible"
    exit 1
fi

# Vérifier la connexion au cluster
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Impossible de se connecter au cluster Kubernetes"
    echo "   Assurez-vous que Docker Desktop Kubernetes est activé"
    exit 1
fi

echo "✅ Connexion au cluster OK"

# Déployer les ressources
echo ""
echo "📦 Déploiement du namespace..."
kubectl apply -f namespace.yaml

echo ""
echo "📦 Déploiement de l'application test..."
kubectl apply -f test-app-deployment.yaml
kubectl apply -f test-app-service.yaml

echo ""
echo "📦 Déploiement des Ingress..."
kubectl apply -f test-ingress.yaml
kubectl apply -f test-ingress-excluded.yaml

echo ""
echo "⏳ Attente du démarrage des pods..."
kubectl wait --for=condition=ready pod -l app=test-app -n portal-checker-test --timeout=60s

echo ""
echo "📊 État des ressources déployées:"
kubectl get all,ingress -n portal-checker-test

echo ""
echo "✅ Déploiement terminé!"
echo ""
echo "🔍 Pour tester la découverte par portal-checker:"
echo "   curl http://localhost:5001/refresh"
echo "   curl http://localhost:5001/"
echo ""
echo "🧹 Pour nettoyer:"
echo "   kubectl delete namespace portal-checker-test"