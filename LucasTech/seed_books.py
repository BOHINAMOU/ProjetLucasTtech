# -*- coding: utf-8 -*-
from django.utils.text import slugify
from Shop.models import Category, Product

cat, _ = Category.objects.get_or_create(
    slug='livres',
    defaults={'name': 'Livres', 'icon': 'fa-book', 'order': 22},
)

SUPER_PROF_WHATSAPP = '22892462962'

PLAN = [
    dict(
        name="Annale H.K.A. Physique-Chimie Tle C — Tome 2 : Chimie",
        description=(
            "Annale collection H.K.A. pour la classe de Terminale C, Tome 2 : Chimie, "
            "programme APC. Cours détaillés, plus de 300 exercices, anciens sujets du "
            "BAC et corrigés détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=4000, image='book01_tlec_chimie_t2.webp',
    ),
    dict(
        name="Annale H.K.A. Physique-Chimie et Technologie 3ème",
        description=(
            "Annale collection H.K.A. pour la classe de 3ème, Physique-Chimie et "
            "Technologie, programme APC. Tous les cours détaillés, plus de 200 exercices "
            "(vrai/faux, QCM, situations complexes), sujets de BEPC (2000-2025) et "
            "corrigés détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=3000, image='book02_3eme_pct.webp',
    ),
    dict(
        name="Annale H.K.A. Physique-Chimie et Technologie 4ème",
        description=(
            "Annale collection H.K.A. pour la classe de 4ème, Physique-Chimie et "
            "Technologie, programme APC. L'essentiel du cours et 200 exercices corrigés. "
            "Vendu pour le compte de Super Prof Togo."
        ),
        price=3000, image='book03_4eme_pct.webp',
    ),
    dict(
        name="Annale H.K.A. Maths 2nde CD",
        description=(
            "Annale collection H.K.A. pour la classe de 2nde CD, Mathématiques, "
            "programme APC. Cours synthétiques, compositions régionales, exercices "
            "d'entraînement, 270 QCM et exercices progressifs, tous les corrigés "
            "détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=4000, image='book04_2ndecd_maths.webp',
    ),
    dict(
        name="Annale H.K.A. Mathématiques Tle C — Tome 1",
        description=(
            "Annale collection H.K.A. pour la classe de Terminale C, Mathématiques, "
            "Tome 1, programme APC. Cours détaillés, plus de 400 exercices, anciens "
            "sujets du BAC et corrigés détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=5000, image='book05_tlec_maths_t1.webp',
    ),
    dict(
        name="Annale H.K.A. Physique Tle C — Tome 1",
        description=(
            "Annale collection H.K.A. pour la classe de Terminale C, Tome 1 : Physique, "
            "programme APC. Cours détaillés, plus de 300 exercices, anciens sujets du "
            "BAC et corrigés détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=4000, image='book06_tlec_physique_t1.webp',
    ),
    dict(
        name="Annale H.K.A. Mathématiques 4ème",
        description=(
            "Annale collection H.K.A. pour la classe de 4ème, Mathématiques, programme "
            "APC. L'essentiel du cours et 200 exercices corrigés. Vendu pour le compte "
            "de Super Prof Togo."
        ),
        price=3000, image='book07_4eme_maths.webp',
    ),
    dict(
        name="Annale H.K.A. Maths — Probatoire 1ère C4",
        description=(
            "Annales collection H.K.A. — Probatoire C4, Mathématiques, programme APC "
            "Première C4. Tous les cours détaillés, plus de 300 séries d'exercices, "
            "corrigés détaillés, sujets des anciens probatoires, épreuves APC et "
            "corrigés de compositions régionales. Vendu pour le compte de Super Prof Togo."
        ),
        price=5000, image='book08_1erec4_maths_proba.webp',
    ),
    dict(
        name="Annale H.K.A. Physique-Chimie — Probatoire 1ère C4",
        description=(
            "Annales collection H.K.A. — Probatoire C4, Physique-Chimie, programme APC "
            "Première C4. Tous les cours détaillés, plus de 300 séries d'exercices, "
            "corrigés détaillés, sujets des anciens probatoires, épreuves APC et "
            "corrigés de compositions régionales. Vendu pour le compte de Super Prof Togo."
        ),
        price=5000, image='book09_1erec4_pc_proba.webp',
    ),
    dict(
        name="Annale H.K.A. Mathématiques 3ème",
        description=(
            "Annale collection H.K.A. pour la classe de 3ème, Mathématiques, programme "
            "APC. Tous les cours détaillés, plus de 200 exercices (vrai/faux, QCM, "
            "textes à compléter, situations complexes), sujets de BEPC (2000-2025) et "
            "corrigés détaillés. Vendu pour le compte de Super Prof Togo."
        ),
        price=3000, image='book10_3eme_maths.webp',
    ),
    dict(
        name="Annale H.K.A. Physique-Chimie — Probatoire 1ère D",
        description=(
            "Annales collection H.K.A. — Probatoire D, Physique-Chimie, programme APC "
            "Première D. Tous les cours détaillés, plus de 300 séries d'exercices, "
            "corrigés détaillés, sujets des anciens probatoires, épreuves APC et "
            "corrigés de compositions régionales. Vendu pour le compte de Super Prof Togo."
        ),
        price=4000, image='book11_1ered_pc_proba.webp',
    ),
    dict(
        name="Annale H.K.A. SVT — Probatoire 1ère D",
        description=(
            "Annales collection H.K.A. — Probatoire D, SVT, programme APC Première D. "
            "Tous les cours détaillés, plus de 300 séries d'exercices, corrigés "
            "détaillés, sujets des anciens probatoires. Vendu pour le compte de Super "
            "Prof Togo."
        ),
        price=4000, image='book12_1ered_svt_proba.webp',
    ),
    dict(
        name="Annale H.K.A. Physique-Chimie Tle D (2026-2027)",
        description=(
            "Annale collection H.K.A. pour la classe de Terminale D, Physique-Chimie, "
            "programme APC, édition 2026-2027. Cours détaillés, plus de 300 exercices "
            "(situations problèmes, questions objectives, questions traditionnelles), "
            "sujets de BAC 2 (2000-2026), compositions régionales et corrigés détaillés. "
            "Vendu pour le compte de Super Prof Togo."
        ),
        price=5000, image='book13_tled_pc.webp',
    ),
]

total_created = 0
for p in PLAN:
    img_file = p.pop('image')
    obj, created = Product.objects.get_or_create(
        name=p['name'],
        defaults=dict(
            category=cat,
            description=p['description'],
            price=p['price'],
            image=f"products_uploads/books/{img_file}",
            contact_whatsapp=SUPER_PROF_WHATSAPP,
            is_available=True,
            stock=20,
        )
    )
    if created:
        total_created += 1
    print(('Créé' if created else 'Existant'), '-', obj.name)

print('--- Total produits ---', Product.objects.count(), '(', total_created, 'nouveaux )')
