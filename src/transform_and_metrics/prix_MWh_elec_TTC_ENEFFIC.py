from datetime import date

def obtenir_parametres_electriques(input_date):
    """
    Retourne l'ensemble des paramètres fiscaux et techniques 
    applicables à une date donnée.
    """
    
    # --- 1. Définition des Historiques (Paliers) ---
    
    # CTA (en euros par jour ou coefficient selon l'usage)
    paliers_cta = [
        (date(2026, 2, 1), 0.15),
        (date(2021, 8, 1), 0.2193),
    ]

    # ACCISE (CSPE) - Prix par MWh
    paliers_accise = [
    (date(2026, 2, 1), 26.58), # Tarif 2026 (ZNI incluse)
    (date(2025, 8, 1), 25.79), # Harmonisation août 2025
    (date(2025, 2, 1), 26.23), # Sortie bouclier PME
    (date(2024, 2, 1), 20.50), # Taux 2024
    ]

    # coef_soutirage_hph - Coefficient de soutirage pour HPH (en EUR/MWh)
    paliers_soutirage_hph = [
        (date(2026, 2, 1), 69.1),
        (date(2021, 8, 1), 69.1),
    ]

    # coef_soutirage_hch - Coefficient de soutirage pour HCH (en EUR/MWh)
    paliers_soutirage_hch = [
        (date(2026, 2, 1), 42.1),
        (date(2021, 8, 1), 42.1),
    ]

    # coef_soutirage_hpe - Coefficient de soutirage pour HPE (en EUR/MWh)
    paliers_soutirage_hpe = [
        (date(2026, 2, 1), 21.3),
        (date(2021, 8, 1), 21.3),
    ]

    # coef_soutirage_hce - Coefficient de soutirage pour HCE (en EUR/MWh)
    paliers_soutirage_hce = [
        (date(2026, 2, 1), 15.2),
        (date(2021, 8, 1), 15.2),
    ]

    # comp_gestion_jour - Composante de gestion journalière (en EUR/j)
    paliers_comp_gestion_jour = [
        (date(2026, 2, 1), 0.59671),
        (date(2021, 8, 1), 0.59671),
    ]

    # comp_comptage_jour - Composante de comptage journalière (en EUR/j)
    paliers_comp_comptage_jour = [
        (date(2026, 2, 1), 0.77608),
        (date(2021, 8, 1), 0.77608),
    ]

    # Soutirage_part_fixe - Soutirage part fixe (en EUR/kVA/jour)
    paliers_soutirage_part_fixe = [
        (date(2026, 2, 1), 0.04825),
        (date(2021, 8, 1), 0.04825),
    ]

    # coef_depassement - Coefficient de dépassement (en EUR/h)
    paliers_coef_depassement = [
        (date(2026, 2, 1), 12.41),
        (date(2021, 8, 1), 12.41),
    ]

    # --- 2. Dictionnaires Annuels (Capacité) ---
    annee = input_date.year
    
    # Données brutes de capacité
    prix_capa_kw = {2024: 27.09, 2025: 14.65, 2026: 0.1}
    
    # Calcul ou récupération des réelles capacités
    # On utilise .get(annee, valeur_par_defaut) pour éviter les erreurs
    reelle_capa_hph = {
        2024: 0.23188 * prix_capa_kw[2024],
        2025: 0.41689 * prix_capa_kw[2025],
        2026: 4.86
    }.get(annee, 4.86)

    reelle_capa_hch = {
        2024: 0.26892 * prix_capa_kw[2024],
        2025: 0.49359 * prix_capa_kw[2025],
        2026: 0.77
    }.get(annee, 0.77)


    reelle_capa_hpe = {
        2024: 0.15 * prix_capa_kw[2024],
        2025: 0.25 * prix_capa_kw[2025],
        2026: 0.3
    }.get(annee, 0.3)

    reelle_capa_hce = {
        2024: 0.1 * prix_capa_kw[2024],
        2025: 0.18 * prix_capa_kw[2025],
        2026: 0.25
    }.get(annee, 0.25)



    # --- 3. Logique d'extraction des paliers ---
    
    def extraire_valeur(paliers, d):
        d = d.date()
        for date_effet, valeur in paliers:
            if d >= date_effet:
                return valeur
        return paliers[-1][1]
    

    # --- 4. Construction du dictionnaire final ---

    params = {
        # Soutirage et Composantes fixes (Valeurs actuelles fournies)
        "coef_soutirage_hph": extraire_valeur(paliers_soutirage_hph, input_date),
        "coef_soutirage_hch": extraire_valeur(paliers_soutirage_hch, input_date),
        "coef_soutirage_hpe": extraire_valeur(paliers_soutirage_hpe, input_date),
        "coef_soutirage_hce": extraire_valeur(paliers_soutirage_hce, input_date),
        "coef_depassement": 12.41,
        "comp_gestion_jour": extraire_valeur(paliers_comp_gestion_jour, input_date),
        "comp_comptage_jour": extraire_valeur(paliers_comp_comptage_jour, input_date),
        "soutirage_part_fixe_kva_jour": extraire_valeur(paliers_soutirage_part_fixe, input_date),
        
        # CTA
        "cta_jour": extraire_valeur(paliers_cta, input_date),
        
        # Capacité (Calculé selon l'année)
        "reelle_capacite_hph": reelle_capa_hph,
        "reelle_capacite_hch": reelle_capa_hch,
        "reelle_capacite_hpe": reelle_capa_hpe,
        "reelle_capacite_hce": reelle_capa_hce,
        
        # CEE & ACCISE (Convertis en EUR/kWh pour faciliter le calcul final)
        "cee_mwh": 7.5,
        "accise_mwh": extraire_valeur(paliers_accise, input_date),
        
        # Taxes
        "taux_tva": 0.20
    }

    return params

