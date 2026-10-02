# AGENTS.md — Portal Checker

## Objectif du projet

Finaliser Portal Checker comme **projet open source propre, documenté et directement exploitable**, sans alourdir inutilement son périmètre.

## Jalon actuel

Faire une dernière passe de polish technique et publier une release mineure propre :

- corriger l'hygiène release/versioning/documentation ;
- rendre les tests réellement bloquants ;
- exposer les statistiques des Ingress/HTTPRoute via un endpoint Prometheus `/metrics` ;
- fournir un dashboard Grafana prêt à importer/provisionner ;
- conserver une cardinalité maîtrisée et ne pas exposer de données sensibles.

La feature Prometheus/Grafana est suivie par l'issue `portal-checker#85`.

## Source de cadrage

Registre central des projets dans LLM Wiki : `wiki/dev/project-manager.md`.
