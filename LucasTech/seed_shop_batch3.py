# -*- coding: utf-8 -*-
from Shop.models import Category, Product, ProductImage

cat_clothes = Category.objects.get(slug='vetements')
cat_shoes = Category.objects.get(slug='chaussures')
cat_bijoux = Category.objects.get(slug='bijoux-accessoires')
cat_beaute = Category.objects.get(slug='beaute-cosmetiques')
cat_jouets = Category.objects.get(slug='jouets-enfants')
cat_accessoires = Category.objects.get(slug='accessoires-tech')
cat_appliances = Category.objects.get(slug='electromenager')

PLAN = [
    ('shop_clothes2/clothes2', cat_clothes, [
        ("Veste en jean tendance", "Un basique indémodable à associer avec tout le monde.", 22000, None),
        ("Ensemble tailleur femme", "Élégance et professionnalisme pour le bureau ou les événements.", 30000, 35000),
        ("Pull chaud homme", "Confort et chaleur pour les journées fraîches.", 18000, None),
        ("Robe de soirée", "Une robe sophistiquée pour briller lors de vos soirées.", 28000, None),
    ]),
    ('shop_shoes2/shoe2', cat_shoes, [
        ("Bottes en cuir femme", "Élégantes et robustes, parfaites pour toutes les saisons.", 32000, 38000),
        ("Escarpins élégants", "Le raffinement à chaque pas, pour vos occasions spéciales.", 20000, None),
        ("Chaussures de sport running", "Légèreté et amorti pour vos séances de course.", 30000, None),
        ("Mocassins homme", "Un classique confortable pour un style décontracté-chic.", 25000, None),
    ]),
    ('shop_jewelry2/jewelry2', cat_bijoux, [
        ("Boucles d'oreilles élégantes", "Une touche de raffinement pour sublimer votre visage.", 8000, None),
        ("Bague fantaisie", "Un accessoire tendance à porter seul ou en superposition.", 6000, None),
        ("Bijoux ensemble mariage", "Un ensemble complet et élégant pour les grandes occasions.", 20000, None),
        ("Bracelet fin doré", "Discret et chic, à porter au quotidien.", 7000, None),
    ]),
    ('shop_cosmetics2/cosmetic2', cat_beaute, [
        ("Sérum visage anti-âge", "Une formule concentrée pour une peau visiblement plus jeune.", 15000, None),
        ("Crème corps hydratante", "Hydratation longue durée pour une peau douce et nourrie.", 9000, None),
        ("Huile de soin capillaire", "Nourrit et fortifie vos cheveux en profondeur.", 8000, None),
        ("Coffret soin visage complet", "Une routine complète pour une peau éclatante.", 25000, 30000),
    ]),
    ('shop_toys2/toy2', cat_jouets, [
        ("Ballon de jeu enfant", "Idéal pour s'amuser en plein air avec les copains.", 5000, None),
        ("Puzzle éducatif", "Stimule la réflexion et la patience des plus jeunes.", 8000, None),
        ("Set de jeu créatif", "Pour développer l'imagination à travers le jeu.", 12000, None),
    ]),
    ('shop_accessories/accessory', cat_accessoires, [
        ("Câble de charge rapide", "Rechargez vos appareils rapidement et en toute sécurité.", 3000, None),
        ("Chargeur secteur double USB", "Chargez deux appareils en même temps facilement.", 6000, None),
        ("Support téléphone voiture", "Gardez votre téléphone accessible et sécurisé en conduisant.", 5000, None),
        ("Powerbank 10000mAh", "Ne tombez jamais en panne de batterie, où que vous soyez.", 15000, 18000),
    ]),
    ('shop_appliances2/appliance2', cat_appliances, [
        ("Réfrigérateur compact", "Idéal pour un petit espace, garde vos aliments au frais.", 180000, 210000),
        ("Micro-ondes", "Réchauffez et cuisinez rapidement, simple d'utilisation.", 65000, None),
        ("Petit réfrigérateur portable", "Pratique pour le bureau, la chambre ou en déplacement.", 95000, None),
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
