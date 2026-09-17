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


# Indicatifs téléphoniques internationaux (pays -> indicatif), pour les
# formulaires qui proposent le choix de l'indicatif dans un menu déroulant
# couvrant tous les pays (ex : inscription à un événement).
DIAL_CODES = {
    "Afghanistan": "+93", "Afrique du Sud": "+27", "Albanie": "+355", "Algérie": "+213",
    "Allemagne": "+49", "Andorre": "+376", "Angola": "+244", "Antigua-et-Barbuda": "+1268",
    "Arabie saoudite": "+966", "Argentine": "+54", "Arménie": "+374", "Australie": "+61",
    "Autriche": "+43", "Azerbaïdjan": "+994", "Bahamas": "+1242", "Bahreïn": "+973",
    "Bangladesh": "+880", "Barbade": "+1246", "Belgique": "+32", "Belize": "+501",
    "Bénin": "+229", "Bhoutan": "+975", "Biélorussie": "+375", "Birmanie (Myanmar)": "+95",
    "Bolivie": "+591", "Bosnie-Herzégovine": "+387", "Botswana": "+267", "Brésil": "+55",
    "Brunei": "+673", "Bulgarie": "+359", "Burkina Faso": "+226", "Burundi": "+257",
    "Cambodge": "+855", "Cameroun": "+237", "Canada": "+1", "Cap-Vert": "+238",
    "République centrafricaine": "+236", "Chili": "+56", "Chine": "+86", "Chypre": "+357",
    "Colombie": "+57", "Comores": "+269", "Congo-Brazzaville": "+242",
    "RD Congo (Kinshasa)": "+243", "Corée du Nord": "+850", "Corée du Sud": "+82",
    "Costa Rica": "+506", "Côte d'Ivoire": "+225", "Croatie": "+385", "Cuba": "+53",
    "Danemark": "+45", "Djibouti": "+253", "Dominique": "+1767", "Égypte": "+20",
    "Émirats arabes unis": "+971", "Équateur": "+593", "Érythrée": "+291", "Espagne": "+34",
    "Estonie": "+372", "Eswatini": "+268", "États-Unis": "+1", "Éthiopie": "+251",
    "Fidji": "+679", "Finlande": "+358", "France": "+33", "Gabon": "+241", "Gambie": "+220",
    "Géorgie": "+995", "Ghana": "+233", "Grèce": "+30", "Grenade": "+1473",
    "Guatemala": "+502", "Guinée": "+224", "Guinée-Bissau": "+245",
    "Guinée équatoriale": "+240", "Guyana": "+592", "Haïti": "+509", "Honduras": "+504",
    "Hongrie": "+36", "Îles Marshall": "+692", "Îles Salomon": "+677", "Inde": "+91",
    "Indonésie": "+62", "Irak": "+964", "Iran": "+98", "Irlande": "+353", "Islande": "+354",
    "Israël": "+972", "Italie": "+39", "Jamaïque": "+1876", "Japon": "+81",
    "Jordanie": "+962", "Kazakhstan": "+7", "Kenya": "+254", "Kirghizistan": "+996",
    "Kiribati": "+686", "Kosovo": "+383", "Koweït": "+965", "Laos": "+856",
    "Lesotho": "+266", "Lettonie": "+371", "Liban": "+961", "Liberia": "+231",
    "Libye": "+218", "Liechtenstein": "+423", "Lituanie": "+370", "Luxembourg": "+352",
    "Macédoine du Nord": "+389", "Madagascar": "+261", "Malaisie": "+60", "Malawi": "+265",
    "Maldives": "+960", "Mali": "+223", "Malte": "+356", "Maroc": "+212",
    "Maurice": "+230", "Mauritanie": "+222", "Mexique": "+52", "Micronésie": "+691",
    "Moldavie": "+373", "Monaco": "+377", "Mongolie": "+976", "Monténégro": "+382",
    "Mozambique": "+258", "Namibie": "+264", "Nauru": "+674", "Népal": "+977",
    "Nicaragua": "+505", "Niger": "+227", "Nigeria": "+234", "Norvège": "+47",
    "Nouvelle-Zélande": "+64", "Oman": "+968", "Ouganda": "+256", "Ouzbékistan": "+998",
    "Pakistan": "+92", "Palaos": "+680", "Palestine": "+970", "Panama": "+507",
    "Papouasie-Nouvelle-Guinée": "+675", "Paraguay": "+595", "Pays-Bas": "+31",
    "Pérou": "+51", "Philippines": "+63", "Pologne": "+48", "Portugal": "+351",
    "Qatar": "+974", "Roumanie": "+40", "Royaume-Uni": "+44", "Russie": "+7",
    "Rwanda": "+250", "Saint-Christophe-et-Niévès": "+1869", "Saint-Marin": "+378",
    "Saint-Vincent-et-les-Grenadines": "+1784", "Sainte-Lucie": "+1758",
    "Salvador": "+503", "Samoa": "+685", "São Tomé-et-Principe": "+239",
    "Sénégal": "+221", "Serbie": "+381", "Seychelles": "+248", "Sierra Leone": "+232",
    "Singapour": "+65", "Slovaquie": "+421", "Slovénie": "+386", "Somalie": "+252",
    "Soudan": "+249", "Soudan du Sud": "+211", "Sri Lanka": "+94", "Suède": "+46",
    "Suisse": "+41", "Suriname": "+597", "Syrie": "+963", "Tadjikistan": "+992",
    "Tanzanie": "+255", "Tchad": "+235", "Tchéquie": "+420", "Thaïlande": "+66",
    "Timor oriental": "+670", "Togo": "+228", "Tonga": "+676",
    "Trinité-et-Tobago": "+1868", "Tunisie": "+216", "Turkménistan": "+993",
    "Turquie": "+90", "Tuvalu": "+688", "Ukraine": "+380", "Uruguay": "+598",
    "Vanuatu": "+678", "Vatican": "+379", "Venezuela": "+58", "Vietnam": "+84",
    "Yémen": "+967", "Zambie": "+260", "Zimbabwe": "+263",
}

# Choix prêts à l'emploi pour un menu déroulant d'indicatif téléphonique,
# triés par indicatif puis pays, au format "+228 — Togo". Le Togo est
# placé en premier (marché principal de Lantante Technologie) pour un accès rapide.
_dial_items = sorted(DIAL_CODES.items(), key=lambda kv: kv[0])
DIAL_CODE_CHOICES = (
    [("+228", "🇹🇬 +228 — Togo")]
    + [
        (code, f"{code} — {country}")
        for country, code in _dial_items
        if country != "Togo"
    ]
)
