# -*- coding: utf-8 -*-
from django.contrib.auth import get_user_model
from django.core.files import File
from Publications.models import Publication, PublicationCategory

User = get_user_model()
author = User.objects.get(email='lucbohinamou@gmail.com')
category = PublicationCategory.objects.get(slug='culture')

YOUTUBE_URL = "https://youtu.be/JjBGJPwWCAk?si=k2-_pEJ-B6OJKEsL"

CONTENT = f"""
<p>🎙️ <strong>SULTAN 2LAFADA</strong> — Transformer les mots en voix, et la voix en conscience.</p>

<p>Ainsi se résume l'univers de cet artiste polyvalent : slameur, rappeur, auteur-compositeur-interprète,
dont la plume s'inspire des réalités de la société et des valeurs de la culture africaine.</p>

<p>À travers ses œuvres consacrées à la paix, l'environnement, la citoyenneté, la santé publique, la
politique et la culture africaine, Sultan 2Lafada fait de la musique un véritable outil d'expression,
d'interpellation et de sensibilisation.</p>

<p>Originaire de la région des Savanes au Togo, l'artiste revient ce 20 septembre 2026 avec un nouveau
titre intitulé « <strong>NOS RACINES</strong> ».</p>

<p>🌍 « NOS RACINES » est une œuvre qui invite à un retour aux sources. Le morceau rappelle, interpelle
et propose des pistes de réflexion face aux enjeux liés à l'identité culturelle africaine, le problème
de la chevelure et au système éducatif africain.</p>

<p>À travers sa plume, Sultan 2Lafada pose une question essentielle : comment construire l'avenir
lorsque l'on s'éloigne de ses propres racines ?</p>

<p>🎵 « NOS RACINES » est disponible sur sa chaîne YouTube :</p>
<p><a href="{YOUTUBE_URL}" target="_blank" rel="noopener">{YOUTUBE_URL}</a></p>

<p>Vous pouvez également retrouver ses deux albums, « ESPOIR » et « ECLOSION », sur les principales
plateformes musicales, notamment YouTube, Amazon Music et Apple Music.</p>

<blockquote>SULTAN 2LAFADA — Des mots pour éveiller. Une voix pour interpeller. Des racines pour
construire l'avenir.</blockquote>
"""

pub, created = Publication.objects.get_or_create(
    title="Sultan 2Lafada dévoile son nouveau titre « Nos Racines »",
    defaults=dict(
        author=author,
        category=category,
        content=CONTENT,
        publication_type='article',
        is_published=True,
        is_featured=False,
    )
)

if created or not pub.cover_image:
    with open('/tmp/pub_sultan/cover.jpg', 'rb') as f:
        pub.cover_image.save('sultan_2lafada_nos_racines.jpg', File(f), save=True)

print(('Créée' if created else 'Existante'), '-', pub.title, '- slug:', pub.slug)
print('Total publications :', Publication.objects.count())
