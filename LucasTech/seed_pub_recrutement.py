# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.core.files import File
from Publications.models import Publication, PublicationCategory, PublicationImage

User = get_user_model()
author = User.objects.get(email='lucbohinamou@gmail.com')
category = PublicationCategory.objects.get(slug='education')

PHONE = "22898535165"

CONTENT = f"""
<p>🚨🚨 <strong>AVIS DE RECRUTEMENT</strong> 🚨🚨</p>

<p>Le <strong>Complexe Scolaire SANTIBON</strong>, sis à Barkoissi, dans le cadre du
renforcement de son personnel enseignant, recherche un(e) <strong>professeur(e) de
Physique-Chimie</strong> pour la rentrée scolaire <strong>2026-2027</strong>.</p>

<h2>Comment postuler</h2>
<p>Toute personne intéressée est priée de nous contacter en message privé (inbox) ou
directement au numéro suivant :</p>
<p>📞 <a href="tel:+228{PHONE[3:]}">+228 98 53 51 65</a> —
<a href="https://wa.me/{PHONE}" target="_blank" rel="noopener">écrire sur WhatsApp</a></p>

<blockquote>Merci d'avance pour votre intérêt, et n'hésitez pas à partager largement
cette annonce autour de vous. 🙏🙏</blockquote>
"""

pub, created = Publication.objects.get_or_create(
    title="Recrutement : le Complexe Scolaire SANTIBON recherche un(e) professeur(e) de Physique-Chimie",
    defaults=dict(
        author=author,
        category=category,
        content=CONTENT,
        publication_type='article',
        is_published=True,
        is_featured=True,
    )
)

if created or not pub.cover_image:
    with open('/tmp/pub_recrutement/cover.jpg', 'rb') as f:
        pub.cover_image.save('santibon_recrutement_cover.jpg', File(f), save=True)

if created:
    gallery_files = ['gallery1.jpg', 'gallery2.jpg', 'gallery3.jpg']
    captions = [
        "Physique-Chimie : au coeur des apprentissages scientifiques",
        "Travaux pratiques et expérimentation en laboratoire",
        "Un cadre d'enseignement stimulant pour les élèves",
    ]
    for i, (fname, caption) in enumerate(zip(gallery_files, captions), start=1):
        with open(f'/tmp/pub_recrutement/{fname}', 'rb') as f:
            img = PublicationImage(publication=pub, caption=caption, order=i)
            img.image.save(fname, File(f), save=True)

print(('Créée' if created else 'Existante'), '-', pub.title, '- slug:', pub.slug)
print('Total publications :', Publication.objects.count())
