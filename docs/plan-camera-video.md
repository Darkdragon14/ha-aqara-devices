# Plan: Aqara Camera Video

## Objectif

Ajouter une premiere prise en charge video only pour les cameras Aqara dans Home Assistant.

## Decision initiale

Commencer par le flux RTSP LAN natif.

Flux cibles:

- `ch1`: haute qualite, active par defaut.
- `ch2`: qualite moyenne, optionnel plus tard.
- `ch3`: basse qualite, optionnel plus tard.

## Portee initiale

- Ajouter la plateforme Home Assistant `camera`.
- Creer une entite camera par camera compatible.
- Utiliser `stream_source()` avec l'URL RTSP.
- Fournir les snapshots via `ffmpeg.async_get_image`.
- Garder le controle on/off via les switches existants.

## Hors perimetre initial

- Pas de 2-way audio.
- Pas de go2rtc obligatoire.
- Pas de telnet/root G3.
- Pas de modification automatique de `go2rtc.yaml`.
- Pas de cloud streaming reverse-engineered.

## Configuration necessaire

Ajouter dans l'options flow:

- IP camera ou hostname.
- Username RTSP.
- Password RTSP.
- Canal par defaut, probablement `ch1`.

## Fichiers a modifier

- `const.py`
- `__init__.py`
- `config_flow.py`
- `options_flow.py`
- Nouveau fichier `camera.py`
- `manifest.json` si dependances necessaires
- Traductions si ajout de champs UI

## Etapes

1. Ajouter `camera` dans `PLATFORMS`.
2. Ajouter les constantes de config RTSP.
3. Etendre le flow/options pour saisir IP et credentials RTSP.
4. Creer `camera.py`.
5. Ajouter une classe `AqaraCameraEntity`.
6. Implementer `stream_source()`.
7. Implementer `async_camera_image()`.
8. Rattacher l'entite au device Aqara existant avec `DeviceInfo`.
9. Tester dans Home Assistant avec le flux `ch1`.
10. Verifier logs, snapshot et live stream.

## Implementation recommandee

- Ne pas rendre la configuration RTSP obligatoire pour charger l'integration.
- Creer l'entite camera uniquement quand les champs RTSP sont presents.
- Utiliser `rtsp://<user>:<password>@<host>:8554/ch1` comme source initiale.
- Encoder correctement username/password dans l'URL RTSP.
- Exposer les erreurs RTSP dans les logs sans afficher le mot de passe.
- Garder le flux HA standard pour permettre `camera.snapshot`, `camera.record` et `camera.play_stream`.

## Extension future

- Ajouter `ch2` et `ch3` comme entites desactivees par defaut.
- Ajouter support go2rtc/WebRTC.
- Ajouter 2-way audio uniquement apres validation video stable.
- Ajouter auto-detection RTSP LAN si fiable.
- Ajouter une option de preload stream si necessaire.

## Criteres de validation

- Une camera Aqara expose un flux dans Home Assistant.
- Le live stream s'ouvre depuis l'interface Home Assistant.
- Les snapshots fonctionnent.
- Les credentials invalides echouent proprement.
- L'integration continue de charger sans configuration RTSP.
- Les modeles sans RTSP restent inchanges.

## Risques

- RTSP LAN doit etre active dans l'app Aqara.
- Certains modeles n'exposent pas `/ch1`.
- Les credentials RTSP sont distincts des credentials Aqara Cloud.
- Les flux LAN ne fonctionnent pas hors reseau local sans relais.
- go2rtc ameliore la latence et le WebRTC, mais n'augmente pas la qualite native du flux.
