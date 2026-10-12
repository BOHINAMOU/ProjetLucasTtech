# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from Publications.models import Publication, PublicationCategory, PublicationImage

User = get_user_model()
author = User.objects.get(email='lucbohinamou@gmail.com')
category = PublicationCategory.objects.get(slug='education')

WHATSAPP_GROUP = "https://chat.whatsapp.com/L5TQa7m20P6HW8wSzSLKkC"
WHATSAPP_1 = "22891973334"
WHATSAPP_2 = "22899406554"

CONTENT = f"""
<p>En Afrique, des milliers de créateurs de contenu vivent déjà de TikTok, YouTube et
Facebook — sans studio, sans gros matériel, juste avec un smartphone et une bonne
stratégie. Cette formation complète vous donne toutes les clés pour créer vos comptes
correctement, choisir la bonne niche et commencer à générer des revenus grâce à vos
contenus.</p>

<h2>Ce que vous allez apprendre</h2>
<ul>
<li>Créer et configurer correctement un compte TikTok, YouTube et Facebook orienté monétisation dès le départ</li>
<li>Choisir sa niche : comment trouver le sujet qui vous correspond et qui rapporte réellement</li>
<li>Les critères et conditions de monétisation propres à chaque plateforme</li>
<li>Créer du contenu régulier qui attire l'algorithme et fidélise une audience</li>
<li>Diversifier ses revenus : publicité, partenariats, affiliation, vente de produits/services</li>
<li>Les erreurs qui font perdre des comptes (et donc des revenus) — et comment les éviter</li>
</ul>

<h2><i class="fa-brands fa-tiktok"></i> TikTok</h2>
<p>Comprendre l'algorithme, publier au bon rythme, rejoindre le programme de monétisation
et transformer les vues en revenus réguliers.</p>

<h2><i class="fa-brands fa-youtube"></i> YouTube</h2>
<p>Configurer une chaîne professionnelle, atteindre les seuils du programme partenaire,
et exploiter les Shorts pour accélérer sa croissance.</p>

<h2><i class="fa-brands fa-facebook"></i> Facebook</h2>
<p>Créer une page qui respecte les standards de monétisation, utiliser les vidéos et le
direct pour engager une communauté, et activer les outils de revenus de la plateforme.</p>

<blockquote>Pas besoin d'être déjà connu : avec la bonne méthode, tout le monde peut démarrer
et progresser, même en partant de zéro.</blockquote>

<h2>Comment s'inscrire</h2>
<p>Deux façons de nous rejoindre :</p>
<ul>
<li><strong>Rejoignez le groupe WhatsApp de la formation</strong> :
<a href="{WHATSAPP_GROUP}" target="_blank" rel="noopener">{WHATSAPP_GROUP}</a></li>
<li><strong>Écrivez-nous directement sur WhatsApp</strong> :
<a href="https://wa.me/{WHATSAPP_1}" target="_blank" rel="noopener">+228 91 97 33 34</a>
ou
<a href="https://wa.me/{WHATSAPP_2}" target="_blank" rel="noopener">+228 99 40 65 54</a></li>
</ul>
<p>Vous pouvez aussi remplir directement le formulaire d'inscription ci-dessus pour réserver votre place.</p>
"""

pub, created = Publication.objects.get_or_create(
    title="Formation complète : Monétisation en Afrique (TikTok, YouTube & Facebook)",
    defaults=dict(
        author=author,
        category=category,
        content=CONTENT,
        publication_type='evenement',
        registration_open=True,
        is_published=True,
        is_featured=False,
        cover_image='publications/covers/monetisation_afrique_cover.jpg',
    )
)

from django.core.files import File

if created or not pub.cover_image:
    with open('/tmp/pub_monetisation/cover.jpg', 'rb') as f:
        pub.cover_image.save('monetisation_afrique_cover.jpg', File(f), save=True)

if created:
    gallery_files = ['gallery1.jpg', 'gallery2.jpg', 'gallery3.jpg', 'gallery4.jpg', 'gallery5.jpg']
    captions = [
        "Créer du contenu, un smartphone suffit pour démarrer",
        "Rester connecté à sa communauté au quotidien",
        "Suivre ses statistiques pour ajuster sa stratégie",
        "Les réseaux sociaux, un vrai levier de revenus",
        "Filmer et publier régulièrement pour progresser",
    ]
    for i, (fname, caption) in enumerate(zip(gallery_files, captions), start=1):
        with open(f'/tmp/pub_monetisation/{fname}', 'rb') as f:
            img = PublicationImage(publication=pub, caption=caption, order=i)
            img.image.save(fname, File(f), save=True)

print(('Créée' if created else 'Existante'), '-', pub.title, '- slug:', pub.slug)
print('Total publications :', Publication.objects.count())
