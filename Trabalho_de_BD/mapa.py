"""
Geometrias das sub-bacias -> GeoJSON em latitude/longitude (sem shapely/pyproj).

A coluna GEOMETRIA do CSV é WKT em coordenadas UTM (metros). O arquivo não declara o sistema; pelas ordens de grandeza
(E ≈ 598–620 mil, N ≈ 7,78–7,81 milhões) e pelo resultado (cai dentro de Belo Horizonte) assume-se UTM zona 23 Sul
(SIRGAS 2000 / SAD69 diferem de poucas dezenas de metros, irrelevante na escala do mapa).
"""
import re

import numpy as np

# --- elipsoide GRS80 / projeção UTM
_A = 6378137.0
_F = 1 / 298.257222101
_K0, _E0 = 0.9996, 500000.0


def utm_para_latlon(e, n, zona=23, sul=True):
    """Inversa de Transverse Mercator (série de Krüger, 4ª ordem). Retorna (lat, lon) em graus."""
    e = np.asarray(e, float); n = np.asarray(n, float)
    nn = _F / (2 - _F)
    A = _A / (1 + nn) * (1 + nn ** 2 / 4 + nn ** 4 / 64)
    b = [nn / 2 - 2 * nn ** 2 / 3 + 37 * nn ** 3 / 96 - nn ** 4 / 360,
         nn ** 2 / 48 + nn ** 3 / 15 - 437 * nn ** 4 / 1440,
         17 * nn ** 3 / 480 - 37 * nn ** 4 / 840,
         4397 * nn ** 4 / 161280]
    d = [2 * nn - 2 * nn ** 2 / 3 - 2 * nn ** 3 + 116 * nn ** 4 / 45,
         7 * nn ** 2 / 3 - 8 * nn ** 3 / 5 - 227 * nn ** 4 / 45,
         56 * nn ** 3 / 15 - 136 * nn ** 4 / 35,
         4279 * nn ** 4 / 630]
    xi = (n - (10_000_000.0 if sul else 0.0)) / (_K0 * A)
    eta = (e - _E0) / (_K0 * A)
    xi_p, eta_p = xi.copy(), eta.copy()
    for j in range(1, 5):
        xi_p -= b[j - 1] * np.sin(2 * j * xi) * np.cosh(2 * j * eta)
        eta_p -= b[j - 1] * np.cos(2 * j * xi) * np.sinh(2 * j * eta)
    chi = np.arcsin(np.sin(xi_p) / np.cosh(eta_p))
    lat = chi + sum(d[j - 1] * np.sin(2 * j * chi) for j in range(1, 5))
    lon0 = np.radians(zona * 6 - 183)
    lon = lon0 + np.arctan2(np.sinh(eta_p), np.cos(xi_p))
    return np.degrees(lat), np.degrees(lon)


_NUM = r"-?\d+(?:\.\d+)?"
_PAR = re.compile(r"(" + _NUM + r")\s+(" + _NUM + r")")


def _anel(txt, zona, sul):
    pts = np.array(_PAR.findall(txt), float)
    lat, lon = utm_para_latlon(pts[:, 0], pts[:, 1], zona, sul)
    return [[round(float(x), 5), round(float(y), 5)] for x, y in zip(lon, lat)]


def wkt_para_geojson(wkt, zona=23, sul=True):
    """POLYGON / MULTIPOLYGON (com buracos) -> geometria GeoJSON [lon, lat]."""
    t = str(wkt).strip()
    tipo = t.split("(")[0].strip().upper()
    corpo = t[t.index("("):]
    if tipo == "POLYGON":
        aneis = [_anel(r, zona, sul) for r in re.findall(r"\(([^()]+)\)", corpo)]
        return {"type": "Polygon", "coordinates": aneis}
    if tipo == "MULTIPOLYGON":
        polis = re.split(r"\)\)\s*,\s*\(\(", corpo[1:-1].strip()[1:-1])
        return {"type": "MultiPolygon",
                "coordinates": [[_anel(r, zona, sul) for r in re.findall(r"([^()]+)", p) if _PAR.search(r)] for p in polis]}
    raise ValueError(f"Tipo de geometria não suportado: {tipo}")


def _achar(df, *nomes):
    """Nome real da coluna, ignorando maiúsculas/minúsculas, espaços e BOM."""
    mapa = {str(c).lstrip("\ufeff").strip().upper(): c for c in df.columns}
    for n in nomes:
        if n.upper() in mapa:
            return mapa[n.upper()]
    return None


def construir_geojson(raw, zona=23, sul=True):
    """FeatureCollection com properties.cod_sub_bacia. Retorna None se o CSV não tem geometria utilizável."""
    cg = _achar(raw, "GEOMETRIA", "GEOMETRY", "GEOM", "WKT", "THE_GEOM")
    cc = _achar(raw, "COD_SUB_BACIA")
    if cg is None or cc is None:
        return None
    feats, vistos = [], set()
    for cod, wkt in zip(raw[cc], raw[cg]):
        if cod in vistos or not isinstance(wkt, str) or not wkt.strip():
            continue
        try:
            geom = wkt_para_geojson(wkt, zona, sul)
        except (ValueError, IndexError):
            continue                                   # WKT inválido: ignora só essa linha
        vistos.add(cod)
        feats.append({"type": "Feature", "properties": {"cod_sub_bacia": int(cod)}, "geometry": geom})
    return {"type": "FeatureCollection", "features": feats} if feats else None


def filtrar_geojson(gj, codigos):
    codigos = set(int(c) for c in codigos)
    return {"type": "FeatureCollection",
            "features": [f for f in gj["features"] if f["properties"]["cod_sub_bacia"] in codigos]}


def _pontos(geom):
    if geom["type"] == "Polygon":
        return [p for anel in geom["coordinates"] for p in anel]
    return [p for poli in geom["coordinates"] for anel in poli for p in anel]


def caixa(gj):
    """(lon_min, lat_min, lon_max, lat_max)"""
    pts = np.array([p for f in gj["features"] for p in _pontos(f["geometry"])])
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


def centro_zoom(gj, largura_px=900, altura_px=620):
    """Centro e zoom (escala web-mercator) para enquadrar todas as feições."""
    x0, y0, x1, y1 = caixa(gj)
    lat_c = (y0 + y1) / 2
    dx = max(x1 - x0, 1e-4)
    dy = max((y1 - y0) / np.cos(np.radians(lat_c)), 1e-4)
    zoom = min(np.log2(360 * largura_px / (512 * dx)), np.log2(360 * altura_px / (512 * dy))) - 0.15
    return {"lat": float(lat_c), "lon": float((x0 + x1) / 2)}, float(np.clip(zoom, 3, 16))
