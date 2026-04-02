def prix_MWh_gaz_TTC(date, P_souscrite_HPH=70, P_souscrite_HCH=70,
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
    fixe, variable = prix_MWh_gaz_TTC(date)
    total = fixe + variable * conso_gaz_kwh / 1000
        
    """