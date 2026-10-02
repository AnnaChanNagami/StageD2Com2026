#!/usr/bin/env python

#Command d'importation des modules et des bibliothèques nécessaires pour exécuter des tpaches administratives dans une application Django
import os
import sys


def main():
   # Définir la variable d'environnement DJANGO_SETTINGS_MODULE pour spécifier le module de paramètres Django à utiliser
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'qwenweb.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Aucun module Django n'a été trouvé. Êtes-vous sûr que Django est installé et"
            "disponible sur votre PYTHONPATH ? Avez-vous "
            "oublié d'activer un environnement virtuel ?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
