"""Adresse IP réelle du client derrière nginx (impossible à falsifier par l'en-tête X-Forwarded-For).

nginx écrit X-Real-IP = $remote_addr et AJOUTE l'adresse réelle à la fin de X-Forwarded-For :
seule cette dernière valeur est fiable (les précédentes viennent du client).
"""


def ip_client(request):
    meta = request.META
    reel = (meta.get('HTTP_X_REAL_IP') or '').strip()
    if reel:
        return reel
    fwd = [x.strip() for x in (meta.get('HTTP_X_FORWARDED_FOR') or '').split(',') if x.strip()]
    if fwd:
        return fwd[-1]
    return meta.get('REMOTE_ADDR', '') or ''
