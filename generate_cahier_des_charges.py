#!/usr/bin/env python3
"""
Script de generation du Cahier des Charges - Projet Qwen3-ASR
Version pour debutants : language clair, explications simples, analogies
"""

from fpdf import FPDF
from datetime import datetime


class CahierPDF(FPDF):
    """Classe personnalisee pour le cahier des charges"""

    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 8, 'Cahier des Charges - Qwen3-ASR (Debutant)', align='L')
            self.cell(0, 8, f'Page {self.page_no()}', align='R', new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(20, 60, 120)
            self.set_line_width(0.3)
            self.line(10, 14, 200, 14)
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Document genere le {datetime.now().strftime("%d/%m/%Y")}', align='C')

    def chapter_title(self, num, title):
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(20, 60, 120)
        self.cell(0, 10, f'{num}. {title}', new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(20, 60, 120)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def section_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def subsection_title(self, title):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 7, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def explanation_box(self, title, text):
        """Boite d'explication pour les concepts cles"""
        self.set_fill_color(255, 248, 220)  # Fond jaune pale
        self.set_draw_color(200, 150, 50)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 22, 'DF')
        self.set_xy(12, y_start + 2)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(150, 100, 0)
        self.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(12)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(80, 60, 0)
        self.multi_cell(186, 4, text)
        self.set_y(y_start + 23)

    def tip_box(self, text):
        """Astuce ou conseil"""
        self.set_fill_color(230, 245, 255)  # Fond bleu pale
        self.set_draw_color(50, 120, 200)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 14, 'DF')
        self.set_xy(12, y_start + 2)
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(30, 80, 150)
        self.multi_cell(186, 4, f'A noter : {text}')
        self.set_y(y_start + 15)

    def bullet_list(self, items):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(40, 40, 40)
        for item in items:
            x = self.get_x()
            self.cell(15, 5, '-', new_x="END")
            self.multi_cell(0, 5, item)
            self.ln(1)
        self.ln(1)

    def numbered_list(self, items):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(40, 40, 40)
        for i, item in enumerate(items, 1):
            x = self.get_x()
            self.cell(15, 5, f'{i}.', new_x="END")
            self.multi_cell(0, 5, item)
            self.ln(1)
        self.ln(1)

    def code_block(self, code):
        self.set_font('Courier', '', 8)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        self.set_text_color(40, 40, 40)
        lines = code.split('\n')
        line_height = 4
        block_height = len(lines) * line_height + 6
        if self.get_y() + block_height > 270:
            self.add_page()
        y_start = self.get_y()
        self.rect(10, y_start, 190, block_height, 'DF')
        self.set_xy(12, y_start + 3)
        for line in lines:
            self.cell(0, line_height, line, new_x="LMARGIN", new_y="NEXT")
            self.set_x(12)
        self.set_y(y_start + block_height + 3)
        self.ln(1)

    def table_simple(self, headers, rows, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(20, 60, 120)
        self.set_text_color(255, 255, 255)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, 1, 0, 'C', fill=True)
        self.ln()
        self.set_font('Helvetica', '', 8)
        self.set_text_color(40, 40, 40)
        for row in rows:
            max_h = 7
            for i, cell in enumerate(row):
                lines = self.multi_cell(col_widths[i], 5, cell, dry_run=True, output="LINES")
                h = max(7, len(lines) * 5)
                if h > max_h:
                    max_h = h
            for i, cell in enumerate(row):
                x = self.get_x()
                y = self.get_y()
                self.rect(x, y, col_widths[i], max_h)
                self.set_xy(x + 1, y + 1)
                self.multi_cell(col_widths[i] - 2, 5, cell)
                self.set_xy(x + col_widths[i], y)
            self.ln(max_h)
        self.ln(2)

    def analogy_box(self, text):
        """Une analogie pour expliquer simplement"""
        self.set_fill_color(240, 255, 240)  # Fond vert pale
        self.set_draw_color(50, 150, 50)
        y_start = self.get_y()
        self.rect(10, y_start, 190, 16, 'DF')
        self.set_xy(12, y_start + 2)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(30, 100, 30)
        self.cell(0, 5, 'Pour comprendre :', new_x="LMARGIN", new_y="NEXT")
        self.set_x(12)
        self.set_font('Helvetica', 'I', 9)
        self.set_text_color(40, 80, 40)
        self.multi_cell(186, 4, text)
        self.set_y(y_start + 17)


