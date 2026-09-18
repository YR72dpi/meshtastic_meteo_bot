SHELL := /bin/sh
COMPOSE := docker compose
SERVICE := meteo-meshtastic

.PHONY: help build up down restart update logs ps test send sh clean

help: ## Affiche cette aide
	@echo "Cibles disponibles :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

build: ## Construit l'image Docker
	$(COMPOSE) build

up: ## Démarre le conteneur en arrière-plan (scheduler quotidien 8h)
	$(COMPOSE) up -d --build

down: ## Arrête et supprime le conteneur
	$(COMPOSE) down

restart: ## Redémarre le conteneur sans reconstruire l'image
	$(COMPOSE) restart

update: ## Reconstruit l'image avec le code/.env actuels et recrée le conteneur
	$(COMPOSE) up -d --build --force-recreate

logs: ## Affiche les logs en continu du scheduler
	$(COMPOSE) logs -f $(SERVICE)

ps: ## Affiche l'état du conteneur
	$(COMPOSE) ps

test: ## Génère un exemple de message sans l'envoyer (--dry-run)
	$(COMPOSE) run --rm $(SERVICE) python meteo_rouen_meshtastic.py --dry-run

send: ## Envoie immédiatement le message météo sur le canal Meshtastic
	$(COMPOSE) run --rm $(SERVICE) python meteo_rouen_meshtastic.py

sh: ## Ouvre un shell dans un conteneur éphémère (debug)
	$(COMPOSE) run --rm $(SERVICE) sh

clean: ## Arrête le conteneur et supprime l'image construite localement
	$(COMPOSE) down --rmi local

.DEFAULT_GOAL := help
