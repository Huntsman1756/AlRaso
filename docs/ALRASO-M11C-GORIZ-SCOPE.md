# ALRASO M1.1-C — GORIZ_REAL_WORLD_EXCEPTION

Fecha de ejecución: 2026-09-05 · Predecesor: `docs/ALRASO-M11-VECTOR-DISCOVERY.md`
(Evidence: `tooling/m11c_goriz_scope.evidence.json`, raw artifacts en
`discovery/evidence/m11c-goriz/`, verificador en vivo `tooling/m11c_goriz_identity.py`)

## Pregunta y gate

¿Es el vector oficial `ENP101_137` (WFS ICEAragon) **inequívocamente el mismo ámbito
jurídico** que la "Zona de acampada de alta montaña adyacente al refugio de Góriz"
(PRUG D 49/2015, Anexo 11.5 Mapa 29)? Un nombre parecido o "estar encima del refugio"
no basta.

| Gate | Significado | Consecuencia |
|---|---|---|
| **A** | `OFFICIAL_SCOPE_LINK_PROVEN` | continuar con la norma y codificar el caso |
| B | `OFFICIAL_VECTOR_EXISTS_BUT_LINK_NOT_PROVEN` | `SPATIAL_EVIDENCE_INCOMPLETE`, parar |
| C | `NO_USABLE_VECTOR` | parar |

## Resultado: **A — OFFICIAL_SCOPE_LINK_PROVEN** (reconfirmado en vivo el 2026-09-05)

Cadena de identidad (cada eslabón fijado por SHA-256 en el lock):

1. **Norma.** El texto del PRUG (fijado `bec715b7…`) nombra la zona en p. 20 con
   remisión expresa "Anexo 11.5 Cartografía. Mapa 29", y la regla 9.2.1.3.1 (mod.
   D 16/2022) habla de la "Zona de Uso Moderado de Góriz".
2. **Vector estatal con atributo jurídico.** El WFS oficial de OAPN
   `ZonificacionPRUG:view_zon_zonificacion_prug` (registro estatal de la zonificación
   PRUG de todos los parques nacionales) publica el feature
   "Zona de acampada adyacente al refugio de Góriz" con
   `Zona = "Zona de Uso Moderado"`, `Normativa = "Decreto 49/2015, de 8 de abril,(BOA 80, 29/04/2015)"`,
   `Observaciones = "Uso público. Área vivac. Sector Ordesa"`, `Superficie = 1,251 ha`.
   El enlace jurídico lo afirma el propio registro oficial sobre el feature; no es
   una inferencia nominal nuestra.
3. **Identidad vectorial con el feature autonómico.** OAPN ↔ `ENP101_137` (ICEAragon,
   EPSG:25830): **IoU 0.999844, Hausdorff 0,005 m, sim-diff 1,95 m², centroides a 4,4 mm**,
   ambas 2 partes; áreas 12.505,91 / 12.505,94 m². Es literalmente el mismo objeto
   vectorial publicado por dos administraciones.
4. **Ancla del refugio.** `ENP101_025` "Refugio de Góriz" (401,24 m²) también es idéntico
   en ambos servicios (IoU 0,9992, Hausdorff 0,005 m); la acampada está a 7,37 m del
   refugio y es la **única** ZUM de Ordesa en 250 m a la redonda (de 130 ZUM que suman
   115,48 ha ≈ los "115,89 ha" del texto del PRUG; desfase ~0,4 % registrado sin resolver).

Riesgos y reservas registrados en el lock: posible linaje compartido OAPN/ICEAragon;
el Mapa 29 en PDF no sirvió como tercero vectorial (canal muerto, abajo); el enlace
jurídico descansa en el atributo `Normativa` del registro estatal.

## Norma vigente (fijada con hash desde el PDF del BOA)

D 16/2022, de 26 de enero (BOA 08-02-2022), modifica 9.2.1.3.1 del PRUG. Verbatim:

> La actividad del vivac o acampada nocturna queda prohibida en el sector Ordesa, con
> la excepción, hasta el 31 de diciembre de 2023, de un cupo de 90 personas que se
> establece para la Zona de Uso Moderado de Góriz en los casos de aforo completo del
> refugio. A partir de esa fecha dicho cupo quedará reducido a 50 personas. En todo
> caso, la pernocta no excederá de tres noches.

El listado oficial de legislación del parque (`pnomp.es/es/legislacion`, fijado
`6035bd5e…`) no incluye ninguna modificación posterior del régimen de pernocta.
Desde 2024-01-01 el cupo es de **50 personas**.

## Las tres capas (política del proyecto, aplicada)

| Capa | Contenido | Conducta del resolver |
|---|---|---|
| **Legal rule** | prohibición sectorial + excepción ZUM Góriz (cupo, aforo completo, ≤3 noches) | versiona bitemporalmente, evidencia fijada |
| **Operational condition** | "aforo completo del refugio" y noches previstas: hechos que aporta el llamante | ausentes → `UNDETERMINED + INCOMPLETE` (fail-closed) |
| **Live state** | disponibilidad del cupo / reservas (plataforma OAPN) | **nunca** se trata como legalidad; fuera del corpus |

