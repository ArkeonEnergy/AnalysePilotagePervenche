def prix_MWh_elec_TTC(date, prix_MWh_elec_SPOT, P_souscrite_HPH=70, P_souscrite_HCH=70,
                         P_souscrite_HPE=70, P_souscrite_HCE=70):
    """
    Calcule le prix de l'électricité en euros par MWh TTC pour une date donnée,
    en utilisant le prix spot de l'électricité en euros par MWh HT et en appliquant
    les paramètres tarifaires du contrat MET 2024/2025 à Pervenches.

    Args:
        date (datetime): La date pour laquelle calculer le prix.
        prix_MWh_elec_SPOT (float): Le prix spot de l'électricité en euros par MWh HT.
        P_souscrite_HPH (float): Puissance souscrite en kVA pour Heure Pleine Hiver.
        P_souscrite_HCH (float): Puissance souscrite en kVA pour Heure Creuse Hiver.
        P_souscrite_HPE (float): Puissance souscrite en kVA pour Heure Pleine Été.
        P_souscrite_HCE (float): Puissance souscrite en kVA pour Heure Creuse Été.

    Returns:
        tuple: part_fixe_heure_TTC (float), part_variable_MWh_TTC (float)

    exemple:
    date = datetime.datetime(2025, 1, 1, 10,    0)
    prix_spot = 17.95  # Exemple de prix spot en €/MWh HT
    fixe, variable = prix_MWh_elec_TTC(date, prix_spot)
    total = fixe + variable * conso_elec_kwh / 1000
        
    """
    # Définir les périodes pour les taux de TVA
    Heure_ete_start = date.replace(month=4, day=1, hour=0, minute=0, second=0, microsecond=0)
    Heure_hiver_start = date.replace(month=11, day=1, hour=0, minute=0, second=0, microsecond=0)
    heure_creuse_start = 22
    heure_pleine_start = 6

    Abonnement_mois = 30 # Abonnement mensuel en euros

    frais_accès_marche_MWh = 6.5  # Frais d'accès au marché en euros par MWh
    COEF_SPOT_mensuel = [0.63, 0.6, 0.51, 0.37, 0.2, 0.18, 0.26, 0.19, 0.26, 0.4, 0.49, 0.61]
    COEF_ARENH_mensuel = [0.42, 0.45, 0.54, 0.68, 0.85, 0.87, 0.79, 0.86, 0.79, 0.65, 0.56, 0.44]
    prix_ARENH_MWh = 42  # Prix ARENH en euros par MWh

    frais_puissance_souscrite_jour = 0.05  # Frais de puissance souscrite en euros par kVA par jour
    frais_compteur_jour = 0.6  # Frais de compteur en euros par jour par compteur
    frais_depassement_puissance_heure = 12.65 # Frais de dépassement de puissance en euros par heure
    redevance_PDL_jour = 0.79  # Redevance PDL en euros par jour

    CTA_jour = 0.2193  # Contribution Tarifaire d'Acheminement en euros par jour

    acheminement_VEASHCE_kWh = 0.02 # Variable d'acheminement VEASHCE en euros par kWh
    acheminement_VEASHPH_kWh = 0.06 # Variable d'acheminement VEASHPH en euros par kWh
    acheminement_VEASHCH_kWh = 0.05 # Variable d'acheminement VEASHCH en euros par kWh
    acheminement_VEASHPE_kWh = 0.03 # Variable d'acheminement VEASHPE en euros par kWh

    obligation_capacité_HPH = {2024: 0.23188, 2025: 0.41689, 2026: 0.41689}  # Obligation de capacité en kW par MWh pour HPH
    obligation_capacité_HCH = {2024: 0.26892, 2025: 0.49359, 2026: 0.49359}  # Obligation de capacité en kW par MWh pour HCH
    prix_capacité_kW = {2024: 27.09, 2025: 14.65, 2026: 0.1}  # Prix de la capacité en euros par kW
    reelle_capacité_HPH = {2024: obligation_capacité_HPH[2024] * prix_capacité_kW[2024],
                          2025: obligation_capacité_HPH[2025] * prix_capacité_kW[2025],
                          2026: obligation_capacité_HPH[2026] * prix_capacité_kW[2026]}
    reelle_capacité_HCH = {2024: obligation_capacité_HCH[2024] * prix_capacité_kW[2024],
                          2025: obligation_capacité_HCH[2025] * prix_capacité_kW[2025],
                          2026: obligation_capacité_HCH[2026] * prix_capacité_kW[2026]}
    
    prix_CEE_MWh = 6.58 # Prix des Certificats d'Économies d'Énergie en euros par MWh

    ACCISE_prix_CSPE_MWh = 26.23  # Prix des accises CSPE en euros par MWh

    taux_TVA = 0.20  # Taux de TVA par défaut (20%)

    # Vérifier si été ou hiver
    if Heure_ete_start <= date < Heure_hiver_start:
        saison = 'été'
    else:
        saison = 'hiver'
    #verifier si heure pleine ou creuse
    if saison == 'été':
        if heure_pleine_start <= date.hour < heure_creuse_start:
            periode = 'HPE'  # Heure Pleine Été
        else:
            periode = 'HCE'  # Heure Creuse Été
    else:
        if heure_pleine_start <= date.hour < heure_creuse_start:
            periode = 'HPH'  # Heure Pleine Hiver
        else:
            periode = 'HCH'  # Heure Creuse Hiver

    # cas HPH
    if periode == 'HPH':
        part_fixe_heure = Abonnement_mois / 30 / 24 + (frais_puissance_souscrite_jour * P_souscrite_HPH + frais_compteur_jour + redevance_PDL_jour) * (1 + CTA_jour) /24
        part_variable_conso_MWh = frais_accès_marche_MWh + prix_MWh_elec_SPOT * COEF_SPOT_mensuel[date.month - 1] + prix_ARENH_MWh * COEF_ARENH_mensuel[date.month - 1]
        part_variable_acheminement_MWh = acheminement_VEASHPH_kWh * 1000
        part_variable_capacité_MWh = reelle_capacité_HPH[date.year]
        part_variable_CEE = prix_CEE_MWh
        part_variable_ACCISE = ACCISE_prix_CSPE_MWh
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE
    # cas HCH
    elif periode == 'HCH':
        part_fixe_heure = Abonnement_mois / 30 / 24 + (frais_puissance_souscrite_jour * P_souscrite_HCH + frais_compteur_jour + redevance_PDL_jour) * (1 + CTA_jour) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT * COEF_SPOT_mensuel[date.month - 1] + frais_accès_marche_MWh + prix_ARENH_MWh * COEF_ARENH_mensuel[date.month - 1]
        part_variable_acheminement_MWh = acheminement_VEASHCH_kWh * 1000
        part_variable_capacité_MWh = reelle_capacité_HCH[date.year]
        part_variable_CEE = prix_CEE_MWh
        part_variable_ACCISE = ACCISE_prix_CSPE_MWh
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE
    # cas HPE
    elif periode == 'HPE':
        part_fixe_heure = Abonnement_mois / 30 / 24 + (frais_puissance_souscrite_jour * P_souscrite_HPE + frais_compteur_jour + redevance_PDL_jour) * (1 + CTA_jour) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT * COEF_SPOT_mensuel[date.month - 1] + frais_accès_marche_MWh + prix_ARENH_MWh * COEF_ARENH_mensuel[date.month - 1]
        part_variable_acheminement_MWh = acheminement_VEASHPE_kWh * 1000
        part_variable_capacité_MWh = 0  # Pas d'obligation de capacité en HPE
        part_variable_CEE = prix_CEE_MWh
        part_variable_ACCISE = ACCISE_prix_CSPE_MWh
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE

    # cas HCE
    else:  # periode == 'HCE'
        part_fixe_heure = Abonnement_mois / 30 / 24 + (frais_puissance_souscrite_jour * P_souscrite_HCE + frais_compteur_jour + redevance_PDL_jour) * (1 + CTA_jour) /24
        part_variable_conso_MWh = prix_MWh_elec_SPOT * COEF_SPOT_mensuel[date.month - 1] + frais_accès_marche_MWh + prix_ARENH_MWh * COEF_ARENH_mensuel[date.month - 1]
        part_variable_acheminement_MWh = acheminement_VEASHCE_kWh * 1000
        part_variable_capacité_MWh = 0  # Pas d'obligation de capacité en HCE
        part_variable_CEE = prix_CEE_MWh
        part_variable_ACCISE = ACCISE_prix_CSPE_MWh
        part_variable_MWh = part_variable_conso_MWh + part_variable_acheminement_MWh + part_variable_capacité_MWh + part_variable_CEE + part_variable_ACCISE

    part_fixe_heure_TTC = round(part_fixe_heure * (1 + taux_TVA), 2)
    part_variable_MWh_TTC = round(part_variable_MWh * (1 + taux_TVA), 2)


    return part_fixe_heure_TTC, part_variable_MWh_TTC


if __name__ == "__main__":
    import datetime
    date = datetime.datetime(2025, 1, 1, 10,    0)
    conso_elec_kwh = 500
    prix_spot = 17.95  # Exemple de prix spot en €/MWh HT
    fixe, variable = prix_MWh_elec_TTC(date, prix_spot)
    total = fixe + variable * conso_elec_kwh / 1000
    print(total)