# -*- coding: utf-8 -*-
from django.utils.text import slugify
from Shop.models import Category, Product, ProductImage

def get_cat(name, icon='fa-tag', order=99):
    slug = slugify(name)
    cat, _ = Category.objects.get_or_create(slug=slug, defaults={'name': name, 'icon': icon, 'order': order})
    return cat

cat_phones = Category.objects.get(slug='telephones-smartphones')
cat_computers = Category.objects.get(slug='ordinateurs-laptops')
cat_shoes = Category.objects.get(slug='chaussures')
cat_accessoires = Category.objects.get(slug='accessoires-tech')
cat_appliances = Category.objects.get(slug='electromenager')
cat_beaute = Category.objects.get(slug='beaute-cosmetiques')
cat_clothes = Category.objects.get(slug='vetements')
cat_bijoux = Category.objects.get(slug='bijoux-accessoires')
cat_sacs = Category.objects.get(slug='sacs-bagagerie')
cat_jouets = Category.objects.get(slug='jouets-enfants')
cat_montres = get_cat('Montres', 'fa-clock', 20)
cat_parfums = get_cat('Parfums', 'fa-spray-can', 21)

PLAN = [
    # (folder_prefix, category, [(name, description, price, old_price, group_size), ...])
    ('shop_phones/phone', cat_phones, [
        ("Smartphone Android 128 Go", "Smartphone performant avec 128 Go de stockage, écran haute définition et bonne autonomie. Idéal pour un usage quotidien intensif.", 89000, 105000),
        ("Smartphone Android 256 Go Pro", "Modèle haut de gamme avec 256 Go de stockage, appareil photo performant et charge rapide. Pour ceux qui veulent le meilleur.", 125000, 145000),
        ("iPhone reconditionné", "iPhone reconditionné, testé et garanti fonctionnel à 100%. Une qualité Apple à prix réduit.", 195000, 230000),
        ("Smartphone entrée de gamme", "Un smartphone fiable et abordable pour appeler, naviguer et rester connecté sans se ruiner.", 45000, None),
        ("Smartphone double SIM 4G", "Compatible 4G avec double carte SIM, parfait pour séparer vie pro et perso sur un seul appareil.", 65000, 75000),
    ], 3),
    ('shop_computers/computer', cat_computers, [
        ("Laptop Core i5 8 Go RAM", "Ordinateur portable polyvalent, idéal pour le travail bureautique, les études et la navigation web.", 275000, 310000),
        ("Laptop Core i7 16 Go RAM", "Puissance et rapidité pour le multitâche, le montage ou le développement. 16 Go de RAM pour ne jamais ralentir.", 425000, 480000),
        ("Ordinateur portable bureautique", "Un PC portable simple et efficace pour la bureautique, les emails et les documents.", 185000, None),
        ("PC portable gaming", "Configuration musclée pensée pour le gaming et les logiciels exigeants, carte graphique dédiée.", 495000, 560000),
        ("MacBook reconditionné", "MacBook reconditionné, vérifié et garanti. L'écosystème Apple à un prix plus accessible.", 550000, 620000),
        ("Mini PC compact", "Un petit boîtier puissant pour un bureau minimaliste, parfait pour la bureautique et le streaming.", 165000, None),
    ], 3),
    ('shop_shoes/shoe', cat_shoes, [
        ("Baskets sport homme", "Baskets confortables et résistantes, parfaites pour le sport ou un usage quotidien.", 25000, None),
        ("Baskets sport femme", "Design moderne et confort optimal pour accompagner toutes vos activités.", 25000, None),
        ("Chaussures de ville homme", "Élégance et confort pour un look professionnel ou une sortie habillée.", 35000, 42000),
        ("Sneakers tendance", "Le style urbain du moment, à porter en toute occasion.", 28000, None),
    ], 3),
    ('shop_usb/usb', cat_accessoires, [
        ("Clé USB 32 Go", "Stockage pratique et rapide pour vos fichiers, photos et documents.", 5000, None),
        ("Clé USB 64 Go", "Plus d'espace pour tous vos fichiers, transferts rapides garantis.", 8000, None),
        ("Clé USB 128 Go", "Grande capacité pour sauvegarder vidéos, projets et archives complètes.", 13000, 15000),
    ], 3),
    ('shop_appliances/appliance', cat_appliances, [
        ("Mixeur électrique", "Mixeur puissant pour préparer vos jus, sauces et préparations culinaires en un rien de temps.", 22000, None),
        ("Bouilloire électrique", "Chauffe rapidement l'eau pour votre thé, café ou préparations diverses.", 15000, None),
        ("Fer à repasser", "Un repassage efficace et rapide, semelle glissante pour tous types de tissus.", 18000, None),
        ("Ventilateur de table", "Restez au frais avec ce ventilateur silencieux et compact, idéal bureau ou chambre.", 20000, 24000),
    ], 3),
    ('shop_cosmetics/cosmetic', cat_beaute, [
        ("Kit de maquillage complet", "Un kit complet pour tous vos looks : fards, rouges à lèvres, pinceaux et plus.", 25000, 30000),
        ("Crème hydratante visage", "Hydratation intense pour une peau douce et éclatante au quotidien.", 8000, None),
        ("Palette de fards à paupières", "Une large gamme de couleurs pour sublimer votre regard en toute occasion.", 12000, None),
        ("Rouge à lèvres longue tenue", "Couleur intense qui dure toute la journée, formule confortable.", 5000, None),
    ], 3),
    ('shop_clothes/clothes', cat_clothes, [
        ("Robe élégante femme", "Une robe raffinée pour toutes les occasions, coupe flatteuse et tissu de qualité.", 20000, 24000),
        ("Chemise homme classique", "Chemise élégante et confortable, parfaite pour le bureau ou les sorties.", 15000, None),
        ("Ensemble jean & veste", "Un look casual-chic prêt à porter, alliant confort et style.", 25000, None),
        ("T-shirt tendance", "Coton doux et coupe moderne pour un style décontracté au quotidien.", 8000, None),
    ], 3),
    ('shop_watches/watch', cat_montres, [
        ("Montre classique homme", "Une montre élégante au design intemporel, parfaite pour toutes les occasions.", 20000, 24000),
        ("Montre élégante femme", "Raffinement et précision pour accompagner votre style avec grâce.", 18000, None),
        ("Montre sport étanche", "Résistante à l'eau, idéale pour le sport et les activités outdoor.", 22000, None),
        ("Montre cuir vintage", "Un bracelet en cuir et un cadran rétro pour un style intemporel.", 25000, 30000),
    ], 3),
    ('shop_jewelry/jewelry', cat_bijoux, [
        ("Chaîne en or plaqué homme", "Une chaîne élégante plaquée or, robuste et brillante, pour un style affirmé.", 15000, 18000),
        ("Collier chaîne femme", "Un collier fin et élégant à porter seul ou superposé selon votre humeur.", 12000, None),
        ("Bracelet chaîne", "Un bracelet chic et discret qui complète parfaitement votre tenue.", 8000, None),
        ("Ensemble bijoux (collier + bracelet)", "Un set assorti pour un look harmonieux et soigné en toute occasion.", 18000, 22000),
    ], 3),
    ('shop_perfume/perfume', cat_parfums, [
        ("Parfum homme longue tenue", "Une fragrance boisée et intense qui dure toute la journée.", 22000, 26000),
        ("Parfum femme floral", "Des notes florales délicates pour une élégance subtile et durable.", 22000, 26000),
        ("Eau de toilette unisexe", "Une fragrance fraîche et légère, adaptée à tous les styles.", 18000, None),
        ("Coffret parfum cadeau", "Un coffret soigné, parfait pour offrir ou se faire plaisir.", 28000, 34000),
    ], 3),
    ('shop_handbags/handbag', cat_sacs, [
        ("Sac à main élégant", "Un sac élégant et fonctionnel pour accompagner toutes vos journées.", 18000, None),
        ("Sac à main cuir", "Finition cuir soignée, robuste et intemporel, pour un style affirmé.", 22000, 26000),
        ("Pochette soirée", "Compacte et chic, la pochette idéale pour vos sorties et événements.", 12000, None),
        ("Sac bandoulière", "Pratique et stylé, parfait pour un usage quotidien mains libres.", 16000, None),
    ], 3),
    ('shop_toys/toy', cat_jouets, [
        ("Jouet éducatif enfant", "Un jouet ludique qui stimule l'apprentissage et l'éveil de votre enfant.", 10000, None),
        ("Peluche douce", "Douce et câline, la compagne idéale pour les petits comme les grands.", 6000, None),
        ("Coffret jeux de construction", "Des heures de créativité et d'amusement pour développer l'imagination.", 15000, 18000),
        ("Voiture télécommandée", "Rapide et robuste, pour des heures de jeu plein d'action.", 18000, 22000),
    ], 3),
    ('shop_soap/soap', cat_beaute, [
        ("Savon naturel artisanal", "Fabriqué à base d'ingrédients naturels, doux pour la peau et parfumé.", 2000, None),
        ("Lot de savons parfumés", "Un assortiment de savons aux parfums variés pour toute la famille.", 5000, 6000),
        ("Savon noir traditionnel", "Le savon noir traditionnel pour un nettoyage en profondeur et une peau douce.", 2500, None),
    ], 3),
    ('shop_schoolbags/schoolbag', cat_sacs, [
        ("Sac à dos scolaire", "Solide et spacieux, parfait pour transporter livres et fournitures en toute sécurité.", 12000, 14000),
        ("Cartable enfant", "Confortable et coloré, pensé pour accompagner les plus jeunes à l'école.", 10000, None),
        ("Sac à dos ado", "Design moderne et compartiments pratiques pour la vie scolaire.", 14000, 17000),
    ], 3),
]

import os
MEDIA_ROOT_PRODUCTS = 'shop/products'

total_created = 0
for folder_prefix, category, products, group_size in PLAN:
    for i, prod in enumerate(products):
        name, description, price, old_price = prod
        start = i * group_size + 1
        image_files = [f"{folder_prefix.split('/')[1]}-{start + j}.jpg" for j in range(group_size)]
        folder = folder_prefix.split('/')[0]

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
                img_path = f"products_uploads/{folder}/{img_file}"
                ProductImage.objects.create(product=obj, image=img_path, order=order)
        print(('Créé' if created else 'Existant'), '-', obj.name)

print('--- Total produits ---', Product.objects.count(), '(', total_created, 'nouveaux )')