"Hay reserva disponible" ≠ "es legal"; "fuera de la ZUM de Góriz" ≠ "PROHIBITED en
Sector Ordesa" (la delimitación sectorial sigue `SPATIAL_EVIDENCE_INCOMPLETE` → el
resolver responde `UNDETERMINED`, ver prueba offline).

> **"fuera de Góriz" no significa "Sector Ordesa prohibido".**
> Este éxito parcial no reintroduce por otra vía la frontera sectorial cuya
> inexistencia oficial acabamos de demostrar: ningún punto fuera del polígono de la
> ZUM autoriza a concluir prohibición sectorial.

## Política de artefactos (redistribución)

Mientras `DATA_REUSE_TERMS_VERIFICATION=NOT_VERIFIED` (NOTICE.md §4), este repositorio
**no redistribuye** features geoespaciales oficiales completas: los artefactos
comiteados en `discovery/evidence/m11c-goriz/` guardan URL canónica, fecha de
obtención, IDs de feature, propiedades, metadatos geométricos (tipo/partes/n_puntos/
bbox) y digests normalizados de coordenadas; la carga completa es re-descargable desde
las URLs fijadas. Única excepción mínima necesaria: el anillo WGS84 de la ZUM (1,25 ha)
en `alraso/resources/fixture_goriz.json`, imprescindible para el caso de aceptación
offline. Los textos (decreto del BOA, listado de legislación) se guardan como extractos
de texto.

## Los tres puntos + semántica de borde

Medidos sobre la geometría oficial (EPSG:25830 y su conversión a WGS84 en el lock):

| Punto | contains | covers | intersects | distancia |
|---|---|---|---|---|
| inside (centroide) | ✔ | ✔ | ✔ | 0 m |
| outside (E, 492,9 m) | ✘ | ✘ | ✘ | 492,9 m |
| border vertex | ✘ | ✔ | ✔ | 0 m |
| inside a 3 m del vértice | ✔ | ✔ | ✔ | 0 m |

**Decisión de semántica:** el borde cuenta como **dentro** (ST_Intersects/ST_Covers,
boundary-inclusive); ST_Contains (boundary-exclusive) queda registrada como contraste.
El ray-casting even-odd del provider de fixtures no debe usarse para puntos
exactamente sobre el borde (limitación ya documentada en `alraso/spatial.py`); la
referencia de producción es PostGIS `ST_Intersects` (SRID 4258).

## Canales muertos (registro honesto, para no repetirlos)

- CSW RCA de ICEAragon: HTTP 403 en GetRecords.
- `opendata.aragon.es`: 0 datasets para "zonificación"/"Ordesa".
- Buscador del BOA: 0 resultados incluso para "Ordesa" (no fiable como evidencia negativa).
- `datosabiertos.aragon.es`: fallo de DNS.
- **Geometría vectorial del Mapa 29 (PDF): no extraíble.** La página es un único JPEG
  fundido con el hillshade; la mejor IoU frente al polígono oficial fue ≤ 0,12 en todas
  las hipótesis de georreferencia, y la georreferencia OCG embebida se contradice con la
  escala impresa 1:5.000. La identidad ya no depende de este canal.

## Primer caso real end-to-end

`alraso/resources/fixture_goriz.json` codifica el scope `ss-ordesa-goriz-zum` con la
geometría oficial verificada (WGS84, 2 partes) y la lectura literal de D 16/2022:
`PERMITTED` condicionado a `refuge_capacity_full == true` y `nights ≤ 3`, vigente desde
2022-02-09. El cupo de 50 **no** se codifica como legalidad (capa operational/live).

Resultado demostrado por `tests/test_m11c_goriz_evidence.py` (100 % offline):

- dentro + hechos satisfechos → `PERMITTED` / `CURRENT`, con evidencia rastreable hasta
  el PDF del BOA y los dos WFS oficiales;
- dentro sin hechos → `UNDETERMINED` / `INCOMPLETE` (la condición operativa no se inventa);
- fuera de la ZUM → `UNDETERMINED` (nunca `PROHIBITED` por ausencia).

## Reproducción

```text
python tooling/m11c_goriz_identity.py            # comprobación fresca contra los dos WFS oficiales
python tooling/m11c_goriz_identity.py --verify   # + comparación con el lock (gate A sigue vivo)
pytest                                           # suite offline (incluye el caso real Góriz)
```

La herramienta offline-inconclusiva jamás convierte un fallo de red en "el vínculo se
rompió": `VERIFICATION_INCONCLUSIVE` con exit 2.

## Consecuencia para el hito

**M1.1 queda CERRADO** con una capacidad real demostrada: el primer ámbito con geometría
oficial identity-proven resuelve de extremo a extremo con decisión trazable y separación
estricta legal/operativo/live. La rama Sector Ordesa permanece CERRADA en
`SPATIAL_EVIDENCE_INCOMPLETE` y ninguna consulta "fuera de Góriz" la reabre por sí sola.
Siguiente hito: **M2-A Picos de Europa** (multi-comunidad, multi-ordenanza).