def prix_MWh_elec_TTC_ENEFFIC(date_t, prix_MWh_elec_SPOT, P_souscrite_HPH=70, P_souscrite_HCH=70,
                         P_souscrite_HPE=70, P_souscrite_HCE=70):
    """
    Calcule le prix de l'électricité en euros par MWh TTC pour une date donnée,
    en utilisant le prix spot de l'électricité en euros par MWh HT et en appliquant
    les paramètres tarifaires du contrat MET 2024/2025 à Pervenches.

    Args:
        date_t (datetime): La date pour laquelle calculer le prix.
        prix_MWh_elec_SPOT (float): Le prix spot de l'électricité en euros par MWh HT.
        P_souscrite_HPH (float): Puissance souscrite en kVA pour Heure Pleine Hiver.
        P_souscrite_HCH (float): Puissance souscrite en kVA pour Heure Creuse Hiver.
        P_souscrite_HPE (float): Puissance souscrite en kVA pour Heure Pleine Été.
        P_souscrite_HCE (float): Puissance souscrite en kVA pour Heure Creuse Été.

    Returns:
        tuple: part_fixe_heure_TTC (float), part_variable_MWh_TTC (float)

    exemple:
    date = datetime.datetime(2025, 1, 1, 10,    0)
    prix_spot = 17.95  # Exemple de prix spot eimportn €/MWh HT
    fixe, variable = prix_MWh_elec_TTC_ENEFFIC(date, prix_spot)
    total = fixe + variable * conso_elec_kwh / 1000
        
    """
    # Définir les périodes pour les taux de TVA
    Heure_ete_start = date_t.replace(month=4, day=1, hour=0, minute=0, second=0, microsecond=0)
    Heure_hiver_start = date_t.replace(month=11, day=1, hour=0, minute=0, second=0, microsecond=0)
    heure_creuse_start = 22
    heure_pleine_start = 6

    # Récupérer les paramètres pour la date donnée
    params = obtenir_parametres_electriques(date_t)
    TP0 = 9.5

    # Vérifier si été ou hiver
    if Heure_ete_start <= date_t < Heure_hiver_start:
        saison = 'été'
    else:
        saison = 'hiver'
    #verifier si heure pleine ou creuse
    if saison == 'été':
        if heure_pleine_start <= date_t.hour < heure_creuse_start:
            periode = 'HPE'  # Heure Pleine Été
        else:
            periode = 'HCE'  # Heure Creuse Été
    else:
        if heure_pleine_start <= date_t.hour < heure_creuse_start:
            periode = 'HPH'  # Heure Pleine Hiver
        else:
            periode = 'HCH'  # Heure Creuse Hiver

    # cas HPH
    if periode == 'HPH':
        part_fixe_heure = (params['soutirage_part_fixe_kva_jour'] * P_souscrite_HPH + params['comp_comptage_jour'] + params['comp_gestion_jour']) * (1 + params['cta_jour']) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT + TP0
        part_variable_acheminement_MWh = params['coef_soutirage_hph']
        part_variable_capacité_MWh = params['reelle_capacite_hph']
        part_variable_CEE = params['cee_mwh']
        part_variable_ACCISE = params['accise_mwh']
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE
    # cas HCH
    elif periode == 'HCH':
        part_fixe_heure = (params['soutirage_part_fixe_kva_jour'] * P_souscrite_HCH + params['comp_comptage_jour'] + params['comp_gestion_jour']) * (1 + params['cta_jour']) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT + TP0
        part_variable_acheminement_MWh = params['coef_soutirage_hch']
        part_variable_capacité_MWh = params['reelle_capacite_hch']
        part_variable_CEE = params['cee_mwh']
        part_variable_ACCISE = params['accise_mwh']
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE
    # cas HPE
    elif periode == 'HPE':
        part_fixe_heure = (params['soutirage_part_fixe_kva_jour'] * P_souscrite_HPE + params['comp_comptage_jour'] + params['comp_gestion_jour']) * (1 + params['cta_jour']) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT + TP0
        part_variable_acheminement_MWh = params['coef_soutirage_hpe']
        part_variable_capacité_MWh = params['reelle_capacite_hpe']
        part_variable_CEE = params['cee_mwh']
        part_variable_ACCISE = params['accise_mwh']
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE
    # cas HCE
    elif periode == 'HCE':
        part_fixe_heure = (params['soutirage_part_fixe_kva_jour'] * P_souscrite_HCE + params['comp_comptage_jour'] + params['comp_gestion_jour']) * (1 + params['cta_jour']) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT + TP0
        part_variable_acheminement_MWh = params['coef_soutirage_hce']
        part_variable_capacité_MWh = params['reelle_capacite_hce']
        part_variable_CEE = params['cee_mwh']
        part_variable_ACCISE = params['accise_mwh']
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE

    part_fixe_heure_TTC = round(part_fixe_heure * (1 + params['taux_tva']), 2)
    part_variable_MWh_TTC = round(part_variable_MWh * (1 + params['taux_tva']), 2)


    return part_fixe_heure_TTC, part_variable_MWh_TTC



if __name__ == "__main__":
    import datetime
    date_i = datetime.datetime(2026, 1, 1, 10,    0)
    conso_elec_kwh = 200
    prix_spot = 17.95  # Exemple de prix spot en €/MWh HT
    fixe, variable = prix_MWh_elec_TTC_ENEFFIC(date_i, prix_spot)
    print(fixe)
    print(variable)
    total = fixe + variable * conso_elec_kwh / 1000
    print(total)