# Liste complète des pays (noms en français), utilisée par tous les
# formulaires du site qui demandent un pays (inscription formation,
# inscription/profil utilisateur, etc.) afin d'avoir une liste unique
# et cohérente partout.

COUNTRIES = [
    "Afghanistan", "Afrique du Sud", "Albanie", "Algérie", "Allemagne",
    "Andorre", "Angola", "Antigua-et-Barbuda", "Arabie saoudite", "Argentine",
    "Arménie", "Australie", "Autriche", "Azerbaïdjan", "Bahamas", "Bahreïn",
    "Bangladesh", "Barbade", "Belgique", "Belize", "Bénin", "Bhoutan",
    "Biélorussie", "Birmanie (Myanmar)", "Bolivie", "Bosnie-Herzégovine",
    "Botswana", "Brésil", "Brunei", "Bulgarie", "Burkina Faso", "Burundi",
    "Cambodge", "Cameroun", "Canada", "Cap-Vert", "République centrafricaine",
    "Chili", "Chine", "Chypre", "Colombie", "Comores", "Congo-Brazzaville",
    "RD Congo (Kinshasa)", "Corée du Nord", "Corée du Sud", "Costa Rica",
    "Côte d'Ivoire", "Croatie", "Cuba", "Danemark", "Djibouti", "Dominique",
    "Égypte", "Émirats arabes unis", "Équateur", "Érythrée", "Espagne",
    "Estonie", "Eswatini", "États-Unis", "Éthiopie", "Fidji", "Finlande",
    "France", "Gabon", "Gambie", "Géorgie", "Ghana", "Grèce", "Grenade",
    "Guatemala", "Guinée", "Guinée-Bissau", "Guinée équatoriale", "Guyana",
    "Haïti", "Honduras", "Hongrie", "Îles Marshall", "Îles Salomon", "Inde",
    "Indonésie", "Irak", "Iran", "Irlande", "Islande", "Israël", "Italie",
    "Jamaïque", "Japon", "Jordanie", "Kazakhstan", "Kenya", "Kirghizistan",
    "Kiribati", "Kosovo", "Koweït", "Laos", "Lesotho", "Lettonie", "Liban",
    "Liberia", "Libye", "Liechtenstein", "Lituanie", "Luxembourg",
    "Macédoine du Nord", "Madagascar", "Malaisie", "Malawi", "Maldives",
    "Mali", "Malte", "Maroc", "Maurice", "Mauritanie", "Mexique",
    "Micronésie", "Moldavie", "Monaco", "Mongolie", "Monténégro",
    "Mozambique", "Namibie", "Nauru", "Népal", "Nicaragua", "Niger",
    "Nigeria", "Norvège", "Nouvelle-Zélande", "Oman", "Ouganda",
    "Ouzbékistan", "Pakistan", "Palaos", "Palestine", "Panama",
    "Papouasie-Nouvelle-Guinée", "Paraguay", "Pays-Bas", "Pérou",
    "Philippines", "Pologne", "Portugal", "Qatar", "Roumanie",
    "Royaume-Uni", "Russie", "Rwanda", "Saint-Christophe-et-Niévès",
    "Saint-Marin", "Saint-Vincent-et-les-Grenadines", "Sainte-Lucie",
    "Salvador", "Samoa", "São Tomé-et-Principe", "Sénégal", "Serbie",
    "Seychelles", "Sierra Leone", "Singapour", "Slovaquie", "Slovénie",
    "Somalie", "Soudan", "Soudan du Sud", "Sri Lanka", "Suède", "Suisse",
    "Suriname", "Syrie", "Tadjikistan", "Tanzanie", "Tchad", "Tchéquie",
    "Thaïlande", "Timor oriental", "Togo", "Tonga", "Trinité-et-Tobago",
    "Tunisie", "Turkménistan", "Turquie", "Tuvalu", "Ukraine", "Uruguay",
    "Vanuatu", "Vatican", "Venezuela", "Vietnam", "Yémen", "Zambie",
    "Zimbabwe",
    "Autre",
]

# Choix prêts à l'emploi pour un forms.ChoiceField Django : [(valeur, libellé), ...]
COUNTRY_CHOICES = [("", "Sélectionnez votre pays")] + [(c, c) for c in COUNTRIES]