def build_pdf():
    pdf = CahierPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ============================================================
    # PAGE DE TITRE
    # ============================================================
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font('Helvetica', 'B', 28)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 15, 'Cahier des Charges', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font('Helvetica', '', 18)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 12, 'Outil de Transcription Audio', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 12, 'Projet Qwen3-ASR', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 8, 'Version pour debutants', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f'Date : {datetime.now().strftime("%d/%m/%Y")}', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, 'Statut : En cours de developpement', align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(15)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, 'Ce document explique le projet de maniere simple et claire.\n'
                   'Chaque terme technique est explique pour que tout le monde puisse comprendre.', align='C')
    pdf.ln(15)
    pdf.set_draw_color(20, 60, 120)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())

    # ============================================================
    # GLOSSAIRE - AVANT TOUT
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('', 'Glossaire - Les termes expliques')
    pdf.body_text(
        "Avant de commencer, voici les mots techniques utilises dans ce document "
        "et leur explication simple :"
    )
    pdf.table_simple(
        ['Terme', 'Explication simple', 'Exemple concret'],
        [
            ['ASR', 'Reconnaissance automatique de la parole. C\'est la machine qui ecoute et ecrit ce qu\'elle entend.', 'Quand vous dites "bonjour" a votre telephone et qu\'il ecrit "bonjour"'],
            ['Django', 'Un "kit" pour creer des sites web avec Python. Il fait le travail de fond (base de donnees, securite).', 'Comme WordPress, mais en code Python au lieu de PHP'],
            ['Python', 'Un langage de programmation (la langue qu\'on parle avec l\'ordinateur). Facile a apprendre.', 'Le langage le plus utilise en IA et en science des donnees'],
            ['SQL', 'Le langage pour parler aux bases de donnees (les grands classeurs qui stockent les informations).', 'Comme un Excel mais en ligne de commande, pour stocker des millions de donnees'],
            ['SQLite', 'Une base de donnees legere qui tient dans un seul fichier. Parfaite pour les petits projets.', 'Un fichier .db sur votre ordinateur qui contient toutes les donnees'],
            ['API', 'Une "interface" pour que deux programmes se parlent. Comme un guichet de service.', 'Votre telephone appelle une API pour obtenir la meteo'],
            ['JSON', 'Un format simple pour ecrire des donnees. Facile a lire meme pour un humain.', '{"nom": "Pierre", "age": 25}'],
            ['PDF', 'Le format de document que vous lisez en ce moment ! Portable Document Format.', 'Un fichier qu\'on peut ouvrir partout sans rien installer'],
            ['Serveur', 'Un ordinateur qui reste allume 24h/24 et qui repond aux requetes du web.', 'Le serveur de Gmail qui gere votre boite mail'],
            ['Token', 'Un "morceau de mot" que la machine comprend. "Bonjour" = ["bon", "jour"].', 'L\'ASR coupe les mots en petits morceaux pour les analyser'],
            ['Timestamp', 'Un point dans le temps, comme un marque-page dans une video.', '"A 3min 25sec, la personne a dit ceci"'],
            ['CER/WER', 'Des mesures d\'erreur. CER = erreur par lettre, WER = erreur par mot. Plus c\'est bas, mieux c\'est.', 'Si vous tapez "bonjour" au lieu de "bonjour" = CER 0%. Si "bonjour" au lieu de "bonjour" = WER 100%'],
        ],
        [25, 90, 75]
    )

    # ============================================================
    # TABLE DES MATIERES
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('', 'Sommaire')
    pdf.body_text("Voici tout ce que ce document va expliquer :")

    toc = [
        ('1', 'Presentation - De quoi parle ce projet ?', True),
        ('1.1', 'Le probleme a resoudre', False),
        ('1.2', 'Ce qu\'on veut faire (nos objectifs)', False),
        ('1.3', 'Les outils qu\'on va utiliser', False),
        ('2', 'Architecture - Comment le projet est organise', True),
        ('2.1', 'Les "couches" du projet', False),
        ('2.2', 'Le parcours d\'une transcription', False),
        ('2.3', 'Les fichiers et dossiers', False),
        ('3', 'Donnees - Ce qu\'on stocke', True),
        ('3.1', 'La table principale', False),
        ('3.2', 'Le cycle de vie d\'un job', False),
        ('3.3', 'Les regles a respecter', False),
        ('4', 'Fonctionnalites - Ce que l\'utilisateur fait', True),
        ('4.1', 'Uploader un fichier audio', False),
        ('4.2', 'Corriger la transcription', False),
        ('4.3', 'Voir les statistiques', False),
        ('4.4', 'Telecharger le resultat', False),
        ('5', 'Le moteur - Comment la machine ecrit ce qu\'elle entend', True),
        ('5.1', 'Le modele Qwen3-ASR', False),
        ('5.2', 'Le service qui parle au modele', False),
        ('5.3', 'Le worker (l\'ouvrier de fond)', False),
        ('6', 'Interface web - Ce que l\'utilisateur voit', True),
        ('6.1', 'Le tableau de bord', False),
        ('6.2', 'La page d\'upload', False),
        ('6.3', 'La page de detail', False),
        ('6.4', 'La page de correction', False),
        ('6.5', 'La page de statistiques', False),
        ('7', 'Gestion de projet - Comment on organise le travail', True),
        ('7.1', 'La methodologie (notre facon de travailler)', False),
        ('7.2', 'L\'equipe', False),
        ('7.3', 'Le planning', False),
        ('7.4', 'Les risques', False),
        ('8', 'Qualite - Ce qu\'on exige', True),
        ('A', 'Annexe A : Comment demarrer le projet', True),
        ('B', 'Annexe B : Les adresses web (routes)', True),
        ('C', 'Annexe C : Les outils a installer', True),
        ('D', 'Annexe D : Les commandes utiles', True),
    ]

    for num, title, is_main in toc:
        if is_main:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.ln(2)
        else:
            pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(12, 5, num, new_x="END")
        pdf.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")

    # ============================================================
    # 1. PRESENTATION
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('1', 'Presentation - De quoi parle ce projet ?')

    pdf.section_title('1.1 Le probleme a resoudre')
    pdf.body_text(
        "Imaginez que vous ayez une reunion de 2 heures et que vous vouliez avoir "
        "le texte de tout ce qui a ete dit. Aujourd\'hui, il faut ecouter et tout "
        "ecrire a la main. C\'est long, ennuyeux, et on fait des erreurs."
    )
    pdf.body_text(
        "Notre projet resout ce probleme : on cree un outil web (un site internet) "
        "qui ecoute un fichier audio et ecrit automatiquement ce qu\'il entend. "
        "C\'est comme un traducteur humain, mais en machine."
    )

    pdf.explanation_box(
        "C'est quoi un "Speech-to-Text" ?",
        "Speech-to-Text, c'est le nom technique de ce qu'on fait. "
        "Ca veut dire "de la parole au texte". La machine ecoute l'audio "
        "et produit le texte correspondant. C'est comme les sous-titres automatiques "
        "de YouTube, mais en mieux."
    )

    pdf.section_title('1.2 Ce qu\'on veut faire (nos objectifs)')
    pdf.body_text("Voici ce que notre outil doit faire :")
    pdf.numbered_list([
        "Uploader (deposer) un fichier audio (WAV, MP3, FLAC...)",
        "La machine l'ecoute et ecrit ce qu'elle entend",
        "Afficher le resultat avec les timestamps (a telle minute, telle seconde)",
        "Permettre a l'utilisateur de corriger les erreurs",
        "Montrer des statistiques (combien d'erreurs, temps de traitement)",
        "Permettre de telecharger le resultat en different formats",
    ])

    pdf.analogy_box(
        "C'est comme un secretarye virtuel : vous lui donnez un enregistrement, "
        "il vous rend le texte ecrit, et vous pouvez le corriger."
    )

    pdf.section_title('1.3 Les outils qu\'on va utiliser')
    pdf.body_text(
        "Pour creer ce projet, on utilise plusieurs "outils" (des logiciels). "
        "Voici les principaux :"
    )
    pdf.table_simple(
        ['Outil', 'A quoi ca sert', 'Analogie'],
        [
            ['Django', 'Creer le site web (le "moteur" derriere)', 'Le chassis d\'une voiture'],
            ['Python', 'Le langage pour ecrire le code', 'Le francais, mais pour parler aux ordinateurs'],
            ['Qwen3-ASR', 'Le modele IA qui ecoute et ecrit', 'Le cerveau qui comprend la parole'],
            ['SQLite', 'Stocker les donnees (les transcriptions)', 'Un grand classeur avec des onglets'],
            ['Bootstrap', 'Rendre le site joli et facile a utiliser', 'La peinture et le mobilier de la maison'],
            ['Chart.js', 'Creer des graphiques de statistiques', 'Un tableur qui fait des courbes'],
        ],
        [30, 70, 90]
    )

    # ============================================================
    # 2. ARCHITECTURE
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('2', 'Architecture - Comment le projet est organise')

    pdf.section_title('2.1 Les "couches" du projet')
    pdf.body_text(
        "Un projet web, c'est comme un immeuble avec plusieurs etages. "
        "Chaque etage a un role precis :"
    )
    pdf.code_block(
        '  +-----------------------------------------------+\n'
        '  |  ETAGE 4 : LA VITRINE (Ce que l\'utilisateur voit) |\n'
        '  |  Les pages web, les boutons, les formulaires   |\n'
        '  +-----------------------------------------------+\n'
        '  |  ETAGE 3 : LE DIRECTEUR (Les vues)             |\n'
        '  |  Les "cerveaux" qui decident quoi faire        |\n'
        '  +-----------------------------------------------+\n'
        '  |  ETAGE 2 : LE SPECIALISTE (Le modele ASR)     |\n'
        '  |  La machine qui ecoute et ecrit                |\n'
        '  +-----------------------------------------------+\n'
        '  |  ETAGE 1 : L\'ARCHIVISTE (La base de donnees)  |\n'
        '  |  Tout ce qu\'on stocke pour ne pas l\'oublier    |\n'
        '  +-----------------------------------------------+'
    )

    pdf.analogy_box(
        "C'est comme un restaurant : le serveur (vitrine) prend la commande, "
        "le chef (directeur) la prepare, le cuisinier (specialiste) cuisine, "
        "et le garde-manger (archiviste) stocke les ingredients."
    )

    pdf.section_title('2.2 Le parcours d\'une transcription')
    pdf.body_text(
        "Quand un utilisateur clique sur "Upload", voici ce qui se passe, "
        "etape par etape :"
    )
    pdf.numbered_list([
        "L'utilisateur selectionne un fichier audio et clique sur "Transcrire"",
        "Le site web envoie le fichier au serveur Django",
        "Django cree un "job" (une tache) dans la base de donnees avec le statut "en attente"",
        "Le "worker" (un programme qui tourne en arriere-plan) voit le job et commence a travailler",
        "Le worker appelle le modele Qwen3-ASR qui ecoute l'audio",
        "Le modele produit le texte avec les timestamps (a quelle seconde)",
        "Le worker sauvegarde le resultat dans la base de donnees",
        "Le statut du job passe de "en attente" a "termine"",
        "L'utilisateur voit le resultat sur son ecran"
    ])

    pdf.explanation_box(
        "C'est quoi un "worker" ?",
        "Un worker, c'est un programme qui tourne en continu (comme une tournette) "
        "et qui attend qu'on lui donne du travail. C'est comme un ouvrier qui attend "
        "les commandes sur un convoyeur. Quand un job arrive, il le prend et le traite."
    )

    pdf.section_title('2.3 Les fichiers et dossiers')
    pdf.body_text(
        "Voici comment les fichiers du projet sont organises, comme dans un armoire :"
    )
    pdf.code_block(
        '  Qwen3-ASR/                    (Le dossier principal)\n'
        '  +-- pyproject.toml            (La liste des outils a installer)\n'
        '  +-- webapp/                   (Le dossier du site web)\n'
        '      +-- manage.py             (La "commande magique" pour tout faire)\n'
        '      +-- qwenweb/             (Les regles du site)\n'
        '      |   +-- settings.py      (Les parametres principaux)\n'
        '      +-- transcriptions/      (Le coeur du projet)\n'
        '          +-- models.py        (Comment on stocke les donnees)\n'
        '          +-- views.py         (Les "cerveaux" du site)\n'
        '          +-- urls.py          (Les adresses web)\n'
        '          +-- qwen_service.py  (Le lien avec le modele IA)\n'
        '          +-- metrics.py       (Le calcul des erreurs)\n'
        '          +-- templates/       (Les pages web)\n'
        '          +-- static/          (Les styles CSS)'
    )

    # ============================================================
    # 3. DONNEES
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('3', 'Donnees - Ce qu\'on stocke')

    pdf.section_title('3.1 La table principale : TranscriptionJob')
    pdf.body_text(
        "Toute la projection est stockee dans une "table" (comme un Excel) "
        "appelee TranscriptionJob. Chaque ligne represente une transcription."
    )
    pdf.body_text(
        "Voici les "colonnes" de cette table, avec leur role explique :"
    )
    pdf.table_simple(
        ['Colonne', 'Type', 'Role simple', 'Exemple'],
        [
            ['id', 'UUID', 'Le numero de telephone du job', 'a1b2c3d4-...'],
            ['status', 'Texte', 'Ou en est le travail ?', 'pending / running / completed'],
            ['language', 'Texte', 'Dans quelle langue parle-t-on ?', 'fr (francais), en (anglais)'],
            ['audio_file', 'Fichier', 'Le chemin vers le fichier audio', 'media/uploads/abc123.wav'],
            ['transcript_text', 'Texte', 'Le texte ecrit par la machine', 'Bonjour, bienvenue...'],
            ['corrected_text', 'Texte', 'Le texte corrige par l\'humain', 'Bonjour, bienvenue...'],
            ['segments', 'JSON', 'Les morceaux avec le temps', '[{debut: 0s, fin: 3s, texte: "..."}]'],
            ['processing_time', 'Nombre', 'Combien de temps ca a pris', '12.5 secondes'],
            ['cer_score', 'Nombre (0-1)', 'Taux d\'erreur par lettre (0 = parfait)', '0.05 = 5% d\'erreurs'],
            ['wer_score', 'Nombre (0-1)', 'Taux d\'erreur par mot (0 = parfait)', '0.08 = 8% d\'erreurs'],
            ['created_at', 'Date', 'Quand le job a ete cree', '2026-09-10 15:30:00'],
            ['completed_at', 'Date', 'Quand le job est termine', '2026-09-10 15:30:15'],
        ],
        [30, 25, 75, 60]
    )

    pdf.explanation_box(
        "C'est quoi un UUID ?",
        "UUID, c'est l'acronyme de Universal Unique Identifier. C'est comme un "
        "numero de securite sociale pour les jobs : unique au monde, impossible a "
        "deviner, et on ne le change jamais."
    )

    pdf.section_title('3.2 Le cycle de vie d\'un job')
    pdf.body_text(
        "Un job ne reste pas toujours dans le meme etat. Il evolue, "
        "comme un colis postal :"
    )
    pdf.code_block(
        '  EN ATTENTE (pending)                                    \n'
        '       |                                                  \n'
        '       |  Le worker prend le job                         \n'
        '       v                                                  \n'
        '  EN COURS (running)                                      \n'
        '       |                                                  \n'
        '       +-- Succes -------->  TERMINE (completed)          \n'
        '       |                                                  \n'
        '       +-- Echec --------->  ECHEC (failed)               '
    )

    pdf.bullet_list([
        "Pending (en attente) : le job est cree, le worker ne l'a pas encore vu",
        "Running (en cours) : le worker a commence a traiter le job",
        "Completed (termine) : tout s'est bien passe, le texte est disponible",
        "Failed (echec) : un probleme est survenu (fichier corrompu, erreur, etc.)"
    ])

    pdf.section_title('3.3 Les regles a respecter')
    pdf.body_text(
        "Voici les reggles que le projet doit suivre (comme les regles d'un jeu) :"
    )
    pdf.numbered_list([
        "Chaque transcription a un numero unique (UUID) qui ne change jamais",
        "Le statut passe de pending a running, jamais l'inverse directement",
        "On ne peut passer de completed a failed que si on relance le traitement",
        "Le fichier audio est stocke avec le numero UUID (pas le nom original)",
        "Le texte transcrit n'apparait que si le traitement reussit",
        "Le texte corrige est optionnel : l'utilisateur choisit de corriger ou non",
        "Les segments JSON contiennent : debut (en secondes), fin, et texte",
        "Le temps de traitement = date de fin - date de debut",
        "Le taux d'erreur (CER/WER) n'est calcule que si on a un texte corrige",
        "Si on supprime un job, on supprime aussi le fichier audio"
    ])

    # ============================================================
    # 4. FONCTIONNALITES
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('4', 'Fonctionnalites - Ce que l\'utilisateur fait')

    pdf.section_title('4.1 Uploader un fichier audio')
    pdf.body_text(
        "C'est la premiere chose que l'utilisateur fait. Il choisit un fichier "
        "audio sur son ordinateur et l'envoie au site."
    )
    pdf.body_text("Voici ce qui se passe en coulisses :")
    pdf.numbered_list([
        "L'utilisateur clique sur le bouton "Choisir un fichier"",
        "Il selectionne un fichier audio (WAV, MP3, FLAC, OGG ou M4A)",
        "Il choisit quelques options : langue (auto/fr/en), timestamps (oui/non)",
        "Il clique sur "Transcrire"",
        "Le fichier est envoye au serveur (max 2 Go)",
        "Un job est cree dans la base de donnees",
        "L'utilisateur est redirige vers la page de detail"
    ])

    pdf.tip_box(
        "Le format "auto" pour la langue signifie que le modele detecte "
        "automatiquement la langue parle dans l'audio."
    )

    pdf.section_title('4.2 Corriger la transcription')
    pdf.body_text(
        "La machine n'est pas parfaite. Parfois, elle se trompe. "
        "La page de correction permet a l'utilisateur de corriger les erreurs."
    )
    pdf.body_text("Comment ca marche :")
    pdf.bullet_list([
        "A gauche : le texte original (ce que la machine a ecrit)",
        "A droite : un editeur ou l'utilisateur ecrit la version corree",
        "Quand il sauvegarde, le corrected_text est stocke",
        "Les taux d'erreur (CER/WER) sont recalcules automatiquement",
    ])

    pdf.analogy_box(
        "C'est comme un professeur qui corrige une copie d'eleve : "
        "il lit ce que l'eleve a ecrit, le corrige, et note la note."
    )

    pdf.section_title('4.3 Voir les statistiques')
    pdf.body_text(
        "Les statistiques montrent a quel point la machine est precise "
        "et rapide. C'est comme un tableau de bord dans une voiture."
    )
    pdf.bullet_list([
        "CER (Character Error Rate) : pourcentage de lettres erronees. Plus c'est bas, mieux c'est.",
        "WER (Word Error Rate) : pourcentage de mots erronees.",
        "Temps de traitement : combien de secondes la machine a mis pour transcrire.",
        "Nombre de mots et de caracteres dans le texte.",
        "Duree de l'audio d'origine.",
    ])

    pdf.section_title('4.4 Telecharger le resultat')
    pdf.body_text(
        "L'utilisateur peut telecharger la transcription en different formats :"
    )
    pdf.table_simple(
        ['Format', 'Pour quoi faire', 'Exemple de contenu'],
        [
            ['TXT', 'Lire le texte simplement', 'Bonjour, bienvenue a la reunion.'],
            ['SRT', 'Sous-titres pour une video', '00:00:01 --> 00:00:05\\nBonjour, bienvenue'],
            ['JSON', 'Integrer dans un autre programme', '{"texte": "...", "segments": [...]}'],
        ],
        [20, 80, 90]
    )

    # ============================================================
    # 5. LE MOTEUR
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('5', 'Le moteur - Comment la machine ecrit')

    pdf.section_title('5.1 Le modele Qwen3-ASR')
    pdf.body_text(
        "Le modele Qwen3-ASR, c'est le "cerveau" qui ecoute l'audio et "
        "produit le texte. C'est un modele d'intelligence artificielle."
    )

    pdf.explanation_box(
        "C'est quoi un "modele IA" ?",
        "Un modele IA, c'est un programme qui a ete entraine avec des millions "
        "d'exemples. Pour Qwen3-ASR, on lui a montre 200 000 heures d'audio "
        "avec le texte correspondant. Il a appris a associer les sons aux mots."
    )

    pdf.body_text("Les capacites du modele :")
    pdf.bullet_list([
        "1.7 milliard de parametres (c'est le nombre de "connexions" dans son cerveau)",
        "Supporte 11 langues : francais, anglais, allemand, espagnol, italien, japonais, russe, portugais, coreen, arabe, chinois",
        "Genere des timestamps : il dit a quelle seconde chaque mot a ete prononce",
        "Peut detecter automatiquement la langue parlee",
        "Marche sur GPU (rapide) ou CPU (lent mais fonctionne partout)",
    ])

    pdf.section_title('5.2 Le service qui parle au modele')
    pdf.body_text(
        "Le service Qwen3Service, c'est le "passeur" entre notre site web "
        "et le modele IA. C'est un singleton, ce qui veut dire qu'il n'y en "
        "a qu'un seul dans tout le projet."
    )

    pdf.explanation_box(
        "Pourquoi un seul ?",
        "Parce que le modele IA est tres gros (il prend beaucoup de place "
        "en memoire). Si on en creait plusieurs, l'ordinateur n'aurait plus "
        "assez de place. Un seul suffit, il partage son travail."
    )

    pdf.section_title('5.3 Le worker (l\'ouvrier de fond)')
    pdf.body_text(
        "Le worker, c'est le programme qui tourne en arriere-plan et qui "
        "traite les jobs un par un. C'est comme un ouvrier sur une ligne "
        "de production."
    )
    pdf.numbered_list([
        "Le worker demarre et entre en "mode veille"",
        "Il regarde la base de donnees : y a-t-il des jobs en attente ?",
        "Si oui, il prend le premier (le plus ancien)",
        "Il passe le statut a "running"",
        "Il appelle le service Qwen3Service pour transcrire l'audio",
        "Quand c'est fini, il sauvegarde le resultat et passe le statut a "completed"",
        "Si ca plante, il passe le statut a "failed"",
        "Il retourne en mode veille et recommence"
    ])

    # ============================================================
    # 6. INTERFACE WEB
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('6', 'Interface web - Ce que l\'utilisateur voit')

    pdf.section_title('6.1 Le tableau de bord (page d\'accueil)')
    pdf.body_text(
        "C'est la premiere page que l'utilisateur voit. Elle donne un apercu "
        "rapide de ce qui se passe."
    )
    pdf.bullet_list([
        "Le nombre total de transcriptions effectuees",
        "Le taux de succes (combien ont reussi)",
        "Les 5 dernieres transcriptions avec leur statut",
        "Un bouton pour lancer une nouvelle transcription",
        "Un graphique montrant l'evolution des transcriptions",
    ])

    pdf.section_title('6.2 La page d\'upload')
    pdf.body_text(
        "C'est ici que l'utilisateur depose son fichier audio. "
        "C'est comme une zone de depot快递."
    )
    pdf.bullet_list([
        "Un grand bouton ou zone de depot (drag and drop)",
        "Les formats acceptes : WAV, MP3, FLAC, OGG, M4A",
        "La taille maximale : 2 Go (c'est beaucoup !)",
        "Les options : langue, timestamps, tokens maximum",
        "Le bouton "Transcrire" pour lancer le traitement",
    ])

    pdf.section_title('6.3 La page de detail')
    pdf.body_text(
        "Quand le traitement est termine, l'utilisateur voit tout ici :"
    )
    pdf.bullet_list([
        "Le statut : un badge colore (vert = OK, rouge = erreur)",
        "Les informations : langue, duree, timestamps, date",
        "Le texte brut de la transcription",
        "La liste des segments avec les timestamps",
        "Les boutons : corriger, exporter, supprimer",
    ])

    pdf.section_title('6.4 La page de correction')
    pdf.body_text(
        "Pour corriger les erreurs de la machine. C'est comme un formulaire "
        "de correction :"
    )
    pdf.bullet_list([
        "A gauche : le texte original (ce que la machine a ecrit)",
        "A droite : un champ de texte pour ecrire la version corree",
        "Un bouton "Sauvegarder" pour enregistrer",
        "Les statistiques d'erreur recalculees automatiquement",
    ])

    pdf.section_title('6.5 La page de statistiques')
    pdf.body_text(
        "Un tableau de bord avec les metriques de performance :"
    )
    pdf.bullet_list([
        "Le taux d'erreur moyen (CER et WER)",
        "Le temps moyen de traitement",
        "Les statistiques par fichier (nombre de mots, caracteres, duree)",
        "Des graphiques pour visualiser les donnees",
    ])

    # ============================================================
    # 7. GESTION DE PROJET
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('7', 'Gestion de projet - Comment on organise le travail')

    pdf.section_title('7.1 La methodologie (notre facon de travailler)')
    pdf.body_text(
        "On travaille en "sprints" : des periodes de 1 a 2 semaines ou on "
        "se concentre sur un module precis. C'est comme des sprints en course "
        "a pied : on fait un effort intense, puis on souffle."
    )
    pdf.bullet_list([
        "Sprint 1 : Mise en place de l'environnement et integration du modele",
        "Sprint 2 : Upload et worker de traitement",
        "Sprint 3 : Interface de detail et correction",
        "Sprint 4 : Statistiques, export, et tests",
        "Sprint 5 : Optimisation, documentation, deploiement",
    ])

    pdf.section_title('7.2 L\'equipe')
    pdf.body_text(
        "Le projet est developpe dans le cadre d'un stage. "
        "Voici les roles :"
    )
    pdf.table_simple(
        ['Role', 'Ce qu\'il fait', 'Les outils qu\'il utilise'],
        [
            ['Developpeur (Stagiaire)', 'Ecris le code, fait les tests, ecrit la doc', 'VS Code, Git, Django'],
            ['Tuteur de stage', 'Guide, donne des conseils, valide le travail', 'Reunions, revues de code'],
            ['Utilisateurs finaux', 'Testent l\'outil et donnent leur avis', 'Navigateur web'],
        ],
        [35, 75, 80]
    )

    pdf.subsection_title('Nos outils de travail')
    pdf.bullet_list([
        "Git + GitHub : on garde une trace de toutes les modifications",
        "VS Code : l'editeur de code (comme Word, mais pour le code)",
        "Django manage.py : la commande magique pour tout faire",
        "GitHub Issues : on note les bugs et les choses a faire",
        "README.md : la documentation technique du projet",
        "Ce document : le cahier des charges (la reference)",
    ])

    pdf.section_title('7.3 Le planning')
    pdf.body_text("Voici les grandes etapes du projet :")
    pdf.table_simple(
        ['Phase', 'Duree', 'Ce qu\'on fait', 'Comment on sait que c\'est fini'],
        [
            ['1. Mise en place', '1 semaine', 'Installer tout, charger le modele', 'Le serveur demarre, la premiere transcription marche'],
            ['2. Le coeur', '2 semaines', 'Upload, worker, page detail', 'On peut uploader et voir le resultat'],
            ['3. L\'interface', '2 semaines', 'Correction, stats, export', 'Toutes les pages fonctionnent'],
            ['4. La finition', '1 semaine', 'Tests, doc, optimisation', 'Les tests passent, la doc est complete'],
        ],
        [30, 20, 65, 75]
    )

    pdf.section_title('7.4 Les risques')
    pdf.body_text(
        "Comme tout projet, il y a des risques. Voici les plus probables "
        "et comment on les evite :"
    )
    pdf.table_simple(
        ['Qu\'est-ce qui peut passer ?', 'Probabilite', 'Comment on evite'],
        [
            ['Pas assez de memoire pour le modele', 'Moyenne', 'Utiliser CPU au lieu de GPU, reduire la taille'],
            ['La machine est trop lente', 'Haute', 'Optimiser le code, mettre un timeout'],
            ['Le fichier audio est corrompu', 'Moyenne', 'Verifier le fichier avant de le traiter'],
            ['Le modele se trompe trop', 'Moyenne', 'Permettre a l\'humain de corriger'],
            ['On perd les donnees', 'Faible', 'Sauvegarder la base de donnees regulierement'],
        ],
        [50, 25, 115]
    )

    # ============================================================
    # 8. QUALITE
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('8', 'Qualite - Ce qu\'on exige')

    pdf.section_title('8.1 Performance (vitesse)')
    pdf.bullet_list([
        "L'upload doit prendre moins de 5 secondes pour un fichier de 10 Mo",
        "La transcription depend de la duree de l'audio (plus c'est long, plus c'est lent)",
        "On ne traite qu'un seul fichier a la fois (pas de parallele pour l'instant)",
        "Le modele reste en memoire pour ne pas le recharger a chaque fois",
    ])

    pdf.section_title('8.2 Securite')
    pdf.bullet_list([
        "On verifie que le fichier est bien un audio (pas un virus déguise)",
        "On limite la taille a 2 Go (pour ne pas saturer le serveur)",
        "Les fichiers sont stockes avec un nom unique (pas le nom original)",
        "Django protege contre les attaques CSRF (des trucs malicieux via le web)",
    ])

    pdf.section_title('8.3 Compatibilite')
    pdf.bullet_list([
        "Le site marche sur Chrome, Firefox, Safari, Edge (les navigateurs populaires)",
        "Le site s'adapte aux tablettes et aux mobiles (responsive)",
        "Le serveur marche sur Windows, Linux, macOS",
        "Python 3.11 ou plus recent est requis",
    ])

    pdf.section_title('8.4 Maintenance')
    pdf.bullet_list([
        "Le code est commente (on explique ce que fait chaque partie)",
        "Il y a 13 tests qui verifient que tout marche",
        "On utilise Git pour garder une trace des modifications",
        "Le README.md explique comment installer et utiliser le projet",
    ])

    # ============================================================
    # ANNEXES
    # ============================================================
    pdf.add_page()
    pdf.chapter_title('A', 'Annexes')

    pdf.section_title('Annexe A : Comment demarrer le projet')
    pdf.body_text("Voici les etapes pour installer et lancer le projet :")
    pdf.numbered_list([
        "Ouvrir un terminal (ligne de commande)",
        "Aller dans le dossier du projet : cd Qwen3-ASR",
        "Creer un environnement virtuel : python -m venv .venv",
        "Activer l'environnement : .venv/Scripts/activate (Windows)",
        "Installer les outils : pip install -e .",
        "Charger le modele : python -c \"from qwen_asr import Qwen3ASRModel; Qwen3ASRModel.from_pretrained()\"",
        "Preparer la base de donnees : python manage.py migrate",
        "Lancer le serveur : python manage.py runserver 127.0.0.1:8001",
        "Dans un autre terminal, lancer le worker : python manage.py run_worker",
        "Ouvrir le navigateur : http://127.0.0.1:8001/"
    ])

    pdf.tip_box(
        "Si vous avez une erreur, regardez le message d'erreur. "
        "Il dit souvent ce qui ne va pas et comment le corriger."
    )

    pdf.section_title('Annexe B : Les adresses web (routes)')
    pdf.body_text("Chaque page du site a une adresse web. Voici les principales :")
    pdf.table_simple(
        ['Adresse', 'Ce qu\'on y trouve'],
        [
            ['/', 'Le tableau de bord (page d\'accueil)'],
            ['/upload/', 'La page pour uploader un fichier audio'],
            ['/jobs/', 'La liste de toutes les transcriptions'],
            ['/jobs/<uuid>/', 'Le detail d\'une transcription specifique'],
            ['/corrections/<uuid>/', 'La page pour corriger une transcription'],
            ['/stats/', 'Les statistiques globales'],
        ],
        [50, 140]
    )

    pdf.section_title('Annexe C : Les outils a installer')
    pdf.body_text("Voici les "outils" (logiciels) dont vous avez besoin :")
    pdf.table_simple(
        ['Outil', 'A quoi ca sert', 'Comment l\'obtenir'],
        [
            ['Python 3.11+', 'Le langage de programmation', 'python.org'],
            ['Git', 'Le gestionnaire de versions', 'git-scm.com'],
            ['VS Code', 'L\'editeur de code', 'code.visualstudio.com'],
            ['Django', 'Le framework web', 'pip install django'],
            ['Qwen3-ASR', 'Le modele IA', 'pip install qwen3-asr'],
            ['fpdf2', 'Generer des PDF', 'pip install fpdf2'],
        ],
        [30, 70, 90]
    )

    pdf.section_title('Annexe D : Les commandes utiles')
    pdf.body_text("Voici les commandes que vous utiliserez souvent :")
    pdf.table_simple(
        ['Commande', 'Ce qu\'elle fait'],
        [
            ['python manage.py runserver', 'Lance le serveur web'],
            ['python manage.py run_worker', 'Lance le worker (en continu)'],
            ['python manage.py run_worker --once', 'Execute le worker une seule fois'],
            ['python manage.py migrate', 'Prepare la base de donnees'],
            ['python manage.py test', 'Lance les tests'],
            ['python manage.py shell', 'Ouvre une console Python'],
            ['pip install -e .', 'Installe le projet en mode editable'],
        ],
        [85, 105]
    )

    # ============================================================
    # SAUVEGARDE
    # ============================================================
    output_path = 'C:/Users/elodi/Desktop/Stage/Outil Speech to text/Qwen3-ASR/Cahier_des_Charges_Qwen3-ASR.pdf'
    pdf.output(output_path)
    print(f'PDF genere avec succes : {output_path}')
    print(f'Nombre de pages : {pdf.page_no()}')


if __name__ == '__main__':
    build_pdf()
