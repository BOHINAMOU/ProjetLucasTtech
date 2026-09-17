from django.db import migrations


def seed(apps, schema_editor):
    HeroSlide = apps.get_model('core', 'HeroSlide')
    NewsTickerItem = apps.get_model('core', 'NewsTickerItem')

    HeroSlide.objects.create(
        tag="Technologie · Formation · Innovation",
        title="Lantante Technologie, <em>votre avenir</em> commence ici.",
        subtitle="Des solutions digitales, des formations et une boutique Tech pensées pour vous, à Lomé et partout au Togo.",
        image="hero_slides/slide1-lucastech.jpeg",
        link_url="/services/",
        link_text="Découvrir nos services",
        order=1,
    )
    HeroSlide.objects.create(
        tag="Formations",
        title="Apprenez avec des <em>formateurs</em> qui construisent de vrais projets.",
        subtitle="Développement web, e-commerce, réseaux sociaux, systèmes — des programmes professionnels pour progresser vite.",
        image="hero_slides/slide2-formations.png",
        link_url="/formations/",
        link_text="Voir les formations",
        order=2,
    )
    HeroSlide.objects.create(
        tag="E-Commerce",
        title="La boutique Tech <em>pensée</em> pour être vue.",
        subtitle="Produits et accessoires sélectionnés, fiches détaillées, paiement simple et livraison suivie.",
        image="hero_slides/slide3-boutique.png",
        link_url="/shop/",
        link_text="Voir la boutique",
        order=3,
    )

    items = [
        ("Nouveau", "Formation développement web — inscriptions ouvertes", "/formations/"),
        ("Boutique", "Nouveaux produits Tech disponibles", "/shop/"),
        ("Article", "L'Afrique et la révolution numérique en 2026", "/publications/"),
        ("Service", "Créez votre site vitrine en 2 semaines", "/services/"),
        ("Équipe", "Découvrez qui est derrière Lantante Technologie", "/equipe/"),
    ]
    for i, (label, message, link) in enumerate(items, start=1):
        NewsTickerItem.objects.create(label=label, message=message, link_url=link, order=i)


def unseed(apps, schema_editor):
    apps.get_model('core', 'HeroSlide').objects.all().delete()
    apps.get_model('core', 'NewsTickerItem').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_heroslide_newstickeritem'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
