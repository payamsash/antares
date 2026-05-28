"""English / German / French translations for participant-facing text."""

TEXTS = {
    "en": {
        # App
        "app_title": "ANTARES — Advancing Neurofeedback in Tinnitus",
        "language_label": "Language",
        # Tabs
        "tab_subject": "Subject",
        "tab_protocol": "Protocol",
        "tab_session": "Session",
        "tab_log": "Log",
        # Subject form
        "subject_id_label": "Subject ID (4 letters)",
        "subject_id_placeholder": "e.g. abcd",
        "age_label": "Age",
        "sex_label": "Sex",
        "sex_female": "Female",
        "sex_male": "Male",
        "visit_label": "Visit Number",
        "mock_lsl_label": "Mock LSL (no hardware)",
        # Protocol
        "protocol_label": "NF Protocol",
        "protocol_zscore": "Z-Score (recommended)",
        "protocol_threshold": "Threshold",
        "protocol_staircase": "Staircase",
        "protocol_sham": "Sham (control)",
        "zscore_threshold_label": "Z-Score Threshold",
        "warmup_label": "Warmup Windows",
        "threshold_label": "Threshold Value",
        # Session design
        "baseline_dur_label": "Baseline Duration (s)",
        "n_blocks_label": "Number of Blocks",
        "rest_dur_label": "Rest Duration per Block (s)",
        "nf_dur_label": "NF Duration per Block (s)",
        "osc_host_label": "OSC Host (rspv)",
        "osc_port_label": "OSC Port (rspv)",
        # Buttons
        "btn_start": "Start Session",
        "btn_stop": "Abort",
        "btn_rerank": "Re-rank Features Only",
        # Status
        "status_idle": "Ready",
        "status_intake": "Collecting subject information...",
        "status_baseline": "Recording resting-state baseline...",
        "status_analysis": "Analysing EEG & selecting NF target...",
        "status_session": "Running neurofeedback session...",
        "status_done": "Session complete.",
        "status_error": "Error — see log.",
        # Participant-screen texts (shown to the participant, not the operator)
        "welcome_title": "Welcome to ANTARES",
        "welcome_subtitle": "Advancing Neurofeedback in Tinnitus",
        "welcome_session_msg": (
            "Welcome to your neurofeedback session.\n"
            "Please make yourself comfortable and relax.\n"
            "The session will begin in a moment."
        ),
        "welcome_body": (
            "In the first stage we will record a short resting-state EEG.\n"
            "Please keep your gaze fixed on the cross in the centre of the screen."
        ),
        "press_space": "Press the space bar to continue.",
        "waiting_body": "The operator will start the session shortly.\nPlease sit comfortably and relax.",
        "fixation_done_title": "Recording complete.",
        "nf_instructions_title": "Neurofeedback Session",
        "nf_instructions_body": (
            "In this session you will see a visual display on the screen.\n\n"
            "Your goal is to maintain a calm, relaxed focus.\n"
            "When you succeed, the visual will respond to your brain activity.\n\n"
            "Simply observe the display and let your internal state guide it."
        ),
        "block_rest": "Rest — please relax.",
        "block_nf": "Neurofeedback — focus.",
        "end_title": "Session Completed.",
        "end_subtitle": "Thank you for your participation.",
        # Validation
        "err_id_invalid": "Subject ID must be exactly 4 letters.",
        "err_age_invalid": "Please enter a valid age (integer).",
        "err_visit_invalid": "Please enter a valid visit number (integer).",
        "err_config_missing": "config_master.yml not found next to antares_app.py.",
        "err_log_exists": "A session log for visit {visit} already exists for subject {sid}.",
    },
    "de": {
        # App
        "app_title": "ANTARES — Neurofeedback bei Tinnitus",
        "language_label": "Sprache",
        # Tabs
        "tab_subject": "Proband",
        "tab_protocol": "Protokoll",
        "tab_session": "Sitzung",
        "tab_log": "Protokollierung",
        # Subject form
        "subject_id_label": "Probanden-ID (4 Buchstaben)",
        "subject_id_placeholder": "z.B. abcd",
        "age_label": "Alter",
        "sex_label": "Geschlecht",
        "sex_female": "Weiblich",
        "sex_male": "Männlich",
        "visit_label": "Besuchsnummer",
        "mock_lsl_label": "Mock-LSL (ohne Hardware)",
        # Protocol
        "protocol_label": "NF-Protokoll",
        "protocol_zscore": "Z-Score (empfohlen)",
        "protocol_threshold": "Schwellenwert",
        "protocol_staircase": "Treppenstufen",
        "protocol_sham": "Sham (Kontrollbedingung)",
        "zscore_threshold_label": "Z-Score-Schwellenwert",
        "warmup_label": "Einlernfenster",
        "threshold_label": "Schwellenwert",
        # Session design
        "baseline_dur_label": "Baseline-Dauer (s)",
        "n_blocks_label": "Anzahl Blöcke",
        "rest_dur_label": "Ruhedauer pro Block (s)",
        "nf_dur_label": "NF-Dauer pro Block (s)",
        "osc_host_label": "OSC-Host (rspv)",
        "osc_port_label": "OSC-Port (rspv)",
        # Buttons
        "btn_start": "Sitzung starten",
        "btn_stop": "Abbrechen",
        "btn_rerank": "Nur Features neu bewerten",
        # Status
        "status_idle": "Bereit",
        "status_intake": "Probandeninformationen werden gesammelt...",
        "status_baseline": "Ruhezustand-EEG wird aufgezeichnet...",
        "status_analysis": "EEG wird analysiert & NF-Ziel wird ausgewählt...",
        "status_session": "Neurofeedback-Sitzung läuft...",
        "status_done": "Sitzung abgeschlossen.",
        "status_error": "Fehler — siehe Protokollierung.",
        # Participant screen
        "welcome_title": "Willkommen bei ANTARES",
        "welcome_subtitle": "Neurofeedback bei Tinnitus",
        "welcome_session_msg": (
            "Willkommen zu Ihrer Neurofeedback-Sitzung.\n"
            "Bitte machen Sie es sich bequem und entspannen Sie sich.\n"
            "Die Sitzung beginnt gleich."
        ),
        "welcome_body": (
            "Im ersten Schritt führen wir eine kurze Ruhe-EEG-Messung durch.\n"
            "Bitte richten Sie Ihren Blick auf das Kreuz in der Mitte des Bildschirms."
        ),
        "press_space": "Drücken Sie die Leertaste, um fortzufahren.",
        "waiting_body": "Der Operator startet die Sitzung in Kürze.\nBitte sitzen Sie bequem und entspannen Sie sich.",
        "fixation_done_title": "Aufzeichnung abgeschlossen.",
        "nf_instructions_title": "Neurofeedback-Sitzung",
        "nf_instructions_body": (
            "In dieser Sitzung sehen Sie eine visuelle Anzeige auf dem Bildschirm.\n\n"
            "Ihr Ziel ist es, eine ruhige, entspannte Konzentration zu bewahren.\n"
            "Wenn Ihnen das gelingt, reagiert die Anzeige auf Ihre Hirnaktivität.\n\n"
            "Beobachten Sie einfach die Anzeige und lassen Sie Ihren inneren Zustand sie leiten."
        ),
        "block_rest": "Pause — bitte entspannen.",
        "block_nf": "Neurofeedback — konzentrieren.",
        "end_title": "Sitzung abgeschlossen.",
        "end_subtitle": "Vielen Dank für Ihre Teilnahme.",
        # Validation
        "err_id_invalid": "Die Probanden-ID muss genau 4 Buchstaben enthalten.",
        "err_age_invalid": "Bitte geben Sie ein gültiges Alter an (ganze Zahl).",
        "err_visit_invalid": "Bitte geben Sie eine gültige Besuchsnummer an (ganze Zahl).",
        "err_config_missing": "config_master.yml wurde nicht neben antares_app.py gefunden.",
        "err_log_exists": "Für Besuch {visit} existiert bereits ein Sitzungsprotokoll für Proband {sid}.",
    },
    "fr": {
        # App
        "app_title": "ANTARES — Neurofeedback pour les Acouphènes",
        "language_label": "Langue",
        # Tabs
        "tab_subject": "Sujet",
        "tab_protocol": "Protocole",
        "tab_session": "Séance",
        "tab_log": "Journal",
        # Subject form
        "subject_id_label": "ID Sujet (4 lettres)",
        "subject_id_placeholder": "ex. abcd",
        "age_label": "Âge",
        "sex_label": "Sexe",
        "sex_female": "Féminin",
        "sex_male": "Masculin",
        "visit_label": "Numéro de visite",
        "mock_lsl_label": "LSL simulé (sans matériel)",
        # Protocol
        "protocol_label": "Protocole NF",
        "protocol_zscore": "Z-Score (recommandé)",
        "protocol_threshold": "Seuil",
        "protocol_staircase": "Staircase",
        "protocol_sham": "Sham (contrôle)",
        "zscore_threshold_label": "Seuil Z-Score",
        "warmup_label": "Fenêtres d'échauffement",
        "threshold_label": "Valeur seuil",
        # Session design
        "baseline_dur_label": "Durée de la baseline (s)",
        "n_blocks_label": "Nombre de blocs",
        "rest_dur_label": "Durée de repos par bloc (s)",
        "nf_dur_label": "Durée NF par bloc (s)",
        "osc_host_label": "Hôte OSC (rspv)",
        "osc_port_label": "Port OSC (rspv)",
        # Buttons
        "btn_start": "Démarrer la séance",
        "btn_stop": "Abandonner",
        "btn_rerank": "Réordonner les caractéristiques",
        # Status
        "status_idle": "Prêt",
        "status_intake": "Collecte des informations du sujet...",
        "status_baseline": "Enregistrement de la baseline au repos...",
        "status_analysis": "Analyse EEG et sélection de la cible NF...",
        "status_session": "Séance de neurofeedback en cours...",
        "status_done": "Séance terminée.",
        "status_error": "Erreur — voir le journal.",
        # Participant screen
        "welcome_title": "Bienvenue dans ANTARES",
        "welcome_subtitle": "Neurofeedback pour les Acouphènes",
        "welcome_session_msg": (
            "Bienvenue à votre séance de neurofeedback.\n"
            "Installez-vous confortablement et détendez-vous.\n"
            "La séance va commencer dans un instant."
        ),
        "welcome_body": (
            "Dans la première étape, nous enregistrerons un EEG de repos de courte durée.\n"
            "Veuillez fixer la croix au centre de l'écran."
        ),
        "press_space": "Appuyez sur la barre d'espace pour continuer.",
        "waiting_body": "L'opérateur démarrera la séance sous peu.\nVeuillez vous installer confortablement et vous détendre.",
        "fixation_done_title": "Enregistrement terminé.",
        "nf_instructions_title": "Séance de neurofeedback",
        "nf_instructions_body": (
            "Dans cette séance, vous verrez un affichage visuel à l'écran.\n\n"
            "Votre objectif est de maintenir une concentration calme et détendue.\n"
            "Lorsque vous y parvenez, l'affichage réagit à votre activité cérébrale.\n\n"
            "Observez simplement l'affichage et laissez votre état intérieur le guider."
        ),
        "block_rest": "Repos — veuillez vous détendre.",
        "block_nf": "Neurofeedback — concentrez-vous.",
        "end_title": "Séance terminée.",
        "end_subtitle": "Merci pour votre participation.",
        # Validation
        "err_id_invalid": "L'ID sujet doit contenir exactement 4 lettres.",
        "err_age_invalid": "Veuillez entrer un âge valide (nombre entier).",
        "err_visit_invalid": "Veuillez entrer un numéro de visite valide (nombre entier).",
        "err_config_missing": "config_master.yml introuvable à côté de antares_app.py.",
        "err_log_exists": "Un journal de séance pour la visite {visit} existe déjà pour le sujet {sid}.",
    },
}


def t(key: str, lang: str = "en", **kwargs) -> str:
    """Return translated string, falling back to English."""
    text = TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text
