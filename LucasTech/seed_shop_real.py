# -*- coding: utf-8 -*-
from Shop.models import Category, Product, ProductImage

cat_clothes = Category.objects.get(slug='vetements')
cat_sacs = Category.objects.get(slug='sacs-bagagerie')

# (folder, category, name, description, price, old_price, [image_files...])
PLAN = [
    (
        'chemise1', cat_clothes,
        "Chemise oversize rayée femme",
        "Une chemise ample à manches 3/4 et col large, coupe oversize très tendance. "
        "Tissu léger et fluide, parfaite avec un jean ou un legging. "
        "Disponible en plusieurs coloris : rose, vert, rouge et bleu (voir la galerie de photos).",
        15000, None,
        ["chemise1-1.jpg", "chemise1-2.jpg", "chemise1-3.jpg", "chemise1-4.jpg", "chemise1-5.jpg"],
    ),
    (
        'chemise2', cat_clothes,
        "Chemise rayée cintrée style urbain",
        "Chemise boutonnée à rayures, coupe plus cintrée, à porter décontractée avec un short "
        "ou un pantalon. Un basique chic pour toutes vos sorties. "
        "Disponible en plusieurs coloris : bleu marine, bleu ciel, vert et rose.",
        16000, None,
        ["chemise2-1.jpg", "chemise2-2.jpg", "chemise2-3.jpg", "chemise2-4.jpg"],
    ),
    (
        'sac1', cat_sacs,
        "Sac moelleux fausse fourrure \"You Deserve Better\"",
        "Sac à main tout doux en fausse fourrure, anse en satin noué et pampille message "
        "\"You deserve better\". Un accessoire cosy et tendance pour twister toutes vos tenues. "
        "Disponible en plusieurs couleurs : noir, rose, écru et gris.",
        12000, None,
        ["sac1-1.jpg", "sac1-2.jpg", "sac1-3.jpg", "sac1-4.jpg", "sac1-5.jpg", "sac1-6.jpg"],
    ),
    (
        'sac2', cat_sacs,
        "Sac bandoulière imprimé cerises",
        "Petit sac à rabat façon enveloppe, entièrement imprimé de cerises, anse torsadée "
        "et bandoulière amovible incluse. Le détail girly qui complète toutes vos tenues. "
        "Disponible en blanc, noir, rose et bleu ciel.",
        10000, None,
        ["sac2-1.jpg", "sac2-2.jpg", "sac2-3.jpg", "sac2-4.jpg", "sac2-5.jpg", "sac2-6.jpg"],
    ),
    (
        'jogging1', cat_clothes,
        "Ensemble jogging 2 pièces à nœuds",
        "Ensemble deux pièces : brassière rose côtelée et pantalon large bleu marine orné "
        "de petits nœuds roses sur les côtés. Confortable et stylé pour le quotidien ou le sport.",
        20000, None,
        ["jogging1-1.jpg"],
    ),
    (
        'sport1', cat_clothes,
        "Ensemble sport 2 pièces (crop top + short)",
        "Ensemble activewear crop top manches courtes et short taille haute, tissu extensible "
        "et confortable pour le sport ou le quotidien décontracté. "
        "Disponible en bordeaux, kaki et vert sauge.",
        18000, None,
        ["sport1-1.jpg"],
    ),
    (
        'legging1', cat_clothes,
        "Ensemble débardeur et legging côtelé",
        "Ensemble deux pièces côtelé, débardeur ajusté et legging taille haute assortis, "
        "coloris marron chocolat. Idéal pour un look casual-chic toute la journée.",
        17000, None,
        ["legging1-1.jpg"],
    ),
    (
        'robetropic1', cat_clothes,
        "Robe longue imprimée tropicale",
        "Robe longue dos nu à col halter, imprimé floral tropical sur fond jaune pastel, "
        "finition franges au bas de la robe. Une pièce estivale qui ne manque pas d'élégance.",
        22000, None,
        ["robetropic1-1.jpg"],
    ),
    (
        'combi1', cat_clothes,
        "Combinaison asymétrique à nœuds",
        "Combinaison une épaule avec nœud sur la manche, haut drapé et pantacourt ajusté assorti. "
        "Une pièce élégante et sensuelle pour vos sorties. "
        "Disponible en bleu, rose et chocolat.",
        19000, None,
        ["combi1-1.jpg", "combi1-2.jpg", "combi1-3.jpg", "combi1-4.jpg", "combi1-5.jpg", "combi1-6.jpg"],
    ),
    (
        'robebustier1', cat_clothes,
        "Robe longue drapée bustier avec broche",
        "Robe bustier longue fluide, drapé central retenu par une broche dorée et noire au "
        "niveau du buste. Coupe évasée très féminine, idéale pour une soirée. "
        "Disponible en rose, chocolat, rouge et noir.",
        25000, None,
        ["robebustier1-1.jpg", "robebustier1-2.jpg", "robebustier1-3.jpg", "robebustier1-4.jpg"],
    ),
]

total_created = 0
for folder, category, name, description, price, old_price, image_files in PLAN:
    cover_path = f"products_uploads/shop_real/{folder}/{image_files[0]}"

    obj, created = Product.objects.get_or_create(
        name=name,
        defaults=dict(
            category=category,
            description=description,
            price=price,
            old_price=old_price,
            image=cover_path,
            is_available=True,
            stock=15,
        )
    )
    if created:
        total_created += 1
        for order, img_file in enumerate(image_files[1:], start=1):
            ProductImage.objects.create(product=obj, image=f"products_uploads/shop_real/{folder}/{img_file}", order=order)
    print(('Créé' if created else 'Existant'), '-', obj.name)

print('--- Total produits ---', Product.objects.count(), '(', total_created, 'nouveaux )')
