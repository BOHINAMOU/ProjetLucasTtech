# -*- coding: utf-8 -*-
from Shop.models import Category, Product, ProductImage

cat_tablets = Category.objects.get(slug='tablettes')
cat_audio = Category.objects.get(slug='audio-ecouteurs')
cat_tv = Category.objects.get(slug='televisions-ecrans')
cat_camera = Category.objects.get(slug='appareils-photo')
cat_gaming = Category.objects.get(slug='gaming-consoles')
cat_smartwatch = Category.objects.get(slug='montres-connectees')
cat_fitness = Category.objects.get(slug='sport-fitness')
cat_decor = Category.objects.get(slug='maison-decoration')
cat_stationery = Category.objects.get(slug='papeterie-bureau')
cat_food = Category.objects.get(slug='alimentation-boissons')
cat_computers = Category.objects.get(slug='ordinateurs-laptops')
cat_phones = Category.objects.get(slug='telephones-smartphones')

PLAN = [
    ('shop_tablets/tablet', cat_tablets, [
        ("Tablette tactile 64 Go", "Une tablette polyvalente pour naviguer, lire et regarder vos contenus favoris.", 75000, 85000),
        ("Tablette Pro 128 Go", "Plus de stockage et de puissance pour le travail comme les loisirs.", 120000, 140000),
        ("Tablette enfant éducative", "Conçue pour les enfants, avec contenus éducatifs et contrôle parental.", 45000, None),
        ("Tablette graphique dessin", "Pour les créatifs : dessinez et créez directement sur votre tablette.", 55000, None),
    ]),
    ('shop_audio/audio', cat_audio, [
        ("Écouteurs sans fil Bluetooth", "Son de qualité et liberté de mouvement, autonomie longue durée.", 15000, 18000),
        ("Casque audio circum-aural", "Un confort optimal et un son immersif pour la musique et les appels.", 25000, None),
        ("Écouteurs sport intra-auriculaires", "Légers et résistants à la sueur, parfaits pour le sport.", 12000, None),
        ("Enceinte Bluetooth portable", "Un son puissant à emporter partout, autonomie longue durée.", 20000, 24000),
    ]),
    ('shop_tv/tv', cat_tv, [
        ("Télévision LED 32 pouces", "Une image nette et lumineuse pour votre salon, format compact.", 120000, None),
        ("Télévision Smart TV 43 pouces", "Accédez à vos applications préférées directement sur votre téléviseur.", 220000, 250000),
        ("Télévision 55 pouces 4K", "Une qualité d'image exceptionnelle pour une expérience cinéma à la maison.", 380000, 430000),
        ("Barre de son pour TV", "Améliorez le son de votre téléviseur avec cette barre de son puissante.", 45000, None),
    ]),
    ('shop_camera/camera', cat_camera, [
        ("Appareil photo numérique compact", "Facile à utiliser, parfait pour capturer vos moments du quotidien.", 95000, None),
        ("Appareil photo reflex", "Pour les passionnés de photographie, qualité professionnelle.", 350000, 400000),
        ("Caméra sport étanche", "Capturez vos aventures sous tous les angles, résistante à l'eau.", 65000, None),
        ("Trépied professionnel pour caméra", "Stabilité parfaite pour vos photos et vidéos.", 25000, None),
    ]),
    ('shop_gaming/gaming', cat_gaming, [
        ("Manette de jeu sans fil", "Confort et précision pour toutes vos sessions de jeu.", 18000, None),
        ("Console de jeu portable", "Emportez vos jeux favoris partout avec vous.", 85000, 95000),
        ("Casque gaming avec micro", "Son immersif et communication claire pour le jeu en ligne.", 22000, None),
        ("Console de salon nouvelle génération", "Des graphismes impressionnants pour une expérience de jeu ultime.", 250000, 280000),
    ]),
    ('shop_smartwatch/smartwatch', cat_smartwatch, [
        ("Montre connectée fitness", "Suivez votre activité physique et votre santé au quotidien.", 35000, None),
        ("Montre connectée avec appels", "Passez vos appels directement depuis votre poignet.", 55000, 65000),
        ("Bracelet connecté basique", "Suivi simple et efficace de vos pas et de votre sommeil.", 15000, None),
        ("Montre connectée sport étanche", "Résistante à l'eau, parfaite pour la natation et le sport intense.", 40000, None),
    ]),
    ('shop_fitness/fitness', cat_fitness, [
        ("Kit haltères réglables", "Ajustez le poids selon votre entraînement, gain de place garanti.", 30000, None),
        ("Tapis de fitness", "Confortable et antidérapant pour tous vos exercices au sol.", 10000, None),
        ("Corde à sauter", "Un accessoire simple et efficace pour le cardio.", 4000, None),
        ("Vélo d'appartement pliable", "Pédalez à la maison et gagnez de la place une fois plié.", 150000, 170000),
    ]),
    ('shop_decor/decor', cat_decor, [
        ("Lampe de décoration moderne", "Illuminez votre intérieur avec style et élégance.", 15000, None),
        ("Vase décoratif", "Une touche d'élégance pour sublimer votre salon.", 8000, None),
        ("Cadre photo mural", "Pour afficher vos plus beaux souvenirs avec style.", 6000, None),
        ("Coussin décoratif", "Confort et déco réunis pour votre canapé ou votre lit.", 5000, None),
    ]),
    ('shop_stationery/stationery', cat_stationery, [
        ("Lot de stylos et crayons", "Tout le nécessaire pour écrire, dessiner et prendre des notes.", 3000, None),
        ("Cahier et bloc-notes premium", "Papier de qualité pour vos notes et idées.", 4000, None),
        ("Kit de bureau complet", "Organisez votre espace de travail avec ce kit complet.", 12000, None),
        ("Agenda et organiseur", "Planifiez votre semaine et vos objectifs efficacement.", 6000, None),
    ]),
    ('shop_food/food', cat_food, [
        ("Assortiment de boissons", "Une sélection variée de boissons pour toutes les occasions.", 8000, None),
        ("Café en grains premium", "Un café de qualité pour bien commencer la journée.", 6000, None),
        ("Thé et infusions", "Une sélection de thés et infusions pour se détendre.", 5000, None),
        ("Panier de produits gourmands", "Un assortiment gourmand parfait pour offrir ou se faire plaisir.", 15000, None),
    ]),
    ('shop_computers2/computer2', cat_computers, [
        ("Ordinateur portable ultrabook", "Fin, léger et puissant, l'ultrabook idéal pour la mobilité.", 320000, 360000),
        ("PC de bureau complet", "Un poste de travail complet, prêt à l'emploi avec écran inclus.", 245000, None),
        ("Ordinateur portable étudiant", "Léger, fiable et abordable, parfait pour les études.", 165000, None),
        ("Station de travail professionnelle", "Puissance maximale pour les tâches les plus exigeantes.", 550000, 620000),
        ("Laptop 2-en-1 tactile", "La polyvalence d'une tablette et la puissance d'un ordinateur.", 285000, None),
        ("Ordinateur portable robuste", "Conçu pour résister aux conditions difficiles, fiable en toutes circonstances.", 195000, None),
    ]),
    ('shop_phones2/phone2', cat_phones, [
        ("Smartphone caméra pro", "Un appareil photo de qualité professionnelle dans votre poche.", 145000, 165000),
        ("Smartphone écran incurvé", "Un design élégant et un écran immersif pour une expérience unique.", 175000, None),
        ("Smartphone étanche robuste", "Résistant à l'eau et aux chocs, pour un usage sans limite.", 85000, None),
        ("Smartphone grand écran", "Un grand écran pour profiter pleinement de vos contenus.", 95000, None),
    ]),
]

total_created = 0
for folder_prefix, category, products in PLAN:
    folder, prefix = folder_prefix.split('/')
    for i, (name, description, price, old_price) in enumerate(products):
        start = i * 3 + 1
        image_files = [f"{prefix}-{start + j}.jpg" for j in range(3)]
        cover_path = f"products_uploads/{folder}/{image_files[0]}"

        obj, created = Product.objects.get_or_create(
            name=name,
            defaults=dict(
                category=category,
                description=description,
                price=price,
                old_price=old_price,
                image=cover_path,
                is_available=True,
                stock=20,
            )
        )
        if created:
            total_created += 1
            for order, img_file in enumerate(image_files[1:], start=1):
                ProductImage.objects.create(product=obj, image=f"products_uploads/{folder}/{img_file}", order=order)
        print(('Créé' if created else 'Existant'), '-', obj.name)

print('--- Total produits ---', Product.objects.count(), '(', total_created, 'nouveaux )')
